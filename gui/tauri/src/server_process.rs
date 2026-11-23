use std::env;
use std::ffi::OsStr;
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

const RELATIVE_JAR: &str = "server/desktop/build/libs/slimevr.jar";
const FIXED_JAVAS: [&str; 2] = [
    "/opt/homebrew/opt/openjdk/bin/java",
    "/usr/local/opt/openjdk/bin/java",
];
const APPLE_JAVA_STUB: &str = "/usr/bin/java";
const MISSING_JAVA_ERROR: &str =
    "Java 17 or newer not found. Install a JDK (for example: brew install openjdk) and try again.";

/// The checkout the server and bridge run from. Its jar is the only one that matches the user's
/// config (a jar built elsewhere rewrites vrconfig.yml without the fields it doesn't know), so a
/// build from a linked worktree still uses the main checkout. A moved checkout needs a rebuild.
pub fn main_checkout() -> Result<PathBuf, String> {
    resolve_main_checkout(Path::new(env!("CARGO_MANIFEST_DIR")))
}

fn resolve_main_checkout(crate_dir: &Path) -> Result<PathBuf, String> {
    let root = crate_dir.ancestors().nth(2).ok_or("Crate is not inside a checkout")?;
    let git = root.join(".git");
    if git.is_dir() {
        return Ok(root.to_path_buf());
    }
    // A linked worktree's .git is a file: "gitdir: <main>/.git/worktrees/<name>".
    let linked = fs::read_to_string(&git).map_err(|_| format!("No checkout at {}", root.display()))?;
    let main = linked
        .trim()
        .strip_prefix("gitdir: ")
        .and_then(|dir| Path::new(dir).ancestors().nth(3))
        .filter(|main| main.join(".git").is_dir())
        .ok_or_else(|| format!("Could not find the main checkout from {}", root.display()))?;
    Ok(main.to_path_buf())
}

fn matches_server(command: &str, cwd: &str, root: &Path) -> bool {
    let Some((_, invocation)) = command.trim().split_once(" -jar ") else {
        return false;
    };
    let jar = root.join(RELATIVE_JAR);
    // macOS may report /private/var for a checkout addressed through /var.
    let same_directory = Path::new(cwd) == root
        || Path::new(cwd)
            .canonicalize()
            .ok()
            .zip(root.canonicalize().ok())
            .is_some_and(|(cwd, root)| cwd == root);
    invocation == format!("{} run", jar.display())
        || (invocation == format!("{RELATIVE_JAR} run") && same_directory)
}

fn output(command: &mut Command) -> Result<String, String> {
    let result = command.output().map_err(|e| e.to_string())?;
    if !result.status.success() {
        return Err("Could not inspect server process".into());
    }
    String::from_utf8(result.stdout).map_err(|e| e.to_string())
}

fn is_executable(path: &Path) -> bool {
    fs::metadata(path).is_ok_and(|file| file.is_file() && file.permissions().mode() & 0o111 != 0)
}

fn java_home() -> Option<PathBuf> {
    let out = Command::new("/usr/libexec/java_home")
        .stdin(Stdio::null())
        .stderr(Stdio::null())
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    let home = String::from_utf8(out.stdout).ok()?;
    let home = home.trim();
    (!home.is_empty()).then(|| PathBuf::from(home))
}

/// Finds a usable Java binary even under Finder's minimal PATH:
/// `/usr/libexec/java_home`, then Homebrew fixed paths, then PATH (skipping macOS's `/usr/bin/java` stub).
pub fn find_java() -> Result<PathBuf, String> {
    let fixed: Vec<PathBuf> = FIXED_JAVAS.iter().map(PathBuf::from).collect();
    let path = env::var_os("PATH");
    find_java_with(java_home().as_deref(), &fixed, path.as_deref())
}

fn find_java_with(
    home: Option<&Path>,
    fixed: &[PathBuf],
    path: Option<&OsStr>,
) -> Result<PathBuf, String> {
    if let Some(home) = home {
        let java = home.join("bin/java");
        if is_executable(&java) {
            return Ok(java);
        }
    }
    for candidate in fixed {
        if is_executable(candidate) {
            return Ok(candidate.clone());
        }
    }
    if let Some(path) = path {
        for dir in env::split_paths(path) {
            if !dir.is_absolute() {
                continue;
            }
            let candidate = dir.join("java");
            if candidate == Path::new(APPLE_JAVA_STUB) {
                continue;
            }
            if is_executable(&candidate) {
                return Ok(candidate);
            }
        }
    }
    Err(MISSING_JAVA_ERROR.into())
}

