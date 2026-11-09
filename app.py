"""
Python Web Backend for the Gesture-Controlled Snake Game.
Connects the Python Snake Game Engine (snake_game.py) and MediaPipe Hand Tracker (hand_tracker.py)
to the HTML, CSS, and Basic JavaScript Frontend (templates/index.html, static/style.css, static/script.js).
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
import threading
import time
import webbrowser

import config
from hand_tracker import HandTracker
from snake_game import SnakeGame


class BackendController:
    """
    Runs the Snake Game logic and Hand Gesture recognition in Python on a background thread
    and exposes state and actions to the HTML/CSS/JS frontend.
    """

    def __init__(self, camera_index: int = 0, headless_test: bool = False):
        self.lock = threading.Lock()
        self.game = SnakeGame(difficulty=config.DEFAULT_DIFFICULTY)
        self.tracker = HandTracker(camera_index=camera_index)
        self.headless_test = headless_test

        self.state = "START"  # START, CALIBRATE, PLAYING, PAUSED, GAME_OVER
        self.prev_state_before_calib = "START"
        self.calib_countdown = 2.5
        self.sound_queue = []
        self.running = False
        self._thread = None

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        if not self.headless_test:
            self.tracker.start()
        self._thread = threading.Thread(target=self._game_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self.tracker.stop()

    def _emit_sound(self, name: str) -> None:
        if len(self.sound_queue) < 8:
            self.sound_queue.append(name)

    def _start_game_locked(self) -> None:
        self.game.reset()
        self.state = "PLAYING"
        self._emit_sound("select")

    def _game_loop(self) -> None:
        last_time = time.perf_counter()
        while self.running:
            now = time.perf_counter()
            dt = min(now - last_time, 0.1)
            last_time = now

            t_state = self.tracker.get_state()

            with self.lock:
                # 1. Handle Hand Gestures based on current state
                if self.state == "START":
                    if self.tracker.consume_open_palm_action():
                        self._start_game_locked()

                elif self.state == "CALIBRATE":
                    if t_state.get("hand_detected", False):
                        self.calib_countdown -= dt
                        if self.calib_countdown <= 0.0:
                            self.tracker.calibrate_center()
                            self._emit_sound("select")
                            self.state = self.prev_state_before_calib
                    else:
                        self.calib_countdown = 2.5

                elif self.state == "PLAYING":
                    if self.tracker.consume_two_palms_toggle():
                        self.state = "PAUSED"
                        self._emit_sound("pause")
                    else:
                        dir_gesture = t_state.get("direction_gesture", config.GESTURE_NONE)
                        if dir_gesture in config.GESTURE_TO_DIR:
                            self.game.apply_gesture(dir_gesture)

                elif self.state == "PAUSED":
                    if self.tracker.consume_two_palms_toggle():
                        self.state = "PLAYING"
                        self._emit_sound("resume")

                elif self.state == "GAME_OVER":
                    if self.tracker.consume_open_palm_action():
                        self._start_game_locked()

                # 2. Update Snake Game Simulation
                if self.state == "PLAYING":
                    event = self.game.update(dt)
                    if event == "eat":
                        self._emit_sound("eat")
                    elif event == "bonus":
                        self._emit_sound("bonus")
                    elif event == "game_over":
                        self._emit_sound("game_over")
                        self.state = "GAME_OVER"
                elif self.state == "GAME_OVER":
                    self.game.update(dt)

            time.sleep(1.0 / config.FPS)

    def handle_action(self, action: str, value=None) -> None:
        with self.lock:
            if action == "start" or action == "restart":
                self._start_game_locked()

            elif action == "pause":
                if self.state == "PLAYING":
                    self.state = "PAUSED"
                    self._emit_sound("pause")

            elif action == "resume":
                if self.state == "PAUSED":
                    self.state = "PLAYING"
                    self._emit_sound("resume")

            elif action == "toggle_pause":
                if self.state == "PLAYING":
                    self.state = "PAUSED"
                    self._emit_sound("pause")
                elif self.state == "PAUSED":
                    self.state = "PLAYING"
                    self._emit_sound("resume")

            elif action == "space_action":
                if self.state in ("START", "GAME_OVER"):
                    self._start_game_locked()
                elif self.state == "CALIBRATE":
                    self.tracker.calibrate_center()
                    self._emit_sound("select")
                    self.state = self.prev_state_before_calib
                elif self.state == "PLAYING":
                    self.state = "PAUSED"
                    self._emit_sound("pause")
                elif self.state == "PAUSED":
                    self.state = "PLAYING"
                    self._emit_sound("resume")

            elif action == "calibrate":
                if self.state != "CALIBRATE":
                    self.prev_state_before_calib = self.state
                    self.state = "CALIBRATE"
                    self.calib_countdown = 2.5
                    self._emit_sound("select")

            elif action == "lock_calibrate":
                if self.state == "CALIBRATE":
                    self.tracker.calibrate_center()
                    self._emit_sound("select")
                    self.state = self.prev_state_before_calib

            elif action == "reset_calibrate":
                self.tracker.reset_calibration()
                self._emit_sound("select")
                if self.state == "CALIBRATE":
                    self.state = self.prev_state_before_calib

            elif action == "cancel_calibrate":
                if self.state == "CALIBRATE":
                    self.state = self.prev_state_before_calib

            elif action == "difficulty" and isinstance(value, str):
                self.game.set_difficulty(value.upper())
                self._emit_sound("select")

            elif action == "direction" and isinstance(value, str):
                if self.state == "PLAYING":
                    self.game.apply_gesture(value.upper())

    def get_state_dict(self) -> dict:
        t_state = self.tracker.get_state()
        with self.lock:
            sounds = list(self.sound_queue)
            self.sound_queue.clear()

            # Adjust particle coordinates relative to the 640x600 canvas
            canvas_particles = [
                {
                    "x": p["x"] - config.BOARD_X,
                    "y": p["y"] - config.BOARD_Y,
                    "radius": p["radius"],
                    "life": p["life"],
                    "color": list(p["color"]),
                }
                for p in self.game.particles
            ]

            return {
                "state": self.state,
                "score": self.game.score,
                "high_score": self.game.get_high_score(),
                "new_high_score": self.game.new_high_score,
                "difficulty": self.game.difficulty,
                "death_reason": self.game.death_reason,
                "snake": self.game.get_interpolated_snake(),
                "direction": list(self.game.direction),
                "food": list(self.game.food),
                "bonus_food": list(self.game.bonus_food) if self.game.bonus_food else None,
                "particles": canvas_particles,
                "calib_countdown": self.calib_countdown,
                "sound_events": sounds,
                "tracker": {
                    "gesture": t_state.get("gesture", "NONE"),
                    "direction_gesture": t_state.get("direction_gesture", "NONE"),
                    "sign_label": t_state.get("sign_label", "NONE"),
                    "hand_detected": t_state.get("hand_detected", False),
                    "is_open_palm": t_state.get("is_open_palm", False),
                    "is_two_palms": t_state.get("is_two_palms", False),
                    "hands_count": t_state.get("hands_count", 0),
                },
            }


def create_request_handler(controller: BackendController):
    class GestureSnakeHTTPHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Silence per-request console spam from 30 FPS state polling
            pass

        def do_GET(self):
            path = self.path.split("?")[0]

            if path == "/" or path == "/index.html":
                self._serve_file(os.path.join(config.BASE_DIR, "templates", "index.html"), "text/html")

            elif path.startswith("/static/"):
                rel_path = path[len("/static/"):]
                safe_path = os.path.normpath(os.path.join(config.BASE_DIR, "static", rel_path))
                if safe_path.startswith(os.path.join(config.BASE_DIR, "static")):
                    mime_type, _ = mimetypes.guess_type(safe_path)
                    self._serve_file(safe_path, mime_type or "application/octet-stream")
                else:
                    self.send_error(403)

            elif path == "/api/state":
                payload = json.dumps(controller.get_state_dict()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            elif path == "/video_feed":
                self.send_response(200)
                self.send_header("Age", "0")
                self.send_header("Cache-Control", "no-cache, private")
                self.send_header("Pragma", "no-cache")
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()
                try:
                    while controller.running:
                        jpeg_bytes = controller.tracker.get_jpeg_bytes()
                        if jpeg_bytes:
                            self.wfile.write(b"--frame\r\n")
                            self.wfile.write(b"Content-Type: image/jpeg\r\n")
                            self.wfile.write(f"Content-Length: {len(jpeg_bytes)}\r\n\r\n".encode("utf-8"))
                            self.wfile.write(jpeg_bytes)
                            self.wfile.write(b"\r\n")
                        time.sleep(0.033)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == "/api/action":
                length = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    data = json.loads(raw_body.decode("utf-8"))
                    controller.handle_action(data.get("action", ""), data.get("value"))
                except Exception:
                    pass

                resp = b'{"ok": true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            else:
                self.send_error(404)

        def _serve_file(self, file_path: str, content_type: str):
            if not os.path.exists(file_path):
                self.send_error(404)
                return
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    return GestureSnakeHTTPHandler


def run_web_app(host: str = "127.0.0.1", port: int = 5000, camera_index: int = 0, open_browser: bool = True):
    controller = BackendController(camera_index=camera_index)
    controller.start()

    handler_cls = create_request_handler(controller)
    server = ThreadingHTTPServer((host, port), handler_cls)
    url = f"http://{host}:{port}"
    print(f"\n=======================================================")
    print(f" Gesture Snake Web App is running at: {url}")
    print(f" Press Ctrl+C in the terminal to stop the server.")
    print(f"=======================================================\n")

    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server.server_close()
        controller.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Gesture Snake Web App (Python Backend + HTML/CSS/JS Frontend)")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port number (default: 5000)")
    parser.add_argument("--camera", type=int, default=0, help="Webcam device index (default: 0)")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open browser window")
    args = parser.parse_args()

    run_web_app(host=args.host, port=args.port, camera_index=args.camera, open_browser=not args.no_browser)

