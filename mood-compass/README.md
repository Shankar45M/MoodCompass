# 🧭 MoodCompass

**AI-Powered Mood-Aware Place Recommendation System**

MoodCompass captures a live webcam image, detects your facial emotion using Machine Learning, and recommends nearby places based on your explicitly chosen activity — using your detected mood only to personalize the experience.

---

## 🚀 Features

- **Real-time Webcam Capture** — Snap a photo directly from your browser
- **AI Emotion Detection** — Powered by DeepFace (OpenCV + deep learning)
- **Activity-Based Recommendations** — You choose what you want to do; the app finds places nearby
- **Google Maps Integration** — View places on a map and navigate with one click
- **Mood-Personalized UI** — Interface adapts to your detected emotion
- **Responsive Design** — Works across desktop, tablet, and mobile
- **Privacy-First** — No data stored on any server; images processed in-memory only

---

## 🏗️ Tech Stack

| Layer           | Technology                        |
|-----------------|-----------------------------------|
| Frontend        | HTML5, CSS3, Vanilla JavaScript   |
| Backend         | Python, FastAPI, Uvicorn          |
| ML / CV         | OpenCV, DeepFace                  |
| External APIs   | Google Places API, Google Maps JS |
| Browser APIs    | Geolocation, MediaDevices         |
| Storage         | Browser LocalStorage              |

---

## 📁 Project Structure

```
mood-compass/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── emotion.py           # DeepFace emotion detection logic
│   ├── places.py            # Google Places API integration
│   ├── requirements.txt     # Python dependencies
│   ├── .env                 # Environment variables (gitignored)
│   └── .env.example         # Template for environment variables
├── frontend/
│   ├── index.html           # Main HTML page
│   ├── style.css            # Stylesheet
│   ├── script.js            # Application logic
│   └── assets/              # Static assets (icons, images)
├── .gitignore
└── README.md
```

---

## ⚙️ Prerequisites

- **Python 3.9+**
- **pip** (Python package manager)
- **A modern web browser** (Chrome, Edge, Firefox) with webcam access
- **Google Cloud Platform account** with the following APIs enabled:
  - Places API
  - Maps JavaScript API

---

## 🛠️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/mood-compass.git
cd mood-compass
```

### 2. Create a Python virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r backend/requirements.txt
```

### 4. Configure environment variables

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and add your Google Places API key:

```
GOOGLE_PLACES_API_KEY=your_actual_api_key
```

### 5. Run the application

```bash
uvicorn backend.main:app --reload
```

Then open your browser and navigate to:

```
http://127.0.0.1:8000
```

---

## 🔑 Getting a Google Places API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Enable the **Places API** and **Maps JavaScript API**
4. Go to **APIs & Services → Credentials**
5. Click **Create Credentials → API Key**
6. Copy the key into your `backend/.env` file

---

## 🧪 Application Flow

```
Landing Page  →  Start  →  Webcam Capture  →  Emotion Detection
     →  Activity Selection  →  Location Retrieval  →  Nearby Place Results
     →  Open in Google Maps
```

1. User clicks **Start**
2. Browser requests webcam permission
3. User captures a photo
4. Backend detects emotion via DeepFace
5. User explicitly selects an activity (Eat, Chill, Relax, etc.)
6. Browser retrieves geolocation
7. Backend searches Google Places based on selected activity
8. Results displayed as cards with ratings, distance, and navigation links

---

## 🔮 Future Improvements

- Weather-aware recommendations
- Favorites / bookmarks
- Mood history analytics dashboard
- AI-generated recommendation explanations
- Voice assistant integration
- User profiles and preferences
- Multi-language support
- Mobile app (React Native / Flutter)
- Smart recommendation engine with user preference learning

---

## 📄 License

This project is for educational and portfolio purposes.

---

## 🙏 Acknowledgements

- [DeepFace](https://github.com/serengil/deepface) — Facial emotion analysis
- [FastAPI](https://fastapi.tiangolo.com/) — Modern Python web framework
- [Google Maps Platform](https://developers.google.com/maps) — Places & Maps APIs
