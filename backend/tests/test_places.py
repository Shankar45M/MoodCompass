"""
Tests for MoodCompass — Place Scoring Logic (places.py)

Tests the scoring helper functions with synthetic data.
Integration tests mock `query_overpass` to avoid live API calls.
"""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock

# Import the scoring functions under test.
# places.py lives in backend/, tests live in backend/tests/.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from places import (
    compute_proximity_score,
    compute_place_score,
    _build_explanation,
    haversine_distance,
    SEARCH_RADIUS_METERS,
    WEIGHT_ACTIVITY,
    WEIGHT_DISTANCE,
    WEIGHT_MOOD,
    search_nearby_places,
)


# ---------------------------------------------------------------------------
# Synthetic Overpass elements for integration tests
# ---------------------------------------------------------------------------

def _make_element(osm_id, name, lat, lon, amenity="restaurant"):
    """Build a minimal Overpass element dict."""
    return {
        "type": "node",
        "id": osm_id,
        "lat": lat,
        "lon": lon,
        "tags": {
            "name": name,
            "amenity": amenity,
        },
    }


# Three places at different distances from (12.9716, 77.5946) — Bangalore
SAMPLE_ELEMENTS = [
    _make_element(1, "Place Close",  12.9720, 77.5950, "restaurant"),  # ~50 m
    _make_element(2, "Place Medium", 12.9900, 77.6100, "cafe"),        # ~2.5 km
    _make_element(3, "Place Far",    13.0200, 77.6500, "fast_food"),   # ~7.5 km
]


# ===================================================================
# compute_proximity_score
# ===================================================================

class TestComputeProximityScore:
    """Proximity score: 1.0 at origin, 0.0 at or beyond the radius."""

    def test_at_origin(self):
        assert compute_proximity_score(0) == 1.0

    def test_at_radius_edge(self):
        assert compute_proximity_score(SEARCH_RADIUS_METERS) == 0.0

    def test_beyond_radius(self):
        assert compute_proximity_score(SEARCH_RADIUS_METERS + 5000) == 0.0

    def test_midpoint(self):
        score = compute_proximity_score(SEARCH_RADIUS_METERS / 2)
        assert score == 0.5

    def test_quarter_distance(self):
        score = compute_proximity_score(SEARCH_RADIUS_METERS * 0.25)
        assert score == 0.75

    def test_zero_radius_safe(self):
        """Radius of 0 should not raise, returns 0.0."""
        assert compute_proximity_score(100, radius=0) == 0.0

    def test_negative_radius_safe(self):
        assert compute_proximity_score(100, radius=-500) == 0.0

    def test_custom_radius(self):
        score = compute_proximity_score(2500, radius=5000)
        assert score == 0.5

    def test_result_is_rounded(self):
        """Scores are rounded to 4 decimal places."""
        score = compute_proximity_score(3333)
        assert isinstance(score, float)
        # 1 - 3333/10000 = 0.6667
        assert score == 0.6667


# ===================================================================
# compute_place_score
# ===================================================================

class TestComputePlaceScore:
    """Composite score with configurable weights."""

    def test_full_scores_no_mood(self):
        result = compute_place_score(1.0, 1.0, 0.0)
        expected = WEIGHT_ACTIVITY * 1.0 + WEIGHT_DISTANCE * 1.0
        assert result["total"] == round(expected, 4)  # 0.90
        assert result["mood_match"] == 0.0

    def test_zero_proximity(self):
        result = compute_place_score(1.0, 0.0, 0.0)
        assert result["total"] == round(WEIGHT_ACTIVITY, 4)  # 0.65

    def test_with_mood(self):
        result = compute_place_score(1.0, 0.5, 0.8)
        expected = (
            WEIGHT_ACTIVITY * 1.0
            + WEIGHT_DISTANCE * 0.5
            + WEIGHT_MOOD * 0.8
        )
        assert result["total"] == round(expected, 4)

    def test_all_zeros(self):
        result = compute_place_score(0.0, 0.0, 0.0)
        assert result["total"] == 0.0

    def test_breakdown_keys(self):
        result = compute_place_score(1.0, 0.5)
        required_keys = {
            "total", "activity_relevance", "proximity",
            "mood_match", "weights", "explanation",
        }
        assert required_keys == set(result.keys())

    def test_weights_in_breakdown(self):
        result = compute_place_score(1.0, 0.5)
        assert result["weights"]["activity"] == WEIGHT_ACTIVITY
        assert result["weights"]["distance"] == WEIGHT_DISTANCE
        assert result["weights"]["mood"] == WEIGHT_MOOD

    def test_weights_sum_to_one(self):
        w = compute_place_score(1.0, 0.5)["weights"]
        assert abs(w["activity"] + w["distance"] + w["mood"] - 1.0) < 1e-9

    def test_deterministic(self):
        r1 = compute_place_score(1.0, 0.73, 0.4)
        r2 = compute_place_score(1.0, 0.73, 0.4)
        assert r1 == r2


