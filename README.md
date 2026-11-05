# Gesture-Controlled Snake Game (CV + Pygame)

Ek classic **Snake Game** jismein aap keyboard ki jagah **Real-Time Hand Gestures** (via Webcam) se snake ko control karte hain!

## Tech Stack
- **Python 3.12+**
- **Pygame** — Smooth 60 FPS game rendering, particle effects, and procedural sound synthesis
- **MediaPipe** — 21-point 3D real-time hand landmark detection
- **OpenCV** — Low-latency background webcam capture & HUD overlay
- **NumPy** — Vector geometry & real-time audio waveform generation

---

## Hand Gestures & Controls

| Gesture | Action | Keyboard Fallback |
| :--- | :--- | :--- |
| **Hand Right** | Move Snake Right | `Right Arrow` / `D` |
| **Hand Left** | Move Snake Left | `Left Arrow` / `A` |
| **Hand Up** | Move Snake Up | `Up Arrow` / `W` |
| **Hand Down** | Move Snake Down | `Down Arrow` / `S` |
| **2 Hands Open Palm (Dono Haath)** | Pause / Resume Game | `P` / `Space` |
| **Open Palm (Khula Haath)** | Start / Restart Game | `R` / `Space` |
| **Calibration** | Set Neutral Hand Center | `C` |
| **Difficulty Speed** | Easy / Medium / Hard | `1` / `2` / `3` |

---

## Features
- **Real-Time Hand Tracking:** Threaded non-blocking webcam capture with 21 hand landmarks.
- **Smooth Snake Movement:** Sub-grid interpolation for butter-smooth 60 FPS movement.
- **Persistent High Scores:** Automatically saves high scores per difficulty (`Easy`, `Medium`, `Hard`) in `highscore.json`.
- **Hand Calibration Screen:** Press `C` anytime to calibrate your comfortable resting hand position as the center neutral zone.
- **Procedural Arcade Audio:** Built-in sound effects synthesized via NumPy (no external `.wav` files required).

---

## How to Run

1. **Create & Activate Virtual Environment (`.venv`):**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install Dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Start the Game:**
   ```powershell
   python main.py
   ```

