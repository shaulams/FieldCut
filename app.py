import os, json, subprocess, tempfile, threading, time, io, shutil, struct
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, Response

# Optional diarization — requires HUGGINGFACE_TOKEN in .env
_diarization_pipeline = None
_diarization_lock = threading.Lock()

def get_diarization_pipeline():
    global _diarization_pipeline
    token = os.environ.get("HUGGINGFACE_TOKEN")
    if not token:
        return None
    with _diarization_lock:
        if _diarization_pipeline is None:
            try:
                from pyannote.audio import Pipeline
                _diarization_pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    use_auth_token=token,
                )
                print("✓ Speaker diarization pipeline loaded")
            except Exception as e:
                print(f"⚠️  Diarization pipeline failed to load: {e}")
                return None
    return _diarization_pipeline

def assign_speakers(segments, audio_path):
    """Run pyannote diarization and assign speaker labels to segments."""
    pipeline = get_diarization_pipeline()
    if pipeline is None:
        return segments  # no-op: keep S1 for all
    try:
        diarization = pipeline(audio_path)
        # Build list of (start, end, speaker) turns
        turns = [(turn.start, turn.end, speaker)
                 for turn, _, speaker in diarization.itertracks(yield_label=True)]
        # Map each segment to the speaker with the most overlap
        speaker_map = {}  # pyannote label → S1/S2/...
        for seg in segments:
            best_speaker, best_overlap = "S1", 0.0
            for t_start, t_end, spk in turns:
                overlap = min(seg["end"], t_end) - max(seg["start"], t_start)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_speaker = spk
            # Normalise to S1/S2/... labels
            if best_speaker not in speaker_map:
                speaker_map[best_speaker] = f"S{len(speaker_map) + 1}"
            seg["speaker"] = speaker_map[best_speaker]
        return segments
    except Exception as e:
        print(f"⚠️  Diarization failed: {e}")
        return segments

# Load .env file if present (so OPENAI_API_KEY persists across sessions)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from openai import OpenAI

app = Flask(__name__)

# ─── PROJECT DIRECTORY ────────────────────────────────────
_active_project_dir = os.path.join("projects", "_session")

def set_project_dir(path):
    global _active_project_dir
    _active_project_dir = path
    for sub in ['uploads', 'clips', 'narration', 'output']:
        os.makedirs(os.path.join(path, sub), exist_ok=True)

def pdir(folder=""):
    """Return path to a subfolder in the active project directory, creating it if needed."""
    path = os.path.join(_active_project_dir, folder) if folder else _active_project_dir
    os.makedirs(path, exist_ok=True)
    return path

os.makedirs("projects", exist_ok=True)
set_project_dir(_active_project_dir)

api_key = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None
if not api_key:
    print("⚠️  OPENAI_API_KEY not set. Create a .env file with: OPENAI_API_KEY=sk-...")

# Check for ffmpeg
try:
    subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
except (subprocess.CalledProcessError, FileNotFoundError):
    print("⚠️  ffmpeg not found. Install it with: brew install ffmpeg (Mac) or apt install ffmpeg (Linux)")
    print("   Audio cutting and assembly will not work without ffmpeg.")

# In-memory state (persisted per-project)
# Progress tracking for async operations
progress = {"phase": None, "current": 0, "total": 0, "message": ""}

def state_file():
    return os.path.join(_active_project_dir, "state.json")

def load_state():
    sf = state_file()
    # Migrate legacy root-level state.json once, then remove it so it can't re-appear after reset
    if not os.path.exists(sf) and os.path.exists("state.json"):
        shutil.copy2("state.json", sf)
        os.rename("state.json", "state.json.migrated")
    if os.path.exists(sf):
        with open(sf) as f:
            state = json.load(f)
        # Auto-detect phase for legacy projects that predate the phase system
        if "phase" not in state:
            status = state.get("status", "")
            if status in ("assembled",):
                state["phase"] = 3
            elif status in ("clips_ready", "narration_ready", "narration_cut"):
                state["phase"] = 2 if state.get("narration_transcript") else 1
            else:
                state["phase"] = 1
        return state
    return {"transcript": [], "words": [], "clips": [], "text_clips": [],
            "narration_transcript": [], "narration_words": [], "narr_text_clips": [],
            "narration": [], "assembly": [], "source_file": None, "phase": 1}