# ===================================================================
# _build_explanation
# ===================================================================

class TestBuildExplanation:
    """Human-readable explanations change based on score levels."""

    def test_very_close_no_mood(self):
        expl = _build_explanation(1.0, 0.9, 0.0)
        assert "very close" in expl
        assert "mood" not in expl

    def test_nearby(self):
        expl = _build_explanation(1.0, 0.6, 0.0)
        assert "nearby" in expl

    def test_within_search_area(self):
        expl = _build_explanation(1.0, 0.3, 0.0)
        assert "within search area" in expl

    def test_with_mood(self):
        expl = _build_explanation(1.0, 0.5, 0.7)
        assert "mood" in expl

    def test_always_includes_activity(self):
        expl = _build_explanation(1.0, 0.0, 0.0)
        assert "activity" in expl.lower()


# ===================================================================
# Integration: search_nearby_places returns scored places
# ===================================================================

class TestSearchNearbyPlacesScoring:
    """Integration tests — mock Overpass, verify scoring and sorting."""

    def _run(self, coro):
        """Helper to run an async function synchronously."""
        return asyncio.run(coro)

    @patch("places.query_overpass", new_callable=AsyncMock)
    def test_places_have_score_fields(self, mock_overpass):
        mock_overpass.return_value = SAMPLE_ELEMENTS

        places = self._run(
            search_nearby_places("eat", 12.9716, 77.5946)
        )

        assert len(places) == 3
        for place in places:
            assert "score" in place
            assert "score_breakdown" in place
            assert isinstance(place["score"], float)
            assert 0 <= place["score"] <= 1.0

    @patch("places.query_overpass", new_callable=AsyncMock)
    def test_places_sorted_by_score_descending(self, mock_overpass):
        mock_overpass.return_value = SAMPLE_ELEMENTS

        places = self._run(
            search_nearby_places("eat", 12.9716, 77.5946)
        )

        scores = [p["score"] for p in places]
        assert scores == sorted(scores, reverse=True)

    @patch("places.query_overpass", new_callable=AsyncMock)
    def test_closer_place_scores_higher(self, mock_overpass):
        mock_overpass.return_value = SAMPLE_ELEMENTS

        places = self._run(
            search_nearby_places("eat", 12.9716, 77.5946)
        )

        # Closest place should rank first (highest score)
        assert places[0]["name"] == "Place Close"
        assert places[-1]["name"] == "Place Far"

    @patch("places.query_overpass", new_callable=AsyncMock)
    def test_score_breakdown_explanation_present(self, mock_overpass):
        mock_overpass.return_value = SAMPLE_ELEMENTS

        places = self._run(
            search_nearby_places("eat", 12.9716, 77.5946)
        )

        for place in places:
            breakdown = place["score_breakdown"]
            assert "explanation" in breakdown
            assert len(breakdown["explanation"]) > 0
            assert breakdown["activity_relevance"] == 1.0
            assert breakdown["mood_match"] == 0.0  # baseline has no mood

    @patch("places.query_overpass", new_callable=AsyncMock)
    def test_empty_results(self, mock_overpass):
        mock_overpass.return_value = []

        places = self._run(
            search_nearby_places("eat", 12.9716, 77.5946)
        )

        assert places == []

    @patch("places.query_overpass", new_callable=AsyncMock)
    def test_elements_without_name_filtered(self, mock_overpass):
        mock_overpass.return_value = [
            {"type": "node", "id": 99, "lat": 12.97, "lon": 77.59, "tags": {}},
        ]

        places = self._run(
            search_nearby_places("eat", 12.9716, 77.5946)
        )

        assert places == []

    @patch("places.query_overpass", new_callable=AsyncMock)
    def test_elements_without_coords_filtered(self, mock_overpass):
        mock_overpass.return_value = [
            {"type": "node", "id": 99, "tags": {"name": "Ghost Place"}},
        ]

        places = self._run(
            search_nearby_places("eat", 12.9716, 77.5946)
        )

        assert places == []

    @patch("places.query_overpass", new_callable=AsyncMock)
    def test_duplicate_elements_deduplicated(self, mock_overpass):
        dup = _make_element(1, "Same Place", 12.972, 77.595)
        mock_overpass.return_value = [dup, dup]

        places = self._run(
            search_nearby_places("eat", 12.9716, 77.5946)
        )

        assert len(places) == 1

    def test_unknown_activity_returns_empty(self):
        places = self._run(
            search_nearby_places("skydiving", 12.9716, 77.5946)
        )
        assert places == []
