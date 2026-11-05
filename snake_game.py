"""
Core Snake Game Logic:
  - Controls snake movement and smooth animation between grid cells
  - Spawns regular red apples and bonus golden apples
  - Checks wall collisions and self collisions
  - Loads and saves high scores in highscore.json
"""
import json
import math
import os
import random
import time
from typing import Dict, List, Optional, Tuple

import config


class SnakeGame:
    def __init__(self, difficulty: str = config.DEFAULT_DIFFICULTY):
        self.difficulty = difficulty if difficulty in config.DIFFICULTY_LEVELS else config.DEFAULT_DIFFICULTY
        self.high_scores = self._load_high_scores()
        self.reset()

    def _load_high_scores(self) -> Dict[str, int]:
        default_scores = {"EASY": 0, "MEDIUM": 0, "HARD": 0}
        if os.path.exists(config.HIGHSCORE_FILE):
            try:
                with open(config.HIGHSCORE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    for k in default_scores:
                        if k in data and isinstance(data[k], int):
                            default_scores[k] = data[k]
            except Exception:
                pass
        return default_scores

    def save_high_scores(self) -> None:
        try:
            with open(config.HIGHSCORE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.high_scores, f, indent=2)
        except Exception:
            pass

    def set_difficulty(self, difficulty: str) -> None:
        if difficulty in config.DIFFICULTY_LEVELS:
            self.difficulty = difficulty
            self.base_speed = config.DIFFICULTY_LEVELS[self.difficulty]["speed"]
            self.score_mult = config.DIFFICULTY_LEVELS[self.difficulty]["score_mult"]

    def reset(self) -> None:
        self.set_difficulty(self.difficulty)
        start_x = config.GRID_COLS // 2
        start_y = config.GRID_ROWS // 2

        # Snake segments stored as list of (grid_x, grid_y), head is index 0
        self.snake: List[Tuple[int, int]] = [
            (start_x, start_y),
            (start_x - 1, start_y),
            (start_x - 2, start_y),
            (start_x - 3, start_y),
        ]
        # Previous positions for smooth visual interpolation between grid ticks
        self.prev_snake: List[Tuple[int, int]] = list(self.snake)

        self.direction: Tuple[int, int] = config.DIR_RIGHT
        self.next_direction: Tuple[int, int] = config.DIR_RIGHT

        self.score: int = 0
        self.apples_eaten: int = 0
        self.is_game_over: bool = False
        self.death_reason: str = ""
        self.new_high_score: bool = False

        # Timing & smooth movement progress (0.0 to 1.0 between grid steps)
        self.move_accumulator: float = 0.0
        self.current_speed: float = self.base_speed

        # Food & Bonus Food
        self.food: Tuple[int, int] = self._spawn_food()
        self.bonus_food: Optional[Tuple[int, int]] = None
        self.bonus_spawn_time: float = 0.0
        self.bonus_duration: float = 7.5  # seconds before bonus disappears

        # Visual particle / pop effects on eating food
        self.particles: List[Dict] = []

    def _spawn_food(self) -> Tuple[int, int]:
        occupied = set(self.snake)
        if getattr(self, "bonus_food", None):
            occupied.add(self.bonus_food)

        free_cells = [
            (x, y)
            for x in range(config.GRID_COLS)
            for y in range(config.GRID_ROWS)
            if (x, y) not in occupied
        ]
        if not free_cells:
            return (0, 0)
        return random.choice(free_cells)

    def change_direction(self, new_dir: Tuple[int, int]) -> bool:
        """
        Queue a direction change if it is not directly opposite to the current movement direction.
        Returns True if the direction change was accepted.
        """
        if new_dir not in config.OPPOSITE_DIRECTIONS:
            return False
        # Prevent 180-degree self-collision reversal
        if new_dir != config.OPPOSITE_DIRECTIONS.get(self.direction):
            self.next_direction = new_dir
            return True
        return False

    def apply_gesture(self, gesture: str) -> bool:
        """Map a directional gesture string (UP, DOWN, LEFT, RIGHT) to snake direction."""
        if gesture in config.GESTURE_TO_DIR:
            return self.change_direction(config.GESTURE_TO_DIR[gesture])
        return False

    def get_high_score(self) -> int:
        return max(self.score, self.high_scores.get(self.difficulty, 0))

    def update(self, dt: float) -> Optional[str]:
        """
        Advance the snake simulation by dt seconds.
        Returns an event name ('eat', 'bonus', 'game_over', or None) for sound/UI triggers.
        """
        if self.is_game_over:
            self._update_particles(dt)
            return None

        # Update particles
        self._update_particles(dt)

        # Check bonus food expiration
        if self.bonus_food is not None:
            if time.time() - self.bonus_spawn_time > self.bonus_duration:
                self.bonus_food = None

        # Gradual speed scaling as snake grows (caps at +35% of base speed)
        speed_boost = min(self.apples_eaten * 0.12, self.base_speed * 0.35)
        self.current_speed = self.base_speed + speed_boost

        self.move_accumulator += dt * self.current_speed
        event_triggered = None

        while self.move_accumulator >= 1.0:
            self.move_accumulator -= 1.0
            step_event = self._step_grid()
            if step_event:
                event_triggered = step_event
            if self.is_game_over:
                self.move_accumulator = 0.0
                break

        return event_triggered

    def _step_grid(self) -> Optional[str]:
        self.prev_snake = list(self.snake)
        self.direction = self.next_direction

        head_x, head_y = self.snake[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)

        # 1. Check wall collision
        if not (0 <= new_head[0] < config.GRID_COLS and 0 <= new_head[1] < config.GRID_ROWS):
            self._trigger_game_over("Wall Collision!")
            return "game_over"

        # 2. Check self collision (ignoring tail tip if it will move away this step)
        will_eat = (new_head == self.food) or (self.bonus_food is not None and new_head == self.bonus_food)
        body_to_check = self.snake if will_eat else self.snake[:-1]
        if new_head in body_to_check:
            self._trigger_game_over("Bit Yourself!")
            return "game_over"

        # 3. Move snake head forward
        self.snake.insert(0, new_head)

        # 4. Handle eating food
        if new_head == self.food:
            self.apples_eaten += 1
            self.score += self.score_mult
            self._check_high_score()
            self._spawn_particles(new_head, config.COLOR_FOOD)
            # Match prev_snake length for smooth interpolation when growing
            self.prev_snake.append(self.prev_snake[-1])
            self.food = self._spawn_food()

            # Every 5 apples, spawn a temporary Golden Bonus Food
            if self.apples_eaten % 5 == 0 and self.bonus_food is None:
                self.bonus_food = self._spawn_food()
                self.bonus_spawn_time = time.time()

            return "eat"

        if self.bonus_food is not None and new_head == self.bonus_food:
            self.score += self.score_mult * 3
            self._check_high_score()
            self._spawn_particles(new_head, config.COLOR_GOLDEN_FOOD, count=16)
            self.prev_snake.append(self.prev_snake[-1])
            self.bonus_food = None
            return "bonus"

        # Normal move: remove tail
        self.snake.pop()
        return None

    def _check_high_score(self) -> None:
        if self.score > self.high_scores.get(self.difficulty, 0):
            self.high_scores[self.difficulty] = self.score
            self.new_high_score = True
            self.save_high_scores()

    def _trigger_game_over(self, reason: str) -> None:
        self.is_game_over = True
        self.death_reason = reason
        self._check_high_score()
        self._spawn_particles(self.snake[0], config.COLOR_DANGER, count=22)

    def _spawn_particles(self, grid_pos: Tuple[int, int], color: Tuple[int, int, int], count: int = 10) -> None:
        px = config.BOARD_X + grid_pos[0] * config.GRID_SIZE + config.GRID_SIZE // 2
        py = config.BOARD_Y + grid_pos[1] * config.GRID_SIZE + config.GRID_SIZE // 2
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(45, 160)
            self.particles.append({
                "x": float(px),
                "y": float(py),
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "radius": random.uniform(2.5, 5.0),
                "life": 1.0,
                "color": color,
            })

    def _update_particles(self, dt: float) -> None:
        alive = []
        for p in self.particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["life"] -= dt * 2.2
            if p["life"] > 0:
                alive.append(p)
        self.particles = alive

    def get_interpolated_snake(self) -> List[Tuple[float, float]]:
        """
        Return smoothly interpolated (grid_x, grid_y) coordinates for each snake segment
        so movement looks 60 FPS butter-smooth instead of choppy grid jumps.
        """
        alpha = min(max(self.move_accumulator, 0.0), 1.0)
        if self.is_game_over:
            return [(float(x), float(y)) for x, y in self.snake]

        interp_positions: List[Tuple[float, float]] = []
        for i, curr in enumerate(self.snake):
            prev = self.prev_snake[i] if i < len(self.prev_snake) else curr
            ix = prev[0] + (curr[0] - prev[0]) * alpha
            iy = prev[1] + (curr[1] - prev[1]) * alpha
            interp_positions.append((ix, iy))
        return interp_positions

