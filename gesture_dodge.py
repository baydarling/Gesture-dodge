"""Gesture Dodge - Arduino HC-SR04 + Pygame arcade prototype.

Requirements:
    pip install pygame pyserial

Run:
    python gesture_dodge.py

Arduino sends one line per sample: L:0, L:1, or L:2 (115200 baud).
Close Arduino Serial Monitor and any serial_reader.py before running.
"""

import math
import random
import time
from dataclasses import dataclass

import pygame

try:
    import serial
except ImportError:
    serial = None


# ====== ADJUST HERE IF WINDOWS CHANGES THE ARDUINO PORT ======
PORT = "COM9"
BAUD_RATE = 115200
# =============================================================

WIDTH, HEIGHT = 1000, 680
FPS = 60
PLAYER_X = 182
LANE_Y = (221, 359, 497)
TRACK_X = 52
TRACK_W = 896
TRACK_H = 120

BG = (10, 15, 28)
PANEL = (20, 29, 48)
LANE_BG = (17, 28, 47)
LANE_ACTIVE = (23, 46, 60)
BORDER = (52, 77, 103)
WHITE = (229, 245, 252)
MUTED = (135, 158, 179)
CYAN = (78, 233, 218)
GREEN = (112, 250, 177)
RED = (254, 105, 119)
GOLD = (248, 199, 109)


class ArduinoInput:
    """Read newline-delimited lane messages without blocking Pygame."""

    def __init__(self, port):
        self.port = port
        self.connection = None
        self.buffer = bytearray()
        self.last_attempt = -100.0
        self.last_message_time = 0.0
        self.last_error = ""

    @property
    def connected(self):
        return self.connection is not None

    def poll(self):
        """Return most recent valid lane (0..2), or None if none arrived."""
        if serial is None:
            self.last_error = "pyserial kurulu degil"
            return None

        now = time.monotonic()
        if self.connection is None:
            if now - self.last_attempt < 2.0:
                return None
            self.last_attempt = now
            try:
                self.connection = serial.Serial(self.port, BAUD_RATE, timeout=0)
                self.buffer.clear()
                self.last_error = ""
            except (OSError, serial.SerialException) as exc:
                self.last_error = str(exc)
                return None

        latest_lane = None
        try:
            waiting = self.connection.in_waiting
            if waiting:
                self.buffer.extend(self.connection.read(min(waiting, 2048)))
                # Guard against endless data without newline.
                if len(self.buffer) > 4096 and b"\n" not in self.buffer:
                    self.buffer.clear()

            while b"\n" in self.buffer:
                raw_line, _, remaining = self.buffer.partition(b"\n")
                self.buffer = bytearray(remaining)
                message = raw_line.strip().decode("ascii", errors="ignore")
                if message in ("L:0", "L:1", "L:2"):
                    latest_lane = int(message[2])
                    self.last_message_time = now
        except (OSError, serial.SerialException) as exc:
            self.last_error = str(exc)
            self.close()
            return None

        return latest_lane

    def close(self):
        if self.connection is not None:
            try:
                self.connection.close()
            except OSError:
                pass
            self.connection = None
        self.buffer.clear()


