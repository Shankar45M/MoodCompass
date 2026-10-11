"""
MoodCompass — Emotion Detection Module

Handles facial emotion detection using DeepFace.
Separates ML logic from API routing.

Public API:
    warm_up_model()       — Pre-load the DeepFace model (called at startup)
    analyze_emotion(bytes) — Detect emotion from raw image bytes
"""

import logging
import numpy as np
import cv2

logger = logging.getLogger("moodcompass.emotion")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Minimum confidence (0–100) for a detection to be considered reliable.
# Below this threshold the result is returned with status="low_confidence"
# and downstream consumers should treat the emotion as uncertain.
CONFIDENCE_THRESHOLD: float = 50.0

# ---------------------------------------------------------------------------
# Model warm-up
# ---------------------------------------------------------------------------

def warm_up_model() -> None:
    """
    Import DeepFace and trigger model download / compilation
    so the first real request is fast.
    """
    from deepface import DeepFace  # noqa: F811

    # Create a tiny dummy image (48×48 gray) to force model initialization
    dummy = np.zeros((48, 48, 3), dtype=np.uint8)
    try:
        DeepFace.analyze(
            dummy,
            actions=["emotion"],
            enforce_detection=False,
            silent=True,
        )
        logger.info("DeepFace model warmed up successfully")
    except Exception as exc:
        logger.warning("DeepFace warm-up produced a non-fatal error: %s", exc)


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def analyze_emotion(image_bytes: bytes) -> dict:
    """
    Detect the dominant facial emotion from raw image bytes.

    Args:
        image_bytes: JPEG / PNG / WebP image as raw bytes.

    Returns:
        dict with keys:
            status       — "success" or "low_confidence"
            emotion      — dominant emotion label (str)
            confidence   — confidence percentage (float, 0-100)
            all_emotions — full score dict for every emotion
            top_two      — (only when status is "low_confidence")
                           list of top-2 emotions

    Raises:
        ValueError: If no face is detected or the image cannot be decoded.
    """
    from deepface import DeepFace

    # --- Decode image bytes into an OpenCV BGR ndarray --------------------
    np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if frame is None:
        raise ValueError(
            "The uploaded file could not be decoded as an image. "
            "Please upload a valid JPEG, PNG, or WebP file."
        )

    # --- Run DeepFace analysis --------------------------------------------
    try:
        results = DeepFace.analyze(
            frame,
            actions=["emotion"],
            enforce_detection=True,
            silent=True,
        )
    except ValueError:
        raise ValueError(
            "No face was detected in the image. "
            "Please ensure your face is clearly visible and well-lit."
        )

    # DeepFace returns a list when multiple faces are found
    if isinstance(results, list):
        if len(results) == 0:
            raise ValueError("No face was detected in the image.")
        # Use the first (largest / most confident) face
        result = results[0]
    else:
        result = results

    # --- Extract scores ---------------------------------------------------
    all_emotions: dict[str, float] = result.get("emotion", {})
    dominant_emotion: str = result.get("dominant_emotion", "neutral")
    confidence: float = round(all_emotions.get(dominant_emotion, 0.0), 1)

    status = "success" if confidence >= CONFIDENCE_THRESHOLD else "low_confidence"

    response = {
        "status": status,
        "emotion": dominant_emotion,
        "confidence": confidence,
        "all_emotions": {k: round(v, 1) for k, v in all_emotions.items()},
    }

    # If confidence is low, surface the top 2 for the frontend
    if status == "low_confidence":
        sorted_emotions = sorted(
            all_emotions.items(), key=lambda kv: kv[1], reverse=True
        )
        response["top_two"] = [
            {"emotion": em, "confidence": round(conf, 1)}
            for em, conf in sorted_emotions[:2]
        ]

    logger.info(
        "Detected emotion: %s (%.1f%%)", dominant_emotion, confidence
    )
    return response
