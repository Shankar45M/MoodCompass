/**
 * MoodCompass — Main Application Script
 *
 * Orchestrates the full user flow:
 *   Landing → Camera → Emotion → Activity → Loading → Results
 *
 * Each section is managed by dedicated functions.
 * No frameworks — pure Vanilla JS with modern APIs.
 */

"use strict";

/* ==================================================================
   1. CONSTANTS
   ================================================================== */

const API_BASE = window.location.origin;

/** Maps emotion labels to emojis */
const EMOTION_EMOJI = {
    happy:    "😊",
    sad:      "😔",
    angry:    "😠",
    surprise: "😲",
    fear:     "😨",
    disgust:  "🤢",
    neutral:  "😐",
};

/** Maps emotion labels to personalized messages */
const MOOD_MESSAGES = {
    happy:    "You're glowing! Let's find something amazing for you ✨",
    sad:      "Everyone has tough moments. Let's find a place to lift your spirits 💙",
    angry:    "Let's channel that energy into something great 💪",
    surprise: "Oh! Let's turn that surprise into an adventure 🎯",
    fear:     "It's okay — let's find somewhere cozy and comforting 🤗",
    disgust:  "Time for a change of scenery — let's find your vibe 🌿",
    neutral:  "Calm and collected — the world is your oyster 🌊",
};

/** Activity display info */
const ACTIVITY_INFO = {
    eat:           { emoji: "🍔", label: "Eat",           search: "restaurants, cafes & bakeries" },
    chill:         { emoji: "☕", label: "Chill",          search: "cafes, libraries & spas" },
    relax:         { emoji: "🌳", label: "Relax",          search: "parks, gardens & attractions" },
    entertainment: { emoji: "🎬", label: "Entertainment",  search: "movies, arcades & nightlife" },
    exercise:      { emoji: "🏋️", label: "Exercise",       search: "gyms, stadiums & sports" },
    shopping:      { emoji: "🛍️", label: "Shopping",       search: "malls, stores & boutiques" },
};


/* ==================================================================
   2. STATE
   ================================================================== */

const state = {
    stream: null,           // MediaStream from webcam
    capturedBlob: null,     // Captured image as Blob
    emotion: null,          // { emotion, confidence, all_emotions, top_two? }
    activity: null,         // Selected activity key
    location: null,         // { latitude, longitude }
    places: [],             // Array of place objects from API
};


/* ==================================================================
   3. DOM REFERENCES
   ================================================================== */

const dom = {
    // Sections
    hero:       document.getElementById("hero"),
    camera:     document.getElementById("camera"),
    emotion:    document.getElementById("emotion"),
    activity:   document.getElementById("activity"),
    loading:    document.getElementById("loading"),
    results:    document.getElementById("results"),

    // Hero
    btnStart:   document.getElementById("btn-start"),

    // Camera
    video:         document.getElementById("webcam-video"),
    canvas:        document.getElementById("capture-canvas"),
    capturedImg:   document.getElementById("captured-image"),
    btnCapture:    document.getElementById("btn-capture"),
    btnRetake:     document.getElementById("btn-retake"),
    cameraScan:    document.getElementById("camera-scan"),
    shutterFlash:  document.getElementById("shutter-flash"),
    cameraStatus:  document.getElementById("camera-status"),
    cameraStatusText: document.getElementById("camera-status-text"),
    cameraError:   document.getElementById("camera-error"),
    cameraGuide:   document.querySelector(".camera__guide"),
    cameraErrorText: document.getElementById("camera-error-text"),

    // Emotion actions
    btnContinue:       document.getElementById("btn-continue"),
    btnRetakeEmotion:  document.getElementById("btn-retake-emotion"),

    // Emotion
    emotionEmoji:          document.getElementById("emotion-emoji"),
    emotionLabel:          document.getElementById("emotion-label"),
    emotionConfidenceFill: document.getElementById("emotion-confidence-fill"),
    emotionConfidenceText: document.getElementById("emotion-confidence-text"),
    emotionSecondary:      document.getElementById("emotion-secondary"),
    emotionSecondaryList:  document.getElementById("emotion-secondary-list"),
    emotionBreakdown:      document.getElementById("emotion-breakdown"),
    moodMessage:           document.getElementById("mood-message"),

    // Activity
    activityBtns: document.querySelectorAll(".activity__btn"),

    // Loading
    loadingTitle:     document.getElementById("loading-title"),
    loadingSubtitle:  document.getElementById("loading-subtitle"),
    stepLocation:     document.getElementById("step-location"),
    stepSearch:       document.getElementById("step-search"),
    stepResults:      document.getElementById("step-results"),
    loadingError:     document.getElementById("loading-error"),
    loadingErrorText: document.getElementById("loading-error-text"),
    btnRetry:         document.getElementById("btn-retry"),

    // Results
    resultsTitle:     document.getElementById("results-title"),
    resultsSubtitle:  document.getElementById("results-subtitle"),
    resultsGrid:      document.getElementById("results-grid"),
    noResults:        document.getElementById("no-results"),
    btnChangeActivity: document.getElementById("btn-change-activity"),
    btnStartOver:      document.getElementById("btn-start-over"),

    // Toast
    toastContainer: document.getElementById("toast-container"),
};


