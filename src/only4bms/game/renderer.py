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
            cr = int(lane_w * 0.4)
            surf = pygame.Surface((lane_w, lane_w), pygame.SRCALPHA)
            # 1. Circular Shadow
            shadow_color = (0, 0, 0, 160)
            pygame.draw.circle(surf, shadow_color, (lane_w // 2, lane_w // 2 + 2), cr)
            # 2. Main Body
            pygame.draw.circle(surf, (*color, 255), (lane_w // 2, lane_w // 2), cr)
            # 3. Top highlight
            pygame.draw.circle(surf, (255, 255, 255, 160), (lane_w // 2, lane_w // 2 - 1), cr - 1, 3)
            # 4. Inner small circle
            pygame.draw.circle(surf, (255, 255, 255, 110), (lane_w // 2, lane_w // 2), cr // 3, 2)
            self.circle_note_cache[key] = Texture.from_surface(self.renderer, surf)
        return self.circle_note_cache[key]

    def _get_bar_note_texture(self, color, alpha, lane_w):
        key = (color, alpha, lane_w)
        if key not in self.bar_note_cache:
            bw, bh = int(lane_w * 0.8), int(self._s(NOTE_H) * 1.5)
            surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
            
            # Draw the bar head primitives onto this surface ONCE
            pygame.draw.rect(surf, (0, 0, 0, int(180 * (alpha/255))), (0, bh - 4, bw, 4))
            pygame.draw.rect(surf, (*color, alpha), (0, 0, bw, bh - 2))
            pygame.draw.rect(surf, (255, 255, 255, int(150 * (alpha/255))), (0, 0, bw, 2))
            pygame.draw.line(surf, (255, 255, 255, int(110 * (alpha/255))), (0, bh // 2), (bw, bh // 2))
            
            self.bar_note_cache[key] = Texture.from_surface(self.renderer, surf)
        return self.bar_note_cache[key]
        
    def _get_ln_body_texture(self, color, alpha, lane_w):
        key = (color, alpha, lane_w)
        if key not in self.ln_body_cache:
            # We create a 1-pixel high texture that can be stretched by the renderer.blit destination rect
            # This completely avoids drawing rectangles/lines every frame
            surf = pygame.Surface((lane_w, 1), pygame.SRCALPHA)
            b_alpha = int(alpha * 0.6)
            body_margin = int(lane_w * 0.12)
            
            # Fill center
            pygame.draw.rect(surf, (*color, b_alpha), (body_margin, 0, lane_w - body_margin * 2, 1))
            # Draw borders
            pygame.draw.rect(surf, (*color, alpha), (body_margin, 0, 1, 1))
            pygame.draw.rect(surf, (*color, alpha), (lane_w - body_margin - 1, 0, 1, 1))
            
            self.ln_body_cache[key] = Texture.from_surface(self.renderer, surf)
        return self.ln_body_cache[key]

    def _get_bar_effect_texture(self, color, lane_w):
        key = (color, lane_w)
        if key not in self.bar_effect_cache:
            base_r = self._s(50)
            bw = int(lane_w * 0.8) + base_r * 2
            bh = self._s(15 + base_r // 6)
            surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
            pygame.draw.rect(surf, (*color, 255), (0, 0, bw, bh), width=self._s(3), border_radius=self._s(4))
            core_w = int(lane_w * 0.8); core_h = max(1, bh // 3)
            pygame.draw.rect(surf, (255, 255, 255, 255), (base_r, (bh - core_h) // 2, core_w, core_h), border_radius=self._s(2))
            self.bar_effect_cache[key] = Texture.from_surface(self.renderer, surf)
        return self.bar_effect_cache[key]

    def _get_circle_effect_texture(self, color):
        key = color
        if key not in self.circle_effect_cache:
            base_r = self._s(50)
            surf = pygame.Surface((base_r * 2, base_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*color, 255), (base_r, base_r), base_r, self._s(3))
            core_r = max(1, base_r // 2)
            pygame.draw.circle(surf, (255, 255, 255, 255), (base_r, base_r), core_r)
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

    def _ensure_lane_bg_texture(self, lane_w):
        if self.lane_bg_texture and self.lane_bg_texture.width == lane_w * NUM_LANES:
            return
        
        ltw = lane_w * NUM_LANES
        surf = pygame.Surface((ltw + 4, self.height), pygame.SRCALPHA)
        # Boundaries (lx[0]-2 to lx[0]+ltw+2) -> relative (0 to ltw+4)
        pygame.draw.rect(surf, (60, 60, 60, 100), (0, 0, ltw + 4, self.height), 2)
        
        # Lanes and Dividers
        for i in range(NUM_LANES):
            lx_rel = i * lane_w + 2
            # Lane BG (use LANE_BG_ALPHA from constants)
            pygame.draw.rect(surf, (30, 30, 30, LANE_BG_ALPHA), (lx_rel, 0, lane_w, self.height))
            # Divider
            pygame.draw.line(surf, (60, 60, 60, 100), (lx_rel + lane_w, 0), (lx_rel + lane_w, self.height))
            
        self.lane_bg_texture = Texture.from_surface(self.renderer, surf)
        self.note_head_bw = int(lane_w * 0.8)
        self.note_head_bh = int(self.note_h * 1.5)

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
        ltw = game_state['lane_total_w']
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
            self._ensure_lane_bg_texture(lane_w)
            self.lane_bg_texture.alpha = int(255 * fade_mult)
            self.renderer.blit(self.lane_bg_texture, pygame.Rect(lx[0] - 2, 0, ltw + 4, self.height))

            # Active Lane Highlights
            highlight_alpha = int(LANE_BG_ALPHA * fade_mult * 0.25) # Subtle brightness boost
            self.renderer.draw_color = (100, 100, 120, highlight_alpha)
            for i in range(NUM_LANES):
                if pressed[i]:
                    self.renderer.fill_rect((lx[i], 0, lane_w, self.height))

            # Hit Zone
            self.renderer.draw_color = (0, 0, 0, int(150 * fade_mult))
            self.renderer.fill_rect((lx[0], hit_y, ltw, self.height - hit_y))
            # Judgment line sits ABOVE hit_y (bottom edge at hit_y)
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

            if j_text and current_time - j_timer < 500:
                dt = current_time - j_timer
                alpha = int(max(0, 255 * (1 - dt / 500)) * fade_mult)
                if alpha > 0:
                    tex = self._get_text_texture(j_text, False, j_color)
                    tex.alpha = alpha
                    scale = get_bounce(j_timer)
                    tw, th = int(tex.width * scale), int(tex.height * scale)
                    self.renderer.blit(tex, pygame.Rect(lx[0] + ltw // 2 - tw // 2, self.height // 2 - self._s(70) - th // 2, tw, th))


                    # FAST / SLOW Indicator (Only for Player 1)
                    if not is_opponent:
                        j_err = game_state.get('judgment_err', 0)
                        j_key = game_state.get('judgment_key', '')
                        if j_key in ("GREAT", "GOOD") and alpha > 50:
                            err_text = _t("fast") if j_err < 0 else _t("slow")
                            err_color = (100, 200, 255) if j_err < 0 else (255, 150, 50)
                            err_tex = self._get_text_texture(err_text, True, err_color, size_override=self._s(20))
                            err_tex.alpha = alpha
                            self.renderer.blit(err_tex, pygame.Rect(lx[0] + ltw // 2 - err_tex.width // 2, self.height // 2 - self._s(30), err_tex.width, err_tex.height))

            # Jitter Bar (Distribution) - Only for Player 1, rendered independently of judgment text
            if not is_opponent:
                jitter = game_state.get('jitter_history', [])
                if jitter:
                    self._draw_jitter_bar(lx[0], self.height // 2 - self._s(10), ltw, jitter, current_time)

            # Combo - Only for Player 1
            if not is_opponent:
                c_timer = game_state.get('combo_timer', 0)
                if comb > 0 and current_time - c_timer < 500:
                    dt = current_time - c_timer
                    alpha = int(max(0, 255 * (1 - dt / 500)) * fade_mult)
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

            skin_obj = self._get_note_skin(skin_id, False)
            if skin_obj:
                skin_obj.render_effect(self, eff, tx, ty, lane_w)
            elif note_type == 0: # ── Bar Effect ──
                tex = self._get_bar_effect_texture(eff['color'], lane_w)
                tex.alpha = eff['alpha']
                bw = int(lane_w * 0.8) + r * 2
                bh = self._s(15 + r // 6)
                self.renderer.blit(tex, pygame.Rect(tx - bw // 2, ty - bh // 2, bw, bh))
                
            else: # ── Circle Effect ──
                tex = self._get_circle_effect_texture(eff['color'])
                tex.alpha = eff['alpha']
                self.renderer.blit(tex, pygame.Rect(tx - r, ty - r, r*2, r*2))
        effects_list[:] = alive


    def draw_result(self, stats, current_time):
        def calc_score(judgs):
            if not judgs: return 0
            return judgs["PERFECT"] * 1000 + judgs["GREAT"] * 500 + judgs["GOOD"] * 200

        def calc_ex_score(judgs):
            if not judgs: return 0
            return judgs["PERFECT"] * 2 + judgs["GREAT"] * 1
            
        score_h = calc_score(stats['judgments'])
        ex_h = calc_ex_score(stats['judgments'])
        max_ex = stats.get('total_notes', 1) * 2
        ratio_h = min(1.0, ex_h / max_ex)

        # Background tint
        self.renderer.draw_color = (10, 10, 20, 240)
        self.renderer.fill_rect((0, 0, self.width, self.height))

        # ── Statistics Panel (Left) ──
        p1_x = self._sx(50)
        y = self._s(100)
        
        # Song Info
        title_surf = self._get_text_texture(stats['title'], True, (255, 255, 255), size_override=self._s(28))
        title_surf.alpha = 255
        self.renderer.blit(title_surf, pygame.Rect(p1_x, y, title_surf.width, title_surf.height))
        y += self._s(50)

        # Judgments List
        y_save = y
        for key in JUDGMENT_ORDER:
            color = JUDGMENT_DEFS[key]["color"]
            text = self._get_text_texture(f"{key:<10} {stats['judgments'][key]:>4}", False, color, size_override=self._s(22))
            text.alpha = 255
            self.renderer.blit(text, pygame.Rect(p1_x, y, text.width, text.height))
            y += self._s(32)
        
        y += self._s(20)
        score_text = self._get_text_texture(_t("score_label").format(val=f"{score_h:,}"), True, (255, 255, 0), size_override=self._s(32))
        score_text.alpha = 255
        self.renderer.blit(score_text, pygame.Rect(p1_x, y, score_text.width, score_text.height))
        y += self._s(40)
        ex_text = self._get_text_texture(_t("ex_label").format(ex=ex_h, max=max_ex, pct=f"{ratio_h*100:.1f}"), False, (200, 200, 255), size_override=self._s(20))
        ex_text.alpha = 255
        self.renderer.blit(ex_text, pygame.Rect(p1_x, y, ex_text.width, ex_text.height))

        # ── Analytics Graphs (Timing Scatter Plot) ──
        if True:
            graph_x = self._sx(400)
            graph_y = self._s(100)
            graph_w = self.width - graph_x - self._sx(50)
            graph_h = self.height - graph_y - self._s(100) # Enlarged to fill space
            
            # Timing Scatter Plot Box (Semi-transparent)
            self.renderer.draw_color = (20, 20, 30, 150) # Darker, semi-transparent
            self.renderer.fill_rect((graph_x, graph_y, graph_w, graph_h))
            
            # Border
            self.renderer.draw_color = (255, 255, 255, 40)
            self.renderer.draw_rect((graph_x, graph_y, graph_w, graph_h))
            
            # Perfect Line
            self.renderer.draw_color = (255, 255, 255, 60)
            self.renderer.draw_line((graph_x, graph_y + graph_h // 2), (graph_x + graph_w, graph_y + graph_h // 2))
            
            # Label
            t_label = self._get_text_texture(_t("hit_timing"), True, (200, 200, 200), size_override=self._s(16))
            t_label.alpha = 180
            self.renderer.blit(t_label, pygame.Rect(graph_x + self._sx(10), graph_y + self._s(5), t_label.width, t_label.height))

            max_time = stats.get('max_time', 1)
            max_err = 200 # Fixed scale +/- 200ms
            
            def draw_hits(history, color_scale=1.0, size=2):
                for t_hit, err, key in history:
                    if key == "MISS": continue
                    gx = graph_x + int((t_hit / max_time) * graph_w)
                    gy = graph_y + graph_h // 2 + int((err / max_err) * (graph_h // 2))
                    if graph_x <= gx < graph_x + graph_w and graph_y <= gy < graph_y + graph_h:
                        c = JUDGMENT_DEFS[key]["color"]
                        self.renderer.draw_color = (c[0], c[1], c[2], int(200 * color_scale))
                        self.renderer.fill_rect((gx - size//2, gy - size//2, size, size))

            draw_hits(stats.get('hit_history', []))

        f_info = self._get_text_texture(_t("return_hint"), False, (150, 150, 150), size_override=self._s(18))
        f_info.alpha = 255
        self.renderer.blit(f_info, pygame.Rect(self.width // 2 - f_info.width // 2, self.height - self._s(40), f_info.width, f_info.height))

        # ── Challenge Toast Rendering ──
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
