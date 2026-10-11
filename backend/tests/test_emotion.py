"""
Tests for MoodCompass — Emotion Detection Module (emotion.py)

All tests mock DeepFace and cv2 so they run without a GPU,
model files, or a real webcam image.
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A minimal set of bytes that looks like a valid buffer for np.frombuffer.
# The actual content doesn't matter because cv2.imdecode is mocked.
FAKE_IMAGE_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 100

# Canonical DeepFace result for "happy at 92.3 %"
DEEPFACE_HAPPY_RESULT = [
    {
        "dominant_emotion": "happy",
        "emotion": {
            "happy": 92.3,
            "sad": 1.5,
            "angry": 0.8,
            "surprise": 2.1,
            "fear": 0.6,
            "disgust": 0.4,
            "neutral": 2.3,
        },
        "region": {"x": 10, "y": 20, "w": 100, "h": 120},
    }
]

# Low-confidence result: highest emotion is only 35 %
DEEPFACE_LOW_CONFIDENCE_RESULT = [
    {
        "dominant_emotion": "neutral",
        "emotion": {
            "happy": 22.0,
            "sad": 15.0,
            "angry": 5.0,
            "surprise": 3.0,
            "fear": 2.0,
            "disgust": 18.0,
            "neutral": 35.0,
        },
        "region": {"x": 10, "y": 20, "w": 100, "h": 120},
    }
]

# Exactly-at-threshold result (50.0 %)
DEEPFACE_THRESHOLD_RESULT = [
    {
        "dominant_emotion": "sad",
        "emotion": {
            "happy": 10.0,
            "sad": 50.0,
            "angry": 5.0,
            "surprise": 5.0,
            "fear": 10.0,
            "disgust": 5.0,
            "neutral": 15.0,
        },
        "region": {"x": 10, "y": 20, "w": 100, "h": 120},
    }
]

# Two-face result (list of length 2)
DEEPFACE_TWO_FACES_RESULT = [
    {
        "dominant_emotion": "happy",
        "emotion": {
            "happy": 88.0,
            "sad": 2.0,
            "angry": 1.0,
            "surprise": 3.0,
            "fear": 1.0,
            "disgust": 1.0,
            "neutral": 4.0,
        },
        "region": {"x": 10, "y": 20, "w": 100, "h": 120},
    },
    {
        "dominant_emotion": "neutral",
        "emotion": {
            "happy": 10.0,
            "sad": 5.0,
            "angry": 5.0,
            "surprise": 5.0,
            "fear": 5.0,
            "disgust": 5.0,
            "neutral": 65.0,
        },
        "region": {"x": 200, "y": 20, "w": 90, "h": 110},
    },
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_cv2_decode_success():
    """Patch cv2.imdecode to return a valid (fake) BGR frame."""
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    with patch("emotion.cv2.imdecode", return_value=fake_frame) as m:
        yield m


@pytest.fixture
def mock_cv2_decode_failure():
    """Patch cv2.imdecode to return None (undecodable image)."""
    with patch("emotion.cv2.imdecode", return_value=None) as m:
        yield m


# ---------------------------------------------------------------------------
# Test: Successful high-confidence detection
# ---------------------------------------------------------------------------

class TestSuccessfulDetection:
    """High-confidence detection should return status='success'."""

    @patch("deepface.DeepFace.analyze", return_value=DEEPFACE_HAPPY_RESULT)
    def test_returns_status_success(self, mock_df, mock_cv2_decode_success):
        from emotion import analyze_emotion

        result = analyze_emotion(FAKE_IMAGE_BYTES)

        assert result["status"] == "success"
        assert result["emotion"] == "happy"
        assert result["confidence"] == 92.3
        assert "top_two" not in result

    @patch("deepface.DeepFace.analyze", return_value=DEEPFACE_HAPPY_RESULT)
    def test_all_emotions_present(self, mock_df, mock_cv2_decode_success):
        from emotion import analyze_emotion

        result = analyze_emotion(FAKE_IMAGE_BYTES)

        assert isinstance(result["all_emotions"], dict)
        assert len(result["all_emotions"]) == 7
        # All values should be rounded floats
        for v in result["all_emotions"].values():
            assert isinstance(v, float)

    @patch("deepface.DeepFace.analyze", return_value=DEEPFACE_HAPPY_RESULT)
    def test_required_keys_present(self, mock_df, mock_cv2_decode_success):
        from emotion import analyze_emotion

        result = analyze_emotion(FAKE_IMAGE_BYTES)

        required_keys = {"status", "emotion", "confidence", "all_emotions"}
        assert required_keys.issubset(result.keys())


# ---------------------------------------------------------------------------
# Test: Low-confidence detection
# ---------------------------------------------------------------------------

class TestLowConfidenceDetection:
    """Confidence below threshold should return status='low_confidence'."""

    @patch("deepface.DeepFace.analyze", return_value=DEEPFACE_LOW_CONFIDENCE_RESULT)
    def test_returns_status_low_confidence(self, mock_df, mock_cv2_decode_success):
        from emotion import analyze_emotion

        result = analyze_emotion(FAKE_IMAGE_BYTES)

        assert result["status"] == "low_confidence"
        assert result["emotion"] == "neutral"
        assert result["confidence"] == 35.0

    @patch("deepface.DeepFace.analyze", return_value=DEEPFACE_LOW_CONFIDENCE_RESULT)
    def test_top_two_present(self, mock_df, mock_cv2_decode_success):
        from emotion import analyze_emotion

        result = analyze_emotion(FAKE_IMAGE_BYTES)

        assert "top_two" in result
        assert len(result["top_two"]) == 2

        # top_two should be sorted by confidence descending
        assert result["top_two"][0]["confidence"] >= result["top_two"][1]["confidence"]

    @patch("deepface.DeepFace.analyze", return_value=DEEPFACE_LOW_CONFIDENCE_RESULT)
    def test_top_two_structure(self, mock_df, mock_cv2_decode_success):
        from emotion import analyze_emotion

        result = analyze_emotion(FAKE_IMAGE_BYTES)

        for item in result["top_two"]:
            assert "emotion" in item
            assert "confidence" in item
            assert isinstance(item["emotion"], str)
            assert isinstance(item["confidence"], float)


# ---------------------------------------------------------------------------
# Test: Confidence exactly at threshold (boundary)
# ---------------------------------------------------------------------------

class TestThresholdBoundary:
    """Confidence == CONFIDENCE_THRESHOLD should be 'success'."""

    @patch("deepface.DeepFace.analyze", return_value=DEEPFACE_THRESHOLD_RESULT)
    def test_exactly_at_threshold_is_success(self, mock_df, mock_cv2_decode_success):
        from emotion import analyze_emotion

        result = analyze_emotion(FAKE_IMAGE_BYTES)

        # 50.0 >= 50.0 → success
        assert result["status"] == "success"
        assert result["confidence"] == 50.0
        assert "top_two" not in result


# ---------------------------------------------------------------------------
# Test: No face detected
# ---------------------------------------------------------------------------

class TestNoFaceDetected:
    """DeepFace raising ValueError (no face) should propagate as ValueError."""

    @patch(
        "deepface.DeepFace.analyze",
        side_effect=ValueError("Face could not be detected"),
    )
    def test_raises_value_error(self, mock_df, mock_cv2_decode_success):
        from emotion import analyze_emotion

        with pytest.raises(ValueError, match="No face was detected"):
            analyze_emotion(FAKE_IMAGE_BYTES)

    @patch("deepface.DeepFace.analyze", return_value=[])
    def test_empty_list_raises(self, mock_df, mock_cv2_decode_success):
        from emotion import analyze_emotion

        with pytest.raises(ValueError, match="No face was detected"):
            analyze_emotion(FAKE_IMAGE_BYTES)


# ---------------------------------------------------------------------------
# Test: Image decode failure
# ---------------------------------------------------------------------------

class TestImageDecodeFailure:
    """cv2.imdecode returning None should raise ValueError."""

    def test_undecodable_image(self, mock_cv2_decode_failure):
        from emotion import analyze_emotion

        with pytest.raises(ValueError, match="could not be decoded"):
            analyze_emotion(FAKE_IMAGE_BYTES)


# ---------------------------------------------------------------------------
# Test: Multiple faces (uses the first one)
# ---------------------------------------------------------------------------

class TestMultipleFaces:
    """When DeepFace returns multiple faces, the first result is used."""

    @patch("deepface.DeepFace.analyze", return_value=DEEPFACE_TWO_FACES_RESULT)
    def test_uses_first_face(self, mock_df, mock_cv2_decode_success):
        from emotion import analyze_emotion

        result = analyze_emotion(FAKE_IMAGE_BYTES)

        # First face is "happy" at 88 %
        assert result["emotion"] == "happy"
        assert result["confidence"] == 88.0
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Test: Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    """Identical inputs should produce identical outputs."""

    @patch("deepface.DeepFace.analyze", return_value=DEEPFACE_HAPPY_RESULT)
    def test_same_input_same_output(self, mock_df, mock_cv2_decode_success):
        from emotion import analyze_emotion

        r1 = analyze_emotion(FAKE_IMAGE_BYTES)
        r2 = analyze_emotion(FAKE_IMAGE_BYTES)

        assert r1 == r2


# ---------------------------------------------------------------------------
# Test: CONFIDENCE_THRESHOLD is configurable
# ---------------------------------------------------------------------------

class TestThresholdConfigurable:
    """Changing CONFIDENCE_THRESHOLD should affect the status decision."""

    @patch("deepface.DeepFace.analyze", return_value=DEEPFACE_THRESHOLD_RESULT)
    def test_raising_threshold_changes_status(self, mock_df, mock_cv2_decode_success):
        import emotion
        original = emotion.CONFIDENCE_THRESHOLD

        try:
            # Raise threshold above the 50.0 confidence
            emotion.CONFIDENCE_THRESHOLD = 60.0

            result = emotion.analyze_emotion(FAKE_IMAGE_BYTES)
            assert result["status"] == "low_confidence"
            assert "top_two" in result
        finally:
            emotion.CONFIDENCE_THRESHOLD = original

    @patch("deepface.DeepFace.analyze", return_value=DEEPFACE_LOW_CONFIDENCE_RESULT)
    def test_lowering_threshold_changes_status(self, mock_df, mock_cv2_decode_success):
        import emotion
        original = emotion.CONFIDENCE_THRESHOLD

        try:
            # Lower threshold below the 35.0 confidence
            emotion.CONFIDENCE_THRESHOLD = 30.0

            result = emotion.analyze_emotion(FAKE_IMAGE_BYTES)
            assert result["status"] == "success"
            assert "top_two" not in result
        finally:
            emotion.CONFIDENCE_THRESHOLD = original
