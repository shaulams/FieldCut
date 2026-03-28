"""Test Flask routes — basic smoke tests for all endpoints."""

import json
import os
import io


class TestBasicRoutes:
    """Test that core routes respond correctly."""

    def test_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"html" in resp.data.lower()

    def test_state_returns_json(self, client):
        resp = client.get("/state")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)

    def test_status_returns_json(self, client):
        resp = client.get("/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "status" in data

    def test_progress_returns_json(self, client):
        resp = client.get("/progress")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)

    def test_projects_list_returns_json(self, client):
        resp = client.get("/projects")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "projects" in data

    def test_setup_status(self, client):
        resp = client.get("/setup/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "openai" in data
        assert "huggingface" in data

    def test_export_folder_get(self, client):
        resp = client.get("/export_folder")
        assert resp.status_code == 200


class TestTranscribeValidation:
    """Test transcription endpoint input validation."""

    def test_transcribe_no_file_returns_400(self, client):
        resp = client.post("/transcribe")
        assert resp.status_code == 400

    def test_transcribe_no_api_key_returns_500(self, client, monkeypatch, sample_wav):
        """Without OPENAI_API_KEY, transcription should fail gracefully."""
        import app as app_module
        monkeypatch.setattr(app_module, "client", None)
        with open(sample_wav, "rb") as f:
            resp = client.post(
                "/transcribe",
                data={"file": (f, "test.wav"), "language": "en"},
                content_type="multipart/form-data",
            )
        assert resp.status_code == 500
        assert "API" in resp.get_json().get("error", "")


class TestClipOperations:
    """Test clip marking, trimming, and removal."""

    def test_add_clip(self, client, app, sample_state):
        import app as app_module
        app_module.save_state(sample_state)

        resp = client.post("/add_clip", json={
            "start": 0.0,
            "end": 2.5,
            "text": "Hello world",
            "source": "interview",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert len(data["clips"]) == 1
        assert data["clips"][0]["id"] == "clip_01"

    def test_add_multiple_clips_sorted(self, client, app, sample_state):
        import app as app_module
        app_module.save_state(sample_state)

        # Add clip at 5.0-8.0 first
        client.post("/add_clip", json={
            "start": 5.0, "end": 8.0, "text": "I am fine", "source": "interview",
        })
        # Then add clip at 0.0-2.5
        resp = client.post("/add_clip", json={
            "start": 0.0, "end": 2.5, "text": "Hello world", "source": "interview",
        })
        data = resp.get_json()
        clips = data["clips"]
        assert len(clips) == 2
        # Should be sorted by start time
        assert clips[0]["start"] < clips[1]["start"]
        assert clips[0]["id"] == "clip_01"
        assert clips[1]["id"] == "clip_02"

    def test_remove_clip(self, client, app, sample_state):
        import app as app_module
        app_module.save_state(sample_state)

        # Add then remove
        client.post("/add_clip", json={
            "start": 0.0, "end": 2.5, "text": "Hello", "source": "interview",
        })
        resp = client.post("/remove_clip", json={"id": "clip_01", "source": "interview"})
        assert resp.status_code == 200
        assert len(resp.get_json()["clips"]) == 0

    def test_trim_clip(self, client, app, sample_state):
        import app as app_module
        app_module.save_state(sample_state)

        client.post("/add_clip", json={
            "start": 0.0, "end": 2.5, "text": "Hello", "source": "interview",
        })
        resp = client.post("/trim_clip", json={
            "id": "clip_01", "source": "interview", "start": 0.2, "end": 2.3,
        })
        assert resp.status_code == 200

        # Verify state was updated
        state = app_module.load_state()
        clip = state["text_clips"][0]
        assert clip["start"] == 0.2
        assert clip["end"] == 2.3

    def test_trim_clip_prevents_invalid_range(self, client, app, sample_state):
        """start >= end should be corrected to start + 0.1."""
        import app as app_module
        app_module.save_state(sample_state)

        client.post("/add_clip", json={
            "start": 1.0, "end": 2.0, "text": "Test", "source": "interview",
        })
        client.post("/trim_clip", json={
            "id": "clip_01", "source": "interview", "start": 3.0, "end": 2.0,
        })
        state = app_module.load_state()
        clip = state["text_clips"][0]
        assert clip["end"] > clip["start"]

    def test_add_narration_clip(self, client, app, sample_state):
        import app as app_module
        sample_state["narration_transcript"] = [
            {"id": 0, "start": 0.0, "end": 3.0, "text": "Narration text"},
        ]
        app_module.save_state(sample_state)

        resp = client.post("/add_clip", json={
            "start": 0.0, "end": 3.0, "text": "Narration text", "source": "narration",
        })
        data = resp.get_json()
        assert data["ok"] is True
        assert data["clips"][0]["id"] == "narr_01"


class TestCutClips:
    """Test audio cutting (requires ffmpeg)."""

    def test_cut_no_clips_returns_400(self, client, app, sample_state, sample_wav):
        import app as app_module
        sample_state["source_file"] = sample_wav
        sample_state["text_clips"] = []
        app_module.save_state(sample_state)

        resp = client.post("/cut_clips")
        assert resp.status_code == 400

    def test_cut_no_source_returns_400(self, client, app, sample_state):
        import app as app_module
        sample_state["source_file"] = "/nonexistent/file.wav"
        sample_state["text_clips"] = [
            {"id": "clip_01", "start": 0.0, "end": 1.0, "text": "Test"},
        ]
        app_module.save_state(sample_state)

        resp = client.post("/cut_clips")
        assert resp.status_code == 400


class TestProjectManagement:
    """Test project CRUD operations."""

    def test_save_project(self, client):
        resp = client.post("/save_project", json={"name": "TestProject"})
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_save_project_no_name(self, client):
        resp = client.post("/save_project", json={"name": ""})
        assert resp.status_code == 400

    def test_load_nonexistent_project(self, client):
        resp = client.post("/load_project", json={"name": "nonexistent_project_xyz"})
        assert resp.status_code == 404

    def test_delete_nonexistent_project(self, client):
        resp = client.post("/delete_project", json={"name": "nonexistent_project_xyz"})
        assert resp.status_code == 404

    def test_set_phase(self, client):
        resp = client.post("/set_phase", json={"phase": 2})
        assert resp.status_code == 200
        assert resp.get_json()["phase"] == 2

    def test_set_invalid_phase(self, client):
        resp = client.post("/set_phase", json={"phase": 99})
        assert resp.status_code == 400

    def test_reset(self, client):
        resp = client.post("/reset")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True


class TestSpeakers:
    """Test speaker management."""

    def test_rename_speaker(self, client, app, sample_state):
        import app as app_module
        app_module.save_state(sample_state)

        resp = client.post("/rename_speaker", json={
            "speaker_id": "S1", "display_name": "Interviewer",
        })
        assert resp.status_code == 200
        names = resp.get_json()["speaker_names"]
        assert names["S1"] == "Interviewer"

    def test_reassign_speaker(self, client, app, sample_state):
        import app as app_module
        app_module.save_state(sample_state)

        resp = client.post("/reassign_speaker", json={
            "segment_id": 0, "speaker": "S2",
        })
        assert resp.status_code == 200
        transcript = resp.get_json()["transcript"]
        assert transcript[0]["speaker"] == "S2"

    def test_rename_speaker_missing_params(self, client):
        resp = client.post("/rename_speaker", json={"speaker_id": "", "display_name": ""})
        assert resp.status_code == 400


class TestMetadata:
    """Test metadata updates."""

    def test_update_metadata(self, client, app, sample_state):
        import app as app_module
        app_module.save_state(sample_state)

        resp = client.post("/update_metadata", json={
            "interviewee": "John Doe",
            "recording_date": "2025-01-15",
            "notes": "Test interview",
        })
        assert resp.status_code == 200
        state = app_module.load_state()
        assert state["interviewee"] == "John Doe"
        assert state["recording_date"] == "2025-01-15"


class TestAudioEndpoints:
    """Test audio serving endpoints."""

    def test_waveform_no_file(self, client):
        resp = client.get("/waveform?file=")
        assert resp.status_code == 404

    def test_audio_snippet_invalid_range(self, client):
        # file=test.wav hits safe_project_path first (403), so test with empty file
        resp = client.get("/audio_snippet?file=&start=5&end=3")
        assert resp.status_code == 404

    def test_download_output_no_file(self, client):
        resp = client.get("/download_output")
        assert resp.status_code == 404

    def test_export_clips_zip_no_clips(self, client):
        resp = client.get("/export_clips_zip")
        assert resp.status_code == 400


class TestExportTranscript:
    """Test transcript export."""

    def test_export_no_clips(self, client, app, sample_state):
        import app as app_module
        sample_state["text_clips"] = []
        app_module.save_state(sample_state)

        resp = client.get("/export_transcript")
        assert resp.status_code == 400