fn is_server(pid: u32, root: &Path) -> Result<bool, String> {
    let command = output(Command::new("/bin/ps").args([
        "-ww", "-p", &pid.to_string(), "-o", "command=",
    ]))?;
    // lsof's field output preserves spaces in the checkout path.
    let cwd = output(Command::new("/usr/sbin/lsof").args(["-a", "-p", &pid.to_string(), "-d", "cwd", "-Fn"]))?;
    let cwd = cwd
        .lines()
        .find_map(|line| line.strip_prefix('n'))
        .ok_or("Missing process working directory")?;
    Ok(matches_server(&command, cwd, root))
}

fn server_pids(root: &Path) -> Result<Vec<u32>, String> {
    let candidates = Command::new("/usr/bin/pgrep")
        .args(["-x", "java"])
        .output()
        .map_err(|e| e.to_string())?;
    if candidates.status.code() == Some(1) {
        return Ok(Vec::new());
    }
    if !candidates.status.success() {
        return Err("Could not enumerate Java processes".into());
    }
    let candidates = String::from_utf8(candidates.stdout).map_err(|e| e.to_string())?;
    let mut matched = Vec::new();
    for line in candidates.lines() {
        let pid: u32 = line.parse().map_err(|_| "Invalid Java process ID")?;
        if is_server(pid, root)? {
            matched.push(pid);
        }
    }
    Ok(matched)
}

pub fn is_running(root: &Path) -> Result<bool, String> {
    Ok(!server_pids(root)?.is_empty())
}

pub fn stop_server(root: &Path) -> Result<(), String> {
    for pid in server_pids(root)? {
        let status = Command::new("/bin/kill")
            .args(["-TERM", &pid.to_string()])
            .status()
            .map_err(|e| e.to_string())?;
        if !status.success() {
            return Err(format!("Could not stop server process {pid}"));
        }
        let mut exited = false;
        for _ in 0..50 {
            let status = Command::new("/bin/kill")
                .args(["-0", &pid.to_string()])
                .output()
                .map_err(|e| e.to_string())?;
            if !status.status.success() {
                exited = true;
                break;
            }
            std::thread::sleep(std::time::Duration::from_millis(100));
        }
        if !exited {
            return Err(format!("Server process {pid} did not exit; restart cancelled"));
        }
    }
    Ok(())
}

