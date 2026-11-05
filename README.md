# Gesture-Controlled Snake Game

A classic **Snake Game** built with Python where you control the snake using **real-time hand gestures** through your webcam instead of a keyboard.

---

## Tech Stack
- **Python 3.12+**
- **Pygame** — Game window, smooth movement, UI screens, and sound effects
- **MediaPipe** — Real-time hand and finger tracking (21 hand landmarks)
- **OpenCV** — Webcam video capture and hand overlay drawing
- **NumPy** — Math calculations and sound wave generation

---

## Hand Gestures & Controls

| Hand Gesture | Game Action | Keyboard Backup |
| :--- | :--- | :--- |
| **Move Hand Right** | Turn Snake Right | `Right Arrow` / `D` |
| **Move Hand Left** | Turn Snake Left | `Left Arrow` / `A` |
| **Move Hand Up** | Turn Snake Up | `Up Arrow` / `W` |
| **Move Hand Down** | Turn Snake Down | `Down Arrow` / `S` |
| **Show 2 Open Palms (Both Hands)** | Pause / Resume Game | `P` / `Space` |
| **Show 1 Open Palm** | Start / Restart Game | `R` / `Space` |
| **Hand Calibration** | Set Center Hand Position | `C` |
| **Change Speed** | Easy / Medium / Hard | `1` / `2` / `3` |

---

## Key Features
- **Real-Time Hand Tracking:** Detects your hand in a background thread so the game runs smoothly at 60 FPS without lag.
- **Smooth Snake Movement:** Smooth animation between grid cells instead of blocky jumps.
- **Score & High Score Saving:** Automatically saves your best score for each difficulty level (`Easy`, `Medium`, `Hard`) in `highscore.json`.
- **Hand Calibration Screen:** Press `C` anytime to set your comfortable hand position as the center point.
- **Built-In Sound Effects:** Retro arcade sounds generated directly with NumPy and Pygame (no external audio files needed).
- **Split-Screen UI:** Shows the game board on the left and your live webcam feed with a gesture guide on the right.

---

## Project Structure

```text
gesture_snake/
├── main.py                # Main file: starts the game and connects all parts
├── hand_tracker.py        # Webcam and MediaPipe hand gesture detection
├── snake_game.py          # Core snake movement, food, collision, and score logic
├── ui.py                  # Draws the game board, menus, and side panel
├── sound_manager.py       # Creates and plays game sound effects
├── config.py              # Game settings (screen size, colors, speeds)
├── test_game.py           # Unit tests to verify game logic
├── requirements.txt       # Required Python libraries
└── README.md              # Project documentation
```

---

## How to Run the Project

1. **Create and Activate Virtual Environment (`.venv`):**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install Required Libraries:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Start the Game:**
   ```powershell
   python main.py
   ```

4. **Run Unit Tests (Optional):**
   ```powershell
   python test_game.py -v
   ```