/* ==================================================================
   4. UTILITIES
   ================================================================== */

/**
 * Show a section with a fade-in, hide all others.
 * @param {HTMLElement} section - The section to show.
 */
function showSection(section) {
    const sections = [dom.hero, dom.camera, dom.emotion, dom.activity, dom.loading, dom.results];
    sections.forEach(s => {
        if (s === section) {
            s.classList.remove("hidden");
        } else {
            s.classList.add("hidden");
        }
    });

    // Smooth scroll to the section
    section.scrollIntoView({ behavior: "smooth", block: "start" });
}

/**
 * Display a toast notification.
 * @param {string} message - Toast text.
 * @param {"success"|"error"|"info"} type - Toast variant.
 * @param {number} duration - Auto-dismiss ms (default 4000).
 */
function showToast(message, type = "info", duration = 4000) {
    const toast = document.createElement("div");
    toast.className = `toast toast--${type}`;
    toast.textContent = message;
    dom.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("removing");
        toast.addEventListener("animationend", () => toast.remove());
    }, duration);
}

/**
 * Generate star rating HTML from a numeric rating.
 * @param {number} rating - Rating 0-5.
 * @returns {string} Star characters.
 */
function renderStars(rating) {
    const full  = Math.floor(rating);
    const half  = rating - full >= 0.25 ? 1 : 0;
    const empty = 5 - full - half;
    return "★".repeat(full) + (half ? "½" : "") + "☆".repeat(empty);
}

/**
 * Save a recommendation to LocalStorage history.
 */
function saveToHistory(emotion, confidence, activity, place) {
    const entry = {
        date: new Date().toISOString(),
        mood: emotion,
        confidence,
        activity,
        place: place ? place.name : null,
    };

    try {
        const history = JSON.parse(localStorage.getItem("moodcompass_history") || "[]");
        history.push(entry);
        // Keep only last 50 entries
        if (history.length > 50) history.shift();
        localStorage.setItem("moodcompass_history", JSON.stringify(history));
    } catch (e) {
        // LocalStorage might be unavailable — fail silently
    }
}


/* ==================================================================
   5. NAVIGATION / FLOW CONTROL
   ================================================================== */

/** Start → Camera */
function handleStart() {
    showSection(dom.camera);
    initCamera();
}

