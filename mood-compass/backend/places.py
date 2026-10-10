import asyncio
import logging
import math
from urllib.parse import quote_plus

import httpx


logger = logging.getLogger("moodcompass.places")


# ============================================================
# CONFIGURATION
# ============================================================

SEARCH_RADIUS_METERS = 10000
MAX_RESULTS = 15
REQUEST_TIMEOUT = 40.0

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
]


# ============================================================
# ACTIVITY → OSM TAGS
# ============================================================

ACTIVITY_TAG_MAP = {
    "eat": [
        ("amenity", "restaurant"),
        ("amenity", "cafe"),
        ("amenity", "fast_food"),
        ("amenity", "food_court"),
        ("amenity", "ice_cream"),
        ("amenity", "pub"),
        ("amenity", "bar"),
        ("amenity", "biergarten"),
        ("shop", "bakery"),
        ("shop", "confectionery"),
        ("shop", "deli"),
        ("shop", "pastry"),
    ],

    "chill": [
        ("amenity", "cafe"),
        ("amenity", "ice_cream"),
        ("amenity", "library"),
        ("amenity", "restaurant"),

        ("leisure", "park"),
        ("leisure", "garden"),
        ("leisure", "common"),

        ("tourism", "viewpoint"),
        ("tourism", "attraction"),

        ("shop", "books"),
        ("shop", "music"),
    ],

    "exercise": [
        ("leisure", "fitness_centre"), 
        ("leisure", "sports_centre"),   
        ("leisure", "stadium"),         
        ("leisure", "pitch"),           
        ("leisure", "track"),           
        ("leisure", "swimming_pool"),   
        ("amenity", "swimming_pool"),
        ("leisure", "fitness_station"), 
        ("amenity", "dojo"),            
    ],

    "entertainment": [
        ("amenity", "cinema"),
        ("amenity", "theatre"),
        ("leisure", "bowling_alley"),
        ("leisure", "amusement_arcade"),
        ("leisure", "adult_gaming_centre"),
        ("tourism", "museum"),
        ("tourism", "gallery"),
        ("amenity", "arts_centre"),
        ("leisure", "miniature_golf"),
        ("amenity", "community_centre"),
    ],

    "shopping": [
        ("shop", "mall"),
        ("shop", "department_store"),
        ("shop", "clothes"),
        ("shop", "supermarket"),
        ("shop", "convenience"),
        ("shop", "jewelry"),
        ("shop", "shoes"),
        ("shop", "electronics"),
        ("shop", "furniture"),
        ("shop", "books"),
        ("shop", "music"),
        ("shop", "mobile_phone"),
        ("shop", "computer"),
    ],

    "relax": [
        ("leisure", "park"),
        ("leisure", "garden"),
        ("leisure", "nature_reserve"),
        ("leisure", "common"),
        ("natural", "wood"),
        ("natural", "beach"),
        ("natural", "water"),
        ("natural", "peak"),
        ("tourism", "viewpoint"),
        ("tourism", "picnic_site"),
        ("tourism", "attraction"),
        ("amenity", "spa"),
        ("leisure", "spa"),
        ("amenity", "library"),
    ],
}


# ============================================================
# DISTANCE
# ============================================================

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two coordinates in metres.
    """

    earth_radius = 6371000

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(delta_lambda / 2) ** 2
    )

    return 2 * earth_radius * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )


def format_distance(metres):
    if metres < 1000:
        return f"{int(metres)} m"

    return f"{metres / 1000:.1f} km"


# ============================================================
# HELPERS
# ============================================================

def extract_coordinates(element):
    """
    Get coordinates from node, way, or relation.
    """

    if element.get("lat") is not None and element.get("lon") is not None:
        return element["lat"], element["lon"]

    center = element.get("center")

    if center:
        lat = center.get("lat")
        lon = center.get("lon")

        if lat is not None and lon is not None:
            return lat, lon

    return None, None


def build_address(tags):
    parts = []

    house = tags.get("addr:housenumber")
    street = tags.get("addr:street")

    if house and street:
        parts.append(f"{house} {street}")
    elif street:
        parts.append(street)

    for key in [
        "addr:suburb",
        "addr:district",
        "addr:city",
        "addr:postcode",
    ]:
        if tags.get(key):
            parts.append(tags[key])

    return ", ".join(parts) if parts else "Address not available"


def build_maps_url(name, lat, lon):
    query = quote_plus(f"{name} {lat},{lon}")

    return (
        "https://www.google.com/maps/search/"
        f"?api=1&query={query}"
    )


# ============================================================
# OVERPASS QUERY
# ============================================================

def build_overpass_query(tags, latitude, longitude):
    """
    Build a compact Overpass query.
    """

    query_parts = []

    for key, value in tags:
        query_parts.append(
            f'nwr["{key}"="{value}"]'
            f'(around:{SEARCH_RADIUS_METERS},{latitude},{longitude});'
        )

    body = "\n".join(query_parts)

    return f"""
