# Multi-File Upload & Parallel Transcription

## Problem

Users often have multiple interview recordings (different speakers) for the same project. Currently they must merge files externally before uploading, which is slow and adds a manual step. Transcribing one large merged file is also slower than transcribing smaller files in parallel.

## Design

### Approach: Multi-file single endpoint with parallel transcription

The upload zone accepts multiple files. All files are sent to `/transcribe` in one request. The backend spawns a thread per file, transcribes in parallel via Whisper, then merges results into one unified transcript with artificial time offsets so segments don't overlap.

### State changes

`source_file` (string) becomes `source_files` (array):

```json
{
  "source_files": [
    { "filename": "interview_a.wav", "path": "projects/x/uploads/interview_a.wav", "offset": 0, "duration": 300.5 },
    { "filename": "interview_b.wav", "path": "projects/x/uploads/interview_b.wav", "offset": 300.5, "duration": 245.8 }
  ]
}
```

Backward compatible: old projects with `source_file` (string) still load fine.

### Transcript merging

- Each file is transcribed independently (compression + Whisper call per file)
- After all complete, transcripts are merged in upload order
- File B's timestamps are shifted by the sum of all preceding files' durations
- Each segment and word gets a `source_index` field pointing to its entry in `source_files`

### Clip cutting

When cutting a clip, the system:
1. Looks up `source_index` on the segment/word
2. Subtracts the file's `offset` to get the real timestamp within that file
3. Runs ffmpeg against the correct source file

### Progress UX

- Progress bar shows overall status: "Transcribing file 2 of 3..."
- Individual file compression/upload steps tracked
- Errors on one file don't block others; failed files are reported at the end

### UI changes

- Upload zone `<input>` gets `multiple` attribute
- File info bar shows count: "3 files selected" instead of single filename
- Transcript view unchanged — segments appear with speaker colors/labels as before
- A subtle divider or label between file boundaries (optional, low priority)

### Backend changes

- `/transcribe` accepts multiple files in `request.files.getlist("file")`
- Each file gets its own thread for compress + Whisper
- Results collected and merged after all threads complete
- `source_files` array written to state

### What stays the same

- Speaker diarization (runs per-file, results merged)
- Clip selection UI (word clicking)
- Assembly timeline
- All export routes
- Narration workflow