def save_state(state):
    with open(state_file(), "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def merge_segments(raw_segments, pause_threshold=1.0, sentence_gap=0.4, max_duration=45):
    """Merge short Whisper segments into longer passages based on pauses, punctuation, and max duration."""
    SENTENCE_ENDERS = set('.?!。؟')
    passages = []
    current = None
    for seg in raw_segments:
        if current is None:
            current = {**seg}
            continue
        gap = seg["start"] - current["end"]
        cur_duration = current["end"] - current["start"]
        prev_ends_sentence = current["text"] and current["text"][-1] in SENTENCE_ENDERS

        if (gap >= pause_threshold
            or (gap >= sentence_gap and prev_ends_sentence)
            or (cur_duration >= max_duration and gap >= 0.2)):
            passages.append(current)
            current = {**seg}
        else:
            current["end"] = seg["end"]
            current["text"] += " " + seg["text"]
    if current:
        passages.append(current)
    return passages

# ─── ROUTES ───────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/state")
def get_state():
    resp = jsonify(load_state())
    resp.headers["Cache-Control"] = "no-store"
    return resp

# ─── STEP 1: TRANSCRIBE ───────────────────────────────────

@app.route("/transcribe", methods=["POST"])
def transcribe():
    if not client:
        return jsonify({"error": "OPENAI_API_KEY not set"}), 500
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    filename = f.filename
    filepath = os.path.join(pdir("uploads"), filename)
    f.save(filepath)
    whisper_lang = request.form.get("language", "he")
    if whisper_lang == "auto":
        whisper_lang = None

    def do_transcribe():
        state = load_state()
        state["source_file"] = filepath
        state["status"] = "transcribing"
        save_state(state)

        try:
            upload_path = filepath
            if os.path.getsize(filepath) > 25 * 1024 * 1024:
                progress.update(phase="transcribe", current=0, total=3, message="compressing audio…")
                compressed = filepath.rsplit(".", 1)[0] + "_compressed.mp3"
                subprocess.run([
                    "ffmpeg", "-y", "-i", filepath,
                    "-ac", "1", "-ar", "16000", "-b:a", "64k",
                    compressed
                ], capture_output=True, check=True)
                upload_path = compressed
                progress.update(current=1, message="sending to Whisper…")
            else:
                progress.update(phase="transcribe", current=0, total=2, message="sending to Whisper…")

            whisper_kwargs = {
                "model": "whisper-1",
                "response_format": "verbose_json",
                "timestamp_granularities": ["word", "segment"],
            }
            if whisper_lang:
                whisper_kwargs["language"] = whisper_lang

            with open(upload_path, "rb") as audio_file:
                whisper_kwargs["file"] = audio_file
                result = client.audio.transcriptions.create(**whisper_kwargs)

            # Store word-level timestamps
            words = []
            if hasattr(result, 'words') and result.words:
                for w in result.words:
                    words.append({"word": w.word.strip(), "start": w.start, "end": w.end})

            # Store segment-level (merged into passages) for paragraph grouping
            raw = [{"start": seg.start, "end": seg.end, "text": seg.text.strip()} for seg in result.segments]
            passages = merge_segments(raw)

            segments = []
            for i, p in enumerate(passages):
                segments.append({
                    "id": i,
                    "start": p["start"],
                    "end": p["end"],
                    "text": p["text"],
                    "speaker": "S1",
                })

            progress.update(current=progress["total"] - 1, message="processing segments…")

            # Diarization (optional — only if HUGGINGFACE_TOKEN is set)
            if os.environ.get("HUGGINGFACE_TOKEN"):
                progress.update(message="detecting speakers…")
                segments = assign_speakers(segments, filepath)

            # Build speaker_names map from unique speakers in transcript
            seen = []
            for seg in segments:
                spk = seg.get("speaker", "S1")
                if spk not in seen:
                    seen.append(spk)
            speaker_names = {spk: spk for spk in seen}

            state["transcript"] = segments
            state["words"] = words
            state["text_clips"] = []
            state["clips"] = []
            state["status"] = "transcribed"
            state["filename"] = filename
            state["transcription_language"] = whisper_lang or "auto"
            state["speaker_names"] = speaker_names
            save_state(state)
            progress.update(current=progress["total"], message="done", phase=None)

        except Exception as e:
            state["status"] = f"error: {str(e)}"
            save_state(state)
            progress.update(phase=None, current=0, total=0, message="")

    threading.Thread(target=do_transcribe).start()
    return jsonify({"message": "Transcription started"})

@app.route("/status")
def status():
    state = load_state()
    return jsonify({
        "status": state.get("status", "idle"),
        "segment_count": len(state.get("transcript", [])),
        "filename": state.get("filename", "")
    })

@app.route("/progress")
def get_progress():
    return jsonify(progress)

# ─── STEP 2: TEXT-BASED CLIP MARKING ──────────────────────

@app.route("/add_clip", methods=["POST"])
def add_clip():
    """Add a clip from text selection with word-level timestamps."""
    data = request.json
    start = data["start"]
    end = data["end"]
    text = data.get("text", "")
    source = data.get("source", "interview")  # "interview" or "narration"

    state = load_state()

    if source == "narration":
        clips = state.get("narr_text_clips", [])
        prefix = "narr"
    else:
        clips = state.get("text_clips", [])
        prefix = "clip"

    # Auto-number
    clip_id = f"{prefix}_{len(clips) + 1:02d}"
    clips.append({
        "id": clip_id,
        "start": round(start, 3),
        "end": round(end, 3),
        "text": text,
        "source": source
    })

    # Sort by start time and renumber
    clips.sort(key=lambda c: c["start"])
    for i, c in enumerate(clips):
        c["id"] = f"{prefix}_{i + 1:02d}"

    if source == "narration":
        state["narr_text_clips"] = clips
    else:
        state["text_clips"] = clips

    save_state(state)
    return jsonify({"ok": True, "clip_id": clip_id, "clips": clips})

@app.route("/trim_clip", methods=["POST"])
def trim_clip():
    """Fine-tune start/end time of a marked clip."""
    data = request.json
    clip_id = data["id"]
    source = data.get("source", "interview")
    new_start = data.get("start")
    new_end = data.get("end")

    state = load_state()
    clips = state.get("narr_text_clips" if source == "narration" else "text_clips", [])

    for c in clips:
        if c["id"] == clip_id:
            if new_start is not None:
                c["start"] = round(max(0, float(new_start)), 3)
            if new_end is not None:
                c["end"] = round(float(new_end), 3)
            # Ensure start < end with at least 0.1s
            if c["start"] >= c["end"]:
                c["end"] = c["start"] + 0.1
            break

    if source == "narration":
        state["narr_text_clips"] = clips
    else:
        state["text_clips"] = clips

    save_state(state)
    return jsonify({"ok": True})


@app.route("/remove_clip", methods=["POST"])
def remove_clip():
    """Remove a clip by ID."""
    data = request.json
    clip_id = data["id"]
    source = data.get("source", "interview")

    state = load_state()

    if source == "narration":
        clips = state.get("narr_text_clips", [])
        prefix = "narr"
    else:
        clips = state.get("text_clips", [])
        prefix = "clip"

    clips = [c for c in clips if c["id"] != clip_id]

    # Renumber
    for i, c in enumerate(clips):
        c["id"] = f"{prefix}_{i + 1:02d}"

    if source == "narration":
        state["narr_text_clips"] = clips
    else:
        state["text_clips"] = clips

    save_state(state)
    return jsonify({"ok": True, "clips": clips})

# ─── STEP 3: CUT CLIPS ────────────────────────────────────

@app.route("/cut_clips", methods=["POST"])
def cut_clips():
    state = load_state()
    source = state.get("source_file")

    if not source or not os.path.exists(source):
        return jsonify({"error": "Source audio file not found"}), 400

    text_clips = state.get("text_clips", [])
    if not text_clips:
        return jsonify({"error": "No clips marked"}), 400

    state["status"] = "cutting"
    save_state(state)

    def do_cut():
      try:
        st = load_state()
        source_path = st.get("source_file", "")
        if not source_path or not os.path.exists(source_path):
            st["status"] = f"error: source file not found — {source_path}"
            save_state(st)
            progress.update(phase=None, message="")
            return

        clips = st.get("text_clips", [])
        progress.update(phase="cut", current=0, total=len(clips), message=f"cutting 0/{len(clips)} clips…")

        cut_files = []
        for i, clip in enumerate(clips):
            progress.update(current=i, message=f"cutting {clip['id']}… ({i+1}/{len(clips)})")
            out_path = os.path.join(pdir("clips"), f"{clip['id']}.wav")
            duration = clip["end"] - clip["start"]
            cmd = [
                "ffmpeg", "-y",
                "-i", source_path,
                "-ss", str(clip["start"]),
                "-t", str(duration),
                "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "1",
                out_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                cut_files.append({
                    "id": clip["id"],
                    "path": out_path,
                    "start": clip["start"],
                    "end": clip["end"],
                    "duration": round(duration, 2)
                })

        st["clips"] = cut_files
        st["status"] = "clips_ready"
        save_state(st)

        # Auto-generate transcript Word doc
        try:
            import docx as docx_lib
            from docx.shared import Pt, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH

            def set_rtl_doc(paragraph):
                pPr = paragraph._p.get_or_add_pPr()
                pPr.append(docx_lib.oxml.OxmlElement('w:bidi'))
                for run in paragraph.runs:
                    rPr = run._r.get_or_add_rPr()
                    rPr.append(docx_lib.oxml.OxmlElement('w:rtl'))

            doc = docx_lib.Document()
            style = doc.styles['Normal']
            style.font.name = 'David'
            style.font.size = Pt(13)

            title = doc.add_heading(st.get("filename", "תמלול"), level=1)
            title.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            set_rtl_doc(title)

            for clip in st.get("text_clips", []):
                start_fmt = f"{int(clip['start']//60):02d}:{int(clip['start']%60):02d}"
                end_fmt = f"{int(clip['end']//60):02d}:{int(clip['end']%60):02d}"
                p = doc.add_paragraph()
                run = p.add_run(f"{clip['id']}  ({start_fmt} – {end_fmt})")
                run.bold = True
                run.font.size = Pt(14)
                run.font.color.rgb = RGBColor(0x33, 0x99, 0x66)
                set_rtl_doc(p)
                tp = doc.add_paragraph(clip.get("text", ""))
                set_rtl_doc(tp)
                doc.add_paragraph("")

            doc.save(os.path.join(pdir("output"), "transcript.docx"))
        except Exception:
            pass  # Word doc generation is best-effort

        progress.update(phase=None, current=len(clips), total=len(clips), message="done")
      except Exception as e:
        st = load_state()
        st["status"] = f"error: clip cutting failed — {str(e)}"
        save_state(st)
        progress.update(phase=None, message="")

    threading.Thread(target=do_cut).start()
    return jsonify({"message": "Cutting started"})

@app.route("/export_transcript", methods=["GET"])
def export_transcript():
    import docx
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn

    def set_rtl(paragraph):
        """Set proper RTL on a paragraph (bidi) and all its runs (rtl)."""
        pPr = paragraph._p.get_or_add_pPr()
        pPr.append(docx.oxml.OxmlElement('w:bidi'))
        for run in paragraph.runs:
            rPr = run._r.get_or_add_rPr()
            rPr.append(docx.oxml.OxmlElement('w:rtl'))

    state = load_state()
    text_clips = state.get("text_clips", [])
    if not text_clips:
        return jsonify({"error": "No clips to export"}), 400

    doc = docx.Document()

    # Set default font for Hebrew
    style = doc.styles['Normal']
    style.font.name = 'David'
    style.font.size = Pt(13)

    title = doc.add_heading(state.get("filename", "תמלול"), level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_rtl(title)

    for clip in text_clips:
        start_fmt = f"{int(clip['start']//60):02d}:{int(clip['start']%60):02d}"
        end_fmt = f"{int(clip['end']//60):02d}:{int(clip['end']%60):02d}"

        p = doc.add_paragraph()
        run = p.add_run(f"{clip['id']}  ({start_fmt} – {end_fmt})")
        run.bold = True
        run.font.size = Pt(14)
        run.font.color.rgb = RGBColor(0x33, 0x99, 0x66)
        set_rtl(p)

        tp = doc.add_paragraph(clip.get("text", ""))
        set_rtl(tp)

        doc.add_paragraph("")  # spacer

    out_path = os.path.join(pdir("output"), "transcript.docx")
    doc.save(out_path)
    return send_file(out_path, as_attachment=True, download_name="transcript.docx")

# ─── STEP 4: NARRATION ────────────────────────────────────

@app.route("/upload_narration_audio", methods=["POST"])
def upload_narration_audio():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files["file"]
    filepath = os.path.join(pdir("narration"), f.filename)
    f.save(filepath)
    state = load_state()
    state["narration_source"] = filepath
    state["narration_filename"] = f.filename
    save_state(state)
    return jsonify({"ok": True, "filename": f.filename})

@app.route("/import_script", methods=["POST"])
def import_script():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files["file"]
    filename = f.filename.lower()

    if filename.endswith(".docx"):
        import docx
        tmp = tempfile.mktemp(suffix=".docx")
        f.save(tmp)
        doc = docx.Document(tmp)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        os.unlink(tmp)
    elif filename.endswith(".txt"):
        text = f.read().decode("utf-8")
    else:
        return jsonify({"error": "Unsupported format. Use .docx or .txt"}), 400

    return jsonify({"text": text})

@app.route("/process_narration", methods=["POST"])
def process_narration():
    """Transcribe already-uploaded narration audio with optional script text."""
    if not client:
        return jsonify({"error": "OPENAI_API_KEY not set"}), 500

    data = request.json or {}
    script_text = data.get("script", "").strip()

    state = load_state()
    filepath = state.get("narration_source")
    if not filepath or not os.path.exists(filepath):
        return jsonify({"error": "Upload narration audio first"}), 400

    state["status"] = "processing_narration"
    save_state(state)

    def do_process():
        st = load_state()
        try:
            upload_path = filepath
            if os.path.getsize(filepath) > 25 * 1024 * 1024:
                progress.update(phase="narration", current=0, total=3, message="compressing narration…")
                compressed = filepath.rsplit(".", 1)[0] + "_compressed.mp3"
                subprocess.run([
                    "ffmpeg", "-y", "-i", filepath,
                    "-ac", "1", "-ar", "16000", "-b:a", "64k",
                    compressed
                ], capture_output=True, check=True)
                upload_path = compressed
                progress.update(current=1, message="transcribing narration…")
            else:
                progress.update(phase="narration", current=0, total=2, message="transcribing narration…")

            narr_lang = st.get("transcription_language", "he")
            whisper_kwargs = {
                "model": "whisper-1",
                "response_format": "verbose_json",
                "timestamp_granularities": ["word", "segment"],
            }
            if narr_lang and narr_lang != "auto":
                whisper_kwargs["language"] = narr_lang
            if script_text:
                whisper_kwargs["prompt"] = script_text[:500]

            with open(upload_path, "rb") as audio_file:
                whisper_kwargs["file"] = audio_file
                result = client.audio.transcriptions.create(**whisper_kwargs)

            # Word-level timestamps
            words = []
            if hasattr(result, 'words') and result.words:
                for w in result.words:
                    words.append({"word": w.word.strip(), "start": w.start, "end": w.end})

            raw = [{"start": seg.start, "end": seg.end, "text": seg.text.strip()} for seg in result.segments]
            passages = merge_segments(raw)

            st["narration_transcript"] = []
            for i, p in enumerate(passages):
                st["narration_transcript"].append({
                    "id": i,
                    "start": p["start"],
                    "end": p["end"],
                    "text": p["text"],
                })

            st["narration_words"] = words
            st["narr_text_clips"] = []
            st["narration"] = []
            st["narration_source"] = filepath
            st["status"] = "narration_ready"
            save_state(st)
            progress.update(phase=None, current=progress["total"], total=progress["total"], message="done")

        except Exception as e:
            st["status"] = f"error: {str(e)}"
            save_state(st)
            progress.update(phase=None, current=0, total=0, message="")

    threading.Thread(target=do_process).start()
    return jsonify({"message": "Processing narration…"})

@app.route("/cut_narration", methods=["POST"])
def cut_narration():
    state = load_state()
    source = state.get("narration_source")
    if not source or not os.path.exists(source):
        return jsonify({"error": "Narration source not found"}), 400

    narr_clips = state.get("narr_text_clips", [])
    if not narr_clips:
        return jsonify({"error": "No narration clips marked"}), 400

    state["status"] = "cutting_narration"
    save_state(state)

    def do_cut():
        st = load_state()
        clips = st.get("narr_text_clips", [])
        progress.update(phase="cut_narr", current=0, total=len(clips),
                        message=f"cutting 0/{len(clips)} narration clips…")

        narration_files = []
        for i, clip in enumerate(clips):
            clip_name = f"{clip['id']}.wav"
            out_path = os.path.join(pdir("narration"), clip_name)
            duration = clip["end"] - clip["start"]
            progress.update(current=i, message=f"cutting {clip['id']}… ({i+1}/{len(clips)})")
            cmd = [
                "ffmpeg", "-y",
                "-i", source,
                "-ss", str(clip["start"]),
                "-t", str(duration),
                "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "1",
                out_path
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            narration_files.append({
                "name": clip_name,
                "path": out_path,
                "start": clip["start"],
                "end": clip["end"],
                "duration": round(duration, 2),
                "text": clip.get("text", "")
            })

        st["narration"] = narration_files
        st["status"] = "narration_cut"
        save_state(st)
        progress.update(phase=None, current=len(clips), total=len(clips), message="done")

    threading.Thread(target=do_cut).start()
    return jsonify({"message": "Cutting narration…"})

# ─── STEP 5: ASSEMBLE ─────────────────────────────────────

@app.route("/assemble", methods=["POST"])
def assemble():
    import datetime as _dt
    data = request.json
    assembly_order = data.get("order", [])
    gap_seconds = max(0.0, min(5.0, float(data.get("gap", 1.0))))
    output_name = "rough_cut_{}.wav".format(_dt.datetime.now().strftime("%Y%m%d_%H%M%S"))

    state = load_state()
    clips_map = {c["id"]: c["path"] for c in state.get("clips", [])}
    narration_map = {n["name"]: n["path"] for n in state.get("narration", [])}

    file_paths = []
    for item in assembly_order:
        if item["type"] == "narration":
            path = narration_map.get(item["file"])
        elif item["type"] == "clip":
            path = clips_map.get(item["id"])
        else:
            continue
        if path and os.path.exists(path):
            file_paths.append(os.path.abspath(path))

    if not file_paths:
        return jsonify({"error": "No valid files in assembly order"}), 400

    state["status"] = "assembling"
    save_state(state)

    def do_assemble():
        try:
            progress.update(phase="assemble", current=0, total=len(file_paths), message="assembling rough cut…")

            output_path = os.path.join(pdir("output"), output_name)

            # Generate silence file for gaps between clips
            silence_path = os.path.join(pdir("output"), "_silence.wav")
            if gap_seconds > 0:
                subprocess.run([
                    "ffmpeg", "-y", "-f", "lavfi", "-t", str(gap_seconds),
                    "-i", "anullsrc=r=44100:cl=mono",
                    "-c:a", "pcm_s16le", silence_path
                ], capture_output=True)

            final_paths = [file_paths[0]]
            for i in range(1, len(file_paths)):
                if gap_seconds > 0:
                    final_paths.append(os.path.abspath(silence_path))
                final_paths.append(file_paths[i])

            cmd = ["ffmpeg", "-y"]
            for p in final_paths:
                cmd += ["-i", p]
            filter_parts = "".join(f"[{i}:a]" for i in range(len(final_paths)))
            cmd += [
                "-filter_complex", f"{filter_parts}concat=n={len(final_paths)}:v=0:a=1[out]",
                "-map", "[out]",
                "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "1",
                output_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            st = load_state()
            if result.returncode != 0:
                err_msg = result.stderr[:500] if result.stderr else "ffmpeg failed"
                st["status"] = f"error: {err_msg}"
                save_state(st)
                progress.update(phase=None, message="")
            else:
                st["status"] = "assembled"
                st["output_file"] = output_path
                st["output_filename"] = output_name
                save_state(st)
                progress.update(phase=None, current=len(file_paths), total=len(file_paths), message="done")
        except Exception as e:
            st = load_state()
            st["status"] = f"error: assembly failed — {str(e)}"
            save_state(st)
            progress.update(phase=None, message="")

    threading.Thread(target=do_assemble).start()
    return jsonify({"message": "Assembly started"})


@app.route("/export_paper_edit", methods=["POST"])
def export_paper_edit():
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    data = request.json
    assembly_order = data.get("order", [])

    state = load_state()
    # Merge text_clips and cut clips so start/end are always available
    clips_map = {c["id"]: c for c in state.get("text_clips", [])}
    clips_map.update({c["id"]: c for c in state.get("clips", [])})
    narration_map = {n["name"]: n for n in state.get("narration", [])}
    narr_clips_map = {c["id"]: c for c in state.get("narr_text_clips", [])}

    # Build clip_id → text lookup from text_clips (primary) and legacy segment clip_id
    clip_text = {}
    for clip in state.get("text_clips", []):
        if clip.get("text"):
            clip_text[clip["id"]] = clip["text"]
    for clip in state.get("narr_text_clips", []):
        if clip.get("text"):
            clip_text[clip["id"]] = clip["text"]
    # Legacy fallback: segments with clip_id set
    for seg in state.get("transcript", []):
        cid = seg.get("clip_id")
        if cid and cid not in clip_text:
            clip_text[cid] = clip_text.get(cid, "") + seg.get("text", "")
    for seg in state.get("narration_transcript", []):
        cid = seg.get("clip_id")
        if cid and cid not in clip_text:
            clip_text[cid] = clip_text.get(cid, "") + seg.get("text", "")

    doc = Document()
    # RTL paragraph direction for Hebrew
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    def set_rtl(para):
        pPr = para._p.get_or_add_pPr()
        bidi = OxmlElement('w:bidi')
        pPr.append(bidi)
        for run in para.runs:
            rPr = run._r.get_or_add_rPr()
            rtl = OxmlElement('w:rtl')
            rPr.append(rtl)

    # Set document-wide RTL (bidi) on the default paragraph style
    from docx.oxml.ns import qn as _qn
    doc_defaults = doc.styles['Normal']._element
    pPr_default = doc_defaults.get_or_add_pPr() if hasattr(doc_defaults, 'get_or_add_pPr') else None
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'David'
    normal_style.font.size = Pt(12)
    # Apply RTL to the Normal style paragraph properties
    normal_pPr = normal_style._element.get_or_add_pPr()
    normal_pPr.append(OxmlElement('w:bidi'))

    # Use a plain paragraph for the title (heading styles override RTL alignment)
    title = doc.add_paragraph()
    title_run = title.add_run(state.get("project_name", "תמלול סופי"))
    title_run.bold = True
    title_run.font.size = Pt(22)
    title_run.font.name = 'David'
    title.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_rtl(title)
    # Bottom border under title
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '6')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), '1D9E75')
    pBdr.append(bottom)
    title._p.get_or_add_pPr().append(pBdr)

    for i, item in enumerate(assembly_order, 1):
        item_type = item.get("type")
        if item_type == "clip":
            cid = item.get("id")
            clip = clips_map.get(cid, {})
            start = clip.get("start", 0)
            end = clip.get("end", 0)
            text = clip_text.get(cid, "").strip()

            # Type label
            label_para = doc.add_paragraph()
            label_run = label_para.add_run(f"[{i}] CLIP — {cid}  {start:.1f}s – {end:.1f}s")
            label_run.bold = True
            label_run.font.color.rgb = RGBColor(0x1D, 0x9E, 0x75)

            # Text
            if text:
                p = doc.add_paragraph(text)
                set_rtl(p)
            else:
                doc.add_paragraph("(no transcript text)")

        elif item_type == "narration":
            fname = item.get("file", "")
            text = clip_text.get(item.get("id", ""), "").strip()

            label_para = doc.add_paragraph()
            label_run = label_para.add_run(f"[{i}] NARRATION — {fname}")
            label_run.bold = True
            label_run.font.color.rgb = RGBColor(0x37, 0x8A, 0xDD)

            if text:
                p = doc.add_paragraph(text)
                set_rtl(p)

        doc.add_paragraph()  # spacer

    # Name the docx after the rough cut file (same timestamp)
    rough_cut_name = state.get("output_filename", "rough_cut")
    docx_name = rough_cut_name.replace(".wav", ".docx") if rough_cut_name.endswith(".wav") else "transcript.docx"
    out_path = os.path.join(pdir("output"), docx_name)
    doc.save(out_path)
    return send_file(out_path, as_attachment=True, download_name=docx_name)


# ─── AUDIO ────────────────────────────────────────────────

@app.route("/waveform")
def waveform():
    """Extract waveform amplitude data for canvas rendering."""
    filepath = request.args.get("file", "")
    n_points = int(request.args.get("points", 1000))

    if not filepath or not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404

    # Extract mono PCM at 100 Hz — manageable even for 2-hour files
    cmd = [
        "ffmpeg", "-i", filepath,
        "-ac", "1", "-filter:a", "aresample=100",
        "-map_metadata", "-1",
        "-f", "s16le", "-acodec", "pcm_s16le", "pipe:1"
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0 or not result.stdout:
        return jsonify({"error": "ffmpeg failed"}), 500

    raw = result.stdout
    n_samples = len(raw) // 2
    samples = struct.unpack(f"<{n_samples}h", raw)

    duration = n_samples / 100.0

    # Downsample to n_points using RMS per chunk
    chunk = max(1, n_samples // n_points)
    points = []
    max_rms = 1.0
    rms_list = []
    for i in range(0, n_samples, chunk):
        seg = samples[i:i + chunk]
        rms = (sum(s * s for s in seg) / len(seg)) ** 0.5
        rms_list.append(rms)
    if rms_list:
        max_rms = max(rms_list) or 1.0
        points = [round(r / max_rms, 4) for r in rms_list]

    return jsonify({"points": points, "duration": round(duration, 2)})


@app.route("/audio_snippet")
def audio_snippet():
    """Extract a small audio snippet on the fly as MP3 — instant playback, no buffering."""
    filepath = request.args.get("file", "")
    start = request.args.get("start", type=float, default=0)
    end = request.args.get("end", type=float, default=0)

    if not filepath or not os.path.exists(filepath):
        return "File not found", 404

    duration = end - start
    if duration <= 0 or duration > 300:
        return "Invalid range", 400

    # Add small padding to avoid cutting words
    padded_start = max(0, start - 0.05)
    padded_duration = duration + 0.1

    # Use ffmpeg to extract snippet as MP3 (small, instant playback)
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(padded_start),
        "-i", filepath,
        "-t", str(padded_duration),
        "-c:a", "libmp3lame", "-b:a", "128k",
        "-f", "mp3",
        "pipe:1"
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        return "ffmpeg error", 500

    return Response(result.stdout, mimetype="audio/mpeg",
                    headers={"Cache-Control": "public, max-age=3600"})

@app.route("/audio/<path:filepath>")
def stream_audio(filepath):
    """Serve audio files for in-browser playback."""
    if not os.path.exists(filepath):
        return "Not found", 404
    return send_file(filepath, mimetype="audio/wav", conditional=True)

@app.route("/download/<path:filename>")
def download(filename):
    return send_file(os.path.join(pdir("output"), filename), as_attachment=True)

@app.route("/export_clips_zip")
def export_clips_zip():
    import zipfile, io
    state = load_state()
    clips = state.get("clips", [])
    if not clips:
        return jsonify({"error": "No clips to export"}), 400
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for clip in clips:
            path = clip.get("path", "")
            if path and os.path.exists(path):
                zf.write(path, os.path.basename(path))
    buf.seek(0)
    project_name = state.get("project_name", "clips")
    zip_name = f"{project_name}_clips.zip"
    return Response(buf.read(), mimetype="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{zip_name}"'})

@app.route("/download_output")
def download_output():
    """Download the most recent assembled output for the active project."""
    state = load_state()
    output_file = state.get("output_file")
    output_name = state.get("output_filename", "rough_cut.wav")
    if not output_file or not os.path.exists(output_file):
        return jsonify({"error": "No output file found"}), 404
    return send_file(output_file, as_attachment=True, download_name=output_name)

@app.route("/set_phase", methods=["POST"])
def set_phase():
    data = request.get_json(force=True)
    phase = data.get("phase")
    if phase not in (1, 2, 3):
        return jsonify({"error": "phase must be 1, 2, or 3"}), 400
    state = load_state()
    state["phase"] = phase
    save_state(state)
    return jsonify({"ok": True, "phase": phase})

# ─── PROJECTS ────────────────────────────────────────────

@app.route("/save_project", methods=["POST"])
def save_project():
    import re
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Project name is required"}), 400

    safe_name = re.sub(r'[^a-zA-Z0-9\u0590-\u05FF \-_]', '', name).strip()
    if not safe_name:
        return jsonify({"error": "Invalid project name"}), 400

    target_dir = os.path.join("projects", safe_name)

    if _active_project_dir == target_dir:
        # Already in the right place — just update project_name in state
        pass
    elif os.path.basename(_active_project_dir) == "_session":
        # Rename _session → named project
        session_state = load_state()
        if not session_state.get("source_file"):
            # Empty session — do not overwrite an existing named project with blank data
            if os.path.exists(target_dir):
                set_project_dir(target_dir)
            else:
                set_project_dir(target_dir)
                empty = {"project_name": safe_name}
                save_state(empty)
        else:
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            shutil.copytree(_active_project_dir, target_dir)
            set_project_dir(target_dir)
    else:
        # Save-as from one project to another name
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        shutil.copytree(_active_project_dir, target_dir)
        set_project_dir(target_dir)

    state = load_state()
    state["project_name"] = safe_name
    save_state(state)
    return jsonify({"ok": True, "name": safe_name})


@app.route("/projects")
def list_projects():
    projects = []
    if os.path.exists("projects"):
        for entry in sorted(os.listdir("projects")):
            if entry == "_session":
                continue
            entry_path = os.path.join("projects", entry)
            state_path = os.path.join(entry_path, "state.json")
            if os.path.isdir(entry_path) and os.path.exists(state_path):
                try:
                    with open(state_path) as f:
                        s = json.load(f)
                    projects.append({
                        "name": entry,
                        "interviewee": s.get("interviewee", ""),
                        "recording_date": s.get("recording_date", ""),
                    })
                except Exception:
                    projects.append({"name": entry, "interviewee": "", "recording_date": ""})
    return jsonify({"projects": projects})


def _migrate_paths(state, project_dir):
    """Rewrite legacy root-relative paths to project-scoped paths."""
    prefix_map = {
        "uploads/": os.path.join(project_dir, "uploads") + os.sep,
        "clips/": os.path.join(project_dir, "clips") + os.sep,
        "narration/": os.path.join(project_dir, "narration") + os.sep,
        "output/": os.path.join(project_dir, "output") + os.sep,
    }
    def fix(path):
        if not path:
            return path
        for old_prefix, new_prefix in prefix_map.items():
            if path.startswith(old_prefix):
                return new_prefix + path[len(old_prefix):]
        return path

    state["source_file"] = fix(state.get("source_file"))
    state["narration_source"] = fix(state.get("narration_source"))
    for c in state.get("clips", []):
        c["path"] = fix(c.get("path", ""))
    for n in state.get("narration", []):
        n["path"] = fix(n.get("path", ""))
    if "output_file" in state:
        state["output_file"] = fix(state["output_file"])
    return state


@app.route("/load_project", methods=["POST"])
def load_project():
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Project name is required"}), 400

    project_dir = os.path.join("projects", name)
    if not os.path.exists(os.path.join(project_dir, "state.json")):
        return jsonify({"error": "Project not found"}), 404

    set_project_dir(project_dir)
    state = load_state()
    state = _migrate_paths(state, project_dir)
    save_state(state)
    return jsonify({"ok": True, "state": state})


@app.route("/delete_project", methods=["POST"])
def delete_project():
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Project name is required"}), 400

    project_dir = os.path.join("projects", name)
    if not os.path.exists(project_dir):
        return jsonify({"error": "Project not found"}), 404

    shutil.rmtree(project_dir)
    # If we just deleted the active project, switch to a fresh session
    if _active_project_dir == project_dir:
        set_project_dir(os.path.join("projects", "_session"))
    return jsonify({"ok": True})


@app.route("/update_metadata", methods=["POST"])
def update_metadata():
    data = request.json or {}
    state = load_state()
    for field in ["interviewee", "recording_date", "notes"]:
        if field in data:
            state[field] = data[field]
    save_state(state)
    return jsonify({"ok": True})


@app.route("/rename_speaker", methods=["POST"])
def rename_speaker():
    data = request.json or {}
    speaker_id = data.get("speaker_id", "").strip()   # e.g. "S1"
    display_name = data.get("display_name", "").strip()  # e.g. "Interviewer"
    if not speaker_id or not display_name:
        return jsonify({"error": "speaker_id and display_name required"}), 400
    state = load_state()
    if "speaker_names" not in state:
        state["speaker_names"] = {}
    state["speaker_names"][speaker_id] = display_name
    save_state(state)
    return jsonify({"ok": True, "speaker_names": state["speaker_names"]})


@app.route("/duplicate_project", methods=["POST"])
def duplicate_project():
    data = request.json or {}
    name = data.get("name", "").strip()
    project_dir = os.path.join("projects", name)
    if not os.path.exists(project_dir):
        return jsonify({"error": "Project not found"}), 404

    # Find a unique name for the copy
    new_name = name + " copy"
    counter = 2
    while os.path.exists(os.path.join("projects", new_name)):
        new_name = f"{name} copy {counter}"
        counter += 1

    new_dir = os.path.join("projects", new_name)
    shutil.copytree(project_dir, new_dir)

    # Update project_name in the copy's state
    new_state_path = os.path.join(new_dir, "state.json")
    if os.path.exists(new_state_path):
        with open(new_state_path) as f:
            s = json.load(f)
        s["project_name"] = new_name
        with open(new_state_path, "w") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)

    set_project_dir(new_dir)
    loaded_state = load_state()
    return jsonify({"ok": True, "name": new_name, "state": loaded_state})


@app.route("/reset", methods=["POST"])
def reset():
    set_project_dir(os.path.join("projects", "_session"))
    sf = state_file()
    if os.path.exists(sf):
        os.unlink(sf)
    # Permanently consume legacy root state.json so it can never re-migrate after reset
    if os.path.exists("state.json"):
        os.rename("state.json", "state.json.migrated")
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(debug=True, port=5555)
