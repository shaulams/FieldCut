# Field Cut — Claude Code Context

## What this project is

A local web app for audio journalism production. Built for journalists
who record field interviews and produce narrative audio pieces (radio documentary / podcast).

## The pipeline this app automates

1. Upload a WAV or MP3 interview file (any language, 1+ speakers, 10-120 min)
2. Transcribe via OpenAI Whisper API with word-level timestamps
3. Optional: speaker diarization via pyannote (detects who's talking)
4. User clicks words in the transcript UI to mark clip boundaries
5. App cuts the source audio into numbered clip files using ffmpeg
6. User records narration separately, uploads WAV files
7. User uploads narration WAVs and marks narration clips the same way
8. User drags clips and narration into an assembly timeline
9. App assembles everything into a single rough cut WAV via ffmpeg
10. Export: Word doc transcript, paper edit, clips ZIP, rough cut WAV

## Stack

- **Backend**: Python / Flask (app.py) — vanilla, no framework beyond Flask
- **Frontend**: Vanilla JS + CSS — no framework, no build step
- **Audio processing**: ffmpeg (must be installed on the system)
- **Transcription**: OpenAI Whisper API (`whisper-1` model, `verbose_json` format with word + segment timestamps)
- **Speaker diarization**: pyannote.audio (optional, requires HUGGINGFACE_TOKEN)
- **State**: JSON file per project — no database
- **Config**: config.json (app-wide settings like export folder)
- **Linting/Formatting**: ruff (config in pyproject.toml)
- **Testing**: pytest (config in pyproject.toml)
- **Port**: 5555

## Project structure

```
fieldcut/
├── CLAUDE.md           ← you are here
├── app.py              ← Flask server, all routes
├── Makefile            ← dev commands (make setup/run/test/lint/format)
├── pyproject.toml      ← ruff + pytest config
├── requirements.txt    ← core deps (flask, openai, python-docx, dotenv)
├── requirements-dev.txt ← dev deps (pytest, ruff, pre-commit)
├── requirements-speaker.txt ← optional (pyannote.audio for diarization)
├── .pre-commit-config.yaml ← ruff pre-commit hooks
├── .env                ← API keys (gitignored)
├── config.json         ← app-wide settings (gitignored)
├── demo/               ← bundled demo interviews (en, he)
├── static/
│   └── lang.js         ← i18n strings (English, Hebrew)
├── templates/
│   └── index.html      ← full UI (transcript, timeline, assembly panel)
├── tests/              ← pytest test suite
│   ├── conftest.py     ← shared fixtures
│   ├── test_helpers.py ← unit tests for helper functions
│   ├── test_routes.py  ← Flask route tests
│   └── test_pipeline.py ← integration tests (require ffmpeg)
├── .agents/skills/     ← agent skills (Codex, Claude Code, etc.)
├── .claude/skills/     ← symlinks to .agents/skills/
└── projects/           ← per-project data (gitignored)
    ├── _session/       ← default temporary project
    └── {project_name}/ ← saved projects
        ├── uploads/    ← source audio files
        ├── clips/      ← cut clip WAVs
        ├── narration/  ← narration audio
        ├── output/     ← rough cut, docx, zip
        └── state.json  ← project state
```

## Environment

Requires env variables in `.env`:
```
OPENAI_API_KEY=sk-...           # required
HUGGINGFACE_TOKEN=hf_...        # optional, for speaker diarization
```

The app has a first-run setup wizard that creates `.env` if missing.

Run with:
```bash
make setup    # creates venv, installs all deps
make run      # starts the server on port 5555
make test     # runs pytest
make lint     # checks ruff lint + format
make format   # auto-fixes formatting
```

## Key API routes

| Route | Method | What it does |
|---|---|---|
| `/` | GET | Serves the UI |
| `/state` | GET | Returns full project state as JSON |
| `/transcribe` | POST | Accepts audio file + language + diarize flag, transcribes in background |
| `/status` | GET | Returns transcription status + segment count |
| `/progress` | GET | Returns progress phase/step/message for UI progress bar |
| `/add_clip` | POST | Adds a clip from word-level text selection |
| `/remove_clip` | POST | Removes a clip |
| `/cut_clips` | POST | Runs ffmpeg to cut all marked clips from source file |
| `/upload_narration_audio` | POST | Accepts narration WAV file |
| `/assemble` | POST | Takes ordered assembly list, runs ffmpeg concat |
| `/export_transcript` | GET | Downloads transcript as Word doc with speaker colors |
| `/export_paper_edit` | POST | Downloads assembly as Word doc |
| `/export_clips_zip` | GET | Downloads all clips as ZIP |
| `/download_output` | GET | Downloads the assembled rough cut |
| `/save_project` | POST | Saves current session as named project |
| `/load_project` | POST | Loads a saved project |
| `/projects` | GET | Lists all saved projects |
| `/load_demo` | POST | Loads bundled demo interview |
| `/setup/status` | GET | Checks which API keys are configured |
| `/setup/save_keys` | POST | Validates and saves API keys to .env |
| `/export_folder` | GET/POST | Get/set the auto-export folder |
| `/rename_speaker` | POST | Rename a speaker label |
| `/reassign_speaker` | POST | Change a segment's speaker assignment |
| `/reset` | POST | Clears session state |

## State shape

```json
{
  "source_file": "projects/myproject/uploads/interview.wav",
  "filename": "interview.wav",
  "status": "transcribed",
  "transcription_language": "he",
  "project_name": "myproject",
  "transcript": [
    {
      "id": 0,
      "start": 12.4,
      "end": 28.1,
      "text": "the transcript text",
      "speaker": "S1"
    }
  ],
  "words": [
    { "word": "the", "start": 12.4, "end": 12.6 }
  ],
  "speaker_names": { "S1": "Interviewer", "S2": "Guest" },
  "text_clips": [
    { "id": "clip_01", "start": 12.4, "end": 28.1, "text": "clip text" }
  ],
  "clips": [
    { "id": "clip_01", "path": "projects/myproject/clips/clip_01.wav", "start": 12.4, "end": 28.1 }
  ],
  "narration": [
    { "name": "intro.wav", "path": "projects/myproject/narration/intro.wav" }
  ]
}
```

## Security notes

- All file-serving routes use `safe_project_path()` to prevent path traversal
- `/setup/save_keys` is restricted to localhost only
- API keys stored in `.env` (gitignored)
- App binds to 127.0.0.1 only (not exposed to network)

## Audio notes

- Source files can be any language — Whisper handles auto-detection
- Speaker diarization uses Apple MPS GPU on Mac for ~7x speedup
- MP3 files are auto-converted to WAV for pyannote compatibility
- ffmpeg copy mode (`-c copy`) for cutting, concat demuxer for assembly
- All files must have matching sample rate + channels for assembly

## UI notes

- RTL-ready with `dir="rtl"` — switches based on language
- Font: Alef/Heebo (Hebrew) + JetBrains Mono for timestamps/codes
- Dark and light themes
- Speaker colors: S1 green, S2 blue, S3 orange, S4 purple
- Bilingual: English + Hebrew (add more in static/lang.js)

## Development rules

- **No frameworks on the frontend** — vanilla JS only, no React/Vue/Angular, no build step
- **No database** — JSON file per project is the persistence model
- **Run `make lint` before committing** — CI enforces ruff checks
- **Add tests for new routes** — use the fixtures in `tests/conftest.py`
- **Use `friendly_error()`** for user-facing error messages
- **Keep it simple** — this is a tool for journalists, not a tech demo

## Agent skills

Developer skills are installed in `.agents/skills/` (works with Codex, Claude Code, Cursor, Gemini CLI, and others). Symlinked to `.claude/skills/` for Claude Code.

Installed skills:
- **flask** — Flask patterns, blueprints, testing, extensions
- **pytest** — Fixtures, parametrize, mocking, Flask test client
- **security-auditor** — OWASP Top 10 scanning, vulnerability patterns
- **openai-whisper-api** — Whisper transcription API reference
- **requesting-code-review** — Structured code review workflow
- **run-tests** — Full test suite: unit, integration, e2e API, browser smoke tests

To install more: `npx skills find <query>` then `npx skills add <package>`
