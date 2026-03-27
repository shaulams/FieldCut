# Field Cut — Claude Code Context

## What this project is

A local web app for audio journalism production. Built for a Hebrew-language journalist
who records field interviews and produces narrative audio pieces (think radio documentary / podcast).

The app replaces a manual workflow that currently uses:
- Google Pinpoint (transcription)
- Google Docs (script writing)
- Reaper (manual cutting and assembly)

## The pipeline this app automates

1. Upload a WAV or MP3 interview file (Hebrew, 1-2 speakers, 10–120 min)
2. Transcribe via OpenAI Whisper API → timestamped segments, Hebrew text
3. User clicks segments in the transcript UI to mark clip boundaries
4. App cuts the source audio into numbered clip files using ffmpeg
5. User records narration separately in Reaper, exports WAV files
6. User uploads narration WAVs and defines assembly order in the UI
7. App assembles narration + clips into a single rough cut WAV via ffmpeg

## Stack

- **Backend**: Python / Flask (app.py)
- **Frontend**: Single HTML template (templates/index.html) — vanilla JS, no framework
- **Audio processing**: ffmpeg (must be installed on the system)
- **Transcription**: OpenAI Whisper API (`whisper-1` model, `verbose_json` format with segment timestamps)
- **State**: JSON file (`state.json`) — single session, no database
- **Port**: 5555

## Project structure

```
fieldcut/
├── CLAUDE.md           ← you are here
├── app.py              ← Flask server, all routes
├── requirements.txt    ← flask, openai
├── state.json          ← auto-generated, current session state
├── templates/
│   └── index.html      ← full UI (transcript, timeline, assembly panel)
├── uploads/            ← source audio files
├── clips/              ← cut clip WAVs (clip_01.wav, clip_02.wav…)
├── narration/          ← user-uploaded narration WAVs
└── output/             ← final rough_cut.wav
```

## Environment

Requires one env variable:
```
OPENAI_API_KEY=sk-...
```

Run with:
```bash
pip install -r requirements.txt
python app.py
```

## Key API routes

| Route | Method | What it does |
|---|---|---|
| `/` | GET | Serves the UI |
| `/state` | GET | Returns full session state as JSON |
| `/transcribe` | POST | Accepts audio file, kicks off Whisper transcription in background thread |
| `/status` | GET | Polling endpoint — returns transcription status + segment count |
| `/mark` | POST | Toggles a segment as marked/unmarked, auto-renumbers clip IDs |
| `/mark_range` | POST | Marks a range of consecutive segments as one clip |
| `/cut_clips` | POST | Runs ffmpeg to cut all marked clips from source file |
| `/upload_narration` | POST | Accepts multiple WAV files, saves to narration/ |
| `/assemble` | POST | Takes ordered assembly list, runs ffmpeg concat, returns rough_cut.wav |
| `/download/<filename>` | GET | Downloads a file from output/ |
| `/reset` | POST | Clears state.json |

## State shape

```json
{
  "source_file": "uploads/interview.wav",
  "filename": "interview.wav",
  "status": "transcribed",
  "transcript": [
    {
      "id": 0,
      "start": 12.4,
      "end": 28.1,
      "text": "הטקסט בעברית",
      "speaker": "S1",
      "marked": false,
      "clip_id": null
    }
  ],
  "clips": [
    { "id": "clip_01", "path": "clips/clip_01.wav", "start": 41.0, "end": 68.0, "duration": 27.0 }
  ],
  "narration": [
    { "name": "intro.wav", "path": "narration/intro.wav" }
  ]
}
```

## Known limitations to address

- **Speaker diarization is not implemented** — all segments get `"speaker": "S1"`. 
  To add real diarization: integrate `pyannote.audio` or use AssemblyAI's diarization API.
  The transcript UI already supports S1/S2/S3 with different colors.

- **Clip marking is per-segment** — each Whisper segment is ~5-15 seconds. 
  For finer control, consider adding word-level timestamps (`timestamp_granularities: ["word"]`)
  and allowing sub-segment selection.

- **Assembly requires manual input** — user types file names into the assembly order UI.
  Could be improved with drag-and-drop reordering.

- **No multi-project support** — one state.json, one session at a time.
  If needed: add project name to state, save as `state_{project}.json`.

- **ffmpeg must be installed separately** — `brew install ffmpeg` on Mac.
  Add a startup check that warns the user if ffmpeg is not found in PATH.

## Audio notes

- Source files are Hebrew speech, often with background noise (field interviews)
- Whisper handles Hebrew well but may struggle with proper nouns and names
- ffmpeg copy mode (`-c copy`) is used for cutting — fast but requires same codec
  If codec issues arise, switch to `-c:a pcm_s16le` for WAV output
- The assembly uses ffmpeg's concat demuxer — all files must have matching sample rate + channels
  Add a normalization step if files come from different sources

## UI notes

- The UI is RTL-ready (Hebrew) with `dir="rtl"` on the html tag
- Font: Heebo (Hebrew-optimized sans-serif) + JetBrains Mono for timestamps/codes
- Dark theme only
- The transcript panel highlights marked segments in green
- The timeline preview at the bottom shows narration + clip tracks side by side

## What "done" looks like

A journalist can:
1. Drop in an interview WAV
2. Get a readable Hebrew transcript in ~2-3 minutes
3. Click to mark 5-10 clip selections
4. Hit "cut clips" — get numbered WAV files
5. Upload their narration recordings
6. Define the order and hit "assemble"
7. Get a single WAV rough cut ready for final polish in Reaper
