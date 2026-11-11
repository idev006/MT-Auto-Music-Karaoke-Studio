# Windows PySide6 UI and portable deployment specification

## Deployment contract
Goal: copy/zip the complete portable application directory to any supported Windows 11 x64 machine and launch without installing Python or running Installer.exe. Distribution target: PyInstaller **onedir**, not onefile. Build/release artifacts must be tested on a clean computer; Windows security, runtime dependencies and antivirus may still require troubleshooting.

## Runtime paths
- `app_root`: executable directory in frozen build; source root in development.
- `bundle_root`: bundled read-only resources (frozen _MEIPASS or source tree).
- `model_root`: app_root/models; shared Faster Whisper cache, independent from song output folders.
- `data_root`: app_root/data when portable.flag exists and writable; optional %LOCALAPPDATA% fallback with visible user choice.
- `work_root`: user-selected output/temporary workspace, validated writable.
- `external_roots`: registry of source folder identities; rebind by validating metadata/hashes if source moved.
No absolute install paths in committed configuration. Prevent traversal, symlinks escaping managed roots, invalid Windows reserved names, path collisions and output overwrite.

## UI architecture
PySide6 View -> ViewModel -> command/query adapter -> orchestrator. UI listens via Qt queued Signals/Slots and event subscription, never calls FFmpeg or AI on main thread. Initial UI screens: folder import/mapping, batch monitor, job detail/error, timing reviewer, preset inspector/preview, settings/output history. A background worker process is not required for every tiny task but heavy media always subprocess isolated.

The implemented first vertical slice is `mt-karaoke-ui`. `ApplicationOrchestrator` owns a bounded
`ThreadPoolExecutor`; one submitted future owns one source folder. Workers update immutable job
snapshots and sequenced typed events behind one re-entrant lock. A 200 ms GUI bridge consumes only
new event sequences and copies the engine-owned `OrchestratorView` into the Qt table model on the
GUI thread. The UI does not classify terminal states, count jobs, calculate resource policy, or own
worker lifecycle. Queue mutation is disabled while a batch is active, duplicate active
source folders are rejected, and `workers × CPU threads per worker` may not exceed the detected
logical CPU count. The UI uses native Qt controls with no application stylesheet, so the operating
system theme remains authoritative.

Cancellation is currently cooperative at engine progress boundaries. The window refuses to close
until active work reaches a terminal state, which prevents abandoning the executor or media
subprocess resources. Immediate mid-stage FFmpeg/ASR process-tree termination remains a separate
hard-cancellation milestone and must not be claimed by this slice.

## Portable build and launch
`build-portable.bat` builds the PyInstaller `onedir` contract in
`dist/MT-Karaoke-Studio`. The bundle contains read-only fonts, migrations, Alembic configuration,
and the OpenRouter example. Mutable `data`, `logs`, and `config` directories plus `portable.flag`
remain beside the executable. If `MT_FFMPEG_ROOT` points to a redistributable FFmpeg tree, the build
copies it to `ffmpeg`; otherwise the build emits a warning and the operator must choose FFmpeg in
the UI. `run-karaoke-studio.bat` resolves every target relative to `%~dp0` and supports both the
portable executable and the development virtual environment without a hardcoded drive.

The distributable artifact is `release/MT-Karaoke-Studio-Installer.zip`. After extraction,
`install.bat` invokes `installer/install.ps1`, validates and stages the payload, then replaces the
per-user application under `%LOCALAPPDATA%/Programs/MT-Karaoke-Studio` with rollback on failure.
The installer removes `portable.flag`, so mutable user data remains under the PathManager AppData
root and survives application upgrades. The package includes a validated Faster Whisper base model
under `models/faster-whisper`. Optional larger models are downloaded into the same root on first use;
the installer merges and preserves existing model directories on upgrade. It checks 64-bit Windows,
payload integrity, model integrity and disk space, runs `--smoke-test`, writes
`install-manifest.json` and `%LOCALAPPDATA%/MT/MediaStudio/logs/install.log`, and restores the previous
installation on failure. `run.bat` invokes `installer/run.ps1` and starts only the validated installed
executable. Neither entry point requires administrator privileges.

## FFmpeg event flow
FFmpeg rendering uses `-progress pipe:1 -nostats -loglevel error`. The adapter parses `out_time`,
normalizes it against the probed audio duration, and calls the production progress port. The runner
maps render progress into its pipeline range; the orchestrator atomically updates its immutable job
snapshot and appends `JOB_PROGRESS` with a monotonic sequence. The UI consumes events and renders
the engine projection. If cancellation raises through the progress port, the adapter terminates the
FFmpeg process, waits up to 5 seconds, escalates to kill if needed, closes pipes, and re-raises.

## State consistency
UI gets snapshot + revision on opening and after reconnect. Event handlers deduplicate and never directly mutate SQLite. Progress event throttling (~5–10 Hz) avoids UI stalls. User cancellation is an explicit command, orchestrator owns subprocess cleanup and persistence.

Each production target has one atomic `production_data/run_state.json`; state is not represented by
duplicated folders. The stage sequence is `INTAKE -> LYRICS -> TRANSCRIBE -> TIMING -> RENDER ->
QC -> COMPLETE`. Worker failures retain the last engine-owned stage and write
`production_data/failure.log` with the traceback. The UI only displays this projection and offers
detail/output-folder actions; it does not infer pipeline state.

A diagnostic render is checkpoint-reusable only while the prior state is `QC` and the recorded
source-audio, background, ASS and rendered-MP4 hashes all match. The engine decode-checks and probes
the existing MP4 before continuing QC. Missing, stale, corrupt or path-escaping evidence causes a
new render. A diagnostic checkpoint never authorizes publication as `karaoke.mp4`.

## Locale rule
All program-created numeric display values (dates, time, percent, IDs, subtitles generated from data) are ASCII 0–9. Set QLocale explicitly in GUI and numeric widgets, use central formatters. Preserve original lyric/source content and transform *display copies* only where requested by product policy. Test Thai and English Windows locale, DPI scale 100/125/150%.

The desktop entry point sets `QLocale.c()` and the table passes program-created values through the
central ASCII digit formatter. Source paths and original lyric content are preserved.

## Packaging inventory
Executable, Python runtime, required Qt platform plugins, FFmpeg/FFprobe binaries with appropriate redistributable licensing, bundled fonts with lawful redistribution, templates, presets, migration scripts, notices/attribution, config defaults. Test that source data stays unmodified and database migration can run after moving install directory.

## No installer constraint
No Setup.exe or registration to Program Files. User can delete portable folder to uninstall; if AppData mode selected, document external user data cleanup separately. Avoid writes inside read-only Program Files or OS-protected locations.

## Required clean-PC scenarios
Move directory from D: to E:, Unicode folder name, no Python on target, FFmpeg loaded from package path, disk low, interrupted render marked truthfully and restarted as a new run, SQLite schema upgrade, Windows locale Thai numerals, Qt font shaping and alignment.
