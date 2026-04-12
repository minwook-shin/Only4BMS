import math
import time
import random
import pygame
from pygame._sdl2.video import Texture
from only4bms.i18n import get as _t, FONT_NAME, FONT_SIZES
from only4bms import i18n as _i18n
from .constants import (
    BASE_W, BASE_H, JUDGMENT_DEFS, HIT_ZONE_VISUAL_H, GREAT_ZONE_VISUAL_H,
    HIT_ZONE_PULSE_PERIOD, HIT_ZONE_ALPHA_MIN, HIT_ZONE_ALPHA_RANGE,
    LANE_BG_ALPHA, NUM_LANES, HIT_Y, NOTE_H, JUDGMENT_ORDER,
    EFFECT_EXPAND_SPEED, EFFECT_FADE_SPEED
)


class GameRenderer:
    def __init__(self, renderer, window_size, settings):
        self.renderer = renderer
        self.width, self.height = window_size
        self.settings = settings
        self.sx = self.width / BASE_W
        self.sy = self.height / BASE_H
        
        self.font = _i18n.font("hud_normal", self.sy)
        self.bold_font = _i18n.font("hud_bold", self.sy, bold=True)
        
        self.bga_texture = None # Video frame or static image
        self.bga_last_surface = None # Track the last surface we uploaded to avoid redundant updates
        self.bga_updated_once = False
        
        # --- Cache for performance ---
        self.bar_note_cache = {}    # (color, alpha, lane_w) -> Texture
        self.ln_body_cache = {}     # (color, alpha, lane_w) -> Texture
        self.circle_note_cache = {} # (color, alpha, size) -> Texture
        self.bar_effect_cache = {}  # (color, alpha, r) -> Texture
        self.circle_effect_cache = {} # (color, alpha, r) -> Texture
        self.text_cache = {} # (text, font_id, color, alpha) -> Texture
        self.font_obj_cache = {} # (size, bold) -> Font
        self.jitter_texture = None # Pre-rendered jitter bar
        self.jitter_gen = -1 # Track jitter history generation for cache invalidation
        
        # --- Pre-calculated values ---
        self.note_h = self._s(NOTE_H)
        self.hit_y = self._s(HIT_Y)
        self.hit_y_minus_note_h = self.hit_y - self.note_h
        self.h_base_h_ratio = self.height / BASE_H
        self.lane_bg_texture = None # Pre-rendered static lane background
        self.note_head_bw = 0
        self.note_head_bh = 0
        
        
    def _s(self, v): return int(v * self.sy)
    def _sx(self, v): return int(v * self.sx)

    def _get_circle_note_texture(self, color, lane_w):
        key = (color, lane_w)
        if key not in self.circle_note_cache:
            cr  = int(lane_w * 0.42)
            cx  = lane_w // 2
            surf = pygame.Surface((lane_w, lane_w), pygame.SRCALPHA)
            # Outer soft glow rings
            pygame.draw.circle(surf, (*color, 28), (cx, cx), cr + max(2, self._s(4)))
            pygame.draw.circle(surf, (*color, 55), (cx, cx), cr + max(1, self._s(2)))
            # Drop shadow (offset down slightly)
            pygame.draw.circle(surf, (0, 0, 0, 150), (cx, cx + max(1, self._s(2))), cr)
            # Main body
            pygame.draw.circle(surf, (*color, 255), (cx, cx), cr)
            # Inner ring (darker rim for depth)
            inner_c = tuple(max(0, int(c * 0.65)) for c in color)
            pygame.draw.circle(surf, (*inner_c, 210), (cx, cx), cr - max(1, self._s(1)), max(1, self._s(2)))
            # Specular highlight lobe (upper-left)
            spec_r  = max(2, cr // 3)
            spec_cx = cx - cr // 4
            spec_cy = cx - cr // 3
            pygame.draw.circle(surf, (255, 255, 255, 150), (spec_cx, spec_cy), spec_r)
            pygame.draw.circle(surf, (255, 255, 255, 210), (spec_cx, spec_cy), max(1, spec_r // 2))
            # Center pip
            pygame.draw.circle(surf, (255, 255, 255, 110), (cx, cx), max(2, cr // 5), max(1, self._s(1)))
            self.circle_note_cache[key] = Texture.from_surface(self.renderer, surf)
        return self.circle_note_cache[key]

    def _get_bar_note_texture(self, color, alpha, lane_w):
        key = (color, alpha, lane_w)
        if key not in self.bar_note_cache:
            bw  = int(lane_w * 0.88)
            bh  = max(4, int(self._s(NOTE_H) * 1.5))
            surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
            af  = alpha / 255

            # Two-tone body: bright top half, darker bottom half
            half  = bh // 2 + 1
            top_c = tuple(min(255, int(c * 1.2)) for c in color)
            bot_c = tuple(max(0,   int(c * 0.75)) for c in color)
            pygame.draw.rect(surf, (*top_c, alpha), (0, 0, bw, half))
            pygame.draw.rect(surf, (*bot_c, alpha), (0, half, bw, bh - half))

            # White top rim
            rim_h = max(2, self._s(2))
            pygame.draw.rect(surf, (255, 255, 255, int(220 * af)), (0, 0, bw, rim_h))

            # Shine highlight (upper-left semi-transparent bright area)
            shine_w = bw // 3
            shine_h = half - rim_h
            if shine_w > 0 and shine_h > 0:
                sh_surf = pygame.Surface((shine_w, shine_h), pygame.SRCALPHA)
                sh_surf.fill((255, 255, 255, int(55 * af)))
                surf.blit(sh_surf, (0, rim_h))

            # Center accent line
            pygame.draw.rect(surf, (255, 255, 255, int(45 * af)), (0, bh // 3, bw, max(1, self._s(1))))

            # Bottom shadow line
            shad_h = max(2, self._s(2))
            pygame.draw.rect(surf, (0, 0, 0, int(150 * af)), (0, bh - shad_h, bw, shad_h))

            self.bar_note_cache[key] = Texture.from_surface(self.renderer, surf)
        return self.bar_note_cache[key]
        
    def _get_ln_body_texture(self, color, alpha, lane_w):
        key = (color, alpha, lane_w)
        if key not in self.ln_body_cache:
            # 1px tall — stretched by renderer.blit for performance
            surf = pygame.Surface((lane_w, 1), pygame.SRCALPHA)
            margin  = int(lane_w * 0.14)
            inner_w = lane_w - margin * 2
            mid     = lane_w // 2

            # Dim fill body
            pygame.draw.rect(surf, (*color, int(alpha * 0.45)), (margin, 0, inner_w, 1))
            # Center bright stripe (inner third)
            cw = max(1, inner_w // 3)
            pygame.draw.rect(surf, (*color, int(alpha * 0.85)), (mid - cw // 2, 0, cw, 1))
            # White center highlight line
            pygame.draw.rect(surf, (255, 255, 255, int(alpha * 0.35)), (mid - 1, 0, 2, 1))
            # Bright edge glow lines
            pygame.draw.rect(surf, (*color, alpha), (margin,          0, 1, 1))
            pygame.draw.rect(surf, (*color, alpha), (lane_w - margin - 1, 0, 1, 1))

            self.ln_body_cache[key] = Texture.from_surface(self.renderer, surf)
        return self.ln_body_cache[key]

    def _get_bar_effect_texture(self, color, lane_w):
        key = (color, lane_w)
        if key not in self.bar_effect_cache:
            # Texture is stretched by draw_effects; keep it a simple horizontal glow
            # that looks clean at any aspect ratio
            bw   = int(lane_w * 0.88)
            bh   = self._s(18)
            surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
            rr   = max(2, bh // 3)
            # Outer glow fill
            pygame.draw.rect(surf, (*color, 50), (0, 0, bw, bh), border_radius=rr)
            # Bright core (white + color blend)
            ch = max(2, bh // 3)
            cy = (bh - ch) // 2
            pygame.draw.rect(surf, (255, 255, 255, 230), (0, cy, bw, ch), border_radius=max(1, rr // 2))
            pygame.draw.rect(surf, (*color, 170),        (0, cy, bw, ch), border_radius=max(1, rr // 2))
            self.bar_effect_cache[key] = Texture.from_surface(self.renderer, surf)
        return self.bar_effect_cache[key]

    def _get_circle_effect_texture(self, color):
        key = color
        if key not in self.circle_effect_cache:
            base_r  = self._s(50)
            size    = base_r * 2
            cx      = base_r
            surf    = pygame.Surface((size, size), pygame.SRCALPHA)
            # Soft fill glow
            pygame.draw.circle(surf, (*color, 18),  (cx, cx), base_r)
            # Outer ring
            pygame.draw.circle(surf, (*color, 200), (cx, cx), base_r - self._s(2), self._s(2))
            # Mid ring
            inner_r = max(1, base_r * 2 // 3)
            pygame.draw.circle(surf, (*color, 110), (cx, cx), inner_r, self._s(2))
            # Inner ring
            inner2_r = max(1, base_r // 3)
            pygame.draw.circle(surf, (255, 255, 255, 75), (cx, cx), inner2_r, self._s(1))
            # Center flash
            pygame.draw.circle(surf, (255, 255, 255, 210), (cx, cx), max(2, base_r // 5))
            self.circle_effect_cache[key] = Texture.from_surface(self.renderer, surf)
        return self.circle_effect_cache[key]

    # ── Note Skin Plugin Access ───────────────────────────────────────────
    def _get_note_skin(self, skin_id: str, is_auto: bool):
        """Return the NoteSkinBase for skin_id, or None for default/auto."""
        if is_auto or skin_id == 'default':
            return None
        from .skins import get_skin
        return get_skin(skin_id)

    def _get_text_texture(self, text, is_bold, color, size_override=None):
        key = (text, is_bold, color, size_override)
        if key not in self.text_cache:
            if size_override:
                f_key = (size_override, is_bold)
                if f_key not in self.font_obj_cache:
                    self.font_obj_cache[f_key] = pygame.font.SysFont(FONT_NAME, size_override, bold=is_bold)
                font = self.font_obj_cache[f_key]
            else:
                font = self.bold_font if is_bold else self.font
            surf = font.render(text, True, color)
            self.text_cache[key] = Texture.from_surface(self.renderer, surf)
        return self.text_cache[key]

    def _ensure_lane_bg_texture(self, lane_w, num_lanes=None):
        if num_lanes is None:
            num_lanes = NUM_LANES
        cache_key = (lane_w, num_lanes)
        if self.lane_bg_texture and getattr(self, '_lane_bg_key', None) == cache_key:
            return

        ltw  = lane_w * num_lanes
        surf = pygame.Surface((ltw + 4, self.height), pygame.SRCALPHA)

        # Gradient lane background (dark depth + floor glow near hit zone)
        num_bands = 28
        band_h    = max(1, self.height // num_bands)
        hit_t     = self.hit_y / max(1, self.height)

        for band in range(num_bands + 1):
            yy = band * band_h
            ph = min(band_h, self.height - yy)
            if ph <= 0:
                break
            t          = yy / max(1, self.height)
            floor_prox = max(0.0, 1.0 - abs(t - hit_t) / 0.28)
            base_v     = int(12 + 6 * t)
            glow_b     = int(22 * floor_prox)
            r          = base_v + int(glow_b * 0.3)
            g          = base_v + int(glow_b * 0.5)
            b          = base_v + glow_b + 20
            for i in range(num_lanes):
                lx_rel = i * lane_w + 2
                pygame.draw.rect(surf, (r, g, b, LANE_BG_ALPHA), (lx_rel, yy, lane_w, ph))

        # Glowing cyan lane dividers
        for i in range(1, num_lanes):
            dx = i * lane_w + 2
            pygame.draw.line(surf, (0, 212, 255, 12),  (dx - 1, 0), (dx - 1, self.height))
            pygame.draw.line(surf, (0, 212, 255, 38),  (dx,     0), (dx,     self.height))
            pygame.draw.line(surf, (0, 212, 255, 12),  (dx + 1, 0), (dx + 1, self.height))

        # Outer border glow
        pygame.draw.line(surf, (0, 212, 255, 75), (1, 0),       (1,       self.height))
        pygame.draw.line(surf, (0, 212, 255, 38), (0, 0),       (0,       self.height))
        pygame.draw.line(surf, (0, 212, 255, 75), (ltw + 2, 0), (ltw + 2, self.height))
        pygame.draw.line(surf, (0, 212, 255, 38), (ltw + 3, 0), (ltw + 3, self.height))

        self.lane_bg_texture = Texture.from_surface(self.renderer, surf)
        self._lane_bg_key = cache_key
        self.note_head_bw = int(lane_w * 0.8)
        self.note_head_bh = int(self.note_h * 1.5)

    def _ensure_pressed_lane_texture(self, lane_w):
        """Gradient glow rising from hit zone when a lane key is held."""
        if getattr(self, '_pressed_lane_key', None) == lane_w:
            return self._pressed_lane_tex
        surf     = pygame.Surface((lane_w, self.height), pygame.SRCALPHA)
        num_bands = 32
        band_h    = max(1, self.height // num_bands)
        for band in range(num_bands + 1):
            yy = band * band_h
            ph = min(band_h, self.height - yy)
            if ph <= 0:
                break
            if yy >= self.hit_y:
                dist_down = (yy - self.hit_y) / max(1, self.height - self.hit_y)
                alpha     = max(0, int(28 * (1.0 - dist_down)))
            else:
                dist_up = (self.hit_y - yy) / max(1, self.hit_y)
                alpha   = max(0, int(60 * (1.0 - dist_up ** 0.6)))
            if alpha > 0:
                pygame.draw.rect(surf, (50, 160, 255, alpha), (0, yy, lane_w, ph))
        self._pressed_lane_tex = Texture.from_surface(self.renderer, surf)
        self._pressed_lane_key = lane_w
        return self._pressed_lane_tex

    def draw_playing(self, current_time, game_state):
        """
        game_state keys:
        - lane_x (list of x positions)
        - notes (list of notes)
        - lane_pressed (list of bool)
        - judgments (dict)
        - combo (int)
        - judgment_text (str)
        - judgment_color (tuple)
        - judgment_timer (int)
        - lane_total_w (int)
        - speed (float)
        - hw_mult (float)
        """
        lx = game_state['lane_x']
        notes = game_state['notes']
        pressed = game_state['lane_pressed']
        judgments = game_state['judgments']
        comb = game_state['combo']
        j_text = game_state['judgment_text']
        j_color = game_state['judgment_color']
        j_timer = game_state['judgment_timer']
        ltw = game_state['lane_total_w']
        spd = game_state['speed']
        hw = game_state['hw_mult']
        note_type = game_state['note_type'] # Already pre-fetched in rhythm_game
        note_skin = game_state.get('note_skin', 'default')  # 'default' or 'gold'
        current_visual_time = game_state.get('current_visual_time', current_time)
        lane_w = lx[1] - lx[0] if len(lx) > 1 else self._sx(75)
        note_h = self.note_h
        hit_y = self.hit_y

        # Judgment Pulse (Halved thickness for precision)
        perf_h = max(2, self._s(int(HIT_ZONE_VISUAL_H * hw // 2)))
        great_h = max(2, self._s(int(GREAT_ZONE_VISUAL_H * hw // 2)))
        pulse = (math.sin(current_time / HIT_ZONE_PULSE_PERIOD) + 1) / 2
        hit_alpha = int(HIT_ZONE_ALPHA_MIN + pulse * HIT_ZONE_ALPHA_RANGE)

        # Lane boundaries, BG, Hit Zone, and HUD text (Combo/Judgment)
        fade_mult = 1.0
        passed_time = game_state.get('all_notes_passed_time')
        if passed_time is not None:
            elapsed = current_time - passed_time
            fade_mult = max(0.0, 1.0 - elapsed / 500.0) # 500ms fade duration

        if fade_mult > 0:
            # Pre-rendered Lane Background
            self._ensure_lane_bg_texture(lane_w, len(lx))
            self.lane_bg_texture.alpha = int(255 * fade_mult)
            self.renderer.blit(self.lane_bg_texture, pygame.Rect(lx[0] - 2, 0, ltw + 4, self.height))

            # Skin ambient glow — drawn in the side panels, outside the lane area
            _skin_obj = self._get_note_skin(note_skin, False)
            if _skin_obj is not None:
                _skin_obj.draw_lane_ambient(self, lx[0], lx[0] + ltw, current_time, fade_mult)

            # Active Lane Highlights — gradient glow rising from hit zone
            for i in range(len(lx)):
                if i < len(pressed) and pressed[i]:
                    tex = self._ensure_pressed_lane_texture(lane_w)
                    tex.alpha = int(255 * fade_mult)
                    self.renderer.blit(tex, pygame.Rect(lx[i], 0, lane_w, self.height))

            # Hit Zone — dark floor below line
            self.renderer.draw_color = (0, 0, 0, int(150 * fade_mult))
            self.renderer.fill_rect((lx[0], hit_y, ltw, self.height - hit_y))
            # Judgment line — red (original style)
            j_alpha = int(hit_alpha * fade_mult)
            self.renderer.draw_color = (255, 40, 40, j_alpha)
            self.renderer.fill_rect((lx[0], hit_y - perf_h, ltw, perf_h))
            self.renderer.draw_color = (255, 80, 80, int(min(255, hit_alpha + 150) * fade_mult))
            self.renderer.draw_rect((lx[0], hit_y - perf_h, ltw, perf_h))

            # ── Measure / Bar Lines with Speed Change Indicators ──
            measures = game_state.get('measures', [])
            if measures:
                last_bpm = None  # Track BPM of previous measure
                for m_data in measures:
                    mv_time = m_data['visual_time_ms']
                    td = mv_time - current_visual_time
                    my = hit_y - td * spd
                    
                    if my < 0 or my > self.height:
                        last_bpm = m_data.get('bpm')
                        continue
                        
                    # Color based on BPM change (Speed Change Indicator)
                    curr_bpm = m_data.get('bpm')
                    color = (130, 130, 150, int(120 * fade_mult)) # Default Gray
                    
                    if last_bpm is not None and curr_bpm is not None:
                        if curr_bpm > last_bpm + 0.1:   # Faster -> RED
                            color = (255, 60, 60, int(220 * fade_mult))
                        elif curr_bpm < last_bpm - 0.1: # Slower -> BLUE
                            color = (60, 100, 255, int(220 * fade_mult))
                    
                    last_bpm = curr_bpm
                    
                    self.renderer.draw_color = color
                    # Standard measure line (white/gray horizontal line)
                    # We use fill_rect for a thicker line (2-3px) to improve visibility
                    line_h = max(2, self._s(2))
                    self.renderer.fill_rect((lx[0], int(my), ltw, line_h))

            # Judgment / Combo Text
            is_opponent = game_state.get('is_opponent', False)
            def get_bounce(timer, duration=200):
                elapsed = current_time - timer
                if elapsed < 0 or elapsed > duration: return 1.0
                t = elapsed / duration
                return 1.4 - 0.4 * (1 - (1 - t)**2)

            _show_j_text  = self.settings.get('show_judgment_text', 1) != 0
            _show_fast_slow = self.settings.get('show_fast_slow', 1) != 0
            _show_jitter  = self.settings.get('show_jitter_bar', 1) != 0
            _show_combo   = self.settings.get('show_combo', 1) != 0

            if _show_j_text and j_text and current_time - j_timer < 500:
                dt = current_time - j_timer
                alpha = min(255, int(max(0, 255 * (1 - dt / 500)) * fade_mult))
                if alpha > 0:
                    tex = self._get_text_texture(j_text, False, j_color)
                    tex.alpha = alpha
                    scale = get_bounce(j_timer)
                    tw, th = int(tex.width * scale), int(tex.height * scale)
                    jx = lx[0] + ltw // 2 - tw // 2
                    jy = self.height // 2 - self._s(70) - th // 2
                    self.renderer.blit(tex, pygame.Rect(jx, jy, tw, th))

                    # FAST / SLOW Indicator (Only for Player 1)
                    if _show_fast_slow and not is_opponent:
                        j_err = game_state.get('judgment_err', 0)
                        j_key = game_state.get('judgment_key', '')
                        if j_key in ("GREAT", "GOOD") and alpha > 50:
                            err_text = _t("fast") if j_err < 0 else _t("slow")
                            err_color = (100, 200, 255) if j_err < 0 else (255, 150, 50)
                            err_tex = self._get_text_texture(err_text, True, err_color, size_override=self._s(20))
                            err_tex.alpha = alpha
                            self.renderer.blit(err_tex, pygame.Rect(lx[0] + ltw // 2 - err_tex.width // 2, self.height // 2 - self._s(30), err_tex.width, err_tex.height))

            # Jitter Bar (Distribution) - Only for Player 1, rendered independently of judgment text
            if _show_jitter and not is_opponent:
                jitter = game_state.get('jitter_history', [])
                if jitter:
                    self._draw_jitter_bar(lx[0], self.height // 2 - self._s(10), ltw, jitter, current_time)

            # Combo - Only for Player 1
            if _show_combo and not is_opponent:
                c_timer = game_state.get('combo_timer', 0)
                if comb > 0 and current_time - c_timer < 500:
                    dt = current_time - c_timer
                    alpha = min(255, int(max(0, 255 * (1 - dt / 500)) * fade_mult))
                    if alpha > 0:
                        c_tex = self._get_text_texture(str(comb), True, (255, 255, 255))
                        c_tex.alpha = alpha
                        scale = get_bounce(c_timer, 150)
                        tw, th = int(c_tex.width * scale), int(c_tex.height * scale)
                        self.renderer.blit(c_tex, pygame.Rect(lx[0] + ltw // 2 - tw // 2, self.height // 2 + self._s(20) - th // 2, tw, th))
            # Speed Indicator (Player side only)
            if not is_opponent:
                speed_val = game_state.get('speed', 1.0) / self.h_base_h_ratio
                spd_tex = self._get_text_texture(_t("speed_display").format(val=f"{speed_val:.1f}"), False, (200, 200, 200), size_override=self._s(18))
                spd_tex.alpha = int(200 * fade_mult)
                self.renderer.blit(spd_tex, pygame.Rect(lx[0], self.height - self._s(25), spd_tex.width, spd_tex.height))

        # ── Note Rendering Optimization ──
        color = (0, 255, 255)

        def _blit_note_head(skin_obj, is_auto_, nx_, ny_, alpha_):
            if skin_obj:
                if note_type == 0:
                    tex = skin_obj.get_bar_texture(self, lane_w)
                    glow_r = self._s(4)
                    bw, bh = tex.width, tex.height
                    self.renderer.blit(tex, pygame.Rect(nx_ + (lane_w - bw) // 2, ny_ - glow_r, bw, bh))
                else:
                    tex = skin_obj.get_circle_texture(self, lane_w)
                    glow_r = self._s(8)
                    self.renderer.blit(tex, pygame.Rect(nx_ - glow_r, ny_ + note_h // 2 - tex.height // 2, tex.width, tex.height))
            else:
                if note_type == 0:
                    tex = self._get_bar_note_texture(color, alpha_, lane_w)
                    bw, bh = tex.width, tex.height
                    self.renderer.blit(tex, pygame.Rect(nx_ + (lane_w - bw) // 2, ny_ + (note_h - bh), bw, bh))
                else:
                    tex = self._get_circle_note_texture(color, lane_w)
                    tex.alpha = alpha_
                    self.renderer.blit(tex, pygame.Rect(nx_, ny_ + note_h // 2 - lane_w // 2, lane_w, lane_w))

        def _blit_ln_body(skin_obj, nx_, ey_, body_h_, alpha_):
            if skin_obj:
                tex = skin_obj.get_ln_body_texture(self, lane_w)
            else:
                tex = self._get_ln_body_texture(color, alpha_, lane_w)
            self.renderer.blit(tex, pygame.Rect(nx_, int(ey_) + note_h // 2, lane_w, body_h_))

        # 1. Render Held Long Notes first (guarantees they are drawn even if behind note_idx)
        held_lns = game_state.get('held_lns', [])
        for note in held_lns:
            if note is not None:
                is_auto = note.get('is_auto', False)
                alpha = 60 if is_auto else 255
                skin_obj = self._get_note_skin(note_skin, is_auto)
                nx, ny = lx[note['lane']], int(self.hit_y_minus_note_h)

                v_end_time = note.get('visual_end_time_ms', note.get('end_time_ms', note['time_ms']))
                etd = v_end_time - current_visual_time
                ey = self.hit_y_minus_note_h - etd * spd
                body_h = int(self.hit_y_minus_note_h - ey)
                if body_h > 0:
                    _blit_ln_body(skin_obj, nx, ey, body_h, alpha)

                _blit_note_head(skin_obj, is_auto, nx, ny, alpha)

        # 2. Main Loop from note_idx
        start_idx = game_state.get('note_idx', 0)
        held_ln_ids = [id(n) for n in held_lns if n is not None]
        for i in range(start_idx, len(notes)):
            note = notes[i]
            if 'hit' in note and id(note) not in held_ln_ids: continue
            if 'miss' in note: continue

            td = note.get('visual_time_ms', note['time_ms']) - current_visual_time
            y = self.hit_y_minus_note_h - td * spd

            if y < -note_h * 4:
                break

            if y <= self.height:
                is_auto = note.get('is_auto', False)
                alpha = 60 if is_auto else 255
                skin_obj = self._get_note_skin(note_skin, is_auto)
                nx, ny = lx[note['lane']], int(y)

                # Long Note Body
                if note.get('is_ln'):
                    v_end_time = note.get('visual_end_time_ms', note.get('end_time_ms', note['time_ms']))
                    etd = v_end_time - current_visual_time
                    ey = self.hit_y_minus_note_h - etd * spd
                    body_h = int(y - ey)
                    if body_h > 0:
                        _blit_ln_body(skin_obj, nx, ey, body_h, alpha)

                # Hit Connector (Jack)
                if not is_opponent and 'jack_prev_v_time' in note and not is_auto:
                    prev_td = note['jack_prev_v_time'] - current_visual_time
                    prev_y = int(self.hit_y_minus_note_h - prev_td * spd)
                    connector_h = int(prev_y - y)
                    if connector_h > 0:
                        c_alpha = int(100 * fade_mult)
                        if skin_obj:
                            c_tex = skin_obj.get_ln_body_texture(self, lane_w)
                            c_tex.alpha = c_alpha
                        else:
                            c_tex = self._get_ln_body_texture(color, c_alpha, lane_w)
                        self.renderer.blit(c_tex, pygame.Rect(nx + int(lane_w * 0.08), int(y) + note_h // 2, lane_w - int(lane_w * 0.16), connector_h))

                # Note Head
                _blit_note_head(skin_obj, is_auto, nx, ny, alpha)

    def _draw_jitter_bar(self, x, y, w, jitter, current_time):
        jitter_len = len(jitter)
        if jitter_len == 0: return
        
        bar_h = self._s(4)
        max_err = 200

        # Center line (Perfect)
        center_x = x + w // 2
        self.renderer.draw_color = (255, 255, 255, 100)
        self.renderer.draw_line((center_x, y - self._s(5)), (center_x, y + self._s(5)))

        # Rebuild jitter texture only when history changes
        # Use the last entry's timestamp as a cache key (changes whenever a new judgment is added)
        last_hit_t = jitter[-1][1] if isinstance(jitter[-1], tuple) else 0
        jitter_gen = (jitter_len, last_hit_t)
        if self.jitter_gen != jitter_gen:
            surf_h = bar_h * 2 + 2  # Extra height for latest point
            surf = pygame.Surface((w, surf_h), pygame.SRCALPHA)
            half_w = w // 2
            
            for i, item in enumerate(jitter):
                err, hit_t = item if isinstance(item, tuple) else (item, current_time)
                offset_x = int((err / max_err) * half_w)
                px = half_w + offset_x
                
                idx_alpha = 0.2 + 0.8 * (i / jitter_len)
                age_ms = current_time - hit_t
                if age_ms < 0: age_ms = 0
                time_alpha = max(0, 1.0 - (age_ms / 3000.0))
                alpha = int(255 * idx_alpha * time_alpha)
                if alpha <= 0: continue
                
                is_latest = (i == jitter_len - 1)
                point_h = bar_h * 2 if is_latest else bar_h
                
                if is_latest:
                    color = (255, 255, 255, 255)
                elif abs(err) < 40:
                    color = (0, 255, 255, alpha)
                elif err < 0:
                    color = (100, 200, 255, alpha)
                else:
                    color = (255, 150, 50, alpha)
                
                py = (surf_h - point_h) // 2
                pygame.draw.rect(surf, color, (px - 1, py, 2, point_h))
            
            if self.jitter_texture:
                self.jitter_texture.update(surf)
            else:
                self.jitter_texture = Texture.from_surface(self.renderer, surf)
            self.jitter_gen = jitter_gen
        
        if self.jitter_texture:
            surf_h = bar_h * 2 + 2
            self.renderer.blit(self.jitter_texture, pygame.Rect(x, y - surf_h // 2, w, surf_h))

    def draw_bga(self, current_time, bid, assets):
        tex = None
        if bid is not None:
            if bid in assets.videos:
                new_img = assets.videos[bid].get_frame(current_time)
                if new_img and new_img is not self.bga_last_surface:
                    if not self.bga_texture:
                        self.bga_texture = Texture.from_surface(self.renderer, new_img)
                    else:
                        self.bga_texture.update(new_img)
                    self.bga_last_surface = new_img
                    self.bga_updated_once = True
                tex = self.bga_texture if self.bga_updated_once else assets.textures.get(bid)
            else:
                tex = assets.textures.get(bid)
            
        if not tex and assets.cover_texture:
            tex = assets.cover_texture
            
        if tex:
            tex.alpha = 255
            # ── Optimization: Proper Centering & Scaling ──
            tw, th = tex.width, tex.height
            scale = max(self.width / tw, self.height / th)
            
            dw, dh = int(tw * scale), int(th * scale)
            dx = (self.width - dw) // 2
            dy = (self.height - dh) // 2
            
            self.renderer.blit(tex, pygame.Rect(dx, dy, dw, dh))


    def draw_score_bar(self, p1_judgs, ai_judgs):
        def get_weighted_points(judgs):
            pts = judgs["PERFECT"] * 1.0 + judgs["GREAT"] * 0.7 + judgs["GOOD"] * 0.4 - judgs["MISS"] * 1.5
            return pts

        bar_w, bar_h = self.width, self._s(15)
        diff = get_weighted_points(p1_judgs) - get_weighted_points(ai_judgs)
        ratio = 0.5 + (diff / 500.0)
        ratio = max(0.01, min(0.99, ratio))
        mid_x = int(bar_w * ratio)

        self.renderer.draw_color = (0, 120, 255, 255)
        self.renderer.fill_rect((0, 0, mid_x, bar_h))
        self.renderer.draw_color = (255, 50, 50, 255)
        self.renderer.fill_rect((mid_x, 0, bar_w - mid_x, bar_h))
        self.renderer.draw_color = (255, 255, 255, 255)
        self.renderer.fill_rect((mid_x - 2, 0, 4, bar_h))

    def draw_vertical_gauge(self, x, y, w, h, ratio, color, alpha=255):
        # BG
        self.renderer.draw_color = (40, 40, 40, int(180 * (alpha / 255)))
        self.renderer.fill_rect((x, y, w, h))
        # Fill (bottom up)
        fill_h = int(h * ratio)
        if fill_h > 0:
            self.renderer.draw_color = (*color, alpha)
            self.renderer.fill_rect((x, y + h - fill_h, w, fill_h))
        # Border
        self.renderer.draw_color = (100, 100, 100, alpha)
        self.renderer.draw_rect((x, y, w, h))

    def draw_effects(self, effects_list, lanes_x, lane_w):
        if self.settings.get('show_effects', 1) == 0:
            # Still decay alpha so effects don't linger when toggled back on
            for eff in effects_list:
                eff['alpha'] -= EFFECT_FADE_SPEED
            effects_list[:] = [e for e in effects_list if e['alpha'] > 0]
            return
        alive = []
        ty = self._s(500 - 10)  # Pre-calculate once
        for eff in effects_list:
            eff['radius'] += EFFECT_EXPAND_SPEED
            eff['alpha'] -= EFFECT_FADE_SPEED
            if eff['alpha'] <= 0:
                continue
            alive.append(eff)
            
            note_type = eff.get('note_type', 0)
            skin_id = eff.get('skin', 'default')
            r = self._s(eff['radius'])
            tx = lanes_x[eff['lane']] + lane_w // 2

            # Lane flash — universal, applies to all skins and note types
            flash_a = max(0, int((eff['alpha'] - 130) / 125.0 * 60))
            if flash_a > 0:
                self.renderer.draw_color = (*eff['color'], flash_a)
                self.renderer.fill_rect((lanes_x[eff['lane']], 0, lane_w, self.height))

            skin_obj = self._get_note_skin(skin_id, False)
            if skin_obj:
                skin_obj.render_effect(self, eff, tx, ty, lane_w)
            elif note_type == 0: # ── Bar Effect ──
                tex = self._get_bar_effect_texture(eff['color'], lane_w)
                tex.alpha = eff['alpha']
                bw = int(lane_w * 0.8) + r * 2
                bh = self._s(15) + r
                self.renderer.blit(tex, pygame.Rect(tx - bw // 2, ty - bh // 2, bw, bh))
            else: # ── Circle Effect ──
                tex = self._get_circle_effect_texture(eff['color'])
                tex.alpha = eff['alpha']
                self.renderer.blit(tex, pygame.Rect(tx - r, ty - r, r*2, r*2))
        effects_list[:] = alive


    def draw_result(self, stats, current_time):
        from only4bms.ui.components import (
            make_bg_cache as _make_bg,
            draw_glass_panel as _glass,
            C_GLOW_CYAN, C_GLOW_PURPLE,
            C_TEXT_PRIMARY, C_TEXT_SECONDARY, C_TEXT_DIM, C_BORDER_DIM,
        )

        def calc_score(judgs):
            if not judgs: return 0
            return judgs["PERFECT"] * 1000 + judgs["GREAT"] * 500 + judgs["GOOD"] * 200

        def calc_ex_score(judgs):
            if not judgs: return 0
            return judgs["PERFECT"] * 2 + judgs["GREAT"] * 1

        score_h = calc_score(stats['judgments'])
        ex_h    = calc_ex_score(stats['judgments'])
        max_ex  = stats.get('total_notes', 1) * 2
        ratio_h = min(1.0, ex_h / max_ex)

        # ── Create / reuse result Surface ──
        if not hasattr(self, '_res_surf') or self._res_surf.get_size() != (self.width, self.height):
            self._res_surf = pygame.Surface((self.width, self.height))
            self._res_bg   = _make_bg(self.width, self.height)
            self._res_tex  = None
            # Lazy fonts for result screen
            self._res_title_font = _i18n.font("select_title", self.sy, bold=True)
            self._res_score_font = _i18n.font("hud_bold",     self.sy, bold=True)
            self._res_body_font  = _i18n.font("ui_body",      self.sy)
            self._res_small_font = _i18n.font("ui_small",     self.sy)

        surf = self._res_surf
        surf.blit(self._res_bg, (0, 0))

        pad    = self._sx(40)
        top_y  = self._s(60)
        left_w = self.width // 2 - pad
        right_x = self.width // 2 + pad // 2
        right_w = self.width - right_x - pad // 2
        panel_h = self.height - top_y - self._s(55)

        # ── Left panel: Stats ──
        left_rect = pygame.Rect(pad, top_y, left_w, panel_h)
        _glass(surf, left_rect, border_color=(*C_GLOW_CYAN, 75), radius=14, fill_alpha=12)

        cx = pad + self._sx(18)
        y  = top_y + self._s(18)

        # Song title
        title = stats.get('title', '???')
        max_title_w = left_w - self._sx(36)
        if self._res_title_font.size(title)[0] > max_title_w:
            while self._res_title_font.size(title + "...")[0] > max_title_w and len(title) > 1:
                title = title[:-1]
            title += "..."
        title_s = self._res_title_font.render(title, True, C_TEXT_PRIMARY)
        surf.blit(title_s, (cx, y))
        y += title_s.get_height() + self._s(6)

        # Divider
        dw  = left_w - self._sx(36)
        div = pygame.Surface((dw, 1), pygame.SRCALPHA)
        for x in range(dw):
            t = 1.0 - abs(x - dw / 2) / (dw / 2 + 1)
            div.set_at((x, 0), (*C_GLOW_CYAN, int(50 * t)))
        surf.blit(div, (cx, y))
        y += self._s(14)

        # Judgment rows
        for key in JUDGMENT_ORDER:
            color = JUDGMENT_DEFS[key]["color"]
            count = stats['judgments'][key]
            pygame.draw.rect(surf, color, pygame.Rect(cx, y + self._s(5), self._sx(3), self._s(14)), border_radius=1)
            key_s   = self._res_body_font.render(key, True, color)
            count_s = self._res_body_font.render(str(count), True, C_TEXT_PRIMARY)
            surf.blit(key_s,   (cx + self._sx(10), y))
            surf.blit(count_s, (left_rect.right - count_s.get_width() - self._sx(18), y))
            y += self._s(28)

        y += self._s(14)

        # Score
        score_txt = _t("score_label").format(val=f"{score_h:,}")
        score_s   = self._res_score_font.render(score_txt, True, (255, 215, 50))
        surf.blit(score_s, (cx, y))
        y += score_s.get_height() + self._s(8)

        # EX Score
        ex_txt = _t("ex_label").format(ex=ex_h, max=max_ex, pct=f"{ratio_h*100:.1f}")
        ex_s   = self._res_small_font.render(ex_txt, True, (200, 200, 255))
        surf.blit(ex_s, (cx, y))
        y += ex_s.get_height() + self._s(12)

        # EX ratio bar
        bar_w = left_w - self._sx(36)
        bar_h = self._s(6)
        trk   = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        trk.fill((60, 55, 70, 120))
        surf.blit(trk, (cx, y))
        pygame.draw.rect(surf, (*C_BORDER_DIM[:3], 40),
                         pygame.Rect(cx, y, bar_w, bar_h), 1, border_radius=3)
        if ratio_h > 0:
            fill_w   = max(bar_h, int(bar_w * ratio_h))
            fill_col = (100, 255, 150) if ratio_h == 1.0 else C_GLOW_CYAN
            pygame.draw.rect(surf, fill_col, pygame.Rect(cx, y, fill_w, bar_h), border_radius=3)

        # ── Right panel: Timing Scatter Plot ──
        right_rect = pygame.Rect(right_x, top_y, right_w, panel_h)
        _glass(surf, right_rect, border_color=(*C_GLOW_PURPLE, 75), radius=14, fill_alpha=12)

        graph_pad = self._sx(20)
        graph_x   = right_x + graph_pad
        graph_y   = top_y + self._s(44)
        graph_w   = right_w - graph_pad * 2
        graph_h   = panel_h - self._s(80)

        lbl_s = self._res_small_font.render(_t("hit_timing"), True, C_TEXT_SECONDARY)
        surf.blit(lbl_s, (right_x + self._sx(18), top_y + self._s(14)))

        graph_bg = pygame.Surface((graph_w, graph_h), pygame.SRCALPHA)
        graph_bg.fill((0, 0, 0, 55))
        surf.blit(graph_bg, (graph_x, graph_y))
        pygame.draw.rect(surf, (*C_BORDER_DIM[:3], 40),
                         pygame.Rect(graph_x, graph_y, graph_w, graph_h), 1, border_radius=6)

        mid_y = graph_y + graph_h // 2
        pygame.draw.line(surf, (*C_GLOW_CYAN, 40), (graph_x, mid_y), (graph_x + graph_w, mid_y), 1)

        max_time = stats.get('max_time', 1)
        max_err  = 200
        for t_hit, err, key in stats.get('hit_history', []):
            if key == "MISS": continue
            gx = graph_x + int((t_hit / max(max_time, 1)) * graph_w)
            gy = mid_y   + int((err / max_err) * (graph_h // 2))
            if graph_x <= gx < graph_x + graph_w and graph_y <= gy < graph_y + graph_h:
                c   = JUDGMENT_DEFS[key]["color"]
                dot = pygame.Surface((3, 3), pygame.SRCALPHA)
                pygame.draw.circle(dot, (*c, 200), (1, 1), 1)
                surf.blit(dot, (gx - 1, gy - 1))

        # ── Return hint ──
        hint_s = self._res_small_font.render(_t("return_hint"), True, C_TEXT_DIM)
        surf.blit(hint_s, hint_s.get_rect(centerx=self.width // 2,
                                           top=top_y + panel_h + self._s(12)))

        # ── Upload and blit ──
        if self._res_tex is None:
            self._res_tex = Texture.from_surface(self.renderer, surf)
        else:
            self._res_tex.update(surf)
        self._res_tex.alpha = 255
        self.renderer.blit(self._res_tex, pygame.Rect(0, 0, self.width, self.height))

        # ── Challenge Toast (drawn on top via renderer) ──
        if stats.get('newly_completed'):
            self.draw_challenge_toast(stats['newly_completed'], current_time)

    def draw_challenge_toast(self, newly_completed, current_time):
        """Draw a celebratory toast for newly completed challenges."""
        if not newly_completed: return
        
        # We need a start time for the transition (current_time is in ms)
        if not hasattr(self, '_toast_start_t'):
            self._toast_start_t = current_time
            
        elapsed = current_time - self._toast_start_t
        duration = 4000.0 # 4 seconds in ms
        if elapsed > duration: return
        
        # Transitions: 0-500ms fade in & slide, 500-3500ms show, 3500-4000ms fade out
        alpha = 255
        y_offset = 0
        if elapsed < 500:
            ratio = elapsed / 500.0
            alpha = int(255 * ratio)
            y_offset = int(self._s(20) * (1.0 - ratio))
        elif elapsed > 3500:
            ratio = (4000 - elapsed) / 500.0
            alpha = int(255 * max(0, ratio))
            y_offset = int(self._s(20) * (ratio - 1.0)) # optional slide out
            
        # Draw Panel
        tw, th = self._sx(350), self._s(75 + len(newly_completed) * 30)
        tx, ty = (self.width - tw) // 2, self._s(200) + y_offset
        
        self.renderer.draw_color = (30, 30, 45, int(230 * (alpha/255)))
        self.renderer.fill_rect((tx, ty, tw, th))
        self.renderer.draw_color = (255, 200, 0, alpha)
        self.renderer.draw_rect((tx, ty, tw, th))
        
        # Title
        title_txt = _t("new_challenge_toast")
        title_tex = self._get_text_texture(title_txt, True, (255, 220, 50), size_override=self._s(22))
        title_tex.alpha = alpha
        self.renderer.blit(title_tex, pygame.Rect(tx + tw // 2 - title_tex.width // 2, ty + self._s(10), title_tex.width, title_tex.height))
        
        # Challenges
        for i, ch in enumerate(newly_completed):
            ch_name = _t(f"ch_{ch['id']}_title")
            is_hidden = ch.get('hidden', False)
            ch_txt = f"{i+1}. {ch_name}"
            
            if is_hidden:
                # Golden text for hidden challenges
                ch_tex = self._get_text_texture(ch_txt, True, (255, 215, 0), size_override=self._s(18))
            else:
                ch_tex = self._get_text_texture(ch_txt, False, (255, 255, 255), size_override=self._s(18))
            ch_tex.alpha = alpha
            self.renderer.blit(ch_tex, pygame.Rect(tx + self._sx(30), ty + self._s(50 + i * 30), ch_tex.width, ch_tex.height))
            
            # [Completed] badge
            if is_hidden:
                compl_txt = f"[{_t('challenge_completed')}]"
                compl_tex = self._get_text_texture(compl_txt, True, (255, 215, 0), size_override=self._s(14))
            else:
                compl_txt = f"[{_t('challenge_completed')}]"
                compl_tex = self._get_text_texture(compl_txt, True, (0, 255, 100), size_override=self._s(14))
            compl_tex.alpha = alpha
            self.renderer.blit(compl_tex, pygame.Rect(tx + tw - compl_tex.width - self._sx(20), ty + self._s(53 + i * 30), compl_tex.width, compl_tex.height))
        
        # Skin unlock toasts — driven by skin registry, no hardcoded challenge ids
        from .skins import _registry as _skin_registry
        completed_ids = {ch['id'] for ch in newly_completed}
        sy = ty + th - self._s(25)
        for skin in _skin_registry.values():
            if skin.unlock_challenge_id and skin.unlock_challenge_id in completed_ids and skin.unlock_toast_i18n_key:
                skin_tex = self._get_text_texture(_t(skin.unlock_toast_i18n_key), True, skin.ui_color, size_override=self._s(16))
                skin_tex.alpha = alpha
                self.renderer.blit(skin_tex, pygame.Rect(tx + tw // 2 - skin_tex.width // 2, sy, skin_tex.width, skin_tex.height))
                sy -= self._s(22)  # stack toasts if multiple unlock at once
