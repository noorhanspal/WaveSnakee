"""
Unit tests for Gesture-Controlled Snake Game (SnakeGame engine, Gesture mapping, High Score persistence).
"""
import os
import unittest

import config
from snake_game import SnakeGame


class TestSnakeGame(unittest.TestCase):
    def setUp(self):
        self.game = SnakeGame(difficulty="MEDIUM")

    def test_initial_state(self):
        self.assertEqual(len(self.game.snake), 4)
        self.assertEqual(self.game.direction, config.DIR_RIGHT)
        self.assertEqual(self.game.score, 0)
        self.assertFalse(self.game.is_game_over)

    def test_valid_and_opposite_direction_changes(self):
        # Moving RIGHT initially -> cannot reverse directly to LEFT
        self.assertFalse(self.game.change_direction(config.DIR_LEFT))
        self.assertEqual(self.game.next_direction, config.DIR_RIGHT)

        # Can turn UP or DOWN
        self.assertTrue(self.game.change_direction(config.DIR_UP))
        self.assertEqual(self.game.next_direction, config.DIR_UP)

    def test_gesture_mapping(self):
        self.assertTrue(self.game.apply_gesture(config.GESTURE_DOWN))
        self.assertEqual(self.game.next_direction, config.DIR_DOWN)

    def test_eating_food_increments_score_and_length(self):
        head_x, head_y = self.game.snake[0]
        # Place food directly in front of snake head
        self.game.food = (head_x + 1, head_y)
        initial_len = len(self.game.snake)

        # Advance enough time for exactly 1 grid step
        dt = 1.0 / self.game.base_speed + 0.001
        event = self.game.update(dt)

        self.assertEqual(event, "eat")
        self.assertEqual(len(self.game.snake), initial_len + 1)
        self.assertEqual(self.game.score, config.DIFFICULTY_LEVELS["MEDIUM"]["score_mult"])

    def test_wall_collision_triggers_game_over(self):
        # Place snake head at right edge moving right
        self.game.snake[0] = (config.GRID_COLS - 1, 5)
        self.game.direction = config.DIR_RIGHT
        self.game.next_direction = config.DIR_RIGHT

        dt = 1.0 / self.game.base_speed + 0.001
        event = self.game.update(dt)
        self.assertEqual(event, "game_over")
        self.assertTrue(self.game.is_game_over)

    def test_hand_tracker_initializes_mediapipe(self):
        from hand_tracker import HandTracker
        tracker = HandTracker(camera_index=0)
        self.assertIn(tracker.mode, ("MP_TASKS", "MP_SOLUTIONS"))
        tracker.stop()


if __name__ == "__main__":
    unittest.main()