/** Camera captured → Analyzing → Show Emotion */
async function handleCapture() {
    // captureFrame returns a Promise<Blob> via canvas.toBlob
    const blobPromise = captureFrame();
    if (!blobPromise) return;

    const blob = await blobPromise;
    if (!blob) {
        showCameraError("Failed to capture image. Please try again.");
        return;
    }

    state.capturedBlob = blob;
    showCapturedPreview(blob);
    showScanAnimation();

    try {
        const result = await detectEmotion(blob);
        state.emotion = result;
        hideScanAnimation();
        displayEmotion(result);

        // Show emotion section — user clicks "Continue" to proceed
        showSection(dom.emotion);
    } catch (err) {
        hideScanAnimation();
        showCameraError(err.message || "Emotion detection failed. Please retake.");
    }
}

/** Activity selected → Get location → Search places → Show results */
async function handleActivitySelect(activity) {
    state.activity = activity;

    // Highlight selected button
    dom.activityBtns.forEach(btn => {
        btn.classList.toggle("selected", btn.dataset.activity === activity);
    });

    showSection(dom.loading);
    resetLoadingSteps();

    try {
        // Step 1: Get location
        updateLoadingStep("location", "active");
        const loc = await getUserLocation();
        state.location = loc;
        updateLoadingStep("location", "done");

        // Step 2: Search places
        updateLoadingStep("search", "active");
        const data = await fetchRecommendations(activity, loc.latitude, loc.longitude, state.emotion?.emotion);
        state.places = data.places || [];
        updateLoadingStep("search", "done");

        // Step 3: Prepare results
        updateLoadingStep("results", "active");

        // Save first result to history
        if (state.places.length > 0) {
            saveToHistory(
                state.emotion?.emotion,
                state.emotion?.confidence,
                activity,
                state.places[0]
            );
        }

        await new Promise(r => setTimeout(r, 500)); // Brief visual delay
        updateLoadingStep("results", "done");

        // Show results
        displayResults(activity, state.places);
        showSection(dom.results);
    } catch (err) {
        showLoadingError(err.message || "Something went wrong. Please try again.");
    }
}

/** Retake photo */
function handleRetake() {
    state.capturedBlob = null;
    state.emotion = null;
    dom.capturedImg.classList.remove("visible");
    dom.capturedImg.src = "";
    dom.btnRetake.classList.add("hidden");
    dom.btnCapture.disabled = false;
    dom.cameraError.classList.add("hidden");

    // Restart camera if stream stopped
    if (!state.stream || !state.stream.active) {
        initCamera();
    }
}

/** Change activity (back to activity selection) */
function handleChangeActivity() {
    dom.activityBtns.forEach(btn => btn.classList.remove("selected"));
    showSection(dom.activity);
}

/** Start over (back to hero) */
function handleStartOver() {
    stopCamera();
    state.capturedBlob = null;
    state.emotion = null;
    state.activity = null;
    state.location = null;
    state.places = [];
    dom.capturedImg.classList.remove("visible");
    dom.capturedImg.src = "";
    dom.resultsGrid.innerHTML = "";
    dom.activityBtns.forEach(btn => btn.classList.remove("selected"));
    showSection(dom.hero);
}


/* ==================================================================
   6. CAMERA
   ================================================================== */

/** Initialize the webcam stream */
async function initCamera() {
    dom.cameraStatus.classList.remove("hidden");
    dom.cameraStatusText.textContent = "Initializing camera…";
    dom.cameraError.classList.add("hidden");
    dom.btnCapture.disabled = true;

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: "user",
                width:  { ideal: 640 },
                height: { ideal: 480 },
            },
            audio: false,
        });

        state.stream = stream;
        dom.video.srcObject = stream;

        dom.video.addEventListener("loadedmetadata", () => {
            dom.cameraStatus.classList.add("hidden");
            dom.btnCapture.disabled = false;
        }, { once: true });

    } catch (err) {
        dom.cameraStatus.classList.add("hidden");
        let msg = "Camera access was denied.";
        if (err.name === "NotFoundError") {
            msg = "No camera found. Please connect a webcam and try again.";
        } else if (err.name === "NotAllowedError") {
            msg = "Camera permission was denied. Please allow camera access in your browser settings.";
        } else if (err.name === "NotReadableError") {
            msg = "Camera is already in use by another application.";
        }
        showCameraError(msg);
    }
}

