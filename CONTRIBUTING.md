# Contributing to FieldCut

Thanks for your interest in contributing! FieldCut is an open-source audio journalism tool, and we welcome contributions of all kinds — bug fixes, new features, documentation improvements, and translations.

## Getting Started

### 1. Fork & Clone

```bash
# Fork via GitHub UI, then:
git clone https://github.com/YOUR_USERNAME/FieldCut.git
cd FieldCut
```

### 2. Set Up Your Environment

```bash
# Quick setup (creates venv, installs all deps including dev tools):
make setup

# Or manually:
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install ffmpeg (required for audio processing)
# macOS:   brew install ffmpeg
# Ubuntu:  sudo apt install ffmpeg
# Windows: https://ffmpeg.org/download.html

# Optional: install pre-commit hooks (auto-formats on commit)
pre-commit install
```

### 3. Configure API Keys (optional for most development)

Copy `.env.example` to `.env` and add your keys. You only need the OpenAI key if you're testing transcription features:

```bash
cp .env.example .env
# Edit .env with your keys
```

### 4. Run the App

```bash
make run
# Or: python app.py
# Open http://localhost:5555
```

## Running Tests

```bash
# Run all tests
make test

# Run a specific test file
pytest tests/test_routes.py -v

# Run a specific test
pytest tests/test_helpers.py::TestMergeSegments::test_single_segment_unchanged -v
```

Tests don't require API keys — external services are mocked or skipped. You do need `ffmpeg` installed for the pipeline tests.

## Linting & Formatting

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check for lint errors and formatting issues
make lint

# Auto-fix formatting and lint issues
make format
```

If you installed the pre-commit hooks (`pre-commit install`), formatting is applied automatically on every commit.

## Making Changes

### Branch Naming

Create a branch from `main` with a descriptive name:

```bash
git checkout -b feature/waveform-zoom      # New feature
git checkout -b fix/clip-boundary-bug       # Bug fix
git checkout -b docs/setup-instructions     # Documentation
```

### Commit Messages

Use [conventional commits](https://www.conventionalcommits.org/):

```
feat: add clip boundary snapping to word boundaries
fix: prevent crash when source file is deleted mid-cut
docs: add Arabic translation instructions
chore: update pytest to 8.x
refactor: extract audio processing into separate module
test: add tests for assembly gap calculation
```

### Code Style

- **Backend:** Python, follow existing patterns. Run `make lint` before pushing — CI enforces it
- **Frontend:** Vanilla JS in `templates/index.html` and `static/lang.js` — no frameworks, no build step
- **Keep it simple** — this is a tool for journalists, not a tech demo
- **Error handling:** Use `friendly_error()` for user-facing errors, always provide a helpful message
- **Tests:** Add tests for new functionality

### Adding a New Language

FieldCut has built-in i18n. To add a language:

1. Open `static/lang.js`
2. Copy the `en` block
3. Translate all values (keep keys unchanged)
4. Set `_meta.name` to the language's own name and `_meta.dir` to `"ltr"` or `"rtl"`

## Submitting a Pull Request

1. Push your branch to your fork
2. Open a PR against `main` on the original repo
3. Fill in the PR template — describe what you changed and why
4. Make sure CI passes (tests run automatically)
5. Wait for review

### What Makes a Good PR

- **Small and focused** — one concern per PR
- **Tests included** — if you added or changed behavior
- **Description explains why** — not just what you changed
- **Screenshots** for UI changes

## Reporting Bugs

Open an issue with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Your OS, Python version, and browser

## Questions?

Open an issue or start a discussion. We're happy to help!
