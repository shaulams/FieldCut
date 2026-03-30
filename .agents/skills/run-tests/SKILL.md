---
name: run-tests
description: Run all FieldCut tests — unit, integration, e2e API, and browser smoke tests. Use after code changes to verify nothing is broken.
allowed-tools: Bash, Read, Grep
---

# Run Tests

Run the full FieldCut test suite after any code change. This skill covers unit tests, integration tests, API e2e tests, and a browser smoke test against the running app.

## When to Use

- After modifying `app.py`, `templates/index.html`, `static/`, or `tests/`
- Before committing or creating a PR
- After fixing a bug to verify the fix and check for regressions
- When asked to "run tests", "verify", or "check everything works"

## Test Layers

### 1. Lint Check (fast, always run first)

```bash
python -m ruff check .
python -m ruff format --check .
```

If this fails, run `python -m ruff format . && python -m ruff check --fix .` to auto-fix, then re-run.

### 2. Unit Tests — `tests/test_helpers.py`

Pure function tests (no Flask, no ffmpeg):
- `TestMergeSegments` — Whisper segment merging logic
- `TestFriendlyError` — Exception-to-user-message conversion
- `TestGetClipSpeaker` — Speaker detection by time overlap

### 3. Route Tests — `tests/test_routes.py`

Flask test client tests for all API endpoints:
- `TestBasicRoutes` — GET smoke tests (/, /state, /status, /progress, /projects, /setup/status, /export_folder)
- `TestTranscribeValidation` — Input validation for /transcribe
- `TestClipOperations` — Add, sort, remove, trim clips
- `TestCutClips` — Cut validation (no clips, no source)
- `TestProjectManagement` — Save, load, delete, phase, reset
- `TestSpeakers` — Rename, reassign
- `TestMetadata` — Update metadata
- `TestAudioEndpoints` — Waveform, snippet, download, zip
- `TestAssemblyOrder` — Save/get/clear assembly order persistence
- `TestTrimStateSync` — Trim values reflected in state
- `TestExportTranscript` — Transcript export

### 4. Integration Tests — `tests/test_pipeline.py`

End-to-end tests requiring ffmpeg:
- `TestCutPipeline` — Mark clips → cut with ffmpeg → verify WAV output
- `TestWaveformPipeline` — Extract waveform data from WAV
- `TestProjectPipeline` — Full project save/load/delete/duplicate lifecycle

### 5. E2E API Smoke Test (against running server)

If the app is running on port 5555, hit the live API to verify:

```bash
# Check app is alive
curl -sf http://127.0.0.1:5555/ > /dev/null && echo "OK: index" || echo "FAIL: index"

# Check state endpoint
curl -sf http://127.0.0.1:5555/state | python -c "import sys,json; d=json.load(sys.stdin); print('OK: state' if 'transcript' in d else 'FAIL: state')"

# Check status endpoint
curl -sf http://127.0.0.1:5555/status | python -c "import sys,json; d=json.load(sys.stdin); print('OK: status' if 'status' in d else 'FAIL: status')"

# Check assembly_order endpoint
curl -sf http://127.0.0.1:5555/assembly_order | python -c "import sys,json; d=json.load(sys.stdin); print('OK: assembly_order' if 'assembly' in d else 'FAIL: assembly_order')"

# Check projects list
curl -sf http://127.0.0.1:5555/projects | python -c "import sys,json; d=json.load(sys.stdin); print('OK: projects' if 'projects' in d else 'FAIL: projects')"

# Check setup status
curl -sf http://127.0.0.1:5555/setup/status | python -c "import sys,json; d=json.load(sys.stdin); print('OK: setup' if 'openai' in d else 'FAIL: setup')"
```

### 6. Browser Smoke Test (requires Chrome automation)

If browser tools are available (e.g., Claude-in-Chrome MCP), verify:
1. Navigate to `http://127.0.0.1:5555`
2. Verify the page loads (check for "Field Cut" title or topbar element)
3. Check that the phase bar renders with 3 phases
4. Check that the transcript pane has an upload zone
5. Toggle theme (dark/light) and verify it switches
6. Toggle language (EN/HE) and verify RTL/LTR switches

## Running Everything

Run all automated tests in one command:

```bash
python -m ruff check . && python -m ruff format --check . && python -m pytest tests/ -v --tb=short
```

Or via Make:

```bash
make lint && make test
```

## Common Failures

| Failure | Likely cause |
|---------|-------------|
| `ImportError: app` | Missing dependencies — run `pip install -r requirements.txt` |
| `ffmpeg: command not found` | ffmpeg not installed — `brew install ffmpeg` (macOS) |
| `test_pipeline` tests skip | ffmpeg missing — install it for full coverage |
| `E402` lint error | Import order issue — `from openai import OpenAI` must be after dotenv loading |
| Ruff format fails | Run `make format` to auto-fix |
