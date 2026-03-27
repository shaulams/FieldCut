# Field Cut

A local web app for audio journalism production. Upload a field interview, get a timestamped transcript, mark clips, cut them, add narration, and assemble a rough cut — all in the browser.

Built for radio journalists and podcast producers who work with field recordings and want to go from raw interview to rough cut without jumping between five different tools.

<!-- TODO: add a screenshot -->
<!-- ![Field Cut screenshot](docs/screenshot.png) -->

## What it does

1. **Transcribe** — Upload a WAV/MP3 interview. Whisper API transcribes it to Hebrew text with word-level timestamps.
2. **Mark clips** — Select text in the transcript to mark clip boundaries. Clips are numbered automatically.
3. **Cut** — One click cuts the source audio into separate WAV files using ffmpeg.
4. **Narration** (optional) — Upload your narration recording, transcribe it, and mark narration clips the same way.
5. **Assemble** — Drag interview clips and narration into order, hit assemble, get a single rough-cut WAV.

## Requirements

- Python 3.9+
- [ffmpeg](https://ffmpeg.org/) installed and in your PATH
- An [OpenAI API key](https://platform.openai.com/api-keys) (for Whisper transcription)

## Quick start

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/fieldcut.git
cd fieldcut

# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up your API key
cp .env.example .env
# Edit .env and paste your OpenAI API key

# Run
python app.py
```

Open http://localhost:5555 in your browser.

## How much does it cost?

The only cost is OpenAI's Whisper API:
- **$0.006 per minute** of audio
- A 60-minute interview costs about **$0.36**

Everything else runs locally on your machine.

## Project management

Field Cut supports saving and loading multiple projects. Click **"projects"** in the top bar to see saved projects, or **"+ new project"** to start fresh. Your audio files, clips, and session state are saved per project.

## Tech stack

- **Backend:** Python / Flask
- **Frontend:** Single HTML file, vanilla JS (no build step, no framework)
- **Audio processing:** ffmpeg
- **Transcription:** OpenAI Whisper API
- **State:** JSON file (no database needed)

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## License

[MIT](LICENSE)
