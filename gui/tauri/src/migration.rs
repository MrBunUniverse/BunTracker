use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use tauri::{AppHandle, Manager};

const LEGACY_IDENTIFIER: &str = "dev.slimevr.tauri-spike";
const CURRENT_IDENTIFIER: &str = "io.github.mrbununiverse.buntracker";
const MIGRATION_MARKER: &str = ".migrated-from-dev.slimevr.tauri-spike";
#[cfg(target_os = "macos")]
const LEGACY_DEBUG_BINARY: &str = "slimevr-tauri-spike";

/// Derives the legacy sibling directory when `new_dir` ends with `CURRENT_IDENTIFIER`.
fn legacy_sibling(new_dir: &Path) -> Option<PathBuf> {
    let name = new_dir.file_name()?.to_str()?;
    if name != CURRENT_IDENTIFIER {
        return None;
    }
    Some(new_dir.parent()?.join(LEGACY_IDENTIFIER))
}

/// Recursively copies regular files and subdirectories from `src` into `dst`.
/// Skips symlinks and special files so migration cannot loop or block.
fn copy_dir_recursive(src: &Path, dst: &Path) -> io::Result<()> {
    fs::create_dir_all(dst)?;
    for entry in fs::read_dir(src)? {
        let entry = entry?;
        let file_type = entry.file_type()?;
        let from = entry.path();
        let to = dst.join(entry.file_name());
        if file_type.is_dir() {
            copy_dir_recursive(&from, &to)?;
        } else if file_type.is_file() {
            fs::copy(&from, &to)?;
        }
    }
    Ok(())
}

/// Recursively merges regular files and subdirectories from `src` into an existing `dst`
/// without overwriting files in `dst` that are newer than or the same age as `src`.
/// Skips symlinks and special files so migration cannot loop or block.
fn merge_dir_without_overwriting_newer(src: &Path, dst: &Path) -> io::Result<()> {
    fs::create_dir_all(dst)?;
    for entry in fs::read_dir(src)? {
        let entry = entry?;
        let file_type = entry.file_type()?;
        let from = entry.path();
        let to = dst.join(entry.file_name());
        if file_type.is_dir() {
            merge_dir_without_overwriting_newer(&from, &to)?;
        } else if file_type.is_file() {
            let should_copy = if to.exists() {
                match (
                    fs::metadata(&from).and_then(|m| m.modified()),
                    fs::metadata(&to).and_then(|m| m.modified()),
                ) {
                    (Ok(src_mtime), Ok(dst_mtime)) => src_mtime > dst_mtime,
                    _ => false,
                }
            } else {
                true
            };
            if should_copy {
                fs::copy(&from, &to)?;
            }
        }
    }
    Ok(())
}

/// Checks whether a legacy app process appears to be running (either the old `slimevr-tauri-spike`
/// binary or any process holding open files under `old_webkit_dir`, such as a release
/// `Bun Tracker.app` built with the legacy bundle identifier).
#[cfg(target_os = "macos")]
fn is_legacy_app_running(old_webkit_dir: &Path) -> bool {
    let my_pid = std::process::id().to_string();

    if let Ok(out) = std::process::Command::new("pgrep")
        .args(["-x", LEGACY_DEBUG_BINARY])
        .output()
    {
        if out.status.success() {
            let stdout = String::from_utf8_lossy(&out.stdout);
            if stdout.lines().any(|line| {
                let pid = line.trim();
                !pid.is_empty() && pid != my_pid
            }) {
                return true;
            }
        }
    }

    if old_webkit_dir.is_dir() {
        if let Ok(out) = std::process::Command::new("lsof")
            .arg("-t")
            .arg("+D")
            .arg(old_webkit_dir)
            .output()
        {
            if out.status.success() {
                let stdout = String::from_utf8_lossy(&out.stdout);
                if stdout.lines().any(|line| {
                    let pid = line.trim();
                    !pid.is_empty() && pid != my_pid
                }) {
                    return true;
                }
            }
        }
    }

    false
}