/** Stop all camera tracks */
function stopCamera() {
    if (state.stream) {
        state.stream.getTracks().forEach(t => t.stop());
        state.stream = null;
    }
}

/** Capture the current video frame as a Blob */
function captureFrame() {
    const video = dom.video;
    const canvas = dom.canvas;

    if (!video.videoWidth || !video.videoHeight) {
        showCameraError("Camera is not ready yet. Please wait a moment.");
        return null;
    }

    canvas.width  = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");

    // Draw the frame WITHOUT mirroring.
    // The live video is mirrored via CSS for selfie feel,
    // but the captured image sent to DeepFace must be un-mirrored
    // so face detection works correctly on the raw frame.
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    return new Promise(resolve => {
        canvas.toBlob(blob => resolve(blob), "image/jpeg", 0.92);
    });
}

/**
 * Show the captured image preview overlay on the video.
 * @param {Blob} blob - The captured image blob (already resolved).
 */
function showCapturedPreview(blob) {
    // Revoke any previous object URL to prevent memory leaks
    if (dom.capturedImg.src.startsWith("blob:")) {
        URL.revokeObjectURL(dom.capturedImg.src);
    }

    const url = URL.createObjectURL(blob);
    dom.capturedImg.src = url;
    dom.capturedImg.classList.add("visible");
    dom.btnCapture.disabled = true;
    dom.btnRetake.classList.remove("hidden");

    // Shutter flash effect
    dom.shutterFlash.classList.remove("hidden");
    setTimeout(() => dom.shutterFlash.classList.add("hidden"), 350);
}

/** Show scan line animation */
function showScanAnimation() {
    dom.cameraScan.classList.remove("hidden");
}

/** Hide scan line animation */
function hideScanAnimation() {
    dom.cameraScan.classList.add("hidden");
}

/** Show camera error */
function showCameraError(msg) {
    dom.cameraErrorText.textContent = msg;
    dom.cameraError.classList.remove("hidden");
    showToast(msg, "error");
}


/* ==================================================================
   7. EMOTION DETECTION (API call)
   ================================================================== */

/**
 * Send the captured image to the backend for emotion analysis.
 * @param {Blob} blob - The image blob.
 * @returns {Promise<Object>} Emotion result object.
 */
async function detectEmotion(blob) {
    const formData = new FormData();
    formData.append("image", blob, "capture.jpg");

    const response = await fetch(`${API_BASE}/api/detect-emotion`, {
        method: "POST",
        body: formData,
    });

    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail?.message || err.message || `Server error (${response.status})`);
    }

    return response.json();
}


/* ==================================================================
   8. DISPLAY EMOTION
   ================================================================== */

function displayEmotion(result) {
    const { emotion, confidence, all_emotions, top_two } = result;

    // Apply mood-aware data attribute for CSS theming
    dom.emotion.setAttribute("data-mood", emotion);

    // Main emotion display
    dom.emotionEmoji.textContent = EMOTION_EMOJI[emotion] || "🤔";
    dom.emotionLabel.textContent = emotion;

    // Animated confidence counter (count up from 0)
    animateCounter(dom.emotionConfidenceText, confidence);

    // Reset then animate the confidence bar
    dom.emotionConfidenceFill.style.width = "0%";
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            dom.emotionConfidenceFill.style.width = `${confidence}%`;
        });
    });

    // Mood message
    dom.moodMessage.textContent = MOOD_MESSAGES[emotion] || MOOD_MESSAGES.neutral;

    // Secondary emotions (if low confidence)
    if (top_two && top_two.length > 0) {
        dom.emotionSecondary.classList.remove("hidden");
        dom.emotionSecondaryList.innerHTML = top_two
            .map(e => `
                <div class="emotion__secondary-item">
                    <span>${EMOTION_EMOJI[e.emotion] || "🤔"}</span>
                    <span>${e.emotion}</span>
                    <span>${e.confidence}%</span>
                </div>
            `).join("");
    } else {
        dom.emotionSecondary.classList.add("hidden");
    }

    // Full breakdown with staggered bars
    if (all_emotions) {
        const sorted = Object.entries(all_emotions).sort(([,a], [,b]) => b - a);
        dom.emotionBreakdown.innerHTML = sorted
            .map(([emo, score]) => `
                <div class="emotion__breakdown-row">
                    <span class="emotion__breakdown-label">${EMOTION_EMOJI[emo] || ""} ${emo}</span>
                    <div class="emotion__breakdown-bar">
                        <div class="emotion__breakdown-fill" style="width: ${score}%"></div>
                    </div>
                    <span class="emotion__breakdown-value">${score}%</span>
                </div>
            `).join("");
    }
}

