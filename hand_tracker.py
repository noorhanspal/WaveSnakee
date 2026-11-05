"""
Hand Tracking and Gesture Detection Module.
How it works:
  1. Reads frames from the webcam in a background thread so the game never lags.
  2. Uses MediaPipe to detect 21 landmarks (points) on up to 2 hands.
  3. Recognizes simple gestures:
     - Move 1 hand UP / DOWN / LEFT / RIGHT -> Turn the snake
     - Show 2 Open Palms (both hands) -> Pause or Resume the game
     - Show 1 Open Palm -> Start or Restart the game
"""
from collections import deque
import math
import os
import sys
import threading
import time
import types
from typing import Deque, Dict, List, Optional, Tuple

import cv2
import numpy as np
import pygame

import config

# Avoid MediaPipe unnecessarily importing full TensorFlow just for doc_controls decorator
if "tensorflow" not in sys.modules:
    tf_stub = types.ModuleType("tensorflow")
    tf_tools_stub = types.ModuleType("tensorflow.tools")
    tf_docs_stub = types.ModuleType("tensorflow.tools.docs")
    doc_controls_obj = types.SimpleNamespace(do_not_generate_docs=lambda x: x)
    tf_docs_stub.doc_controls = doc_controls_obj
    tf_tools_stub.docs = tf_docs_stub
    tf_stub.tools = tf_tools_stub
    sys.modules["tensorflow"] = tf_stub
    sys.modules["tensorflow.tools"] = tf_tools_stub
    sys.modules["tensorflow.tools.docs"] = tf_docs_stub

try:
    import mediapipe as mp
    HAS_MP_SOLUTIONS = hasattr(mp, "solutions") and hasattr(mp.solutions, "hands")
    HAS_MP_TASKS = hasattr(mp, "tasks") and hasattr(mp.tasks, "vision")
except Exception:
    mp = None
    HAS_MP_SOLUTIONS = False
    HAS_MP_TASKS = False


