import pygame
import time
import math
import numpy as np
from only4bms.i18n import get as _t, FONT_NAME
from only4bms import i18n as _i18n
from .settings_menu import COLOR_ACCENT, COLOR_SELECTED_BG, COLOR_TEXT_PRIMARY, COLOR_PANEL_BG, BASE_W, BASE_H

class CalibrationMenu:
    def __init__(self, settings, renderer, window):
        from pygame._sdl2.video import Texture
        self.settings = settings
        self.renderer = renderer
        self.window = window
        self.w, self.h = self.window.size
        self.sx, self.sy = self.w / BASE_W, self.h / BASE_H
        
        self.screen = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.texture = None
        self.clock = pygame.time.Clock()
        
        # Fonts
        self.title_font = _i18n.font("ui_title", self.sy, bold=True)
        self.font = _i18n.font("ui_body", self.sy)
        self.small_font = _i18n.font("ui_small", self.sy)
        
        # Calibration State
        self.running = True
        self.start_time = time.perf_counter()
        self.beat_interval = 1.0 # 1 second (60 BPM)
        self.offsets = []
        self.last_hit_diff = 0
        self.last_hit_time = 0
        self.message = _t("tap_to_beat")
        
        # Load a simple beep
        self.click_sound = None
        try:
            # Create a simple 440Hz sine wave beep
            sample_rate = 44100
            duration = 0.05
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            tone = np.sin(440 * t * 2 * np.pi)
            # Fade out
            fade = np.linspace(1, 0, len(tone))
            tone = (tone * fade * 32767).astype(np.int16)
            # Stereo
            stereo_tone = np.vstack((tone, tone)).T.copy(order='C')
            self.click_sound = pygame.sndarray.make_sound(stereo_tone)
        except:
            pass

    def _s(self, v):
        return max(1, int(v * self.sy))

    def run(self):
        from pygame._sdl2.video import Texture
        pygame.key.set_repeat(0)
        
        while self.running:
            t_now = time.perf_counter() - self.start_time
            
            # Play beep on beat (with small threshold)
            if (t_now % self.beat_interval) < (1.0/60.0) and t_now > 0.1:
                # Basic debouncing for the beep trigger in the loop
                if not hasattr(self, '_last_beep_time') or (time.perf_counter() - self._last_beep_time > 0.5):
                    if self.click_sound: self.click_sound.play()
                    self._last_beep_time = time.perf_counter()
            
            self._handle_events(t_now)
            self._draw(t_now)
            
            if not self.texture:
                self.texture = Texture.from_surface(self.renderer, self.screen)
            else:
                self.texture.update(self.screen)
            
            self.renderer.clear()
            self.renderer.blit(self.texture, pygame.Rect(0, 0, self.w, self.h))
            self.renderer.present()
            self.clock.tick(self.settings.get('fps', 60))
            
        return self.settings

    def _handle_events(self, t_now):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.last_hit_time = time.perf_counter()
                    # Calculate difference from nearest beat
                    nearest_beat = round(t_now / self.beat_interval) * self.beat_interval
                    diff_ms = (t_now - nearest_beat) * 1000.0
                    self.offsets.append(diff_ms)
                    self.last_hit_diff = diff_ms
                    if len(self.offsets) > 20: self.offsets.pop(0)
                    
                    avg = sum(self.offsets) / len(self.offsets)
                    self.message = _t("cal_last_avg").format(last=f"{diff_ms:+.1f}ms", avg=f"{avg:+.1f}ms")
                elif event.key == pygame.K_y: # Apply to Judge Delay
                    if self.offsets:
                        avg = sum(self.offsets) / len(self.offsets)
                        self.settings['judge_delay'] = round(self.settings.get('judge_delay', 0) + avg, 1)
                        self.offsets = []
                        self.message = _t("applied_judge").format(val=f"{avg:+.1f}ms")
                elif event.key == pygame.K_v: # Apply to Visual Offset
                    if self.offsets:
                        avg = sum(self.offsets) / len(self.offsets)
                        self.settings['visual_offset'] = int(self.settings.get('visual_offset', 0) - avg)
                        self.offsets = []
                        self.message = _t("applied_visual").format(val=f"{-avg:+.1f}ms")
                elif event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                    self.running = False

    def _draw(self, t_now):
        # Background
        self.screen.fill((15, 15, 25))
        
        # Header
        self.screen.blit(self.title_font.render(_t("calibration_title"), True, COLOR_ACCENT), (self._s(50), self._s(40)))
        
        # Visual Metronome Bar
        rect_w = self._s(500)
        rect_h = self._s(30)
        rx = (self.w - rect_w) // 2
        ry = self.h // 2 - rect_h // 2
        
        pygame.draw.rect(self.screen, (30, 30, 45), (rx, ry, rect_w, rect_h), border_radius=15)
        pygame.draw.rect(self.screen, (50, 50, 70), (rx, ry, rect_w, rect_h), 2, border_radius=15)
        
        # Progress indicator (Sinusoidal oscillation)
        # Hit center (pos=0.5) at t=0, 1, 2... synchronized with beep
        pos = 0.5 + 0.5 * math.sin(t_now * math.pi)
        indicator_x = rx + int(pos * rect_w)
        
        # Indicator Glow
        glow_size = self._s(25)
        glow_surf = pygame.Surface((glow_size*2, glow_size*2), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (*COLOR_ACCENT, 60), (glow_size, glow_size), glow_size)
        self.screen.blit(glow_surf, (indicator_x - glow_size, ry + rect_h // 2 - glow_size))
        
        pygame.draw.circle(self.screen, COLOR_ACCENT, (indicator_x, ry + rect_h // 2), self._s(12))
        
        # Center line (The Target 0ms)
        pygame.draw.line(self.screen, (255, 255, 255), (self.w // 2, ry - 30), (self.w // 2, ry + rect_h + 30), 3)

        # Timing History (Visual jitter bars)
        for off in self.offsets:
            # Map -500ms to 500ms onto the bar
            off_pos = (off / 500.0) # -1.0 to 1.0
            off_x = self.w // 2 + int(off_pos * (rect_w / 2))
            if rx <= off_x <= rx + rect_w:
                pygame.draw.line(self.screen, (*COLOR_ACCENT, 120), (off_x, ry + 2), (off_x, ry + rect_h - 2), 2)

        # Hit Flash
        flash_age = time.perf_counter() - self.last_hit_time
        if flash_age < 0.2:
            alpha = int(255 * (1 - flash_age / 0.2))
            s = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            pygame.draw.rect(s, (*COLOR_ACCENT, alpha // 10), (0, 0, self.w, self.h))
            self.screen.blit(s, (0, 0))

        # Stats & Message
        msg_surf = self.font.render(self.message, True, COLOR_TEXT_PRIMARY)
        self.screen.blit(msg_surf, msg_surf.get_rect(center=(self.w // 2, ry + self._s(120))))
        
        avg_hint = _t("avg_offset") + ": " + (f"{sum(self.offsets)/len(self.offsets):+.1f}ms" if self.offsets else "N/A")
        av_surf = self.small_font.render(avg_hint, True, COLOR_ACCENT)
        self.screen.blit(av_surf, av_surf.get_rect(center=(self.w // 2, ry + self._s(160))))

        hint_txt = _t("cal_hint")
        h_surf = self.small_font.render(hint_txt, True, (150, 150, 150))
        self.screen.blit(h_surf, h_surf.get_rect(center=(self.w // 2, self.h - self._s(50))))