/**
 * Animate a number counting up from 0 to target.
 * @param {HTMLElement} el - Element to update textContent.
 * @param {number} target - Target number (e.g. 92.3).
 */
function animateCounter(el, target) {
    const duration = 1000;
    const start = performance.now();

    function step(now) {
        const progress = Math.min((now - start) / duration, 1);
        // Ease-out quad
        const eased = 1 - (1 - progress) * (1 - progress);
        const current = (eased * target).toFixed(1);
        el.textContent = `${current}%`;
        if (progress < 1) requestAnimationFrame(step);
    }

    requestAnimationFrame(step);
}


/* ==================================================================
   9. GEOLOCATION
   ================================================================== */

/**
 * Get the user's current location via the Geolocation API.
 * @returns {Promise<{latitude: number, longitude: number}>}
 */
function getUserLocation() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject(new Error("Geolocation is not supported by your browser."));
            return;
        }

        navigator.geolocation.getCurrentPosition(
            (position) => {
                resolve({
                    latitude:  position.coords.latitude,
                    longitude: position.coords.longitude,
                });
            },
            (err) => {
                let msg = "Could not retrieve your location.";
                switch (err.code) {
                    case err.PERMISSION_DENIED:
                        msg = "Location permission was denied. Please allow location access and try again.";
                        break;
                    case err.POSITION_UNAVAILABLE:
                        msg = "Location information is unavailable. Please check your device settings.";
                        break;
                    case err.TIMEOUT:
                        msg = "Location request timed out. Please try again.";
                        break;
                }
                reject(new Error(msg));
            },
            {
                enableHighAccuracy: true,
                timeout: 15000,
                maximumAge: 300000, // 5 min cache
            }
        );
    });
}


/* ==================================================================
   10. RECOMMENDATIONS (API call)
   ================================================================== */

/**
 * Fetch place recommendations from the backend.
 */
async function fetchRecommendations(activity, latitude, longitude, emotion = "neutral") {
    const params = new URLSearchParams({
        activity,
        latitude,
        longitude,
        emotion: emotion || "neutral",
    });

    const response = await fetch(`${API_BASE}/api/recommend?${params}`);

    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail?.message || err.message || `Server error (${response.status})`);
    }

    return response.json();
}


/* ==================================================================
   11. DISPLAY RESULTS
   ================================================================== */