class HandTracker:
    """
    Captures webcam frames in a background thread, tracks up to 2 hands,
    and outputs low-latency gestures:
      - UP / DOWN / LEFT / RIGHT (instant motion delta + zone + index finger pointing)
      - TWO_PALMS (2 Open Palms -> Pause / Resume)
      - OPEN_PALM (1 Open Palm anywhere in view -> Start / Restart)
    """

    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.cap: Optional[cv2.VideoCapture] = None
        self.camera_available: bool = False

        # Calibration center (normalized 0.0 - 1.0 coordinates in mirrored webcam frame)
        self.calib_x: float = 0.5
        self.calib_y: float = 0.5
        self.neutral_radius: float = config.NEUTRAL_ZONE_RADIUS

        # Shared thread-safe state
        self._lock = threading.Lock()
        self.running: bool = False
        self._thread: Optional[threading.Thread] = None

        self.current_gesture: str = config.GESTURE_NONE
        self.direction_gesture: str = config.GESTURE_NONE
        self.is_open_palm: bool = False
        self.is_two_palms: bool = False
        self.hand_detected: bool = False
        self.hands_count: int = 0
        self.open_fingers_count: int = 0
        self.hand_pos: Tuple[float, float] = (0.5, 0.5)

        # Frame caching to avoid redundant surface conversion on main Pygame thread
        self.latest_rgb_frame: Optional[np.ndarray] = None
        self._frame_dirty: bool = False
        self._cached_surface: Optional[pygame.Surface] = None

        # Motion history ring buffer: stores (timestamp, x, y) for instant swipe/movement turns
        self._pos_history: Deque[Tuple[float, float, float]] = deque(maxlen=6)
        self._last_motion_dir: str = config.GESTURE_NONE
        self._last_motion_time: float = 0.0

        # Debounce state for 2-Hand Open Palms (Pause/Resume) and 1-Hand Open Palm (Start/Restart)
        self._last_two_palms_time: float = 0.0
        self._two_palms_latched: bool = False
        self._two_palms_hold_start: Optional[float] = None
        self._palm_start_time: Optional[float] = None
        self._palm_latched: bool = False

        # Video timestamp tracking (strictly monotonically increasing ms for VIDEO mode)
        self._start_perf = time.perf_counter()
        self._last_timestamp_ms: int = 0

        # Initialize MediaPipe detector in fast VIDEO mode
        self.mode: str = "OPENCV_FALLBACK"
        self.backend_name: str = "OpenCV Hand Tracker"
        self.hands_detector = None
        self.task_landmarker = None

        if HAS_MP_TASKS and os.path.exists(config.HAND_LANDMARKER_MODEL):
            try:
                base_options = mp.tasks.BaseOptions(model_asset_path=config.HAND_LANDMARKER_MODEL)
                options = mp.tasks.vision.HandLandmarkerOptions(
                    base_options=base_options,
                    running_mode=mp.tasks.vision.RunningMode.VIDEO,
                    num_hands=2,
                    min_hand_detection_confidence=0.45,
                    min_hand_presence_confidence=0.45,
                    min_tracking_confidence=0.45,
                )
                self.task_landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
                self.mode = "MP_TASKS"
                self.backend_name = "MediaPipe Video Tracker"
            except Exception:
                self.task_landmarker = None

        if self.mode == "OPENCV_FALLBACK" and HAS_MP_SOLUTIONS:
            try:
                self.hands_detector = mp.solutions.hands.Hands(
                    static_image_mode=False,
                    max_num_hands=2,
                    model_complexity=0,
                    min_detection_confidence=0.50,
                    min_tracking_confidence=0.45,
                )
                self.mode = "MP_SOLUTIONS"
                self.backend_name = "MediaPipe Hands"
            except Exception:
                self.hands_detector = None

    def start(self) -> bool:
        """Start the background camera capture & hand tracking thread."""
        if self.running:
            return self.camera_available

        self.running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        """Stop the background capture thread and release the webcam."""
        self.running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        if self.task_landmarker is not None:
            try:
                self.task_landmarker.close()
            except Exception:
                pass
            self.task_landmarker = None
        if self.hands_detector is not None:
            try:
                self.hands_detector.close()
            except Exception:
                pass
            self.hands_detector = None

    def calibrate_center(self) -> bool:
        """Set the current detected hand position as the neutral center zone."""
        with self._lock:
            if self.hand_detected:
                self.calib_x = float(np.clip(self.hand_pos[0], 0.22, 0.78))
                self.calib_y = float(np.clip(self.hand_pos[1], 0.22, 0.78))
                return True
            else:
                self.calib_x = 0.5
                self.calib_y = 0.5
                return False

    def reset_calibration(self) -> None:
        with self._lock:
            self.calib_x = 0.5
            self.calib_y = 0.5

    def get_state(self) -> Dict:
        """Return a snapshot of the current hand tracking state."""
        with self._lock:
            return {
                "gesture": self.current_gesture,
                "direction_gesture": self.direction_gesture,
                "is_open_palm": self.is_open_palm,
                "is_two_palms": self.is_two_palms,
                "hand_detected": self.hand_detected,
                "hands_count": self.hands_count,
                "open_fingers": self.open_fingers_count,
                "hand_pos": self.hand_pos,
                "calib_center": (self.calib_x, self.calib_y),
                "camera_available": self.camera_available,
                "backend": self.backend_name,
            }

    def consume_two_palms_toggle(self) -> bool:
        """
        Return True once when the user shows 2 Open Palms (both hands open).
        Latches until the user lowers at least one hand, with cooldown so it never flickers.
        """
        now = time.time()
        with self._lock:
            if self.is_two_palms:
                if self._two_palms_hold_start is None:
                    self._two_palms_hold_start = now
                held_long_enough = (now - self._two_palms_hold_start) >= config.TWO_PALMS_HOLD_SEC
                cooldown_ok = (now - self._last_two_palms_time) >= config.TWO_PALMS_COOLDOWN_SEC
                if held_long_enough and not self._two_palms_latched and cooldown_ok:
                    self._two_palms_latched = True
                    self._last_two_palms_time = now
                    return True
            else:
                self._two_palms_hold_start = None
                self._two_palms_latched = False
        return False

    def consume_open_palm_action(self) -> bool:
        """
        Return True when the user shows an Open Palm anywhere on screen for PALM_HOLD_SEC.
        Works regardless of whether the hand is inside or outside the center circle!
        """
        now = time.time()
        with self._lock:
            if self.is_open_palm or self.is_two_palms:
                if self._palm_start_time is None:
                    self._palm_start_time = now
                elif not self._palm_latched and (now - self._palm_start_time >= 0.35):
                    self._palm_latched = True
                    self._palm_start_time = now
                    return True
            else:
                self._palm_start_time = None
                self._palm_latched = False
        return False

    def get_pygame_surface(self) -> pygame.Surface:
        """
        Return the latest annotated webcam frame as a Pygame Surface.
        Uses dirty-flag caching so surface conversion only runs when a new camera frame arrives.
        """
        with self._lock:
            if not self._frame_dirty and self._cached_surface is not None:
                return self._cached_surface
            frame = self.latest_rgb_frame
            self._frame_dirty = False

        if frame is None:
            if self._cached_surface is None:
                surf = pygame.Surface((config.CAM_WIDTH, config.CAM_HEIGHT))
                surf.fill((18, 22, 32))
                self._cached_surface = surf
            return self._cached_surface

        self._cached_surface = pygame.surfarray.make_surface(np.transpose(frame, (1, 0, 2)))
        return self._cached_surface

    def _capture_loop(self) -> None:
        """Background thread: opens camera at low latency and processes frames continuously."""
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(self.camera_index)

        if cap.isOpened():
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap = cap
            with self._lock:
                self.camera_available = True
        else:
            with self._lock:
                self.camera_available = False

        while self.running:
            if self.cap is None or not self.camera_available:
                self._render_no_camera_frame()
                time.sleep(0.1)
                continue

            ret, bgr_frame = self.cap.read()
            if not ret or bgr_frame is None:
                time.sleep(0.01)
                continue

            small_bgr = cv2.resize(bgr_frame, (config.CAM_WIDTH, config.CAM_HEIGHT), interpolation=cv2.INTER_LINEAR)
            small_bgr = cv2.flip(small_bgr, 1)
            rgb_frame = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2RGB)

            if self.mode == "MP_TASKS" and self.task_landmarker is not None:
                self._process_mediapipe_tasks_frame(rgb_frame)
            elif self.mode == "MP_SOLUTIONS" and self.hands_detector is not None:
                self._process_mediapipe_solutions_frame(rgb_frame)
            else:
                self._process_opencv_fallback_frame(rgb_frame)

            time.sleep(0.001)

    def _process_mediapipe_tasks_frame(self, rgb_frame: np.ndarray) -> None:
        """Detect up to 2 hands using fast MediaPipe VIDEO tracking mode."""
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb_frame))
        ts_ms = int((time.perf_counter() - self._start_perf) * 1000)
        if ts_ms <= self._last_timestamp_ms:
            ts_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = ts_ms

        result = self.task_landmarker.detect_for_video(mp_image, ts_ms)
        all_hands = result.hand_landmarks if result.hand_landmarks else []
        self._evaluate_multi_hand_landmarks(rgb_frame, all_hands)

    def _process_mediapipe_solutions_frame(self, rgb_frame: np.ndarray) -> None:
        """Detect up to 2 hands using legacy MediaPipe Solutions Hands API."""
        results = self.hands_detector.process(rgb_frame)
        all_hands = [h.landmark for h in results.multi_hand_landmarks] if results.multi_hand_landmarks else []
        self._evaluate_multi_hand_landmarks(rgb_frame, all_hands)

    def _evaluate_multi_hand_landmarks(self, rgb_frame: np.ndarray, all_hands: List) -> None:
        """
        Low-latency gesture & direction evaluator:
          - `is_open_palm`: True whenever a hand has >= 4 open fingers (works anywhere on screen!)
          - `is_two_palms`: True whenever 2 hands are visible and both have >= 3 open fingers
          - `dir_gesture`: Hybrid Motion Delta + Zone + Pointing direction
        """
        annotated = rgb_frame
        h, w, _ = annotated.shape
        now = time.perf_counter()

        hands_count = len(all_hands)
        detected = hands_count > 0
        raw_gesture = config.GESTURE_NONE
        dir_gesture = config.GESTURE_NONE
        is_open_palm = False
        is_two_palms = False
        open_fingers = 0
        control_pt = self.hand_pos

        hand_finger_counts: List[int] = []
        hand_finger_states: List[List[bool]] = []
        hand_is_palm: List[bool] = []

        for hand_lm in all_hands:
            cnt, states = self._count_open_fingers(hand_lm)
            hand_finger_counts.append(cnt)
            hand_finger_states.append(states)
            # A hand is considered an Open Palm if at least 4 fingers (e.g. Index, Middle, Ring, Pinky) are open
            palm_ok = (cnt >= 4) or (sum(states[1:]) >= 4)
            hand_is_palm.append(palm_ok)
            self._draw_hand_skeleton(annotated, hand_lm, w, h)

        # 1. Check 2-Hands Open Palm (both hands visible and open)
        if hands_count >= 2 and hand_finger_counts[0] >= 3 and hand_finger_counts[1] >= 3:
            is_two_palms = True
            is_open_palm = True
            raw_gesture = config.GESTURE_TWO_PALMS
            open_fingers = hand_finger_counts[0] + hand_finger_counts[1]
            lm0, lm1 = all_hands[0], all_hands[1]
            control_pt = (
                float(np.clip(0.5 * (lm0[9].x + lm1[9].x), 0.0, 1.0)),
                float(np.clip(0.5 * (lm0[9].y + lm1[9].y), 0.0, 1.0)),
            )
            self._pos_history.clear()

        elif detected:
            lm = all_hands[0]
            open_fingers = hand_finger_counts[0]
            finger_states = hand_finger_states[0]
            is_open_palm = hand_is_palm[0]

            # Track Index Finger Tip (8) blended slightly with MCP/Palm (9)
            raw_x = 0.75 * lm[8].x + 0.25 * lm[9].x
            raw_y = 0.75 * lm[8].y + 0.25 * lm[9].y

            prev_x, prev_y = self.hand_pos
            smooth_x = float(np.clip(0.72 * raw_x + 0.28 * prev_x, 0.0, 1.0))
            smooth_y = float(np.clip(0.72 * raw_y + 0.28 * prev_y, 0.0, 1.0))
            control_pt = (smooth_x, smooth_y)

            self._pos_history.append((now, smooth_x, smooth_y))

            # A) Instant Motion / Swipe Detection
            motion_dir = self._detect_motion_direction(now, smooth_x, smooth_y)

            # B) Position relative to calibrated neutral circle
            dx = smooth_x - self.calib_x
            dy = smooth_y - self.calib_y
            dist = math.hypot(dx, dy)
            zone_dir = config.GESTURE_NONE
            if dist > self.neutral_radius:
                if abs(dx) > abs(dy):
                    zone_dir = config.GESTURE_RIGHT if dx > 0 else config.GESTURE_LEFT
                else:
                    zone_dir = config.GESTURE_DOWN if dy > 0 else config.GESTURE_UP

            # C) Index finger pointing vector (MCP 5 -> TIP 8)
            idx_dx = lm[8].x - lm[5].x
            idx_dy = lm[8].y - lm[5].y
            idx_len = math.hypot(idx_dx, idx_dy)
            point_dir = config.GESTURE_NONE
            if finger_states[1] and not finger_states[2] and not finger_states[3] and idx_len > 0.10:
                if abs(idx_dx) > abs(idx_dy):
                    point_dir = config.GESTURE_RIGHT if idx_dx > 0 else config.GESTURE_LEFT
                else:
                    point_dir = config.GESTURE_DOWN if idx_dy > 0 else config.GESTURE_UP

            if motion_dir != config.GESTURE_NONE:
                dir_gesture = motion_dir
                self._last_motion_dir = motion_dir
                self._last_motion_time = now
            elif point_dir != config.GESTURE_NONE:
                dir_gesture = point_dir
            elif (now - self._last_motion_time) < 0.22 and self._last_motion_dir != config.GESTURE_NONE:
                dir_gesture = self._last_motion_dir
            else:
                dir_gesture = zone_dir

            if dir_gesture != config.GESTURE_NONE:
                raw_gesture = dir_gesture
            elif is_open_palm:
                raw_gesture = config.GESTURE_OPEN_PALM
        else:
            self._pos_history.clear()

        self._draw_hud_overlay(
            annotated, detected, control_pt, raw_gesture, dir_gesture, hands_count, is_open_palm
        )

        with self._lock:
            self.hand_detected = detected
            self.hands_count = hands_count
            self.open_fingers_count = open_fingers
            self.is_open_palm = is_open_palm
            self.is_two_palms = is_two_palms
            self.hand_pos = control_pt
            self.current_gesture = raw_gesture
            self.direction_gesture = dir_gesture if not is_two_palms else config.GESTURE_NONE
            self.latest_rgb_frame = annotated
            self._frame_dirty = True

    def _detect_motion_direction(self, now: float, curr_x: float, curr_y: float) -> str:
        if len(self._pos_history) < 2:
            return config.GESTURE_NONE

        ref_t, ref_x, ref_y = self._pos_history[0]
        for t, px, py in self._pos_history:
            if now - t <= 0.16:
                ref_t, ref_x, ref_y = t, px, py
                break

        vx = curr_x - ref_x
        vy = curr_y - ref_y
        move_dist = math.hypot(vx, vy)

        if move_dist >= config.SWIPE_DELTA_THRESHOLD:
            if abs(vx) >= abs(vy) * 1.25:
                return config.GESTURE_RIGHT if vx > 0 else config.GESTURE_LEFT
            elif abs(vy) >= abs(vx) * 1.25:
                return config.GESTURE_DOWN if vy > 0 else config.GESTURE_UP
        return config.GESTURE_NONE

    def _count_open_fingers(self, lm) -> Tuple[int, List[bool]]:
        """
        Check which of the 5 fingers [Thumb, Index, Middle, Ring, Pinky] are extended.
        Uses relaxed wrist-to-tip vs wrist-to-PIP comparison so natural open palms
        always register 4-5 open fingers effortlessly.
        """
        wrist = lm[0]

        def dist_sq(a, b):
            return (a.x - b.x) ** 2 + (a.y - b.y) ** 2

        thumb_open = (
            dist_sq(lm[4], lm[17]) > dist_sq(lm[3], lm[17]) * 1.08
            and dist_sq(lm[4], wrist) > dist_sq(lm[2], wrist) * 1.06
        )

        finger_tips = [8, 12, 16, 20]
        finger_pips = [6, 10, 14, 18]
        finger_mcps = [5, 9, 13, 17]
        states = [thumb_open]
        for tip_idx, pip_idx, mcp_idx in zip(finger_tips, finger_pips, finger_mcps):
            tip_d = dist_sq(lm[tip_idx], wrist)
            pip_d = dist_sq(lm[pip_idx], wrist)
            mcp_d = dist_sq(lm[mcp_idx], wrist)
            is_open = (tip_d > pip_d * 1.05) and (tip_d > mcp_d * 1.15)
            states.append(is_open)

        return sum(1 for s in states if s), states

    def _draw_hand_skeleton(self, rgb_frame: np.ndarray, lm, w: int, h: int) -> None:
        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (5, 9), (9, 10), (10, 11), (11, 12),
            (9, 13), (13, 14), (14, 15), (15, 16),
            (13, 17), (17, 18), (18, 19), (19, 20), (0, 17)
        ]
        pts = [(int(p.x * w), int(p.y * h)) for p in lm]
        for i, j in connections:
            cv2.line(rgb_frame, pts[i], pts[j], (0, 210, 190), 2, cv2.LINE_AA)
        for idx, pt in enumerate(pts):
            radius = 4 if idx in (4, 8, 12, 16, 20) else 2
            color = (255, 215, 0) if idx == 8 else (88, 166, 255)
            cv2.circle(rgb_frame, pt, radius, color, -1, cv2.LINE_AA)

    def _draw_hud_overlay(
        self,
        rgb_frame: np.ndarray,
        detected: bool,
        control_pt: Tuple[float, float],
        gesture: str,
        dir_gesture: str,
        hands_count: int = 0,
        is_open_palm: bool = False,
    ) -> None:
        h, w, _ = rgb_frame.shape
        cx = int(self.calib_x * w)
        cy = int(self.calib_y * h)
        rad = int(self.neutral_radius * min(w, h))

        cv2.line(rgb_frame, (cx - rad * 2, cy - rad * 2), (cx + rad * 2, cy + rad * 2), (55, 70, 95), 1, cv2.LINE_AA)
        cv2.line(rgb_frame, (cx + rad * 2, cy - rad * 2), (cx - rad * 2, cy + rad * 2), (55, 70, 95), 1, cv2.LINE_AA)

        zone_color = (46, 213, 115) if detected else (110, 125, 145)
        cv2.circle(rgb_frame, (cx, cy), rad, zone_color, 2, cv2.LINE_AA)
        cv2.circle(rgb_frame, (cx, cy), 2, zone_color, -1, cv2.LINE_AA)

        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(rgb_frame, "UP", (cx - 12, max(15, cy - rad - 8)), font, 0.40, (180, 200, 220), 1, cv2.LINE_AA)
        cv2.putText(rgb_frame, "DOWN", (cx - 20, min(h - 8, cy + rad + 16)), font, 0.40, (180, 200, 220), 1, cv2.LINE_AA)
        cv2.putText(rgb_frame, "LEFT", (max(6, cx - rad - 40), cy + 4), font, 0.40, (180, 200, 220), 1, cv2.LINE_AA)
        cv2.putText(rgb_frame, "RIGHT", (min(w - 48, cx + rad + 8), cy + 4), font, 0.40, (180, 200, 220), 1, cv2.LINE_AA)

        if hands_count >= 2:
            cv2.putText(
                rgb_frame,
                "2 HANDS OPEN PALM",
                (10, 22),
                font,
                0.50,
                (255, 165, 2),
                2,
                cv2.LINE_AA,
            )
        elif detected and hands_count == 1:
            hx = int(control_pt[0] * w)
            hy = int(control_pt[1] * h)
            cv2.line(rgb_frame, (cx, cy), (hx, hy), (0, 245, 212), 2, cv2.LINE_AA)
            cv2.circle(rgb_frame, (hx, hy), 7, (0, 245, 212), 2, cv2.LINE_AA)
            cv2.circle(rgb_frame, (hx, hy), 3, (255, 255, 255), -1, cv2.LINE_AA)
            if is_open_palm:
                cv2.putText(
                    rgb_frame,
                    "OPEN PALM DETECTED",
                    (10, 22),
                    font,
                    0.48,
                    (46, 213, 115),
                    2,
                    cv2.LINE_AA,
                )

    def _process_opencv_fallback_frame(self, rgb_frame: np.ndarray) -> None:
        annotated = rgb_frame
        h, w, _ = annotated.shape
        ycrcb = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2YCrCb)
        mask = cv2.inRange(ycrcb, np.array([0, 133, 77], dtype=np.uint8), np.array([255, 173, 127], dtype=np.uint8))
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_contours = [c for c in contours if cv2.contourArea(c) > 1200]
        valid_contours.sort(key=cv2.contourArea, reverse=True)

        hands_count = min(len(valid_contours), 2)
        detected = hands_count > 0
        raw_gesture = config.GESTURE_NONE
        dir_gesture = config.GESTURE_NONE
        is_open_palm = False
        is_two_palms = False
        control_pt = self.hand_pos
        open_fingers = 0

        if hands_count >= 2:
            for c in valid_contours[:2]:
                cv2.drawContours(annotated, [c], -1, (255, 165, 2), 2)
            raw_gesture = config.GESTURE_TWO_PALMS
            is_two_palms = True
            is_open_palm = True
            open_fingers = 10
        elif hands_count == 1:
            largest = valid_contours[0]
            area = cv2.contourArea(largest)
            cv2.drawContours(annotated, [largest], -1, (0, 245, 212), 2)
            m = cv2.moments(largest)
            if m["m00"] != 0:
                cx = (m["m10"] / m["m00"]) / w
                cy = (m["m01"] / m["m00"]) / h
                control_pt = (float(np.clip(cx, 0.0, 1.0)), float(np.clip(cy, 0.0, 1.0)))

            hull = cv2.convexHull(largest)
            hull_area = cv2.contourArea(hull)
            solidity = area / hull_area if hull_area > 0 else 1.0

            dx = control_pt[0] - self.calib_x
            dy = control_pt[1] - self.calib_y
            dist = math.hypot(dx, dy)

            if dist > self.neutral_radius:
                if abs(dx) > abs(dy):
                    dir_gesture = config.GESTURE_RIGHT if dx > 0 else config.GESTURE_LEFT
                else:
                    dir_gesture = config.GESTURE_DOWN if dy > 0 else config.GESTURE_UP

            if solidity < 0.78:
                is_open_palm = True
                open_fingers = 5

            raw_gesture = dir_gesture if dir_gesture != config.GESTURE_NONE else (
                config.GESTURE_OPEN_PALM if is_open_palm else config.GESTURE_NONE
            )

        self._draw_hud_overlay(
            annotated, detected, control_pt, raw_gesture, dir_gesture, hands_count, is_open_palm
        )

        with self._lock:
            self.hand_detected = detected
            self.hands_count = hands_count
            self.open_fingers_count = open_fingers
            self.is_open_palm = is_open_palm
            self.is_two_palms = is_two_palms
            self.hand_pos = control_pt
            self.current_gesture = raw_gesture
            self.direction_gesture = dir_gesture if not is_two_palms else config.GESTURE_NONE
            self.latest_rgb_frame = annotated
            self._frame_dirty = True

    def _render_no_camera_frame(self) -> None:
        frame = np.zeros((config.CAM_HEIGHT, config.CAM_WIDTH, 3), dtype=np.uint8)
        frame[:] = (22, 28, 40)
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, "Webcam Not Detected", (65, 120), font, 0.65, (255, 110, 120), 2, cv2.LINE_AA)
        cv2.putText(frame, "Keyboard Controls Active:", (65, 155), font, 0.50, (200, 210, 225), 1, cv2.LINE_AA)
        cv2.putText(frame, "Arrows/WASD = Move | P = Pause | R = Restart", (20, 185), font, 0.42, (140, 160, 185), 1, cv2.LINE_AA)
        with self._lock:
            self.latest_rgb_frame = frame
            self._frame_dirty = True
