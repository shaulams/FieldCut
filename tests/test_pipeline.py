"""End-to-end pipeline tests — clip marking through cutting.

These tests verify the full flow without hitting external APIs.
Transcription is simulated; ffmpeg cutting is real.
"""

import json
import os
import time
import subprocess
import pytest


def ffmpeg_available():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


@pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not installed")
class TestCutPipeline:
    """Test the clip cutting pipeline with real ffmpeg."""

    def test_mark_and_cut_single_clip(self, client, app, sample_state, sample_wav):
        """Full flow: set state → mark clip → cut → verify output."""
        import app as app_module

        sample_state["source_file"] = sample_wav
        app_module.save_state(sample_state)

        # Mark a clip
        resp = client.post("/add_clip", json={
            "start": 0.0, "end": 0.5, "text": "Hello", "source": "interview",
        })
        assert resp.status_code == 200

        # Cut clips
        resp = client.post("/cut_clips")
        assert resp.status_code == 200

        # Wait for async cutting to complete
        for _ in range(20):
            time.sleep(0.3)
            state = app_module.load_state()
            if state.get("status") in ("clips_ready", "error"):
                break

        state = app_module.load_state()
        assert state["status"] == "clips_ready", f"Expected clips_ready, got: {state['status']}"
        assert len(state["clips"]) == 1
        assert os.path.exists(state["clips"][0]["path"])

    def test_mark_and_cut_multiple_clips(self, client, app, sample_state, sample_wav):
        """Cut multiple clips and verify all output files exist."""
        import app as app_module

        sample_state["source_file"] = sample_wav
        app_module.save_state(sample_state)

        client.post("/add_clip", json={
            "start": 0.0, "end": 0.3, "text": "Part one", "source": "interview",
        })
        client.post("/add_clip", json={
            "start": 0.4, "end": 0.8, "text": "Part two", "source": "interview",
        })

        resp = client.post("/cut_clips")
        assert resp.status_code == 200

        for _ in range(20):
            time.sleep(0.3)
            state = app_module.load_state()
            if state.get("status") in ("clips_ready", "error"):
                break

        state = app_module.load_state()
        assert state["status"] == "clips_ready"
        assert len(state["clips"]) == 2
        for clip in state["clips"]:
            assert os.path.exists(clip["path"])


@pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg not installed")
class TestWaveformPipeline:
    """Test waveform extraction."""

    def test_waveform_from_wav(self, client, app, sample_wav, monkeypatch):
        import app as app_module

        # Copy wav into the project uploads dir
        import shutil
        dest = os.path.join(app_module.pdir("uploads"), "test.wav")
        shutil.copy2(sample_wav, dest)

        # Patch safe_project_path to allow our temp dir
        monkeypatch.setattr(app_module, "safe_project_path", lambda p: os.path.realpath(p))

        resp = client.get(f"/waveform?file={dest}&points=100")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "points" in data
        assert "duration" in data
        assert len(data["points"]) > 0


class TestProjectPipeline:
    """Test project save/load/delete cycle."""

    def test_full_project_lifecycle(self, client, app, sample_state):
        import app as app_module

        # Simulate having a source_file so save_project copies the session
        sample_state["source_file"] = "/tmp/fake.wav"
        app_module.save_state(sample_state)

        # Save project
        resp = client.post("/save_project", json={"name": "TestProject123"})
        assert resp.status_code == 200

        # List projects
        resp = client.get("/projects")
        names = [p["name"] for p in resp.get_json()["projects"]]
        assert "TestProject123" in names

        # Load project
        resp = client.post("/load_project", json={"name": "TestProject123"})
        assert resp.status_code == 200
        state = resp.get_json()["state"]
        assert "transcript" in state
        assert len(state["transcript"]) == 3

        # Duplicate
        resp = client.post("/duplicate_project", json={"name": "TestProject123"})
        assert resp.status_code == 200
        assert "copy" in resp.get_json()["name"]

        # Delete original
        resp = client.post("/delete_project", json={"name": "TestProject123"})
        assert resp.status_code == 200

        # Verify deleted
        resp = client.post("/load_project", json={"name": "TestProject123"})
        assert resp.status_code == 404
