# Windows PySide6 UI and portable deployment specification

## Deployment contract
Goal: copy/zip the complete portable application directory to any supported Windows 11 x64 machine and launch without installing Python or running Installer.exe. Distribution target: PyInstaller **onedir**, not onefile. Build/release artifacts must be tested on a clean computer; Windows security, runtime dependencies and antivirus may still require troubleshooting.

## Runtime paths
- `app_root`: executable directory in frozen build; source root in development.
- `bundle_root`: bundled read-only resources (frozen _MEIPASS or source tree).
- `data_root`: app_root/data when portable.flag exists and writable; optional %LOCALAPPDATA% fallback with visible user choice.
- `work_root`: user-selected output/temporary workspace, validated writable.
- `external_roots`: registry of source folder identities; rebind by validating metadata/hashes if source moved.
No absolute install paths in committed configuration. Prevent traversal, symlinks escaping managed roots, invalid Windows reserved names, path collisions and output overwrite.

## UI architecture
PySide6 View -> ViewModel -> command/query adapter -> orchestrator. UI listens via Qt queued Signals/Slots and event subscription, never calls FFmpeg or AI on main thread. Initial UI screens: folder import/mapping, batch monitor, job detail/error, timing reviewer, preset inspector/preview, settings/output history. A background worker process is not required for every tiny task but heavy media always subprocess isolated.

## State consistency
UI gets snapshot + revision on opening and after reconnect. Event handlers deduplicate and never directly mutate SQLite. Progress event throttling (~5–10 Hz) avoids UI stalls. User cancellation is an explicit command, orchestrator owns subprocess cleanup and persistence.

## Locale rule
All program-created numeric display values (dates, time, percent, IDs, subtitles generated from data) are ASCII 0–9. Set QLocale explicitly in GUI and numeric widgets, use central formatters. Preserve original lyric/source content and transform *display copies* only where requested by product policy. Test Thai and English Windows locale, DPI scale 100/125/150%.

## Packaging inventory
Executable, Python runtime, required Qt platform plugins, FFmpeg/FFprobe binaries with appropriate redistributable licensing, bundled fonts with lawful redistribution, templates, presets, migration scripts, notices/attribution, config defaults. Test that source data stays unmodified and database migration can run after moving install directory.

## No installer constraint
No Setup.exe or registration to Program Files. User can delete portable folder to uninstall; if AppData mode selected, document external user data cleanup separately. Avoid writes inside read-only Program Files or OS-protected locations.

## Required clean-PC scenarios
Move directory from D: to E:, Unicode folder name, no Python on target, FFmpeg loaded from package path, disk low, interrupted render resumed, SQLite schema upgrade, Windows locale Thai numerals, Qt font shaping and alignment.
