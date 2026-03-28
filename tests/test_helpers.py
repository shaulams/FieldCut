"""Test helper functions — merge_segments, friendly_error, get_clip_speaker, etc."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import merge_segments, friendly_error, get_clip_speaker


class TestMergeSegments:
    """Test the segment merging logic."""

    def test_single_segment_unchanged(self):
        raw = [{"start": 0.0, "end": 2.0, "text": "Hello world"}]
        result = merge_segments(raw)
        assert len(result) == 1
        assert result[0]["text"] == "Hello world"

    def test_merge_close_segments(self):
        raw = [
            {"start": 0.0, "end": 1.0, "text": "Hello"},
            {"start": 1.1, "end": 2.0, "text": "world"},
        ]
        result = merge_segments(raw, pause_threshold=1.0)
        # Gap is 0.1s — well under threshold, should merge
        assert len(result) == 1
        assert "Hello" in result[0]["text"]
        assert "world" in result[0]["text"]

    def test_split_on_long_pause(self):
        raw = [
            {"start": 0.0, "end": 1.0, "text": "Hello."},
            {"start": 3.0, "end": 4.0, "text": "World."},
        ]
        result = merge_segments(raw, pause_threshold=1.0)
        # Gap is 2.0s — over threshold, should split
        assert len(result) == 2

    def test_split_on_sentence_end_with_gap(self):
        raw = [
            {"start": 0.0, "end": 1.0, "text": "First sentence."},
            {"start": 1.5, "end": 2.5, "text": "Second sentence."},
        ]
        result = merge_segments(raw, sentence_gap=0.4)
        # Gap 0.5s > sentence_gap 0.4s, and previous ends with period
        assert len(result) == 2

    def test_empty_input(self):
        assert merge_segments([]) == []

    def test_max_duration_split(self):
        """Segments exceeding max_duration should split at the next gap."""
        raw = [
            {"start": 0.0, "end": 30.0, "text": "Very long segment"},
            {"start": 30.2, "end": 31.0, "text": "continuation"},
            {"start": 31.3, "end": 32.0, "text": "more text"},
        ]
        result = merge_segments(raw, max_duration=25)
        # First segment is 30s > max_duration 25s, gap 0.2 >= 0.2, should split
        assert len(result) >= 2


class TestFriendlyError:
    """Test error message formatting."""

    def test_invalid_api_key(self):
        msg = friendly_error(Exception("401 Unauthorized invalid_api_key"))
        assert "API key" in msg.lower() or "Invalid" in msg

    def test_rate_limit(self):
        msg = friendly_error(Exception("429 rate_limit exceeded"))
        assert "rate limit" in msg.lower() or "quota" in msg.lower()

    def test_network_error(self):
        msg = friendly_error(Exception("Connection timed out"))
        assert "network" in msg.lower() or "connection" in msg.lower()

    def test_ffmpeg_error(self):
        msg = friendly_error(Exception("ffmpeg: command not found"))
        assert "ffmpeg" in msg.lower()

    def test_long_error_truncated(self):
        msg = friendly_error(Exception("x" * 200))
        assert len(msg) <= 120

    def test_generic_error(self):
        msg = friendly_error(Exception("something went wrong"))
        assert msg == "something went wrong"


class TestGetClipSpeaker:
    """Test speaker detection for clips."""

    def test_single_speaker(self):
        transcript = [
            {"start": 0.0, "end": 5.0, "speaker": "S1"},
        ]
        clip = {"start": 1.0, "end": 3.0}
        assert get_clip_speaker(clip, transcript) == "S1"

    def test_overlapping_speakers(self):
        transcript = [
            {"start": 0.0, "end": 2.0, "speaker": "S1"},
            {"start": 2.0, "end": 5.0, "speaker": "S2"},
        ]
        # Clip 1.0-4.0: 1s overlap with S1, 2s overlap with S2
        clip = {"start": 1.0, "end": 4.0}
        assert get_clip_speaker(clip, transcript) == "S2"

    def test_no_transcript(self):
        clip = {"start": 1.0, "end": 3.0}
        result = get_clip_speaker(clip, [])
        assert result == "S1"  # default
