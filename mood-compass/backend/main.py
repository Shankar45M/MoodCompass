"""
MoodCompass — FastAPI Application Entry Point

Configures the application, registers API routes,
serves the frontend as static files, and manages
cross-cutting concerns (CORS, error handling, logging).
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure the backend package directory is on sys.path so sibling modules
# (emotion, places) can be imported regardless of the working directory.
_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from fastapi import FastAPI, File, Query, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from emotion import analyze_emotion, warm_up_model
from places import search_nearby_places

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger("moodcompass")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

# ---------------------------------------------------------------------------
# Application Lifespan (startup / shutdown hooks)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks before the app begins serving requests."""
    logger.info("🧭  MoodCompass is starting up …")
    logger.info("   Frontend directory: %s", FRONTEND_DIR)

    if not FRONTEND_DIR.exists():
        logger.warning("⚠  Frontend directory not found at %s", FRONTEND_DIR)

    # Pre-warm the emotion detection model so the first request isn't slow.
    try:
        warm_up_model()
        logger.info("✅  Emotion detection model loaded successfully")
    except Exception as exc:
        logger.warning("⚠  Could not pre-warm emotion model: %s", exc)

    yield  # ---- application runs here ----

    logger.info("🧭  MoodCompass is shutting down …")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="MoodCompass API",
    description=(
        "AI-powered Mood-Aware Place Recommendation System. "
        "Detects facial emotion and recommends nearby places "
        "based on the user's explicitly chosen activity."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — allow the frontend (served on the same origin or during dev)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tightened in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global Exception Handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Catch-all handler so unhandled errors return JSON, not HTML tracebacks."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please try again.",
        },
    )


# ===========================================================================
# API ROUTES
# ===========================================================================

# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["System"])
async def health_check():
    """Simple liveness probe."""
    return {"status": "ok", "service": "MoodCompass API", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# POST /api/detect-emotion
# ---------------------------------------------------------------------------

@app.post("/api/detect-emotion", tags=["Emotion"])
async def detect_emotion(image: UploadFile = File(...)):
    """
    Accept a webcam image and return the detected facial emotion.

    Returns:
        {
            "emotion": "happy",
            "confidence": 92.3,
            "all_emotions": { ... }   // full score breakdown
        }

    If confidence < 50 %, the top-2 emotions are highlighted.
    """

    # --- Validate file type ---------------------------------------------------
    if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_file_type",
                "message": (
                    f"Expected image/jpeg, image/png, or image/webp — "
                    f"got '{image.content_type}'."
                ),
            },
        )

    # --- Read image bytes -----------------------------------------------------
    try:
        image_bytes = await image.read()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unreadable_image",
                "message": "Could not read the uploaded image.",
            },
        )

    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "empty_image",
                "message": "The uploaded image is empty.",
            },
        )

    # --- Run emotion analysis -------------------------------------------------
    try:
        result = analyze_emotion(image_bytes)
    except ValueError as ve:
        # Domain errors raised by emotion.py (no face, multiple faces, etc.)
        raise HTTPException(
            status_code=422,
            detail={
                "error": "emotion_detection_failed",
                "message": str(ve),
            },
        )
    except Exception as exc:
        logger.exception("Emotion analysis failed")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "emotion_analysis_error",
                "message": "Emotion analysis encountered an internal error.",
            },
        )

    return result


# ---------------------------------------------------------------------------
# GET /api/recommend
# ---------------------------------------------------------------------------

VALID_ACTIVITIES = {"eat", "chill", "relax", "entertainment", "exercise", "shopping"}

@app.get("/api/recommend", tags=["Recommendations"])
async def recommend_places(
    activity: str = Query(
        ...,
        description="User-chosen activity category",
        examples=["eat", "chill", "relax"],
    ),
    latitude: float = Query(..., ge=-90, le=90, description="User latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="User longitude"),
    emotion: str = Query(
        default="neutral",
        description="Detected emotion (for future personalization)",
    ),
):
    """
    Return nearby place recommendations for the chosen activity.

    The **activity** determines the OpenStreetMap tags to search.
    The **emotion** is stored for analytics / personalization but does NOT
    alter the search category.
    """

    # --- Validate activity ----------------------------------------------------
    activity_lower = activity.strip().lower()
    if activity_lower not in VALID_ACTIVITIES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_activity",
                "message": (
                    f"'{activity}' is not a valid activity. "
                    f"Choose from: {', '.join(sorted(VALID_ACTIVITIES))}."
                ),
            },
        )

    # --- Search places --------------------------------------------------------
    try:
        places = await search_nearby_places(
            activity=activity_lower,
            latitude=latitude,
            longitude=longitude,
        )
    except Exception as exc:
        logger.exception("Place search failed for activity=%s", activity_lower)
        raise HTTPException(
            status_code=502,
            detail={
                "error": "places_search_failed",
                "message": "Could not retrieve nearby places. Please try again.",
            },
        )

    return {
        "activity": activity_lower,
        "emotion": emotion,
        "count": len(places),
        "places": places,
    }


# ===========================================================================
# STATIC FILES — Serve the frontend
# ===========================================================================
# Mounted LAST so API routes take priority over the catch-all static handler.

if FRONTEND_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend",
    )
else:
    logger.warning(
        "Frontend directory '%s' does not exist. "
        "Static file serving is disabled.",
        FRONTEND_DIR,
    )