/// Copies or merges `old_dir` into `new_dir` when `old_dir` is a directory and migration has not
/// yet completed (indicated by `MIGRATION_MARKER` inside `new_dir`).
///
/// - Leaves `old_dir` untouched.
/// - When `new_dir` does not exist yet, stages into a sibling temp directory, writes the marker,
///   and atomically renames on completion.
/// - When `new_dir` already exists without the marker (e.g. a previous attempt failed or was
///   deferred and startup created an empty directory), merges missing or older files from
///   `old_dir` without overwriting newer files, then writes the marker only on success.
pub fn copy_dir_if_missing(old_dir: &Path, new_dir: &Path) -> io::Result<bool> {
    if !old_dir.is_dir() {
        return Ok(false);
    }
    let marker_path = new_dir.join(MIGRATION_MARKER);
    if marker_path.exists() {
        return Ok(false);
    }

    if new_dir.exists() {
        if !new_dir.is_dir() {
            return Ok(false);
        }
        merge_dir_without_overwriting_newer(old_dir, new_dir)?;
        fs::write(&marker_path, b"migrated\n")?;
        return Ok(true);
    }

    let Some(parent) = new_dir.parent() else {
        return Ok(false);
    };
    let Some(name) = new_dir.file_name().and_then(|n| n.to_str()) else {
        return Ok(false);
    };
    fs::create_dir_all(parent)?;
    let staging = parent.join(format!(".{name}.migrating-{}", std::process::id()));
    if staging.exists() {
        let _ = fs::remove_dir_all(&staging);
    }
    if let Err(err) = copy_dir_recursive(old_dir, &staging) {
        let _ = fs::remove_dir_all(&staging);
        return Err(err);
    }
    if let Err(err) = fs::write(staging.join(MIGRATION_MARKER), b"migrated\n") {
        let _ = fs::remove_dir_all(&staging);
        return Err(err);
    }
    if let Err(err) = fs::rename(&staging, new_dir) {
        let _ = fs::remove_dir_all(&staging);
        return Err(err);
    }
    Ok(true)
}

/// Runs `copy_dir_if_missing` unless `legacy_running()` reports that the legacy app is still
/// running, in which case migration is skipped without writing the marker so the next launch
/// will retry.
fn migrate_dir_if_not_running<F>(
    old_dir: &Path,
    new_dir: &Path,
    legacy_running: F,
) -> io::Result<bool>
where
    F: FnOnce() -> bool,
{
    if !old_dir.is_dir() || new_dir.join(MIGRATION_MARKER).exists() {
        return Ok(false);
    }
    if legacy_running() {
        eprintln!(
            "Legacy WebKit storage migration deferred ({} -> {}): legacy app is currently running; will retry on next launch.",
            old_dir.display(),
            new_dir.display()
        );
        return Ok(false);
    }
    copy_dir_if_missing(old_dir, new_dir)
}