[out:json][timeout:60];
(
{body}
);
out center;
"""


# ============================================================
# OVERPASS REQUEST
# ============================================================

async def query_overpass(query):
    """
    Query Overpass endpoints.

    Uses GET with the query as a parameter.
    """

    timeout = httpx.Timeout(
        REQUEST_TIMEOUT,
        connect=15.0,
    )

    headers = {
        "User-Agent": "MoodCompass/1.0 (College Project)"
    }

    errors = []

    async with httpx.AsyncClient(
        timeout=timeout,
        headers=headers,
        follow_redirects=True,
    ) as client:

        for index, endpoint in enumerate(OVERPASS_ENDPOINTS):

            try:
                logger.info(
                    "Querying Overpass endpoint: %s",
                    endpoint,
                )

                response = await client.get(
                    endpoint,
                    params={"data": query},
                )

                response.raise_for_status()

                data = response.json()

                if not isinstance(data, dict):
                    raise RuntimeError(
                        "Invalid response format from Overpass"
                    )

                if "elements" not in data:
                    raise RuntimeError(
                        f"Overpass response has no elements field: "
                        f"{str(data)[:300]}"
                    )

                logger.info(
                    "Overpass returned %d elements",
                    len(data["elements"]),
                )

                return data["elements"]

            except Exception as exc:
                error_message = (
                    f"{endpoint} -> {type(exc).__name__}: {repr(exc)}"
                )

                logger.warning(error_message)

                errors.append(error_message)

                if index < len(OVERPASS_ENDPOINTS) - 1:
                    await asyncio.sleep(1)

    raise RuntimeError(
        "All Overpass API endpoints failed.\n"
        + "\n".join(errors)
    )


# ============================================================
# MAIN FUNCTION
# ============================================================

async def search_nearby_places(
    activity,
    latitude,
    longitude,
):
    """
    Search nearby places using OpenStreetMap + Overpass.
    """

    activity = str(activity).lower().strip()

    if activity not in ACTIVITY_TAG_MAP:
        logger.warning(
            "Unknown activity: %s",
            activity,
        )
        return []

    try:
        latitude = float(latitude)
        longitude = float(longitude)

    except (TypeError, ValueError):
        raise ValueError("Invalid latitude or longitude")

    if not (-90 <= latitude <= 90):
        raise ValueError("Invalid latitude")

    if not (-180 <= longitude <= 180):
        raise ValueError("Invalid longitude")

    logger.info(
        "Searching OSM for activity='%s' near (%.4f, %.4f)",
        activity,
        latitude,
        longitude,
    )

    tags = ACTIVITY_TAG_MAP[activity]

    query = build_overpass_query(
        tags,
        latitude,
        longitude,
    )

    elements = await query_overpass(query)

    places = {}

    for element in elements:

        osm_type = element.get("type")
        osm_id = element.get("id")

        if not osm_type or osm_id is None:
            continue

        unique_id = f"{osm_type}_{osm_id}"

        if unique_id in places:
            continue

        tags = element.get("tags", {})

        name = tags.get("name")

        if not name:
            continue

        place_lat, place_lon = extract_coordinates(element)

        if place_lat is None or place_lon is None:
            continue

        distance_metres = haversine_distance(
            latitude,
            longitude,
            place_lat,
            place_lon,
        )

        places[unique_id] = {
            "name": name,
            "rating": None,
            "user_ratings_total": None,
            "distance": format_distance(distance_metres),
            "distance_metres": round(distance_metres),
            "address": build_address(tags),
            "open_now": None,
            "photo": None,
            "place_id": unique_id,
            "maps_url": build_maps_url(
                name,
                place_lat,
                place_lon,
            ),
            "types": [
                value
                for key, value in tags.items()
                if key in [
                    "amenity",
                    "leisure",
                    "shop",
                    "tourism",
                ]
            ],
        }

    sorted_places = sorted(
        places.values(),
        key=lambda place: place["distance_metres"],
    )

    logger.info(
        "Found %d valid places for '%s'",
        len(sorted_places),
        activity,
    )

    return sorted_places[:MAX_RESULTS]