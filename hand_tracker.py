"""
Hand Tracking and Gesture Detection Module.
Uses a fast Combo Sign System (Finger Count + 1-Finger Pointing) so the snake
turns immediately without needing to keep your hand inside a center circle:
  - 1 Finger Upright (or Point 1 Finger Up)    -> UP
  - 2 Fingers (or Point 1 Finger Down)         -> DOWN
  - 3 Fingers (or Point 1 Finger Left)         -> LEFT
  - 4/5 Fingers (or Point 1 Finger Right)      -> RIGHT
  - 2 Hands Open Palm (Both Hands)             -> PAUSE / RESUME
  - 1 Hand Open Palm (on Start / Game Over)    -> START / RESTART
"""
import math
import os
import sys
import threading
import time
import types
from typing import Dict, List, Optional, Tuple

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
    and outputs instant directional gestures using Finger Count + 1-Finger Pointing.
    """

    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.cap: Optional[cv2.VideoCapture] = None
        self.camera_available: bool = False

        # Calibration center (kept for compatibility)
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
        self.sign_label: str = "NONE"
        self.hand_pos: Tuple[float, float] = (0.5, 0.5)

        # Frame caching
        self.latest_rgb_frame: Optional[np.ndarray] = None
        self._frame_dirty: bool = False
        self._cached_surface: Optional[pygame.Surface] = None

        # 2-frame stability filter to prevent 1-frame camera flicker while staying instant (~30ms)
        self._prev_raw_dir: str = config.GESTURE_NONE
        self._stable_dir: str = config.GESTURE_NONE

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
        with self._lock:
            if self.hand_detected:
                self.calib_x = float(np.clip(self.hand_pos[0], 0.22, 0.78))
                self.calib_y = float(np.clip(self.hand_pos[1], 0.22, 0.78))
                return True
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
                "sign_label": self.sign_label,
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
        Return True when the user shows an Open Palm anywhere on screen for 0.35s.
        Used to Start or Restart the game on menu screens.
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

    def get_jpeg_bytes(self) -> Optional[bytes]:
        """Return the latest annotated webcam frame encoded as JPEG bytes for the web frontend."""
        with self._lock:
            frame = self.latest_rgb_frame.copy() if self.latest_rgb_frame is not None else None

        if frame is None:
            frame = np.zeros((config.CAM_HEIGHT, config.CAM_WIDTH, 3), dtype=np.uint8)
            frame[:] = (22, 28, 40)

        bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        ok, buf = cv2.imencode(".jpg", bgr_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if not ok:
            return None
        return buf.tobytes()

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
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb_frame))
        ts_ms = int((time.perf_counter() - self._start_perf) * 1000)
        if ts_ms <= self._last_timestamp_ms:
            ts_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = ts_ms

        result = self.task_landmarker.detect_for_video(mp_image, ts_ms)
        all_hands = result.hand_landmarks if result.hand_landmarks else []
        self._evaluate_multi_hand_landmarks(rgb_frame, all_hands)

    def _process_mediapipe_solutions_frame(self, rgb_frame: np.ndarray) -> None:
        results = self.hands_detector.process(rgb_frame)
        all_hands = [h.landmark for h in results.multi_hand_landmarks] if results.multi_hand_landmarks else []
        self._evaluate_multi_hand_landmarks(rgb_frame, all_hands)

    def _evaluate_multi_hand_landmarks(self, rgb_frame: np.ndarray, all_hands: List) -> None:
        """
        Instant Combo Gesture Classifier (Finger Count + 1-Finger Pointing):
          1. 2 Hands Open Palm (both hands have >= 3 open fingers) -> TWO_PALMS (Pause / Resume)
          2. 1 Hand Detected:
             - If 1 main finger (Index) is extended:
               Checks the pointing angle from Index MCP (5) to Index Tip (8):
                 * Pointing Up    -> UP
                 * Pointing Down  -> DOWN
                 * Pointing Left  -> LEFT
                 * Pointing Right -> RIGHT
             - If 2 main fingers (Index + Middle) are extended -> DOWN
             - If 3 main fingers (Index + Middle + Ring) are extended -> LEFT
             - If 4 main fingers (All 4 fingers / Open Hand) are extended -> RIGHT
               (and also sets `is_open_palm = True` so Start/Restart works on menu screens!)
        """
        annotated = rgb_frame
        h, w, _ = annotated.shape

        hands_count = len(all_hands)
        detected = hands_count > 0
        raw_gesture = config.GESTURE_NONE
        dir_gesture = config.GESTURE_NONE
        sign_label = "NO HAND"
        is_open_palm = False
        is_two_palms = False
        open_fingers = 0
        control_pt = self.hand_pos

        hand_main_counts: List[int] = []
        hand_total_counts: List[int] = []
        hand_finger_states: List[List[bool]] = []

        for hand_lm in all_hands:
            total_cnt, main_cnt, states = self._count_open_fingers(hand_lm)
            hand_total_counts.append(total_cnt)
            hand_main_counts.append(main_cnt)
            hand_finger_states.append(states)
            self._draw_hand_skeleton(annotated, hand_lm, w, h)

        # 1. Check 2-Hands Open Palm (both hands visible and open)
        if hands_count >= 2 and hand_total_counts[0] >= 3 and hand_total_counts[1] >= 3:
            is_two_palms = True
            is_open_palm = True
            raw_gesture = config.GESTURE_TWO_PALMS
            sign_label = "2 HANDS PALM (PAUSE / RESUME)"
            open_fingers = hand_total_counts[0] + hand_total_counts[1]
            lm0, lm1 = all_hands[0], all_hands[1]
            control_pt = (
                float(np.clip(0.5 * (lm0[9].x + lm1[9].x), 0.0, 1.0)),
                float(np.clip(0.5 * (lm0[9].y + lm1[9].y), 0.0, 1.0)),
            )

        elif detected:
            lm = all_hands[0]
            open_fingers = hand_total_counts[0]
            main_fingers = hand_main_counts[0]  # Count of [Index, Middle, Ring, Pinky]
            states = hand_finger_states[0]      # [Thumb, Index, Middle, Ring, Pinky]
            control_pt = (float(np.clip(lm[8].x, 0.0, 1.0)), float(np.clip(lm[8].y, 0.0, 1.0)))

            # Check if hand is an Open Palm (4 main fingers open, or total >= 4)
            if main_fingers >= 4 or open_fingers >= 4:
                is_open_palm = True

            # COMBO SIGN LOGIC:
            if main_fingers == 1:
                # 1 Finger (usually Index) is open -> Check pointing direction (Up, Down, Left, Right)!
                # Find which single finger is open (default to Index finger 8->5)
                if states[1]:
                    tip, base = lm[8], lm[5]
                elif states[2]:
                    tip, base = lm[12], lm[9]
                elif states[4]:
                    tip, base = lm[20], lm[17]
                else:
                    tip, base = lm[8], lm[5]

                dx = tip.x - base.x
                dy = tip.y - base.y  # dy < 0 is UP, dy > 0 is DOWN

                # If pointing horizontally (Left or Right)
                if abs(dx) > abs(dy) * 0.82:
                    if dx > 0:
                        raw_dir = config.GESTURE_RIGHT
                        sign_label = "POINT RIGHT -> RIGHT"
                    else:
                        raw_dir = config.GESTURE_LEFT
                        sign_label = "POINT LEFT -> LEFT"
                else:
                    # Pointing vertically (Up or Down)
                    if dy > 0:
                        raw_dir = config.GESTURE_DOWN
                        sign_label = "POINT DOWN -> DOWN"
                    else:
                        raw_dir = config.GESTURE_UP
                        sign_label = "1 FINGER / POINT UP -> UP"

                # Draw pointing arrow from base to tip
                bx, by = int(base.x * w), int(base.y * h)
                tx, ty = int(tip.x * w), int(tip.y * h)
                cv2.arrowedLine(annotated, (bx, by), (tx, ty), (0, 245, 212), 3, cv2.LINE_AA, tipLength=0.35)

            elif main_fingers == 0 and states[0]:
                # Thumb only pointing Left / Right / Up
                dx = lm[4].x - lm[2].x
                dy = lm[4].y - lm[2].y
                if abs(dx) > abs(dy):
                    raw_dir = config.GESTURE_RIGHT if dx > 0 else config.GESTURE_LEFT
                else:
                    raw_dir = config.GESTURE_DOWN if dy > 0 else config.GESTURE_UP
                sign_label = f"THUMB POINT -> {raw_dir}"

            elif main_fingers == 2:
                # 2 Fingers (Victory / Peace Sign) -> DOWN
                raw_dir = config.GESTURE_DOWN
                sign_label = "2 FINGERS -> DOWN"

            elif main_fingers == 3:
                # 3 Fingers -> LEFT
                raw_dir = config.GESTURE_LEFT
                sign_label = "3 FINGERS -> LEFT"

            elif main_fingers >= 4:
                # 4/5 Fingers (Open Hand) -> RIGHT during gameplay (and Open Palm on Start/Game Over)
                raw_dir = config.GESTURE_RIGHT
                sign_label = "4/5 FINGERS -> RIGHT"
            else:
                raw_dir = config.GESTURE_NONE
                sign_label = "FIST / NEUTRAL"

            # 2-frame confirmation for finger-count transitions so brief mid-motion frames don't misfire
            if raw_dir == self._prev_raw_dir or raw_dir == self._stable_dir:
                self._stable_dir = raw_dir
            self._prev_raw_dir = raw_dir

            dir_gesture = self._stable_dir
            raw_gesture = dir_gesture if dir_gesture != config.GESTURE_NONE else (
                config.GESTURE_OPEN_PALM if is_open_palm else config.GESTURE_NONE
            )

        self._draw_hud_overlay(annotated, detected, sign_label, dir_gesture, hands_count)

        with self._lock:
            self.hand_detected = detected
            self.hands_count = hands_count
            self.open_fingers_count = open_fingers
            self.sign_label = sign_label
            self.is_open_palm = is_open_palm
            self.is_two_palms = is_two_palms
            self.hand_pos = control_pt
            self.current_gesture = raw_gesture
            self.direction_gesture = dir_gesture if not is_two_palms else config.GESTURE_NONE
            self.latest_rgb_frame = annotated
            self._frame_dirty = True

    def _count_open_fingers(self, lm) -> Tuple[int, int, List[bool]]:
        """
        Accurately determine which fingers [Thumb, Index, Middle, Ring, Pinky] are extended.
        Returns:
          (total_open_count, main_4_fingers_open_count, states_list)
        """
        wrist = lm[0]

        def dist(a, b):
            return math.hypot(a.x - b.x, a.y - b.y)

        # Thumb: compare tip (4) vs IP (3) distance to Pinky MCP (17)
        thumb_open = (
            dist(lm[4], lm[17]) > dist(lm[3], lm[17]) * 1.12
            and dist(lm[4], wrist) > dist(lm[2], wrist) * 1.08
        )

        # 4 Main Fingers: Index (8,6,5), Middle (12,10,9), Ring (16,14,13), Pinky (20,18,17)
        # A finger is extended if:
        #   1) Tip is farther from wrist than PIP joint, AND
        #   2) Tip-to-MCP distance is at least 1.32x PIP-to-MCP distance (straight vs curled)
        finger_triplets = [
            (8, 6, 5),
            (12, 10, 9),
            (16, 14, 13),
            (20, 18, 17),
        ]
        states = [thumb_open]
        main_count = 0
        for tip_i, pip_i, mcp_i in finger_triplets:
            tip_wrist = dist(lm[tip_i], wrist)
            pip_wrist = dist(lm[pip_i], wrist)
            tip_mcp = dist(lm[tip_i], lm[mcp_i])
            pip_mcp = max(dist(lm[pip_i], lm[mcp_i]), 1e-5)

            is_open = (tip_wrist > pip_wrist * 1.04) and (tip_mcp > pip_mcp * 1.28)
            states.append(is_open)
            if is_open:
                main_count += 1

        total_count = main_count + (1 if thumb_open else 0)
        return total_count, main_count, states

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
            radius = 5 if idx in (4, 8, 12, 16, 20) else 3
            color = (255, 215, 0) if idx in (8, 12, 16, 20) else (88, 166, 255)
            cv2.circle(rgb_frame, pt, radius, color, -1, cv2.LINE_AA)

    def _draw_hud_overlay(
        self,
        rgb_frame: np.ndarray,
        detected: bool,
        sign_label: str,
        dir_gesture: str,
        hands_count: int = 0,
    ) -> None:
        h, w, _ = rgb_frame.shape
        font = cv2.FONT_HERSHEY_SIMPLEX

        # Top status bar on webcam preview showing the detected sign & direction
        cv2.rectangle(rgb_frame, (0, 0), (w, 32), (14, 20, 30), -1)
        if hands_count >= 2:
            col = (255, 165, 2)
            txt = "SIGN: 2 HANDS PALM (PAUSE / RESUME)"
        elif detected:
            col = (0, 245, 212) if dir_gesture != config.GESTURE_NONE else (46, 213, 115)
            txt = f"SIGN: {sign_label}"
        else:
            col = (160, 175, 195)
            txt = "SHOW HAND SIGN (1=UP, 2=DOWN, 3=LEFT, 4=RIGHT)"

        cv2.putText(rgb_frame, txt, (10, 21), font, 0.44, col, 1, cv2.LINE_AA)

        # Quick bottom legend bar on webcam preview
        cv2.rectangle(rgb_frame, (0, h - 24), (w, h), (14, 20, 30), -1)
        legend = "1/PtUp:UP | 2/PtDn:DOWN | 3/PtLt:LEFT | 4/PtRt:RIGHT"
        cv2.putText(rgb_frame, legend, (8, h - 8), font, 0.36, (180, 200, 220), 1, cv2.LINE_AA)

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
        sign_label = "NO HAND"

        if hands_count >= 2:
            for c in valid_contours[:2]:
                cv2.drawContours(annotated, [c], -1, (255, 165, 2), 2)
            raw_gesture = config.GESTURE_TWO_PALMS
            is_two_palms = True
            is_open_palm = True
            open_fingers = 10
            sign_label = "2 HANDS PALM"
        elif hands_count == 1:
            largest = valid_contours[0]
            cv2.drawContours(annotated, [largest], -1, (0, 245, 212), 2)
            m = cv2.moments(largest)
            if m["m00"] != 0:
                cx = (m["m10"] / m["m00"]) / w
                cy = (m["m01"] / m["m00"]) / h
                control_pt = (float(np.clip(cx, 0.0, 1.0)), float(np.clip(cy, 0.0, 1.0)))

            dx = control_pt[0] - 0.5
            dy = control_pt[1] - 0.5
            if abs(dx) > abs(dy):
                dir_gesture = config.GESTURE_RIGHT if dx > 0 else config.GESTURE_LEFT
            else:
                dir_gesture = config.GESTURE_DOWN if dy > 0 else config.GESTURE_UP
            raw_gesture = dir_gesture
            is_open_palm = True
            sign_label = dir_gesture

        self._draw_hud_overlay(annotated, detected, sign_label, dir_gesture, hands_count)

        with self._lock:
            self.hand_detected = detected
            self.hands_count = hands_count
            self.open_fingers_count = open_fingers
            self.sign_label = sign_label
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
