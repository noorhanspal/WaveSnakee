"""
Main Entry Point for the Gesture-Controlled Snake Game.
Connects the Pygame UI, Snake Game Logic, Sound Effects, and Webcam Hand Tracker.
"""
import argparse
import os
import sys
import time

import pygame

import config
from hand_tracker import HandTracker
from snake_game import SnakeGame
from sound_manager import SoundManager
from ui import GameUI


class GestureSnakeApp:
    def __init__(self, camera_index: int = 0, headless_test: bool = False):
        if headless_test:
            os.environ["SDL_VIDEODRIVER"] = "dummy"
            os.environ["SDL_AUDIODRIVER"] = "dummy"

        pygame.init()
        pygame.display.set_caption("Gesture Snake AI - Hand Gesture Controlled Snake Game")
        self.screen = pygame.display.set_mode((config.WINDOW_WIDTH, config.WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()

        self.sound = SoundManager()
        self.game = SnakeGame(difficulty=config.DEFAULT_DIFFICULTY)
        self.tracker = HandTracker(camera_index=camera_index)
        self.ui = GameUI(self.screen)

        self.state = "START"  # START, CALIBRATE, PLAYING, PAUSED, GAME_OVER
        self.prev_state_before_calib = "START"
        self.calib_countdown = 2.5
        self.running = True
        self.headless_test = headless_test

    def run(self) -> None:
        if not self.headless_test:
            self.tracker.start()

        last_time = time.perf_counter()
        frames_run = 0

        try:
            while self.running:
                now = time.perf_counter()
                dt = min(now - last_time, 0.1)
                last_time = now

                self._handle_events()
                self._handle_gestures(dt)
                self._update_game(dt)

                cam_surface = self.tracker.get_pygame_surface()
                tracker_state = self.tracker.get_state()
                self.ui.render(
                    game=self.game,
                    cam_surface=cam_surface,
                    tracker_state=tracker_state,
                    game_state=self.state,
                    sound_enabled=self.sound.enabled,
                    calib_countdown=self.calib_countdown,
                )

                pygame.display.flip()
                self.clock.tick(config.FPS)

                if self.headless_test:
                    frames_run += 1
                    if frames_run == 2:
                        self._start_game()
                    elif frames_run == 5:
                        self.game.apply_gesture(config.GESTURE_DOWN)
                    elif frames_run >= 10:
                        self.running = False
        finally:
            self.tracker.stop()
            pygame.quit()

    def _start_game(self) -> None:
        self.game.reset()
        self.state = "PLAYING"
        self.sound.play("select")

    def _enter_calibration(self) -> None:
        if self.state != "CALIBRATE":
            self.prev_state_before_calib = self.state
            self.state = "CALIBRATE"
            self.calib_countdown = 2.5
            self.sound.play("select")

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_mouse_click(event.pos)

            if event.type == pygame.KEYDOWN:
                self._handle_keydown(event.key)

    def _handle_mouse_click(self, pos) -> None:
        # Difficulty buttons
        for diff_key, rect in self.ui.difficulty_buttons.items():
            if rect.collidepoint(pos):
                self.game.set_difficulty(diff_key)
                self.sound.play("select")
                return

        # Top bar / Overlay action buttons
        cal_rect = self.ui.action_buttons.get("CALIBRATE")
        if cal_rect and cal_rect.collidepoint(pos):
            self._enter_calibration()
            return

        mute_rect = self.ui.action_buttons.get("MUTE")
        if mute_rect and mute_rect.collidepoint(pos):
            self.sound.toggle_mute()
            return

        if self.state == "START":
            start_rect = self.ui.action_buttons.get("START")
            if start_rect and start_rect.collidepoint(pos):
                self._start_game()
        elif self.state == "GAME_OVER":
            restart_rect = self.ui.action_buttons.get("RESTART")
            if restart_rect and restart_rect.collidepoint(pos):
                self._start_game()

    def _handle_keydown(self, key: int) -> None:
        if key == pygame.K_ESCAPE:
            if self.state == "CALIBRATE":
                self.state = self.prev_state_before_calib
            else:
                self.running = False
            return

        # Difficulty shortcuts (1 = Easy, 2 = Medium, 3 = Hard)
        if key == pygame.K_1:
            self.game.set_difficulty("EASY")
            self.sound.play("select")
        elif key == pygame.K_2:
            self.game.set_difficulty("MEDIUM")
            self.sound.play("select")
        elif key == pygame.K_3:
            self.game.set_difficulty("HARD")
            self.sound.play("select")
        elif key == pygame.K_c:
            self._enter_calibration()
            return

        if self.state == "START":
            if key in (pygame.K_SPACE, pygame.K_RETURN):
                self._start_game()

        elif self.state == "CALIBRATE":
            if key in (pygame.K_SPACE, pygame.K_RETURN):
                self.tracker.calibrate_center()
                self.sound.play("select")
                self.state = self.prev_state_before_calib
            elif key == pygame.K_r:
                self.tracker.reset_calibration()
                self.sound.play("select")
                self.state = self.prev_state_before_calib

        elif self.state == "PLAYING":
            if key in (pygame.K_UP, pygame.K_w):
                self.game.change_direction(config.DIR_UP)
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.game.change_direction(config.DIR_DOWN)
            elif key in (pygame.K_LEFT, pygame.K_a):
                self.game.change_direction(config.DIR_LEFT)
            elif key in (pygame.K_RIGHT, pygame.K_d):
                self.game.change_direction(config.DIR_RIGHT)
            elif key in (pygame.K_p, pygame.K_SPACE):
                self.state = "PAUSED"
                self.sound.play("pause")
            elif key == pygame.K_r:
                self._start_game()

        elif self.state == "PAUSED":
            if key in (pygame.K_p, pygame.K_SPACE):
                self.state = "PLAYING"
                self.sound.play("resume")
            elif key == pygame.K_r:
                self._start_game()
            elif key == pygame.K_m:
                self.state = "START"

        elif self.state == "GAME_OVER":
            if key in (pygame.K_r, pygame.K_SPACE, pygame.K_RETURN):
                self._start_game()
            elif key == pygame.K_m:
                self.state = "START"

    def _handle_gestures(self, dt: float) -> None:
        t_state = self.tracker.get_state()

        if self.state == "START":
            # Open Palm starts the game
            if self.tracker.consume_open_palm_action():
                self._start_game()

        elif self.state == "CALIBRATE":
            if t_state.get("hand_detected", False):
                self.calib_countdown -= dt
                if self.calib_countdown <= 0.0:
                    self.tracker.calibrate_center()
                    self.sound.play("select")
                    self.state = self.prev_state_before_calib
            else:
                self.calib_countdown = 2.5

        elif self.state == "PLAYING":
            # 1. Check 2-Hands Open Palm Gesture for Pause
            if self.tracker.consume_two_palms_toggle():
                self.state = "PAUSED"
                self.sound.play("pause")
                return

            # 2. Apply Directional Gesture (Up / Down / Left / Right)
            dir_gesture = t_state.get("direction_gesture", config.GESTURE_NONE)
            if dir_gesture in config.GESTURE_TO_DIR:
                self.game.apply_gesture(dir_gesture)

        elif self.state == "PAUSED":
            # 2-Hands Open Palm resumes the game
            if self.tracker.consume_two_palms_toggle():
                self.state = "PLAYING"
                self.sound.play("resume")

        elif self.state == "GAME_OVER":
            # Open Palm restarts the game
            if self.tracker.consume_open_palm_action():
                self._start_game()

    def _update_game(self, dt: float) -> None:
        if self.state == "PLAYING":
            event = self.game.update(dt)
            if event == "eat":
                self.sound.play("eat")
            elif event == "bonus":
                self.sound.play("bonus")
            elif event == "game_over":
                self.sound.play("game_over")
                self.state = "GAME_OVER"
        elif self.state == "GAME_OVER":
            # Keep animating explosion particles on game over
            self.game.update(dt)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Gesture-Controlled Snake Game (Python Backend + HTML/CSS/JS Web Frontend)"
    )
    parser.add_argument("--camera", type=int, default=0, help="Webcam device index (default: 0)")
    parser.add_argument("--port", type=int, default=5000, help="Web server port (default: 5000)")
    parser.add_argument("--pygame", action="store_true", help="Run the desktop Pygame window instead of Web UI")
    parser.add_argument("--headless-test", action="store_true", help="Run a quick automated smoke test and exit")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.pygame or args.headless_test:
        app = GestureSnakeApp(camera_index=args.camera, headless_test=args.headless_test)
        app.run()
    else:
        from app import run_web_app
        run_web_app(port=args.port, camera_index=args.camera, open_browser=True)