/// One-time startup migration from `dev.slimevr.tauri-spike` to `io.github.mrbununiverse.buntracker`.
/// Must run before reading settings/cache or creating the WebView window.
pub fn migrate_legacy_dirs(app: &AppHandle) {
    let mut targets: Vec<PathBuf> = Vec::new();
    for dir in [
        app.path().app_config_dir().ok(),
        app.path().app_data_dir().ok(),
        app.path().app_log_dir().ok(),
    ]
    .into_iter()
    .flatten()
    {
        if !targets.contains(&dir) {
            targets.push(dir);
        }
    }

    for new_dir in targets {
        let Some(old_dir) = legacy_sibling(&new_dir) else {
            continue;
        };
        if let Err(err) = copy_dir_if_missing(&old_dir, &new_dir) {
            eprintln!(
                "Legacy data migration skipped ({} -> {}): {err}",
                old_dir.display(),
                new_dir.display()
            );
        }
    }

    #[cfg(target_os = "macos")]
    if let Ok(home) = std::env::var("HOME") {
        let webkit = PathBuf::from(home)
            .join("Library/WebKit")
            .join(CURRENT_IDENTIFIER);
        if let Some(old_webkit) = legacy_sibling(&webkit) {
            if let Err(err) = migrate_dir_if_not_running(&old_webkit, &webkit, || {
                is_legacy_app_running(&old_webkit)
            }) {
                eprintln!(
                    "Legacy WebKit storage migration failed ({} -> {}): {err}",
                    old_webkit.display(),
                    webkit.display()
                );
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::thread::sleep;
    use std::time::Duration;

    static COUNTER: AtomicU64 = AtomicU64::new(0);

    fn temp_root(label: &str) -> PathBuf {
        let n = COUNTER.fetch_add(1, Ordering::Relaxed);
        let dir = std::env::temp_dir().join(format!(
            "bun-tracker-migration-{label}-{}-{n}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn legacy_sibling_maps_current_identifier_only() {
        let current = Path::new("/tmp/Application Support/io.github.mrbununiverse.buntracker");
        assert_eq!(
            legacy_sibling(current),
            Some(PathBuf::from("/tmp/Application Support/dev.slimevr.tauri-spike"))
        );
        assert_eq!(legacy_sibling(Path::new("/tmp/other-app")), None);
    }

    #[test]
    fn copies_nested_tree_when_new_dir_missing_and_writes_marker() {
        let root = temp_root("copy");
        let old_dir = root.join(LEGACY_IDENTIFIER);
        let new_dir = root.join(CURRENT_IDENTIFIER);
        fs::create_dir_all(old_dir.join("WebsiteData/LocalStorage")).unwrap();
        fs::write(old_dir.join("settings.json"), r#"{"theme":"bun"}"#).unwrap();
        fs::write(
            old_dir.join("WebsiteData/LocalStorage/data.sqlite3"),
            b"sqlite-bytes",
        )
        .unwrap();

        let copied = copy_dir_if_missing(&old_dir, &new_dir).unwrap();
        assert!(copied);
        assert!(new_dir.join(MIGRATION_MARKER).exists());
        assert_eq!(
            fs::read_to_string(new_dir.join("settings.json")).unwrap(),
            r#"{"theme":"bun"}"#
        );
        assert_eq!(
            fs::read(new_dir.join("WebsiteData/LocalStorage/data.sqlite3")).unwrap(),
            b"sqlite-bytes"
        );
        // Old directory and its contents remain untouched.
        assert_eq!(
            fs::read_to_string(old_dir.join("settings.json")).unwrap(),
            r#"{"theme":"bun"}"#
        );

        // Second call is a no-op once marker exists.
        assert!(!copy_dir_if_missing(&old_dir, &new_dir).unwrap());

        fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn does_not_overwrite_when_marker_already_exists() {
        let root = temp_root("marked");
        let old_dir = root.join(LEGACY_IDENTIFIER);
        let new_dir = root.join(CURRENT_IDENTIFIER);
        fs::create_dir_all(&old_dir).unwrap();
        fs::create_dir_all(&new_dir).unwrap();
        fs::write(old_dir.join("settings.json"), r#"{"theme":"old"}"#).unwrap();
        fs::write(new_dir.join("settings.json"), r#"{"theme":"new"}"#).unwrap();
        fs::write(new_dir.join(MIGRATION_MARKER), b"migrated\n").unwrap();

        let copied = copy_dir_if_missing(&old_dir, &new_dir).unwrap();
        assert!(!copied);
        assert_eq!(
            fs::read_to_string(new_dir.join("settings.json")).unwrap(),
            r#"{"theme":"new"}"#
        );

        fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn retries_and_merges_when_dest_exists_without_marker_preserving_newer_files() {
        let root = temp_root("retry-merge");
        let old_dir = root.join(LEGACY_IDENTIFIER);
        let new_dir = root.join(CURRENT_IDENTIFIER);
        fs::create_dir_all(old_dir.join("sub")).unwrap();
        fs::write(old_dir.join("settings.json"), r#"{"theme":"old"}"#).unwrap();
        fs::write(old_dir.join("sub/legacy-only.txt"), "from-legacy").unwrap();

        // Simulate startup having created `new_dir` with a newer file before migration succeeded.
        sleep(Duration::from_millis(20));
        fs::create_dir_all(&new_dir).unwrap();
        fs::write(new_dir.join("settings.json"), r#"{"theme":"newer"}"#).unwrap();

        let copied = copy_dir_if_missing(&old_dir, &new_dir).unwrap();
        assert!(copied);
        assert!(new_dir.join(MIGRATION_MARKER).exists());
        // Newer file in destination is preserved.
        assert_eq!(
            fs::read_to_string(new_dir.join("settings.json")).unwrap(),
            r#"{"theme":"newer"}"#
        );
        // Missing file from legacy directory is merged in.
        assert_eq!(
            fs::read_to_string(new_dir.join("sub/legacy-only.txt")).unwrap(),
            "from-legacy"
        );

        fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn skips_when_legacy_app_is_running_and_retries_next_launch() {
        let root = temp_root("deferred-running");
        let old_dir = root.join(LEGACY_IDENTIFIER);
        let new_dir = root.join(CURRENT_IDENTIFIER);
        fs::create_dir_all(&old_dir).unwrap();
        fs::write(old_dir.join("localstorage.db"), b"legacy-data").unwrap();

        // First launch: legacy app is running -> skip, no marker written.
        let first = migrate_dir_if_not_running(&old_dir, &new_dir, || true).unwrap();
        assert!(!first);
        assert!(!new_dir.join(MIGRATION_MARKER).exists());

        // Even if startup creates an empty destination directory after the skip,
        // the next launch (once legacy app has exited) still migrates.
        fs::create_dir_all(&new_dir).unwrap();
        let second = migrate_dir_if_not_running(&old_dir, &new_dir, || false).unwrap();
        assert!(second);
        assert!(new_dir.join(MIGRATION_MARKER).exists());
        assert_eq!(
            fs::read(new_dir.join("localstorage.db")).unwrap(),
            b"legacy-data"
        );

        fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn no_op_when_old_dir_missing() {
        let root = temp_root("missing-old");
        let old_dir = root.join(LEGACY_IDENTIFIER);
        let new_dir = root.join(CURRENT_IDENTIFIER);

        let copied = copy_dir_if_missing(&old_dir, &new_dir).unwrap();
        assert!(!copied);
        assert!(!new_dir.exists());

        fs::remove_dir_all(&root).unwrap();
    }
}
