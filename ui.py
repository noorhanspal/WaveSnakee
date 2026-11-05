"""
UI Renderer for the Gesture-Controlled Snake Game.
Renders:
  - Split-screen layout (Game Board on Left, Webcam + Gesture HUD + Guide on Right)
  - Smooth interpolated snake with eyes, glowing food, and particle bursts
  - Start Screen (with Gesture Guide & Difficulty Selector)
  - Calibration Screen
  - Pause Overlay & Game Over Screen
"""
import math
import time
from typing import Dict, List, Tuple

import pygame

import config
from snake_game import SnakeGame


class GameUI:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        pygame.font.init()

        # Load clean modern system fonts with fallback
        font_names = "segoeui,verdana,arial,sans-serif"
        self.font_title = pygame.font.SysFont(font_names, 28, bold=True)
        self.font_xl = pygame.font.SysFont(font_names, 36, bold=True)
        self.font_lg = pygame.font.SysFont(font_names, 22, bold=True)
        self.font_md = pygame.font.SysFont(font_names, 17, bold=True)
        self.font_sm = pygame.font.SysFont(font_names, 14, bold=False)
        self.font_xs = pygame.font.SysFont(font_names, 12, bold=True)

        # Interactive button hitboxes populated during render
        self.difficulty_buttons: Dict[str, pygame.Rect] = {}
        self.action_buttons: Dict[str, pygame.Rect] = {}

        # Pre-render static board grid and modal backdrop once for 60 FPS smoothness
        self._board_bg_surface = self._create_board_bg_surface()
        self._modal_backdrop_surface = pygame.Surface(
            (config.BOARD_WIDTH, config.BOARD_HEIGHT), pygame.SRCALPHA
        )
        self._modal_backdrop_surface.fill((10, 14, 22, 215))

    def _create_board_bg_surface(self) -> pygame.Surface:
        surf = pygame.Surface((config.BOARD_WIDTH, config.BOARD_HEIGHT))
        surf.fill(config.COLOR_BOARD_BG)
        for col in range(1, config.GRID_COLS):
            gx = col * config.GRID_SIZE
            pygame.draw.line(surf, config.COLOR_GRID_LINE, (gx, 0), (gx, config.BOARD_HEIGHT), 1)
        for row in range(1, config.GRID_ROWS):
            gy = row * config.GRID_SIZE
            pygame.draw.line(surf, config.COLOR_GRID_LINE, (0, gy), (config.BOARD_WIDTH, gy), 1)
        return surf

    def render(
        self,
        game: SnakeGame,
        cam_surface: pygame.Surface,
        tracker_state: Dict,
        game_state: str,
        sound_enabled: bool,
        calib_countdown: float = 0.0,
    ) -> None:
        self.screen.fill(config.COLOR_BG)
        self._draw_top_bar(game, sound_enabled)
        self._draw_board(game)
        self._draw_side_panel(cam_surface, tracker_state, game, game_state)

        # State Overlays on top of the game board
        if game_state == "START":
            self._draw_start_overlay(game, tracker_state)
        elif game_state == "CALIBRATE":
            self._draw_calibration_overlay(tracker_state, calib_countdown)
        elif game_state == "PAUSED":
            self._draw_pause_overlay(game)
        elif game_state == "GAME_OVER":
            self._draw_game_over_overlay(game)

    def _draw_top_bar(self, game: SnakeGame, sound_enabled: bool) -> None:
        # Title & Subtitle
        title_surf = self.font_title.render("GESTURE SNAKE", True, config.COLOR_SNAKE_HEAD)
        self.screen.blit(title_surf, (config.BOARD_X, 22))

        badge_rect = pygame.Rect(config.BOARD_X + title_surf.get_width() + 12, 28, 48, 22)
        pygame.draw.rect(self.screen, (25, 55, 65), badge_rect, border_radius=6)
        pygame.draw.rect(self.screen, config.COLOR_SNAKE_HEAD, badge_rect, width=1, border_radius=6)
        ai_txt = self.font_xs.render("CV + AI", True, config.COLOR_SNAKE_HEAD)
        self.screen.blit(ai_txt, ai_txt.get_rect(center=badge_rect.center))

        # Score & High Score Pills
        self._draw_stat_pill(295, 18, 125, 48, "SCORE", str(game.score), config.COLOR_ACCENT)
        self._draw_stat_pill(
            430, 18, 135, 48, "HIGH SCORE", str(game.get_high_score()), config.COLOR_WARNING
        )

        # Calibrate & Sound Quick Buttons
        cal_rect = pygame.Rect(575, 22, 52, 40)
        self.action_buttons["CALIBRATE"] = cal_rect
        pygame.draw.rect(self.screen, config.COLOR_PANEL_BG, cal_rect, border_radius=8)
        pygame.draw.rect(self.screen, config.COLOR_PANEL_BORDER, cal_rect, width=1, border_radius=8)
        cal_txt = self.font_xs.render("CAL (C)", True, config.COLOR_TEXT_PRIMARY)
        self.screen.blit(cal_txt, cal_txt.get_rect(center=cal_rect.center))

        snd_rect = pygame.Rect(633, 22, 37, 40)
        self.action_buttons["MUTE"] = snd_rect
        pygame.draw.rect(self.screen, config.COLOR_PANEL_BG, snd_rect, border_radius=8)
        snd_col = config.COLOR_SUCCESS if sound_enabled else config.COLOR_TEXT_SECONDARY
        pygame.draw.rect(self.screen, snd_col, snd_rect, width=1, border_radius=8)
        snd_txt = self.font_xs.render("SND" if sound_enabled else "OFF", True, snd_col)
        self.screen.blit(snd_txt, snd_txt.get_rect(center=snd_rect.center))

    def _draw_stat_pill(
        self, x: int, y: int, w: int, h: int, label: str, value: str, accent_color: Tuple[int, int, int]
    ) -> None:
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, config.COLOR_PANEL_BG, rect, border_radius=10)
        pygame.draw.rect(self.screen, config.COLOR_PANEL_BORDER, rect, width=1, border_radius=10)

        lbl_surf = self.font_xs.render(label, True, config.COLOR_TEXT_SECONDARY)
        val_surf = self.font_lg.render(value, True, accent_color)
        self.screen.blit(lbl_surf, (x + 12, y + 5))
        self.screen.blit(val_surf, (x + 12, y + 19))

    def _draw_board(self, game: SnakeGame) -> None:
        board_rect = pygame.Rect(config.BOARD_X, config.BOARD_Y, config.BOARD_WIDTH, config.BOARD_HEIGHT)
        self.screen.blit(self._board_bg_surface, (config.BOARD_X, config.BOARD_Y))

        # Draw Normal Food (pulsing apple)
        pulse = 0.5 + 0.5 * math.sin(time.time() * 6.0)
        fx = config.BOARD_X + game.food[0] * config.GRID_SIZE + config.GRID_SIZE // 2
        fy = config.BOARD_Y + game.food[1] * config.GRID_SIZE + config.GRID_SIZE // 2
        glow_r = int(config.GRID_SIZE * 0.55 + pulse * 3)
        pygame.draw.circle(self.screen, (75, 25, 38), (fx, fy), glow_r)
        pygame.draw.circle(self.screen, config.COLOR_FOOD, (fx, fy), config.GRID_SIZE // 2 - 2)
        pygame.draw.circle(self.screen, (255, 190, 195), (fx - 2, fy - 3), 3)

        # Draw Bonus Golden Food if active
        if game.bonus_food is not None:
            bx = config.BOARD_X + game.bonus_food[0] * config.GRID_SIZE + config.GRID_SIZE // 2
            by = config.BOARD_Y + game.bonus_food[1] * config.GRID_SIZE + config.GRID_SIZE // 2
            pygame.draw.circle(self.screen, (90, 75, 15), (bx, by), glow_r + 2)
            pygame.draw.circle(self.screen, config.COLOR_GOLDEN_FOOD, (bx, by), config.GRID_SIZE // 2 - 1)
            pygame.draw.circle(self.screen, (255, 250, 210), (bx - 2, by - 3), 3)

        # Draw Smooth Interpolated Snake
        interp_snake = game.get_interpolated_snake()
        total_len = max(len(interp_snake), 1)

        # Draw from tail to head so head sits on top
        for i in range(len(interp_snake) - 1, -1, -1):
            gx, gy = interp_snake[i]
            px = config.BOARD_X + gx * config.GRID_SIZE
            py = config.BOARD_Y + gy * config.GRID_SIZE

            if i == 0:
                # Snake Head
                head_rect = pygame.Rect(int(px) + 1, int(py) + 1, config.GRID_SIZE - 2, config.GRID_SIZE - 2)
                pygame.draw.rect(self.screen, config.COLOR_SNAKE_HEAD, head_rect, border_radius=7)
                self._draw_snake_eyes(head_rect, game.direction)
            else:
                # Smooth color gradient from body to tail
                t = i / total_len
                r = int(config.COLOR_SNAKE_BODY[0] * (1 - t) + config.COLOR_SNAKE_TAIL[0] * t)
                g = int(config.COLOR_SNAKE_BODY[1] * (1 - t) + config.COLOR_SNAKE_TAIL[1] * t)
                b = int(config.COLOR_SNAKE_BODY[2] * (1 - t) + config.COLOR_SNAKE_TAIL[2] * t)
                pad = 2 if i < len(interp_snake) - 2 else 3
                seg_rect = pygame.Rect(
                    int(px) + pad,
                    int(py) + pad,
                    config.GRID_SIZE - pad * 2,
                    config.GRID_SIZE - pad * 2,
                )
                pygame.draw.rect(self.screen, (r, g, b), seg_rect, border_radius=6)

        # Draw Particle Effects
        for p in game.particles:
            rad = max(1, int(p["radius"] * p["life"]))
            pygame.draw.circle(self.screen, p["color"], (int(p["x"]), int(p["y"])), rad)

        # Outer Board Border
        pygame.draw.rect(self.screen, config.COLOR_PANEL_BORDER, board_rect, width=2, border_radius=10)

    def _draw_snake_eyes(self, head_rect: pygame.Rect, direction: Tuple[int, int]) -> None:
        cx, cy = head_rect.center
        dx, dy = direction
        perp_x, perp_y = -dy, dx

        eye1 = (int(cx + dx * 4 + perp_x * 4), int(cy + dy * 4 + perp_y * 4))
        eye2 = (int(cx + dx * 4 - perp_x * 4), int(cy + dy * 4 - perp_y * 4))
        pygame.draw.circle(self.screen, (10, 20, 25), eye1, 3)
        pygame.draw.circle(self.screen, (10, 20, 25), eye2, 3)
        pygame.draw.circle(self.screen, (255, 255, 255), eye1, 1)
        pygame.draw.circle(self.screen, (255, 255, 255), eye2, 1)

    def _draw_side_panel(
        self, cam_surface: pygame.Surface, tracker_state: Dict, game: SnakeGame, game_state: str = "PLAYING"
    ) -> None:
        panel_rect = pygame.Rect(config.PANEL_X, config.PANEL_Y, config.PANEL_WIDTH, config.PANEL_HEIGHT)
        pygame.draw.rect(self.screen, config.COLOR_PANEL_BG, panel_rect, border_radius=14)
        pygame.draw.rect(self.screen, config.COLOR_PANEL_BORDER, panel_rect, width=2, border_radius=14)

        # 1. Panel Header + Hand Status Dot
        hdr = self.font_md.render("LIVE HAND TRACKER", True, config.COLOR_TEXT_PRIMARY)
        self.screen.blit(hdr, (config.PANEL_X + 20, config.PANEL_Y + 14))

        hand_ok = tracker_state.get("hand_detected", False)
        status_col = config.COLOR_SUCCESS if hand_ok else config.COLOR_WARNING
        status_txt = "Hand Locked" if hand_ok else "Show Hand"
        pygame.draw.circle(self.screen, status_col, (config.PANEL_X + config.PANEL_WIDTH - 105, config.PANEL_Y + 25), 5)
        st_surf = self.font_xs.render(status_txt, True, status_col)
        self.screen.blit(st_surf, (config.PANEL_X + config.PANEL_WIDTH - 93, config.PANEL_Y + 17))

        # 2. Webcam Frame
        cam_x = config.PANEL_X + (config.PANEL_WIDTH - config.CAM_WIDTH) // 2
        cam_y = config.PANEL_Y + 44
        self.screen.blit(cam_surface, (cam_x, cam_y))
        cam_border = pygame.Rect(cam_x, cam_y, config.CAM_WIDTH, config.CAM_HEIGHT)
        pygame.draw.rect(
            self.screen,
            config.COLOR_SNAKE_HEAD if hand_ok else config.COLOR_PANEL_BORDER,
            cam_border,
            width=2,
            border_radius=6,
        )

        # 3. Detected Gesture Live Banner
        gesture = tracker_state.get("gesture", config.GESTURE_NONE)
        if tracker_state.get("is_two_palms", False):
            gesture = config.GESTURE_TWO_PALMS
        elif game_state in ("START", "GAME_OVER") and tracker_state.get("is_open_palm", False):
            gesture = config.GESTURE_OPEN_PALM
        banner_y = cam_y + config.CAM_HEIGHT + 12
        banner_rect = pygame.Rect(cam_x, banner_y, config.CAM_WIDTH, 44)
        pygame.draw.rect(self.screen, (16, 22, 32), banner_rect, border_radius=8)

        g_color = self._gesture_color(gesture)
        pygame.draw.rect(self.screen, g_color, banner_rect, width=1, border_radius=8)

        lbl = self.font_xs.render("ACTIVE GESTURE:", True, config.COLOR_TEXT_SECONDARY)
        val = self.font_md.render(self._gesture_display_name(gesture), True, g_color)
        self.screen.blit(lbl, (cam_x + 14, banner_y + 14))
        self.screen.blit(val, (cam_x + 135, banner_y + 10))

        # 4. Difficulty Speed Selector Row
        diff_y = banner_y + 56
        diff_lbl = self.font_xs.render("SPEED / DIFFICULTY (KEYS 1, 2, 3):", True, config.COLOR_TEXT_SECONDARY)
        self.screen.blit(diff_lbl, (cam_x, diff_y))

        btn_w = (config.CAM_WIDTH - 16) // 3
        for idx, (key, info) in enumerate(config.DIFFICULTY_LEVELS.items()):
            bx = cam_x + idx * (btn_w + 8)
            by = diff_y + 20
            b_rect = pygame.Rect(bx, by, btn_w, 32)
            self.difficulty_buttons[key] = b_rect
            is_active = (game.difficulty == key)
            bg_col = (30, 44, 62) if is_active else (16, 22, 32)
            border_col = info["color"] if is_active else config.COLOR_PANEL_BORDER
            pygame.draw.rect(self.screen, bg_col, b_rect, border_radius=7)
            pygame.draw.rect(self.screen, border_col, b_rect, width=2 if is_active else 1, border_radius=7)

            txt_col = info["color"] if is_active else config.COLOR_TEXT_SECONDARY
            t_surf = self.font_xs.render(info["label"].upper(), True, txt_col)
            self.screen.blit(t_surf, t_surf.get_rect(center=b_rect.center))

        # 5. Gesture Guide Table
        guide_y = diff_y + 64
        g_hdr = self.font_xs.render("GESTURE CONTROLS GUIDE:", True, config.COLOR_ACCENT)
        self.screen.blit(g_hdr, (cam_x, guide_y))

        guide_rows = [
            ("Hand Right / Left", "Move Snake Right / Left"),
            ("Hand Up / Down", "Move Snake Up / Down"),
            ("2 Hands Open Palm", "Pause / Resume Game"),
            ("1 Hand Open Palm", "Start / Restart Game"),
            ("Key 'C' / Button", "Calibrate Hand Center"),
        ]
        row_y = guide_y + 22
        for left_txt, right_txt in guide_rows:
            row_rect = pygame.Rect(cam_x, row_y, config.CAM_WIDTH, 30)
            pygame.draw.rect(self.screen, (17, 23, 33), row_rect, border_radius=6)
            l_surf = self.font_xs.render(left_txt, True, config.COLOR_TEXT_PRIMARY)
            r_surf = self.font_xs.render(right_txt, True, config.COLOR_SNAKE_HEAD)
            self.screen.blit(l_surf, (cam_x + 10, row_y + 7))
            self.screen.blit(r_surf, (cam_x + config.CAM_WIDTH - r_surf.get_width() - 10, row_y + 7))
            row_y += 35

    def _gesture_color(self, gesture: str) -> Tuple[int, int, int]:
        if gesture in config.GESTURE_TO_DIR:
            return config.COLOR_SNAKE_HEAD
        if gesture == config.GESTURE_TWO_PALMS:
            return config.COLOR_WARNING
        if gesture == config.GESTURE_OPEN_PALM:
            return config.COLOR_SUCCESS
        return config.COLOR_TEXT_SECONDARY

    def _gesture_display_name(self, gesture: str) -> str:
        mapping = {
            config.GESTURE_NONE: "NEUTRAL / IDLE",
            config.GESTURE_UP: "UP (Move Up)",
            config.GESTURE_DOWN: "DOWN (Move Down)",
            config.GESTURE_LEFT: "LEFT (Move Left)",
            config.GESTURE_RIGHT: "RIGHT (Move Right)",
            config.GESTURE_TWO_PALMS: "2 HANDS PALM (Pause/Resume)",
            config.GESTURE_OPEN_PALM: "OPEN PALM (Start)",
        }
        return mapping.get(gesture, gesture)

    def _draw_board_modal_backdrop(self) -> pygame.Rect:
        self.screen.blit(self._modal_backdrop_surface, (config.BOARD_X, config.BOARD_Y))
        return pygame.Rect(config.BOARD_X, config.BOARD_Y, config.BOARD_WIDTH, config.BOARD_HEIGHT)

    def _draw_start_overlay(self, game: SnakeGame, tracker_state: Dict) -> None:
        board_rect = self._draw_board_modal_backdrop()
        cx = board_rect.centerx
        top = board_rect.top + 38

        title = self.font_xl.render("HAND GESTURE SNAKE", True, config.COLOR_SNAKE_HEAD)
        sub = self.font_sm.render(
            "Control the snake in real-time using your webcam & hand gestures!",
            True,
            config.COLOR_TEXT_PRIMARY,
        )
        self.screen.blit(title, title.get_rect(centerx=cx, top=top))
        self.screen.blit(sub, sub.get_rect(centerx=cx, top=top + 46))

        # Gesture Guide Cards inside Start Screen
        cards = [
            ("MOVE 1 HAND UP / DOWN / LEFT / RIGHT", "Move hand outside the green center circle to steer"),
            ("SHOW 2 HANDS OPEN PALM (DONO HAATH)", "Show both open palms to Pause or Resume the game"),
            ("SHOW OPEN PALM (KHULA HAATH)", "Hold open palm for 0.6s to Start or Restart"),
            ("CALIBRATE HAND ('C' KEY)", "Set your comfortable hand position as the center zone"),
        ]
        card_y = top + 92
        for head_txt, desc_txt in cards:
            c_rect = pygame.Rect(cx - 250, card_y, 500, 62)
            pygame.draw.rect(self.screen, (22, 30, 44), c_rect, border_radius=10)
            pygame.draw.rect(self.screen, config.COLOR_PANEL_BORDER, c_rect, width=1, border_radius=10)
            h_surf = self.font_md.render(head_txt, True, config.COLOR_ACCENT)
            d_surf = self.font_sm.render(desc_txt, True, config.COLOR_TEXT_SECONDARY)
            self.screen.blit(h_surf, (c_rect.x + 18, c_rect.y + 8))
            self.screen.blit(d_surf, (c_rect.x + 18, c_rect.y + 34))
            card_y += 74

        # Start Button
        start_btn = pygame.Rect(cx - 145, card_y + 18, 290, 52)
        self.action_buttons["START"] = start_btn
        pygame.draw.rect(self.screen, config.COLOR_SUCCESS, start_btn, border_radius=12)
        btn_txt = self.font_md.render("SHOW OPEN PALM or PRESS SPACE", True, (10, 20, 15))
        self.screen.blit(btn_txt, btn_txt.get_rect(center=start_btn.center))

        hint = self.font_xs.render(
            "Tip: Press 'C' to calibrate your hand position before starting | Arrow keys also work",
            True,
            config.COLOR_TEXT_SECONDARY,
        )
        self.screen.blit(hint, hint.get_rect(centerx=cx, top=start_btn.bottom + 14))

    def _draw_calibration_overlay(self, tracker_state: Dict, countdown: float) -> None:
        board_rect = self._draw_board_modal_backdrop()
        cx = board_rect.centerx
        cy = board_rect.centery

        title = self.font_xl.render("HAND CALIBRATION", True, config.COLOR_ACCENT)
        self.screen.blit(title, title.get_rect(centerx=cx, top=cy - 140))

        inst1 = self.font_md.render(
            "Hold your hand in a comfortable neutral position in front of the webcam.",
            True,
            config.COLOR_TEXT_PRIMARY,
        )
        inst2 = self.font_sm.render(
            "That position will become the Center Neutral Circle for Up / Down / Left / Right moves.",
            True,
            config.COLOR_TEXT_SECONDARY,
        )
        self.screen.blit(inst1, inst1.get_rect(centerx=cx, top=cy - 80))
        self.screen.blit(inst2, inst2.get_rect(centerx=cx, top=cy - 48))

        hand_ok = tracker_state.get("hand_detected", False)
        status_msg = (
            f"Locking Center in {max(0.0, countdown):.1f}s..."
            if hand_ok
            else "Waiting for hand in webcam view..."
        )
        col = config.COLOR_SUCCESS if hand_ok else config.COLOR_WARNING
        count_surf = self.font_lg.render(status_msg, True, col)
        self.screen.blit(count_surf, count_surf.get_rect(centerx=cx, top=cy + 10))

        sub_hint = self.font_xs.render(
            "Press SPACE to lock immediately  |  Press R to reset to center  |  Press ESC to cancel",
            True,
            config.COLOR_TEXT_SECONDARY,
        )
        self.screen.blit(sub_hint, sub_hint.get_rect(centerx=cx, top=cy + 70))

    def _draw_pause_overlay(self, game: SnakeGame) -> None:
        board_rect = self._draw_board_modal_backdrop()
        cx, cy = board_rect.center

        card = pygame.Rect(cx - 210, cy - 115, 420, 230)
        pygame.draw.rect(self.screen, config.COLOR_PANEL_BG, card, border_radius=14)
        pygame.draw.rect(self.screen, config.COLOR_WARNING, card, width=2, border_radius=14)

        t_surf = self.font_xl.render("GAME PAUSED", True, config.COLOR_WARNING)
        s_surf = self.font_lg.render(f"Current Score: {game.score}", True, config.COLOR_TEXT_PRIMARY)
        i1 = self.font_sm.render("Show 2 OPEN PALMS (Both Hands) or press 'P' to Resume", True, config.COLOR_SNAKE_HEAD)
        i2 = self.font_xs.render("Press 'R' to Restart  |  Press 'M' for Main Menu", True, config.COLOR_TEXT_SECONDARY)

        self.screen.blit(t_surf, t_surf.get_rect(centerx=cx, top=card.top + 24))
        self.screen.blit(s_surf, s_surf.get_rect(centerx=cx, top=card.top + 82))
        self.screen.blit(i1, i1.get_rect(centerx=cx, top=card.top + 135))
        self.screen.blit(i2, i2.get_rect(centerx=cx, top=card.top + 172))

    def _draw_game_over_overlay(self, game: SnakeGame) -> None:
        board_rect = self._draw_board_modal_backdrop()
        cx, cy = board_rect.center

        card = pygame.Rect(cx - 230, cy - 150, 460, 300)
        pygame.draw.rect(self.screen, config.COLOR_PANEL_BG, card, border_radius=16)
        pygame.draw.rect(self.screen, config.COLOR_DANGER, card, width=2, border_radius=16)

        t_surf = self.font_xl.render("GAME OVER", True, config.COLOR_DANGER)
        r_surf = self.font_sm.render(game.death_reason, True, config.COLOR_TEXT_SECONDARY)
        self.screen.blit(t_surf, t_surf.get_rect(centerx=cx, top=card.top + 20))
        self.screen.blit(r_surf, r_surf.get_rect(centerx=cx, top=card.top + 66))

        score_surf = self.font_lg.render(f"Final Score: {game.score}", True, config.COLOR_TEXT_PRIMARY)
        hi_surf = self.font_md.render(f"High Score ({game.difficulty}): {game.get_high_score()}", True, config.COLOR_WARNING)
        self.screen.blit(score_surf, score_surf.get_rect(centerx=cx, top=card.top + 104))
        self.screen.blit(hi_surf, hi_surf.get_rect(centerx=cx, top=card.top + 140))

        if game.new_high_score and game.score > 0:
            nh_surf = self.font_xs.render("NEW HIGH SCORE!", True, config.COLOR_SUCCESS)
            self.screen.blit(nh_surf, nh_surf.get_rect(centerx=cx, top=card.top + 172))

        restart_btn = pygame.Rect(cx - 155, card.bottom - 88, 310, 48)
        self.action_buttons["RESTART"] = restart_btn
        pygame.draw.rect(self.screen, config.COLOR_SUCCESS, restart_btn, border_radius=10)
        b_txt = self.font_md.render("HOLD OPEN PALM or PRESS R", True, (10, 20, 15))
        self.screen.blit(b_txt, b_txt.get_rect(center=restart_btn.center))

        esc_txt = self.font_xs.render("Press 'M' for Main Menu  |  Press 'ESC' to Quit", True, config.COLOR_TEXT_SECONDARY)
        self.screen.blit(esc_txt, esc_txt.get_rect(centerx=cx, top=card.bottom - 30))