@dataclass
class Obstacle:
    x: float
    lane: int
    scored: bool = False


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("GESTURE DODGE | Arduino Arcade")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_title = pygame.font.SysFont("consolas", 36, bold=True)
        self.font_big = pygame.font.SysFont("consolas", 25, bold=True)
        self.font = pygame.font.SysFont("consolas", 19)
        self.font_small = pygame.font.SysFont("consolas", 15)
        self.serial_input = ArduinoInput(PORT)
        self.keyboard_mode = False
        self.best = 0
        self.running = True
        self.reset()

    def reset(self):
        self.lane = 1
        self.player_y = float(LANE_Y[self.lane])
        self.obstacles = []
        self.spawn_in = 1.2
        self.score = 0
        self.lives = 3
        self.elapsed = 0.0
        self.hit_flash = 0.0
        self.invulnerable = 0.0
        self.game_over = False

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_r:
                    self.reset()
                elif event.key == pygame.K_m:
                    self.keyboard_mode = not self.keyboard_mode
                elif self.keyboard_mode or not self.serial_input.connected:
                    if event.key in (pygame.K_1, pygame.K_KP1):
                        self.lane = 0
                    elif event.key in (pygame.K_2, pygame.K_KP2):
                        self.lane = 1
                    elif event.key in (pygame.K_3, pygame.K_KP3):
                        self.lane = 2
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        self.lane = max(0, self.lane - 1)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.lane = min(2, self.lane + 1)

    def update(self, dt):
        incoming_lane = self.serial_input.poll()
        if incoming_lane is not None and not self.keyboard_mode:
            self.lane = incoming_lane

        # Visual smoothing only. Collision uses the selected lane immediately.
        target_y = LANE_Y[self.lane]
        self.player_y += (target_y - self.player_y) * min(1.0, dt * 17.0)

        self.invulnerable = max(0.0, self.invulnerable - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)
        if self.game_over:
            return

        self.elapsed += dt
        self.spawn_in -= dt
        speed = min(590.0, 285.0 + self.score * 13.0)
        if self.spawn_in <= 0:
            self.obstacles.append(Obstacle(WIDTH + 45, random.randint(0, 2)))
            self.spawn_in = max(0.70, 1.45 - self.score * 0.025)

        for obs in self.obstacles:
            obs.x -= speed * dt
            if not obs.scored and obs.x < PLAYER_X - 53:
                obs.scored = True
                self.score += 1
                self.best = max(self.best, self.score)

            if (not obs.scored and self.invulnerable <= 0
                    and obs.lane == self.lane
                    and abs(obs.x - PLAYER_X) < 50):
                obs.scored = True
                self.lives -= 1
                self.invulnerable = 0.9
                self.hit_flash = 0.2
                if self.lives <= 0:
                    self.game_over = True

        self.obstacles = [o for o in self.obstacles if o.x > -100]

    def text(self, value, x, y, font=None, color=WHITE):
        surface = (font or self.font).render(str(value), True, color)
        self.screen.blit(surface, (x, y))
        return surface

    def centered_text(self, value, center_x, center_y, font=None, color=WHITE):
        surface = (font or self.font).render(str(value), True, color)
        self.screen.blit(surface, surface.get_rect(center=(center_x, center_y)))

    def draw_player(self):
        y = int(self.player_y)
        x = PLAYER_X
        if self.invulnerable > 0 and int(self.elapsed * 14) % 2 == 0:
            return
        # Soft halo around the spaceship.
        halo = pygame.Surface((130, 100), pygame.SRCALPHA)
        pygame.draw.ellipse(halo, (44, 245, 208, 32), (0, 10, 130, 75))
        self.screen.blit(halo, (x - 65, y - 50))
        # Small futuristic arrow ship.
        pygame.draw.polygon(self.screen, CYAN, [(x + 32, y), (x - 25, y - 23), (x - 13, y), (x - 25, y + 23)])
        pygame.draw.polygon(self.screen, (177, 255, 242), [(x + 24, y), (x - 15, y - 12), (x - 9, y), (x - 15, y + 12)])
        pygame.draw.circle(self.screen, (18, 46, 65), (x, y), 6)
        # Thruster glow.
        pygame.draw.line(self.screen, (41, 161, 201), (x - 25, y - 8), (x - 35, y - 8), 3)
        pygame.draw.line(self.screen, (41, 161, 201), (x - 25, y + 8), (x - 35, y + 8), 3)

    def draw_obstacle(self, obs):
        x, y = int(obs.x), LANE_Y[obs.lane]
        outer = pygame.Rect(x - 27, y - 39, 54, 78)
        pygame.draw.rect(self.screen, (75, 38, 55), outer.inflate(10, 10), border_radius=8)
        pygame.draw.rect(self.screen, RED, outer, border_radius=7)
        pygame.draw.rect(self.screen, (97, 29, 53), outer.inflate(-10, -10), border_radius=4)
        for dy in (-22, 0, 22):
            pygame.draw.line(self.screen, (255, 172, 173), (x - 14, y + dy - 6), (x + 14, y + dy + 6), 3)

    def draw(self):
        self.screen.fill(BG)
        # Background grid lines.
        for x in range(0, WIDTH, 50):
            pygame.draw.line(self.screen, (17, 28, 44), (x, 0), (x, HEIGHT))
        for y in range(0, HEIGHT, 50):
            pygame.draw.line(self.screen, (17, 28, 44), (0, y), (WIDTH, y))

        # Header.
        self.text("GESTURE", 53, 41, self.font_title, WHITE)
        self.text("DODGE", 247, 41, self.font_title, CYAN)
        pygame.draw.line(self.screen, (47, 77, 98), (52, 104), (948, 104), 2)
        self.text("SKOR", 665, 39, self.font_small, MUTED)
        self.text(f"{self.score:03d}", 665, 58, self.font_big, WHITE)
        self.text("REKOR", 764, 39, self.font_small, MUTED)
        self.text(f"{self.best:03d}", 764, 58, self.font_big, GOLD)
        self.text("CAN", 867, 39, self.font_small, MUTED)
        for i in range(3):
            pygame.draw.circle(self.screen, RED if i < self.lives else (73, 79, 94), (879 + i * 22, 72), 7)

        # Three scrolling lanes.
        self.text("EL HAREKETIYLE SERIT DEGISTIR", 53, 120, self.font_small, MUTED)
        for index, cy in enumerate(LANE_Y):
            rect = pygame.Rect(TRACK_X, cy - TRACK_H // 2, TRACK_W, TRACK_H)
            pygame.draw.rect(self.screen, LANE_ACTIVE if index == self.lane else LANE_BG, rect, border_radius=12)
            pygame.draw.rect(self.screen, CYAN if index == self.lane else BORDER, rect, 2 if index == self.lane else 1, border_radius=12)
            self.text(f"{index}", 76, cy - 13, self.font_big, CYAN if index == self.lane else MUTED)
            # Dashed moving runway marks.
            scroll = int(self.elapsed * 110) % 90
            for x in range(110 - scroll, 915, 90):
                if x > 114:
                    pygame.draw.line(self.screen, (37, 63, 83), (x, cy), (min(x + 28, 925), cy), 2)

        for obs in self.obstacles:
            self.draw_obstacle(obs)
        self.draw_player()

        # Status / instructions footer.
        pygame.draw.line(self.screen, (47, 77, 98), (52, 584), (948, 584), 2)
        if self.keyboard_mode or not self.serial_input.connected:
            mode, mode_color = "KLAVYE MODU", GOLD
        elif time.monotonic() - self.serial_input.last_message_time < 2.0:
            mode, mode_color = "ARDUINO BAGLI", GREEN
        else:
            mode, mode_color = "ARDUINO VERISI BEKLENIYOR", GOLD
        self.text(mode, 54, 602, self.font, mode_color)
        self.text(f"PORT: {PORT}", 54, 630, self.font_small, MUTED)
        self.text("1/2/3 veya OKLAR: serit | M: kontrol modu", 390, 604, self.font_small, MUTED)
        self.text("R: yeniden baslat | ESC: cik", 390, 632, self.font_small, MUTED)

        if self.hit_flash > 0:
            veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            veil.fill((255, 65, 80, 35))
            self.screen.blit(veil, (0, 0))

        if self.game_over:
            veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            veil.fill((7, 12, 25, 205))
            self.screen.blit(veil, (0, 0))
            self.centered_text("OYUN BITTI", WIDTH // 2, HEIGHT // 2 - 55, self.font_title, RED)
            self.centered_text(f"SKORUN: {self.score}", WIDTH // 2, HEIGHT // 2, self.font_big)
            self.centered_text("Tekrar oynamak icin R", WIDTH // 2, HEIGHT // 2 + 53, self.font, MUTED)

        pygame.display.flip()

    def run(self):
        print(f"Gesture Dodge basladi. Seri port: {PORT} / {BAUD_RATE}")
        print("Serial Monitor ve serial_reader.py kapali olmali.")
        print("Klavye ile denemek icin M; 1/2/3 veya oklar; R yeniden baslat; ESC cik.")
        try:
            while self.running:
                dt = min(self.clock.tick(FPS) / 1000.0, 0.05)
                self.handle_events()
                self.update(dt)
                self.draw()
        finally:
            self.serial_input.close()
            pygame.quit()


if __name__ == "__main__":
    Game().run()
