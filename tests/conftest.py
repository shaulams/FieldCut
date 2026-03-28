"""Shared fixtures for FieldCut tests."""

import os
import sys
import json
import shutil
import struct
import tempfile
import subprocess
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app as flask_app


@pytest.fixture
def app(tmp_path):
    """Create a test Flask app with isolated project directory."""
    flask_app.config["TESTING"] = True

    # Redirect project directory to temp
    import app as app_module
    original_dir = app_module._active_project_dir
    test_project_dir = str(tmp_path / "projects" / "_session")
    app_module.set_project_dir(test_project_dir)

    yield flask_app

    # Restore
    app_module.set_project_dir(original_dir)


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def sample_wav(tmp_path):
    """Generate a short valid WAV file (1 second of silence) for testing."""
    wav_path = str(tmp_path / "test_audio.wav")
    # 1 second, 44100 Hz, mono, 16-bit PCM silence
    sample_rate = 44100
    duration = 1
    n_samples = sample_rate * duration
    samples = struct.pack(f"<{n_samples}h", *([0] * n_samples))

    # WAV header
    data_size = len(samples)
    with open(wav_path, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))          # chunk size
        f.write(struct.pack("<H", 1))           # PCM
        f.write(struct.pack("<H", 1))           # mono
        f.write(struct.pack("<I", sample_rate))
        f.write(struct.pack("<I", sample_rate * 2))  # byte rate
        f.write(struct.pack("<H", 2))           # block align
        f.write(struct.pack("<H", 16))          # bits per sample
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(samples)

    return wav_path


@pytest.fixture
def sample_state(tmp_path):
    """Create a pre-populated state for testing clip/assembly operations."""
    return {
        "transcript": [
            {"id": 0, "start": 0.0, "end": 2.5, "text": "Hello world", "speaker": "S1"},
            {"id": 1, "start": 2.5, "end": 5.0, "text": "How are you", "speaker": "S2"},
            {"id": 2, "start": 5.0, "end": 8.0, "text": "I am fine thanks", "speaker": "S1"},
        ],
        "words": [
            {"word": "Hello", "start": 0.0, "end": 0.5},
            {"word": "world", "start": 0.5, "end": 1.0},
            {"word": "How", "start": 2.5, "end": 2.8},
            {"word": "are", "start": 2.8, "end": 3.0},
            {"word": "you", "start": 3.0, "end": 3.5},
        ],
        "text_clips": [],
        "clips": [],
        "narration_transcript": [],
        "narration_words": [],
        "narr_text_clips": [],
        "narration": [],
        "source_file": None,
        "status": "transcribed",
        "phase": 1,
        "speaker_names": {"S1": "S1", "S2": "S2"},
    }
