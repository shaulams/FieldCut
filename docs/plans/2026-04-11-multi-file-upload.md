# Multi-File Upload Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users upload multiple interview files at once, transcribe them in parallel, and work with one unified transcript.

**Architecture:** The `/transcribe` endpoint accepts multiple files via `getlist("file")`. A thread per file handles compression + Whisper. After all threads complete, transcripts merge with time offsets into one unified state. Clip cutting resolves which source file to use via `source_index`.

**Tech Stack:** Python/Flask, threading, ffmpeg, OpenAI Whisper API, vanilla JS

---

### Task 1: Backend — `source_files` state + backward compat

**Files:**
- Modify: `app.py:232-234` (initial state shape)
- Modify: `app.py:516-564` (cut_clips — source file lookup)

**Step 1: Update initial state shape**

In `load_state()` return dict (line 232), add `source_files` and keep `source_file` for backward compat:

```python
return {"transcript": [], "words": [], "clips": [], "text_clips": [],
        "narration_transcript": [], "narration_words": [], "narr_text_clips": [],
        "narration": [], "assembly": [], "source_file": None, "source_files": [], "phase": 1}
```

**Step 2: Add helper to resolve source file for a clip**

Add this function after `get_clip_speaker()` (after line 108):

```python
def resolve_source_for_clip(clip, state):
    """Given a clip with start/end times, find the correct source file and real timestamps."""
    source_files = state.get("source_files", [])
    if not source_files:
        # Legacy single-file project
        sf = state.get("source_file", "")
        return sf, clip["start"], clip["end"]

    # Find which source file this clip belongs to by checking source_index on words/segments
    # or by timestamp range
    for i, sf in enumerate(source_files):
        offset = sf["offset"]
        end_time = offset + sf["duration"]
        if clip["start"] >= offset and clip["start"] < end_time:
            real_start = clip["start"] - offset
            real_end = clip["end"] - offset
            return sf["path"], real_start, real_end
    # Fallback to last file
    sf = source_files[-1]
    return sf["path"], clip["start"] - sf["offset"], clip["end"] - sf["offset"]
```

**Step 3: Update `cut_clips` to use resolver**

In `do_cut()` (line 530), replace the single `source_path` lookup with per-clip resolution:

```python
def do_cut():
  try:
    st = load_state()
    # Validate we have source files
    source_files = st.get("source_files", [])
    source_file = st.get("source_file", "")
    if not source_files and not source_file:
        st["status"] = "error: no source file found"
        save_state(st)
        progress.update(phase=None, message="")
        return
    # For legacy single-file: check it exists
    if not source_files and source_file and not os.path.exists(source_file):
        st["status"] = f"error: source file not found — {source_file}"
        save_state(st)
        progress.update(phase=None, message="")
        return

    clips = st.get("text_clips", [])
    progress.update(phase="cut", current=0, total=len(clips), message=f"cutting 0/{len(clips)} clips…")

    cut_files = []
    for i, clip in enumerate(clips):
        progress.update(current=i, message=f"cutting {clip['id']}… ({i+1}/{len(clips)})")
        source_path, real_start, real_end = resolve_source_for_clip(clip, st)
        if not os.path.exists(source_path):
            continue
        out_path = os.path.join(pdir("clips"), f"{clip['id']}.wav")
        duration = real_end - real_start
        cmd = [
            "ffmpeg", "-y",
            "-i", source_path,
            "-ss", str(real_start),
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
```

**Step 4: Commit**

```bash
git add app.py
git commit -m "feat: add source_files state and clip source resolver"
```

---

### Task 2: Backend — multi-file `/transcribe` endpoint

**Files:**
- Modify: `app.py:279-393` (transcribe route + do_transcribe)

**Step 1: Extract single-file transcription into a reusable function**

Add this function before the `/transcribe` route:

