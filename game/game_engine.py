import array
import io
import math
import random
import warnings
import wave

import pygame
from game.color_button import ColorButton


class GameEngine:
    INITIAL_FLASH_DURATION = 450
    MIN_FLASH_DURATION = 200
    FLASH_DURATION_STEP = 25
    INITIAL_PAUSE_DURATION = 200
    MIN_PAUSE_DURATION = 100
    PAUSE_DURATION_STEP = 10
    BUTTON_FREQUENCIES = (261.63, 329.63, 392.00, 523.25)
    SOUND_SAMPLE_RATE = 44100
    SOUND_DURATION = 0.15
    PLAYER_TURN_DURATION = 5000

    def __init__(self, width, height):
        self.width = width
        self.height = height

        pad_size = 130
        gap = 24
        start_x = width // 2 - pad_size - (gap // 2)
        start_y = 150

        self.buttons = [
            ColorButton(0, pygame.Rect(start_x, start_y, pad_size, pad_size), (110, 20, 20), (255, 50, 50)),                      # Red
            ColorButton(1, pygame.Rect(start_x + pad_size + gap, start_y, pad_size, pad_size), (15, 60, 150), (40, 170, 255)),   # Blue
            ColorButton(2, pygame.Rect(start_x, start_y + pad_size + gap, pad_size, pad_size), (15, 100, 30), (50, 255, 90)),    # Green
            ColorButton(3, pygame.Rect(start_x + pad_size + gap, start_y + pad_size + gap, pad_size, pad_size), (140, 110, 10), (255, 235, 40)), # Yellow
        ]
        self.button_sounds = self._create_button_sounds()

        self.sequence = []
        self.player_input = []
        self.score = 0

        self.state = "WATCH"
        self.game_over_reason = None
        self.showing_step = 0
        self.step_start_time = 0
        self.flash_duration = self.INITIAL_FLASH_DURATION
        self.pause_duration = self.INITIAL_PAUSE_DURATION
        self.is_flashing = False
        self.player_turn_start_time = None

        self.player_lit_button = None
        self.player_lit_start = 0
        self.player_flash_duration = 150

        self.font_title = pygame.font.SysFont(None, 40)
        self.font_medium = pygame.font.SysFont(None, 28)
        self.font_small = pygame.font.SysFont(None, 22)

        self.start_next_round()

    def _create_button_sounds(self):
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            return [
                self._create_tone(frequency)
                for frequency in self.BUTTON_FREQUENCIES
            ]
        except pygame.error as error:
            warnings.warn(
                f"Game audio is unavailable; sound effects are disabled: {error}",
                RuntimeWarning,
            )
            return []

    @classmethod
    def _create_tone(cls, frequency):
        sample_count = int(cls.SOUND_SAMPLE_RATE * cls.SOUND_DURATION)
        samples = array.array("h")
        for sample_index in range(sample_count):
            envelope = 1 - sample_index / sample_count
            sample = math.sin(2 * math.pi * frequency * sample_index / cls.SOUND_SAMPLE_RATE)
            samples.append(int(32767 * 0.25 * envelope * sample))

        audio_buffer = io.BytesIO()
        with wave.open(audio_buffer, "wb") as audio_file:
            audio_file.setnchannels(1)
            audio_file.setsampwidth(2)
            audio_file.setframerate(cls.SOUND_SAMPLE_RATE)
            audio_file.writeframes(samples.tobytes())
        audio_buffer.seek(0)
        return pygame.mixer.Sound(file=audio_buffer)

    def _light_button(self, button):
        button.is_lit = True
        if self.button_sounds:
            self.button_sounds[button.color_id].play()

    def _check_player_timeout(self, now):
        if (
            self.state == "PLAYER_TURN"
            and self.player_turn_start_time is not None
            and now - self.player_turn_start_time >= self.PLAYER_TURN_DURATION
        ):
            self.state = "GAME_OVER"
            self.game_over_reason = "TIME'S UP!"

    def start_next_round(self):
        new_color = random.randint(0, 3)

        self.sequence.append(new_color)

        round_index = len(self.sequence) - 1
        self.flash_duration = max(
            self.MIN_FLASH_DURATION,
            self.INITIAL_FLASH_DURATION - round_index * self.FLASH_DURATION_STEP,
        )
        self.pause_duration = max(
            self.MIN_PAUSE_DURATION,
            self.INITIAL_PAUSE_DURATION - round_index * self.PAUSE_DURATION_STEP,
        )

        self.player_input.clear()
        self.state = "WATCH"
        self.player_turn_start_time = None
        self.showing_step = 0
        self.step_start_time = pygame.time.get_ticks()
        self.is_flashing = True
        self._light_button(self.buttons[self.sequence[0]])

    def update(self):
        now = pygame.time.get_ticks()
        self._check_player_timeout(now)

        if self.player_lit_button is not None:
            if now - self.player_lit_start >= self.player_flash_duration:
                self.player_lit_button.is_lit = False
                self.player_lit_button = None

        if self.state == "WATCH":
            current_btn_id = self.sequence[self.showing_step]

            if self.is_flashing:
                if now - self.step_start_time >= self.flash_duration:
                    self.buttons[current_btn_id].is_lit = False
                    self.is_flashing = False
                    self.step_start_time = now
            else:
                if now - self.step_start_time >= self.pause_duration:
                    self.showing_step += 1
                    if self.showing_step < len(self.sequence):
                        next_id = self.sequence[self.showing_step]
                        self._light_button(self.buttons[next_id])
                        self.is_flashing = True
                        self.step_start_time = now
                    else:
                        self.state = "PLAYER_TURN"
                        self.player_turn_start_time = now

    def handle_event(self, event):
        if self.state == "GAME_OVER":
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                self.reset()
            return

        self._check_player_timeout(pygame.time.get_ticks())
        if self.state == "GAME_OVER":
            return

        if self.state == "PLAYER_TURN" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for btn in self.buttons:
                if btn.contains(event.pos):
                    self._light_button(btn)
                    self.player_lit_button = btn
                    self.player_lit_start = pygame.time.get_ticks()

                    self.register_player_click(btn.color_id)
                    break

    def register_player_click(self, color_id):
        self.player_input.append(color_id)
        current_idx = len(self.player_input) - 1

        if self.player_input[current_idx] != self.sequence[current_idx]:
            self.state = "GAME_OVER"
            self.game_over_reason = "WRONG PATTERN!"
            return

        if len(self.player_input) == len(self.sequence):
            self.score += 1
            self.start_next_round()
        else:
            self.player_turn_start_time = pygame.time.get_ticks()

    def reset(self):
        self.sequence.clear()
        self.player_input.clear()
        self.score = 0
        self.game_over_reason = None
        for btn in self.buttons:
            btn.is_lit = False
        self.player_lit_button = None
        self.start_next_round()

    def render(self, screen):
        screen.fill((22, 24, 30))

        title_surf = self.font_title.render("Memory Pattern Arena", True, (245, 245, 245))
        screen.blit(title_surf, (self.width // 2 - title_surf.get_width() // 2, 20))

        score_surf = self.font_medium.render(f"Score: {self.score}", True, (255, 220, 80))
        screen.blit(score_surf, (self.width // 2 - score_surf.get_width() // 2, 60))

        status_text = "Watch the pattern..." if self.state == "WATCH" else "Your turn: Click the pattern!"
        status_color = (190, 195, 205) if self.state == "WATCH" else (80, 240, 130)
        status_surf = self.font_medium.render(status_text, True, status_color)
        screen.blit(status_surf, (self.width // 2 - status_surf.get_width() // 2, 95))

        if self.state == "PLAYER_TURN":
            elapsed = pygame.time.get_ticks() - self.player_turn_start_time
            remaining = max(0, self.PLAYER_TURN_DURATION - elapsed)
            fraction = remaining / self.PLAYER_TURN_DURATION
            timer_rect = pygame.Rect(self.width // 2 - 125, 128, 250, 16)
            fill_width = int(timer_rect.width * fraction)
            timer_color = (70, 220, 120)
            if fraction <= 0.5:
                timer_color = (245, 190, 60)
            if fraction <= 0.25:
                timer_color = (240, 75, 70)

            label = self.font_small.render("TIME", True, (220, 225, 235))
            screen.blit(label, (timer_rect.left - label.get_width() - 10, 124))
            pygame.draw.rect(screen, (55, 60, 70), timer_rect, border_radius=7)
            if fill_width > 0:
                fill_rect = pygame.Rect(
                    timer_rect.left,
                    timer_rect.top,
                    fill_width,
                    timer_rect.height,
                )
                pygame.draw.rect(screen, timer_color, fill_rect, border_radius=7)
            pygame.draw.rect(screen, (220, 225, 235), timer_rect, width=2, border_radius=7)

            seconds_left = remaining / 1000
            time_label = self.font_small.render(f"{seconds_left:.1f}s", True, (220, 225, 235))
            screen.blit(time_label, (timer_rect.right + 8, 124))

        for btn in self.buttons:
            btn.render(screen)

        if self.state == "GAME_OVER":
            overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            screen.blit(overlay, (0, 0))

            over_surf = self.font_title.render(
                f"{self.game_over_reason} GAME OVER",
                True,
                (240, 70, 70),
            )
            screen.blit(over_surf, (self.width // 2 - over_surf.get_width() // 2, self.height // 2 - 40))

            final_score_surf = self.font_medium.render(f"Final Score: {self.score}", True, (255, 255, 255))
            screen.blit(final_score_surf, (self.width // 2 - final_score_surf.get_width() // 2, self.height // 2 + 10))

            restart_surf = self.font_medium.render("Press [R] to Play Again", True, (200, 200, 200))
            screen.blit(restart_surf, (self.width // 2 - restart_surf.get_width() // 2, self.height // 2 + 50))