function displayResults(activity, places) {
    const info = ACTIVITY_INFO[activity] || {};

    dom.resultsTitle.textContent = `${info.emoji || "📍"} ${info.label || activity} Places`;
    dom.resultsSubtitle.textContent = `Found ${places.length} places near you`;

    if (places.length === 0) {
        dom.resultsGrid.classList.add("hidden");
        dom.noResults.classList.remove("hidden");
        return;
    }

    dom.resultsGrid.classList.remove("hidden");
    dom.noResults.classList.add("hidden");

    dom.resultsGrid.innerHTML = places.map((place, i) => {
        const statusClass = place.open_now === true  ? "open"
                          : place.open_now === false ? "closed"
                          : "unknown";
        const statusText  = place.open_now === true  ? "Open Now"
                          : place.open_now === false ? "Closed"
                          : "Hours N/A";

        const photoHTML = place.photo
            ? `<img class="place-card__image" src="${place.photo}" alt="${place.name}" loading="lazy" />`
            : `<div class="place-card__image-placeholder">${info.emoji || "📍"}</div>`;

        return `
            <article class="place-card" style="animation-delay: ${i * 80}ms">
                <div class="place-card__image-wrap">
                    ${photoHTML}
                    <span class="place-card__status place-card__status--${statusClass}">
                        ${statusText}
                    </span>
                </div>
                <div class="place-card__body">
                    <h3 class="place-card__name">${place.name}</h3>
                    <div class="place-card__meta">
                        <div class="place-card__rating">
                            <span class="place-card__stars">${renderStars(place.rating)}</span>
                            <span class="place-card__rating-value">${place.rating || "—"}</span>
                            ${place.user_ratings_total ? `<span class="place-card__rating-count">(${place.user_ratings_total})</span>` : ""}
                        </div>
                        <div class="place-card__distance">
                            📍 ${place.distance}
                        </div>
                    </div>
                    <p class="place-card__address">${place.address || "Address unavailable"}</p>
                    <div class="place-card__actions">
                        <a class="place-card__nav-btn"
                           href="${place.maps_url}"
                           target="_blank"
                           rel="noopener noreferrer">
                            🗺️ Open in Maps
                        </a>
                    </div>
                </div>
            </article>
        `;
    }).join("");
}


/* ==================================================================
   12. LOADING STEPS
   ================================================================== */

function resetLoadingSteps() {
    [dom.stepLocation, dom.stepSearch, dom.stepResults].forEach(el => {
        el.classList.remove("active", "done");
        el.querySelector(".loading__step-status").textContent = "⏳";
    });
    dom.loadingError.classList.add("hidden");
}

function updateLoadingStep(step, status) {
    const map = {
        location: dom.stepLocation,
        search:   dom.stepSearch,
        results:  dom.stepResults,
    };

    const el = map[step];
    if (!el) return;

    el.classList.remove("active", "done");
    el.classList.add(status);

    const statusEl = el.querySelector(".loading__step-status");
    statusEl.textContent = status === "done" ? "✅" : status === "active" ? "⏳" : "⏳";
}

function showLoadingError(msg) {
    dom.loadingErrorText.textContent = msg;
    dom.loadingError.classList.remove("hidden");
    showToast(msg, "error");
}


/* ==================================================================
   13. EVENT LISTENERS
   ================================================================== */

// Hero: Start
dom.btnStart.addEventListener("click", handleStart);

// Camera: Capture — delegates to handleCapture() for single-source logic
dom.btnCapture.addEventListener("click", handleCapture);

// Camera: Retake
dom.btnRetake.addEventListener("click", handleRetake);

// Emotion: Continue to activity selection
dom.btnContinue.addEventListener("click", () => {
    showSection(dom.activity);
});

// Emotion: Retake photo (go back to camera)
dom.btnRetakeEmotion.addEventListener("click", () => {
    handleRetake();
    showSection(dom.camera);
});

// Activity: Select
dom.activityBtns.forEach(btn => {
    btn.addEventListener("click", () => {
        handleActivitySelect(btn.dataset.activity);
    });
});

// Results: Change activity
dom.btnChangeActivity.addEventListener("click", handleChangeActivity);

// Results: Start over
dom.btnStartOver.addEventListener("click", handleStartOver);

// Loading: Retry
dom.btnRetry.addEventListener("click", () => {
    if (state.activity) {
        handleActivitySelect(state.activity);
    }
});

// Keyboard: Enter on Start button
dom.btnStart.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleStart();
});


/* ==================================================================
   14. INITIALIZATION
   ================================================================== */

// Ensure the hero section is visible on load
showSection(dom.hero);

console.log("🧭 MoodCompass initialized");