/// Starts this checkout's server jar in its own process group.
/// When `restart` is false, leaves an already-running server alone and returns `Ok(false)`.
pub fn start_server(root: &Path, log_dir: &Path, restart: bool) -> Result<bool, String> {
    if !restart && is_running(root)? {
        return Ok(false);
    }
    let jar = root.join(RELATIVE_JAR);
    if !jar.is_file() {
        return Err(format!("No server jar at {}", jar.display()));
    }
    let java = find_java()?;
    if restart {
        stop_server(root)?;
    }

    fs::create_dir_all(log_dir).map_err(|e| e.to_string())?;
    let out = fs::File::create(log_dir.join("server.log")).map_err(|e| e.to_string())?;
    let err = out.try_clone().map_err(|e| e.to_string())?;
    Command::new(&java)
        .args(["-Xmx128M", "-jar"])
        .arg(&jar)
        .arg("run")
        .current_dir(root)
        .stdin(Stdio::null())
        .stdout(out)
        .stderr(err)
        // Own process group, so quitting the app (or Ctrl+C on tauri dev) leaves the server running.
        .process_group(0)
        .spawn()
        .map(|_| true)
        .map_err(|e| format!("Couldn't start the server: {e}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_matches_this_checkouts_jar() {
        let root = Path::new("/Projects/SlimeVR Server");
        assert!(matches_server("java -Xmx128M -jar /Projects/SlimeVR Server/server/desktop/build/libs/slimevr.jar run", "/elsewhere", root));
        assert!(matches_server("java -Xmx128M -jar server/desktop/build/libs/slimevr.jar run", "/Projects/SlimeVR Server", root));
        assert!(!matches_server("java -jar server/desktop/build/libs/slimevr.jar run", "/Projects/other", root));
        assert!(!matches_server("java -jar /Projects/other/server/desktop/build/libs/slimevr.jar run", "/Projects/SlimeVR Server", root));
        assert!(!matches_server("java -jar /Projects/SlimeVR Server/server/desktop/build/libs/slimevr.jar run-extra", "", root));
        assert!(!matches_server("java -jar slimevr.jar run", "/Projects/SlimeVR Server", root));
    }

    #[test]
    fn resolves_the_main_checkout_only() {
        let base = std::env::temp_dir().join(format!("slimevr main checkout {}", std::process::id()));
        let main = base.join("main");
        let worktree = base.join("worktree");
        let moved = base.join("moved");
        fs::create_dir_all(main.join(".git/worktrees/session")).unwrap();
        fs::create_dir_all(&worktree).unwrap();
        let gitdir = format!("gitdir: {}\n", main.join(".git/worktrees/session").display());
        fs::write(worktree.join(".git"), gitdir).unwrap();
        fs::create_dir_all(&moved).unwrap();

        assert_eq!(resolve_main_checkout(&main.join("gui/tauri")).unwrap(), main);
        assert_eq!(resolve_main_checkout(&worktree.join("gui/tauri")).unwrap(), main);
        assert!(resolve_main_checkout(&moved.join("gui/tauri")).is_err());
        fs::write(moved.join(".git"), "gitdir: /nowhere/.git/worktrees/x\n").unwrap();
        assert!(resolve_main_checkout(&moved.join("gui/tauri")).is_err());

        fs::remove_dir_all(&base).unwrap();
    }

    fn make_executable(path: &Path) {
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(path, "#!/bin/sh\n").unwrap();
        fs::set_permissions(path, fs::Permissions::from_mode(0o755)).unwrap();
    }

    #[test]
    fn finds_java_in_priority_order_and_errors_when_missing() {
        let base = env::temp_dir().join(format!("slimevr java search {}", std::process::id()));
        let _ = fs::remove_dir_all(&base);
        let home = base.join("jdk-home");
        let home_java = home.join("bin/java");
        let fixed_a = base.join("homebrew/bin/java");
        let fixed_b = base.join("usr-local/bin/java");
        let path_java = base.join("custom-bin/java");
        let not_exec = base.join("not-exec/java");

        make_executable(&home_java);
        make_executable(&fixed_a);
        make_executable(&fixed_b);
        make_executable(&path_java);
        fs::create_dir_all(not_exec.parent().unwrap()).unwrap();
        fs::write(&not_exec, "").unwrap();

        let path = env::join_paths([
            Path::new("relative"),
            not_exec.parent().unwrap(),
            Path::new("/usr/bin"),
            path_java.parent().unwrap(),
        ])
        .unwrap();

        // 1. java_home wins over fixed and PATH.
        assert_eq!(
            find_java_with(Some(&home), &[fixed_a.clone(), fixed_b.clone()], Some(&path)).unwrap(),
            home_java
        );
        // 2. Fixed paths win over PATH when java_home is absent.
        assert_eq!(
            find_java_with(None, &[fixed_a.clone(), fixed_b.clone()], Some(&path)).unwrap(),
            fixed_a
        );
        assert_eq!(
            find_java_with(None, &[base.join("missing/java"), fixed_b.clone()], Some(&path)).unwrap(),
            fixed_b
        );
        // 3. PATH is used when java_home and fixed paths are absent, skipping relative and /usr/bin/java.
        assert_eq!(
            find_java_with(None, &[base.join("missing/java")], Some(&path)).unwrap(),
            path_java
        );
        // 4. Missing Java returns a clear error (even if /usr/bin is on PATH).
        let minimal_path = env::join_paths([Path::new("/usr/bin")]).unwrap();
        let err = find_java_with(None, &[], Some(&minimal_path)).unwrap_err();
        assert!(err.contains("Java 17 or newer not found"), "{err}");

        fs::remove_dir_all(&base).unwrap();
    }
}