```python
def transcribe_single_file(filepath, whisper_lang, diarize, file_index, total_files):
    """Transcribe a single file. Returns (segments, words, duration) or raises."""
    # Get duration
    try:
        dur_result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", filepath],
            capture_output=True, text=True)
        duration = float(dur_result.stdout.strip())
    except Exception:
        duration = 0

    # Compress if needed
    upload_path = filepath
    if os.path.getsize(filepath) > 25 * 1024 * 1024:
        progress.update(phase="transcribe", current=file_index,
                       total=total_files, message=f"compressing file {file_index+1}/{total_files}…")
        compressed = filepath.rsplit(".", 1)[0] + "_compressed.mp3"
        target_bits = 24 * 1024 * 1024 * 8
        bitrate_kbps = max(8, min(64, int(target_bits / (duration or 1) / 1000)))
        subprocess.run([
            "ffmpeg", "-y", "-i", filepath,
            "-ac", "1", "-ar", "16000", "-b:a", f"{bitrate_kbps}k",
            compressed
        ], capture_output=True, check=True)
        upload_path = compressed

    progress.update(message=f"sending file {file_index+1}/{total_files} to Whisper…")

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

    words = []
    if hasattr(result, 'words') and result.words:
        for w in result.words:
            words.append({"word": w.word.strip(), "start": w.start, "end": w.end})

    raw = [{"start": seg.start, "end": seg.end, "text": seg.text.strip()} for seg in result.segments]
    passages = merge_segments(raw)
    segments = []
    for i, p in enumerate(passages):
        segments.append({
            "id": i, "start": p["start"], "end": p["end"],
            "text": p["text"], "speaker": "S1",
        })

    if diarize and os.environ.get("HUGGINGFACE_TOKEN"):
        segments = assign_speakers(segments, filepath)

    return segments, words, duration
```

**Step 2: Rewrite `/transcribe` to handle multiple files**

