# Operator workflow, batch input and delivery

## Recommended folder shape
```text
SongBatch/
  Song_001/
    song.mp3
    cover.jpg
    video_background.png
    lyrics.txt
  Song_002/
    music.mp3
    cover.png
    video.jpg
    lyrics.docx
  Song_N/
    song.mp3
    cover.jpg
```
Names are examples only; input scanner must use content type, heuristics and explicit operator mapping if uncertain. Missing lyrics -> MP4 blocked/review/transcribe; MP3 cover remains independent.

## Import procedure
1. Select several folders or parent root, with explicit scan depth / deduplicate nested selections.
2. Display inventory, MP3 duration, image thumbnail/dimensions, lyrics presence/encoding.
3. Flag multiple MP3s or ambiguous cover/background mapping; user confirms.
4. Choose output root, default video profile and karaoke preset; optionally override per job.
5. Preflight and start batch, or process only eligible jobs.

## Job progress and review
- Every row shows independent MP3 and MP4 states.
- Problems display message, code, cause, suggested corrective action, ability to retry.
- Uncertain lyrics require human verification; revisions persist separately from display preset.
- Resume only invalidated DAG steps after edits/restart.

## Output structure
```text
MT_OUTPUT/
  Song_001/
    song_with_cover.mp3
    karaoke.mp4
    production_data/
      timing.json
      karaoke.ass
      karaoke.srt
      manifest.json
      qc_report.json
  batch_report.json
```
Do not scan the output tree as input. Publish final artifacts only after validation, never overwrite originals, handle naming collisions via unique job ID/version with mapping recorded in manifest.

## Media QA checklist
MP3 ID3 artwork readback and frame preservation; MP4 decodes; visual still throughout song; subtitle Thai marks safe; audio and video nominal durations; lyrics approval recorded; expected fonts/resources present. If a step cannot be proven, state it as unverified/needs review instead of pretending full success.

## Troubleshooting
Missing project file after clone: inspect `git status`, `git remote -v`, `git pull --ff-only origin main`, `dir pyproject.toml`.
Python dev setup: `py -3.12 -m venv .venv` then `.venv\Scripts\activate.bat` then `python -m pip install -e ".[dev]"`. Engine foundation does not produce media yet; consult Development Roadmap.

## Output governance
User owns original song and image resources; verify rights for distribution. Keep model/provider keys outside repo; cloud uploads only after explicit opt-in.
