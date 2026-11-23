# Releasing Bun Tracker

Version naming, local updates, and release publishing for this fork. Remotes are documented in [UPSTREAM.md](UPSTREAM.md).

## Workflow

- **Day to day:** commit changes on `main` and run the hot-reload dev build (`bash "Start SlimeVR.command"`). Do not bump the version, run a full build, or publish a release for everyday changes.
- **Releases:** full builds, version bumps, tags, and GitHub releases happen only when the owner decides a batch of bug fixes or new features is ready for a new version.

## Naming

Versions use `MAJOR.MINOR.PATCH`:

- `PATCH` for fixes and small changes.
- `MINOR` for new features.
- `MAJOR` for breaking changes.

The version lives in three files and must match across all of them:

- `package.json`
- `gui/app/package.json`
- `gui/tauri/tauri.conf.json`

| Item | Format | Example |
| --- | --- | --- |
| Annotated tag | `vMAJOR.MINOR.PATCH` with message `"vX.Y.Z: <short title>"` | `v0.4.0` / `"v0.4.0: Performance toggle"` |
| GitHub release title | `"vX.Y.Z: <short title>"` on `MrBunUniverse/BunTracker` (`public`) | `v0.4.0: Performance toggle` |
| Version bump commit | `"Release vX.Y.Z"` | `Release v0.4.0` |
| Regular commits | Area prefix when helpful (`GUI:`, `Docs:`) | `GUI: add performance toggle` |
| Release asset | `Bun-Tracker-vX.Y.Z-macos-<arch>.zip` | `Bun-Tracker-v0.4.0-macos-arm64.zip` |

Check the built architecture with `lipo -archs "Bun Tracker.app/Contents/MacOS/"*` (currently `arm64`). Package the `.app` with `ditto` so macOS bundle metadata is preserved:

```bash
ditto -c -k --keepParent "gui/tauri/target/release/bundle/macos/Bun Tracker.app" Bun-Tracker-vX.Y.Z-macos-arm64.zip
```

### Dev build vs full build

- **Dev build**: started with `bash "Start SlimeVR.command"` (Vite on port `5173` with hot reload, `tauri dev`, debug binary `gui/tauri/target/debug/slimevr-tauri-spike`). It has no version of its own and is identified by commit hash. `gui/app/vite.config.ts` injects `__COMMIT_HASH__` (8-character `HEAD`), `__VERSION_TAG__` (tag pointing at `HEAD`, if any), and `__GIT_CLEAN__`. When debug mode is enabled (`config.debug`), `VersionTag` shows `(__VERSION_TAG__ || __COMMIT_HASH__)` plus `-dirty` if the working tree has uncommitted changes.
- **Full build**: `Bun Tracker.app`, built with `tauri build`. Launching it without a terminal auto-starts the server and the ESP32 dongle bridge.

## Dev update

Commit changes as you go on `main` while running `bash "Start SlimeVR.command"`:

- `gui/app/src/` changes hot-reload through Vite.
- `server/` (Kotlin) changes rebuild the jar on launch via the launcher's stale-jar check.
- `gui/tauri/` (Rust) changes require a relaunch.

## Full build and local update

Build the server jar and the Tauri app from the repo root (`pnpm build` runs `tauri build` in `gui/tauri/`):

```bash
./gradlew :server:desktop:shadowJar && pnpm build
```

The bundle is written to `gui/tauri/target/release/bundle/macos/Bun Tracker.app`.

To update the local copy:

1. Quit the Bun Tracker GUI. The server and dongle bridge keep running.
2. Replace `<repo>/Bun Tracker.app` with `gui/tauri/target/release/bundle/macos/Bun Tracker.app`.

`<repo>/Bun Tracker.app` is git-ignored via `.git/info/exclude` (not installed in `~/Applications` for now).

> **Limitation:** `gui/tauri/src/server_process.rs` (`main_checkout()`) bakes `CARGO_MANIFEST_DIR` in at compile time to find `server/desktop/build/libs/slimevr.jar` and `tools/esp32-dongle/bridge.py`. The `.app` is not a standalone installer: it only works on a Mac with this repo checked out at the same path, the jar built, Java 17+ installed, and the dongle bridge's Python available. It is also unsigned and not notarized, so Gatekeeper requires right-click -> Open on other Macs.

## Publishing a release

1. Run the verification checks:

   ```bash
   cd gui/app && pnpm run lint && pnpm test
   cd gui/tauri && cargo check && cargo test
   ```

   If `server/` changed, also run `./gradlew :server:core:test`.

2. Check staged files and diffs for sensitive data: no secrets, no firmware `.bin` dumps, no private notes (such as local `CLAUDE.md` orchestration notes), and no AI attribution lines.
3. Bump the version in `package.json`, `gui/app/package.json`, and `gui/tauri/tauri.conf.json`.
4. Commit the bump:

   ```bash
   git commit -m "Release vX.Y.Z"
   ```

5. Create the annotated tag:

   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z: <short title>"
   ```

6. Confirm `public/main` is an ancestor of `main` (fast-forward only):

   ```bash
   git fetch public && git merge-base --is-ancestor public/main main
   ```

7. Push `main` and the tag to `public` (never force-push):

   ```bash
   git push public main vX.Y.Z
   ```

8. Run the full build:

   ```bash
   ./gradlew :server:desktop:shadowJar && pnpm build
   ```

9. Archive the bundle with `ditto`:

   ```bash
   ditto -c -k --keepParent "gui/tauri/target/release/bundle/macos/Bun Tracker.app" Bun-Tracker-vX.Y.Z-macos-arm64.zip
   ```

10. Create the release on `MrBunUniverse/BunTracker`:

    ```bash
    gh release create vX.Y.Z -R MrBunUniverse/BunTracker \
      --title "vX.Y.Z: <short title>" \
      --notes-file <notes.md> \
      Bun-Tracker-vX.Y.Z-macos-arm64.zip
    ```

    To add an asset to an existing release instead:

    ```bash
    gh release upload vX.Y.Z -R MrBunUniverse/BunTracker Bun-Tracker-vX.Y.Z-macos-arm64.zip
    ```

## Release notes template

```markdown
## What's New

- <Change 1>
- <Change 2>

## Notes

- **Not a standalone installer:** `Bun Tracker.app` resolves the server jar and dongle bridge relative to the repo checkout path baked in at compile time. Running it requires this repo checked out at the same path, the server jar built, Java 17+ installed, and the dongle bridge's Python environment available.
- **Unsigned build:** The app is unsigned and not notarized. On another Mac, right-click `Bun Tracker.app` and choose **Open** to bypass Gatekeeper.
```