```python
@app.route("/transcribe", methods=["POST"])
def transcribe():
    if not client:
        return jsonify({"error": "OPENAI_API_KEY not set"}), 500

    files = request.files.getlist("file")
    if not files:
        return jsonify({"error": "No file uploaded"}), 400

    # Save all uploaded files
    file_infos = []
    for f in files:
        filepath = os.path.join(pdir("uploads"), f.filename)
        f.save(filepath)
        file_infos.append({"filename": f.filename, "path": filepath})

    whisper_lang = request.form.get("language", "he")
    diarize = request.form.get("diarize") == "1"
    if whisper_lang == "auto":
        whisper_lang = None

    def do_transcribe():
        state = load_state()
        state["status"] = "transcribing"
        # Set source_file to first file for backward compat
        state["source_file"] = file_infos[0]["path"]
        save_state(state)

        total_files = len(file_infos)
        progress.update(phase="transcribe", current=0, total=total_files,
                       message=f"transcribing 0/{total_files} files…")

        # Transcribe files in parallel
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = [None] * total_files
        errors = []

        def transcribe_file(idx):
            info = file_infos[idx]
            return idx, transcribe_single_file(info["path"], whisper_lang, diarize, idx, total_files)

        with ThreadPoolExecutor(max_workers=min(total_files, 4)) as executor:
            futures = {executor.submit(transcribe_file, i): i for i in range(total_files)}
            for future in as_completed(futures):
                try:
                    idx, (segments, words, duration) = future.result()
                    results[idx] = {"segments": segments, "words": words, "duration": duration}
                    progress.update(current=sum(1 for r in results if r is not None),
                                   message=f"transcribed {sum(1 for r in results if r is not None)}/{total_files} files…")
                except Exception as e:
                    idx = futures[future]
                    errors.append(f"{file_infos[idx]['filename']}: {friendly_error(e)}")

        if all(r is None for r in results):
            state["status"] = f"error: all files failed — {'; '.join(errors)}"
            save_state(state)
            progress.update(phase=None, current=0, total=0, message="")
            return

        # Merge results with time offsets
        merged_segments = []
        merged_words = []
        source_files = []
        offset = 0.0
        seg_id = 0

        for idx, r in enumerate(results):
            if r is None:
                continue
            info = file_infos[idx]
            source_files.append({
                "filename": info["filename"],
                "path": info["path"],
                "offset": offset,
                "duration": r["duration"]
            })
            for seg in r["segments"]:
                merged_segments.append({
                    "id": seg_id,
                    "start": seg["start"] + offset,
                    "end": seg["end"] + offset,
                    "text": seg["text"],
                    "speaker": seg.get("speaker", "S1"),
                    "source_index": len(source_files) - 1
                })
                seg_id += 1
            for w in r["words"]:
                merged_words.append({
                    "word": w["word"],
                    "start": w["start"] + offset,
                    "end": w["end"] + offset,
                    "source_index": len(source_files) - 1
                })
            offset += r["duration"]

        progress.update(message="processing segments…")

        # Build speaker_names
        seen = []
        for seg in merged_segments:
            spk = seg.get("speaker", "S1")
            if spk not in seen:
                seen.append(spk)
        speaker_names = {spk: spk for spk in seen}

        state["transcript"] = merged_segments
        state["words"] = merged_words
        state["text_clips"] = []
        state["clips"] = []
        state["status"] = "transcribed"
        state["filename"] = ", ".join(info["filename"] for info in file_infos)
        state["source_files"] = source_files
        state["source_file"] = file_infos[0]["path"]  # backward compat
        state["transcription_language"] = whisper_lang or "auto"
        state["speaker_names"] = speaker_names
        if errors:
            state["transcription_warnings"] = errors
        save_state(state)
        progress.update(phase="transcribe", current=total_files, total=total_files, message="done")
        progress["audio_duration"] = offset

    threading.Thread(target=do_transcribe).start()
    return jsonify({"message": "Transcription started"})
```

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: multi-file parallel transcription endpoint"
```

---

### Task 3: Frontend — multi-file upload UI

**Files:**
- Modify: `templates/index.html:456` (file input)
- Modify: `templates/index.html:773-794` (uploadAndTranscribe function)

**Step 1: Add `multiple` attribute to file input**

Line 456, change:
```html
<input type="file" id="audio-input" accept=".wav,.mp3,.m4a,.ogg" onchange="uploadAndTranscribe(event)">
```
to:
```html
<input type="file" id="audio-input" accept=".wav,.mp3,.m4a,.ogg" multiple onchange="uploadAndTranscribe(event)">
```

**Step 2: Update `uploadAndTranscribe` to send multiple files**

```javascript
async function uploadAndTranscribe(event) {
  const files = Array.from(event.target.files);
  if (!files.length) return;
  document.getElementById('upload-zone').style.display = 'none';
  document.getElementById('file-info').textContent =
    files.length === 1 ? files[0].name : `${files.length} files selected`;
  setStatus('working', t('transcribing'));
  const whisperLang = document.getElementById('whisper-lang').value;
  const diarize = document.getElementById('diarize-toggle').checked;
  const formData = new FormData();
  for (const file of files) {
    formData.append('file', file);
  }
  formData.append('language', whisperLang);
  if (diarize) formData.append('diarize', '1');
  const res = await fetch('/transcribe', { method: 'POST', body: formData });
  if (!res.ok) {
    const data = await res.json().catch(() => ({ error: t('server_error') }));
    setStatus('error', data.error || t('transcription_failed'));
    document.getElementById('upload-zone').style.display = '';
    return;
  }
  startProgressPolling();
  startPolling();
}
```

**Step 3: Commit**

```bash
git add templates/index.html
git commit -m "feat: multi-file upload UI"
```

---

### Task 4: Update remaining `source_file` references for compat

**Files:**
- Modify: `app.py` — all routes that read `source_file`

**Step 1: Audit and update all `source_file` references**

Search for all `source_file` usages and ensure they fall back correctly. Key places:

- `load_demo` route: should set both `source_file` and `source_files`
- `save_project` / `load_project`: `source_files` paths need fixing like `source_file`
- `/state` route: already returns full state, no change needed
- `reset` route: no change needed (returns fresh state which now includes `source_files`)

Update `load_state()` to auto-populate `source_files` from legacy `source_file`:

```python
def load_state():
    sf = state_file()
    if os.path.exists(sf):
        with open(sf) as f:
            state = json.load(f)
        # Backward compat: populate source_files from legacy source_file
        if state.get("source_file") and not state.get("source_files"):
            path = state["source_file"]
            if os.path.exists(path):
                try:
                    dur_result = subprocess.run(
                        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                        capture_output=True, text=True)
                    duration = float(dur_result.stdout.strip())
                except Exception:
                    duration = 0
                state["source_files"] = [{
                    "filename": state.get("filename", os.path.basename(path)),
                    "path": path, "offset": 0, "duration": duration
                }]
        # ... existing phase detection ...
```

**Step 2: Update path-fixing in `load_project`**

Where `source_file` path is fixed (line ~1328), also fix `source_files` paths:

```python
state["source_file"] = fix(state.get("source_file"))
for sf in state.get("source_files", []):
    sf["path"] = fix(sf.get("path", ""))
```

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: backward compat for source_files in all routes"
```

---

### Task 5: Manual integration test

**Step 1: Restart the server**

```bash
kill -9 $(lsof -ti:5555) 2>/dev/null
source venv/bin/activate && python app.py
```

**Step 2: Test single file upload (backward compat)**

Upload one file, verify transcription works as before.

**Step 3: Test multi-file upload**

Upload 2+ files, verify:
- Progress shows file count
- Transcript merges correctly with all segments
- Clips can be marked across file boundaries
- Clip cutting produces correct audio from correct source file

**Step 4: Test loading old project**

Load an existing saved project, verify `source_files` auto-populates from `source_file`.
