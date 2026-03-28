# Field Cut

From field tape to rough cut in one place.

A local web app for audio journalism production. Upload a field interview, get a timestamped transcript with speaker detection, mark clips, cut them, add narration, and assemble a rough cut — all in the browser.

Built for radio journalists and podcast producers who work with field recordings and want to go from raw interview to rough cut without jumping between five different tools.

## What it does

1. **Transcribe** — Upload a WAV/MP3 interview. Whisper transcribes it with word-level timestamps. Supports Hebrew, English, Arabic, and more.
2. **Speaker detection** (optional) — Automatically identifies who's talking and color-codes speakers throughout the UI.
3. **Mark clips** — Click words in the transcript to mark clip boundaries. Clips are numbered automatically.
4. **Cut** — One click cuts the source audio into separate WAV files using ffmpeg.
5. **Narration** (optional) — Upload your narration recording, transcribe it, and mark narration clips the same way.
6. **Assemble** — Drag interview clips and narration into order, hit assemble, get a single rough-cut WAV.
7. **Export** — Download clips as a ZIP, transcript as a Word doc (with speaker colors), or the final rough cut.

## Features

- Waveform visualization with zoom, pan, and clip regions
- Speaker diarization with color-coded badges (rename or reassign speakers)
- Clip boundary trimming (fine-tune start/end times)
- Paper edit export (Word doc matching your assembly order)
- Multi-project support (save, load, duplicate projects)
- Export folder — auto-copy outputs to Google Drive, Dropbox, or any local folder
- Bilingual UI (English / Hebrew), easy to add more languages
- Built-in demo interview to try the full pipeline without your own audio
- First-run setup wizard for API keys
- Dark and light themes
- Works on macOS, Windows, and Linux

## Requirements

- Python 3.9+
- [ffmpeg](https://ffmpeg.org/) installed and in your PATH
- An [OpenAI API key](https://platform.openai.com/api-keys) (for Whisper transcription)
- Optional: [HuggingFace token](https://huggingface.co/settings/tokens) (for speaker detection)

## Quick start

```bash
# Clone the repo
git clone https://github.com/shaulams/FieldCut.git
cd FieldCut

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Optional: speaker detection (pulls ~2GB of PyTorch models)
pip install -r requirements-speaker.txt

# Run
python app.py
```

Open http://localhost:5555 in your browser. On first run, the app will ask for your API keys.

Or try the built-in demo — click **"Try a demo interview"** to experience the full pipeline without uploading your own audio.

## How much does it cost?

The only cost is OpenAI's Whisper API:
- **$0.006 per minute** of audio
- A 60-minute interview costs about **$0.36**

Speaker detection runs locally on your machine (free). Everything else is local too.

## Speaker detection setup

Speaker detection uses [pyannote](https://github.com/pyannote/pyannote-audio) and requires a free HuggingFace account:

1. Create a token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) (Read permission)
2. Accept the terms for these models:
   - [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)
   - [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
   - [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
3. Enter the token in the setup wizard, or add `HUGGINGFACE_TOKEN=hf_...` to your `.env` file

On Apple Silicon Macs, speaker detection uses the GPU automatically for faster processing.

## Tech stack

- **Backend:** Python / Flask
- **Frontend:** Single HTML file, vanilla JS (no build step, no framework)
- **Audio processing:** ffmpeg
- **Transcription:** OpenAI Whisper API
- **Speaker detection:** pyannote.audio (runs locally)
- **State:** JSON file (no database needed)

## Adding a new language

Field Cut ships with English and Hebrew. Adding a new language takes ~10 minutes:

1. Open `static/lang.js`
2. Copy the `en` block and paste it as a new key (e.g. `fr` for French, `ar` for Arabic)
3. Translate every string value — keep the keys unchanged
4. Set `_meta.name` to the language's own name (e.g. `"Francais"`) and `_meta.dir` to `"ltr"` or `"rtl"`
5. The language picker in the top bar will automatically include it

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## License

[MIT](LICENSE)
