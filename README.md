# Gesture-Controlled Snake Game

A classic **Snake Game** where you control the snake using **real-time hand gestures** through your webcam instead of a keyboard.
The **Frontend** is built with **HTML, CSS, and Basic Vanilla JavaScript**, and the **Backend** is built entirely in **Python**.

---

## Tech Stack

### Frontend
- **HTML5 (`templates/index.html`)** — Structure, HTML5 Canvas game board, and overlay menus
- **CSS3 (`static/style.css`)** — Modern dark neon styling and split-screen layout
- **Vanilla JavaScript (`static/script.js`)** — Fetches state from Python backend, renders the snake on Canvas, and plays sound effects

### Backend (Python)
- **Python HTTP Server (`app.py`)** — Serves the web frontend, streams live webcam video (`/video_feed`), and provides REST APIs (`/api/state`, `/api/action`)
- **MediaPipe & OpenCV (`hand_tracker.py`)** — Captures webcam video and detects 21 hand landmarks in real time
- **NumPy & Core Engine (`snake_game.py`)** — Handles snake movement, food spawning, collision detection, and high score saving

---

## Hand Gestures & Controls (Combo Sign System)

| Hand Sign / Gesture | Game Action | Keyboard Backup |
| :--- | :--- | :--- |
| **1 Finger (`☝️`) or Point Finger Up** | Turn Snake Up | `Up Arrow` / `W` |
| **2 Fingers (`✌️`) or Point Finger Down** | Turn Snake Down | `Down Arrow` / `S` |
| **3 Fingers (`🤟`) or Point Finger Left** | Turn Snake Left | `Left Arrow` / `A` |
| **4/5 Fingers (`🖐️`) or Point Finger Right** | Turn Snake Right | `Right Arrow` / `D` |
| **Show 2 Open Palms (Both Hands)** | Pause / Resume Game | `P` / `Space` |
| **Show 1 Open Palm** | Start / Restart Game | `R` / `Space` |
| **Change Speed** | Easy / Medium / Hard | `1` / `2` / `3` |

---

## Project Structure

```text
gesture_snake/
├── app.py                 # Python Web Backend (serves HTML/CSS/JS, /video_feed, and /api/state)
├── main.py                # Main launcher (starts Web App by default, or Pygame with --pygame)
├── hand_tracker.py        # Webcam and MediaPipe hand gesture detection
├── snake_game.py          # Core snake movement, food, collision, and score logic
├── config.py              # Game settings (grid size, speeds, constants)
├── templates/
│   └── index.html         # Web Frontend HTML structure
├── static/
│   ├── style.css          # Web Frontend CSS styling
│   └── script.js          # Web Frontend Basic JavaScript logic
├── test_game.py           # Unit tests for backend and game logic
├── requirements.txt       # Required Python libraries
└── README.md              # Project documentation
```

---

## How to Run the Project

1. **Activate Virtual Environment (`.venv`):**
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install Required Libraries:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Start the Web Application:**
   ```powershell
   python app.py
   ```
   *(Or run `python main.py` — it will automatically open `http://127.0.0.1:5000` in your web browser!)*
