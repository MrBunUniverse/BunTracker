use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use tauri::{AppHandle, Manager};

const LEGACY_IDENTIFIER: &str = "dev.slimevr.tauri-spike";
const CURRENT_IDENTIFIER: &str = "io.github.mrbununiverse.buntracker";

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

/// Copies `old_dir` to `new_dir` when `new_dir` does not exist yet and `old_dir` is a directory.
/// Leaves `old_dir` untouched. Stages into a sibling temp directory and renames on completion so
/// a failed copy never leaves a half-migrated directory behind.
pub fn copy_dir_if_missing(old_dir: &Path, new_dir: &Path) -> io::Result<bool> {
    if new_dir.exists() || !old_dir.is_dir() {
        return Ok(false);
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
    if let Err(err) = fs::rename(&staging, new_dir) {
        let _ = fs::remove_dir_all(&staging);
        return Err(err);
    }
    Ok(true)
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

    #[cfg(target_os = "macos")]
    if let Ok(home) = std::env::var("HOME") {
        let webkit = PathBuf::from(home)
            .join("Library/WebKit")
            .join(CURRENT_IDENTIFIER);
        if !targets.contains(&webkit) {
            targets.push(webkit);
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
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};

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
    fn copies_nested_tree_when_new_dir_missing_and_preserves_old_dir() {
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

        fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn does_not_overwrite_when_new_dir_already_exists() {
        let root = temp_root("existing");
        let old_dir = root.join(LEGACY_IDENTIFIER);
        let new_dir = root.join(CURRENT_IDENTIFIER);
        fs::create_dir_all(&old_dir).unwrap();
        fs::create_dir_all(&new_dir).unwrap();
        fs::write(old_dir.join("settings.json"), r#"{"theme":"old"}"#).unwrap();
        fs::write(new_dir.join("settings.json"), r#"{"theme":"new"}"#).unwrap();

        let copied = copy_dir_if_missing(&old_dir, &new_dir).unwrap();
        assert!(!copied);
        assert_eq!(
            fs::read_to_string(new_dir.join("settings.json")).unwrap(),
            r#"{"theme":"new"}"#
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
