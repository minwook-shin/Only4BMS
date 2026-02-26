import math
import time
import pygame
from pygame._sdl2.video import Texture
from .constants import (
    BASE_W, BASE_H, JUDGMENT_DEFS, HIT_ZONE_VISUAL_H, GREAT_ZONE_VISUAL_H,
    HIT_ZONE_PULSE_PERIOD, HIT_ZONE_ALPHA_MIN, HIT_ZONE_ALPHA_RANGE,
    LANE_BG_ALPHA, NUM_LANES, HIT_Y, NOTE_H, JUDGMENT_ORDER
)

class GameRenderer:
    def __init__(self, renderer, window_size, settings):
        self.renderer = renderer
        self.width, self.height = window_size
        self.settings = settings
        self.sx = self.width / BASE_W
        self.sy = self.height / BASE_H
        
        self.font = pygame.font.SysFont(None, self._s(48))
        self.bold_font = pygame.font.SysFont(None, self._s(56), bold=True)
        
        self.bga_texture = None # Video frame or static image
        self.bga_updated_once = False
        
        # --- Cache for performance ---
        self.circle_note_cache = {} # (color, alpha, size) -> Texture
        self.bar_effect_cache = {}  # (color, alpha, r) -> Texture
        self.circle_effect_cache = {} # (color, alpha, r) -> Texture
        self.text_cache = {} # (text, font_id, color, alpha) -> Texture
        self.font_obj_cache = {} # (size, bold) -> Font
        self.ai_vision_texture = None # Pre-rendered scanner static part
        
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

    def _get_bar_effect_texture(self, color, r, lane_w):
        key = (color, r, lane_w)
        if key not in self.bar_effect_cache:
            bw = int(lane_w * 0.8) + r * 2
            bh = self._s(15 + r // 6)
            surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
            pygame.draw.rect(surf, (*color, 255), (0, 0, bw, bh), width=self._s(3), border_radius=self._s(4))
            core_w = int(lane_w * 0.8); core_h = max(1, bh // 3)
            pygame.draw.rect(surf, (255, 255, 255, 255), (r, (bh - core_h) // 2, core_w, core_h), border_radius=self._s(2))
            self.bar_effect_cache[key] = Texture.from_surface(self.renderer, surf)
        return self.bar_effect_cache[key]

    def _get_circle_effect_texture(self, color, r):
        key = (color, r)
        if key not in self.circle_effect_cache:
            surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*color, 255), (r, r), r, self._s(3))
            core_r = max(1, r // 2)
            pygame.draw.circle(surf, (255, 255, 255, 255), (r, r), core_r)
            self.circle_effect_cache[key] = Texture.from_surface(self.renderer, surf)
        return self.circle_effect_cache[key]

    def _get_text_texture(self, text, is_bold, color, size_override=None):
        key = (text, is_bold, color, size_override)
        if key not in self.text_cache:
            if size_override:
                f_key = (size_override, is_bold)
                if f_key not in self.font_obj_cache:
                    self.font_obj_cache[f_key] = pygame.font.SysFont(None, size_override, bold=is_bold)
                font = self.font_obj_cache[f_key]
            else:
                font = self.bold_font if is_bold else self.font
            surf = font.render(text, True, color)
            self.text_cache[key] = Texture.from_surface(self.renderer, surf)
        return self.text_cache[key]

    def _draw_ai_vision(self, x, y, w, h, alpha):
        if not self.ai_vision_texture or self.ai_vision_texture.width != w or self.ai_vision_texture.height != h:
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            v_color = (0, 255, 255, 255)
            # Scanner Frame (Dashed)
            dash = self._s(10); gap = self._s(6)
            for dx in range(0, w, dash + gap):
                dw = min(dash, w - dx)
                pygame.draw.line(surf, v_color, (dx, 0), (dx + dw, 0), 2)
                pygame.draw.line(surf, v_color, (dx, h - 2), (dx + dw, h - 2), 2)
            for dy in range(0, h, dash + gap):
                dh = min(dash, h - dy)
                pygame.draw.line(surf, v_color, (0, dy), (0, dy + dh), 2)
                pygame.draw.line(surf, v_color, (w - 2, dy), (w - 2, dy + dh), 2)
            
            # Robot Eyes
            er = self._s(8); ex = self._s(25); ey = h // 2
            pygame.draw.circle(surf, (255, 255, 255, 255), (w // 2 - ex, ey), er // 2)
            pygame.draw.circle(surf, (0, 255, 255, 180), (w // 2 - ex, ey), er, 2)
            pygame.draw.circle(surf, (255, 255, 255, 255), (w // 2 + ex, ey), er // 2)
            pygame.draw.circle(surf, (0, 255, 255, 180), (w // 2 + ex, ey), er, 2)
            
            # Text
            ai_font = pygame.font.SysFont(None, self._s(22), bold=True)
            ai_surf = ai_font.render("AI Vision", True, (0, 255, 255, 200))
            surf.blit(ai_surf, (self._s(8), self._s(5)))
            
            if self.ai_vision_texture: self.ai_vision_texture.update(surf)
            else: self.ai_vision_texture = Texture.from_surface(self.renderer, surf)

        # Glow
        self.renderer.draw_color = (0, 100, 150, alpha // 6)
        self.renderer.fill_rect((x, y, w, h))
        
        # Frame & Eyes (Blit the pre-rendered texture)
        self.ai_vision_texture.alpha = alpha
        self.renderer.blit(self.ai_vision_texture, pygame.Rect(x, y, w, h))

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

            # AI Vision Area
            if game_state.get('is_ai'):
                vh = self._s(120)
                vy = hit_y - vh
                self._draw_ai_vision(lx[0], vy, ltw, vh, int(hit_alpha * 0.8 * fade_mult))

            # Judgment / Combo Text
            is_ai = game_state.get('is_ai', False)
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
                    
                    # Jitter Bar (Distribution) - Only for Player 1
                    if not is_ai:
                        jitter = game_state.get('jitter_history', [])
                        if jitter:
                            self._draw_jitter_bar(lx[0], self.height // 2 - self._s(10), ltw, jitter, current_time)

                    # FAST / SLOW Indicator (Only for Player 1)
                    if not is_ai:
                        j_err = game_state.get('judgment_err', 0)
                        j_key = game_state.get('judgment_key', '')
                        if j_key in ("GREAT", "GOOD") and alpha > 50:
                            err_text = "FAST" if j_err < 0 else "SLOW"
                            err_color = (100, 200, 255) if j_err < 0 else (255, 150, 50)
                            err_tex = self._get_text_texture(err_text, True, err_color, size_override=self._s(20))
                            err_tex.alpha = alpha
                            self.renderer.blit(err_tex, pygame.Rect(lx[0] + ltw // 2 - err_tex.width // 2, self.height // 2 - self._s(30), err_tex.width, err_tex.height))

            # Combo - Only for Player 1
            if not is_ai:
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
            # Speed Indicator
            speed_val = game_state.get('speed', 1.0) / self.h_base_h_ratio
            spd_tex = self._get_text_texture(f"SPEED x{speed_val:.1f}", False, (200, 200, 200), size_override=self._s(18))
            spd_tex.alpha = int(200 * fade_mult)
            self.renderer.blit(spd_tex, pygame.Rect(lx[0], self.height - self._s(25), spd_tex.width, spd_tex.height))
            
        # ── Note Rendering Optimization ──
        # 1. Render Held Long Notes first (guarantees they are drawn even if behind note_idx)
        held_lns = game_state.get('held_lns', [])
        for note in held_lns:
            if note is not None:
                # Use simplified inline drawing for held notes
                color = (0, 255, 255)
                alpha = 60 if note.get('is_auto', False) else 255
                nx, ny = lx[note['lane']], int(self.hit_y_minus_note_h)
                
                # Long Note Body for held LN
                v_end_time = note.get('visual_end_time_ms', note.get('end_time_ms', note['time_ms']))
                etd = v_end_time - current_visual_time
                ey = self.hit_y_minus_note_h - etd * spd
                body_h = int(self.hit_y_minus_note_h - ey)
                if body_h > 0:
                    b_alpha = int(alpha * 0.6)
                    self.renderer.draw_color = (*color, b_alpha)
                    body_margin = int(lane_w * 0.12)
                    self.renderer.fill_rect((nx + body_margin, int(ey) + note_h // 2, lane_w - body_margin * 2, body_h + note_h // 2))
                    self.renderer.draw_color = (*color, alpha)
                    self.renderer.draw_line((nx + body_margin, int(ey) + note_h // 2), (nx + body_margin, self.hit_y_minus_note_h + note_h // 2))
                    self.renderer.draw_line((nx + lane_w - body_margin, int(ey) + note_h // 2), (nx + lane_w - body_margin, self.hit_y_minus_note_h + note_h // 2))

                # Head
                if note_type == 0:
                    bw, bh = self.note_head_bw, self.note_head_bh
                    bx, by = nx + (lane_w - bw) // 2, ny + (note_h - bh)
                    self.renderer.draw_color = (0, 0, 0, int(180 * (alpha/255)))
                    self.renderer.fill_rect((bx, by + bh - 4, bw, 4))
                    self.renderer.draw_color = (*color, alpha)
                    self.renderer.fill_rect((bx, by, bw, bh - 2))
                    self.renderer.draw_color = (255, 255, 255, int(150 * (alpha/255)))
                    self.renderer.fill_rect((bx, by, bw, 2))
                    self.renderer.draw_color = (255, 255, 255, int(110 * (alpha/255)))
                    self.renderer.draw_line((bx, by + bh // 2), (bx + bw, by + bh // 2))
                else:
                    tex = self._get_circle_note_texture(color, lane_w)
                    tex.alpha = alpha
                    self.renderer.blit(tex, pygame.Rect(nx, ny + note_h // 2 - lane_w // 2, lane_w, lane_w))

        # 2. Main Loop from note_idx
        start_idx = game_state.get('note_idx', 0)
        held_ln_ids = [id(n) for n in held_lns if n is not None]
        for i in range(start_idx, len(notes)):
            note = notes[i]
            if 'hit' in note and id(note) not in held_ln_ids: continue
            if 'miss' in note: continue
            
            td = note.get('visual_time_ms', note['time_ms']) - current_visual_time
            y = self.hit_y_minus_note_h - td * spd
            
            # EARLY BREAK: Skip future notes far above the screen
            if y < -note_h * 4: # Buffer for long note bodies
                break
                
            if y <= self.height:
                color, is_auto = (0, 255, 255), note.get('is_auto', False)
                alpha = 60 if is_auto else 255
                nx, ny = lx[note['lane']], int(y)
                
                # Long Note Body
                if note.get('is_ln'):
                    v_end_time = note.get('visual_end_time_ms', note.get('end_time_ms', note['time_ms']))
                    etd = v_end_time - current_visual_time
                    ey = self.hit_y_minus_note_h - etd * spd
                    body_h = int(y - ey)
                    if body_h > 0:
                        b_alpha = int(alpha * 0.6)
                        self.renderer.draw_color = (*color, b_alpha)
                        body_margin = int(lane_w * 0.12)
                        self.renderer.fill_rect((nx + body_margin, int(ey) + note_h // 2, lane_w - body_margin * 2, body_h + note_h // 2))
                        self.renderer.draw_color = (*color, alpha)
                        self.renderer.draw_line((nx + body_margin, int(ey) + note_h // 2), (nx + body_margin, int(y) + note_h // 2))
                        self.renderer.draw_line((nx + lane_w - body_margin, int(ey) + note_h // 2), (nx + lane_w - body_margin, int(y) + note_h // 2))
                
                # Handling Hit Connector (Jack)
                if 'jack_prev_v_time' in note and not is_auto:
                    prev_td = note['jack_prev_v_time'] - current_visual_time
                    prev_y = int(self.hit_y_minus_note_h - prev_td * spd)
                    connector_h = int(prev_y - y)
                    if connector_h > 0:
                        # Draw faint connector (looks like a skinny LN body)
                        c_alpha = int(100 * fade_mult)
                        self.renderer.draw_color = (*color, int(c_alpha * 0.4))
                        c_margin = int(lane_w * 0.2)
                        self.renderer.fill_rect((nx + c_margin, int(y) + note_h // 2, lane_w - c_margin * 2, connector_h))
                        # Side lines for definition
                        self.renderer.draw_color = (*color, int(c_alpha * 0.6))
                        self.renderer.draw_line((nx + c_margin, int(y) + note_h // 2), (nx + c_margin, prev_y + note_h // 2))
                        self.renderer.draw_line((nx + lane_w - c_margin, int(y) + note_h // 2), (nx + lane_w - c_margin, prev_y + note_h // 2))

                # Note Head
                if note_type == 0:
                    bw, bh = self.note_head_bw, self.note_head_bh
                    bx, by = nx + (lane_w - bw) // 2, ny + (note_h - bh)
                    self.renderer.draw_color = (0, 0, 0, int(180 * (alpha/255)))
                    self.renderer.fill_rect((bx, by + bh - 4, bw, 4))
                    self.renderer.draw_color = (*color, alpha)
                    self.renderer.fill_rect((bx, by, bw, bh - 2))
                    self.renderer.draw_color = (255, 255, 255, int(150 * (alpha/255)))
                    self.renderer.fill_rect((bx, by, bw, 2))
                    self.renderer.draw_color = (255, 255, 255, int(110 * (alpha/255)))
                    self.renderer.draw_line((bx, by + bh // 2), (bx + bw, by + bh // 2))
                else:
                    tex = self._get_circle_note_texture(color, lane_w)
                    tex.alpha = alpha
                    self.renderer.blit(tex, pygame.Rect(nx, ny + note_h // 2 - lane_w // 2, lane_w, lane_w))

    def _draw_jitter_bar(self, x, y, w, jitter, current_time):
        # Bar background
        bar_h = self._s(4)
        center_x = x + w // 2
        max_err = 200 # GOOD threshold
        
        # Center line (Perfect)
        self.renderer.draw_color = (255, 255, 255, 100)
        self.renderer.draw_line((center_x, y - self._s(5)), (center_x, y + self._s(5)))
        
        # Jitter points
        for i, item in enumerate(jitter):
            err, hit_t = item if isinstance(item, tuple) else (item, current_time)
            
            # Map error to bar position
            offset_x = (err / max_err) * (w // 2)
            px = center_x + offset_x
            
            # Recency effect (Fade older points)
            # Duration shows last 2 seconds mostly, but we use the history length too
            idx_alpha = 0.2 + 0.8 * (i / len(jitter))
            # Also fade by time (last 3 seconds)
            age_ms = current_time - hit_t
            if age_ms < 0: age_ms = 0
            time_alpha = max(0, 1.0 - (age_ms / 3000.0))
            alpha = int(255 * idx_alpha * time_alpha)
            
            if alpha <= 0: continue
            
            # Special highlighting for the very last hit
            is_latest = (i == len(jitter) - 1)
            point_h = bar_h * 2 if is_latest else bar_h
            
            color = (100, 200, 255, alpha) if err < 0 else (255, 150, 50, alpha)
            if abs(err) < 40: # PERFECT threshold
                color = (0, 255, 255, alpha)
            
            if is_latest:
                # Add white flash for latest point
                color = (255, 255, 255, 255)
            
            self.renderer.draw_color = color
            self.renderer.draw_rect((px - 1, y - point_h // 2, 2, point_h))

    def draw_bga(self, current_time, bid, assets):
        tex = None
        if bid is not None:
            if bid in assets.videos:
                new_img = assets.videos[bid].get_frame(current_time)
                if new_img:
                    if not self.bga_texture:
                        self.bga_texture = Texture.from_surface(self.renderer, new_img)
                    else:
                        self.bga_texture.update(new_img)
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
        for eff in effects_list[:]:
            from .constants import EFFECT_EXPAND_SPEED, EFFECT_FADE_SPEED
            eff['radius'] += EFFECT_EXPAND_SPEED
            eff['alpha'] -= EFFECT_FADE_SPEED
            if eff['alpha'] <= 0:
                effects_list.remove(eff)
                continue
            
            note_type = eff.get('note_type', 0)
            r = self._s(eff['radius'])
            tx = lanes_x[eff['lane']] + lane_w // 2
            # Shift up by half of NOTE_H (20//2=10) to align with note head center
            ty = self._s(500 - 10) 
            
            if note_type == 0: # ── Bar Effect ──
                tex = self._get_bar_effect_texture(eff['color'], r, lane_w)
                tex.alpha = eff['alpha']
                self.renderer.blit(tex, pygame.Rect(tx - tex.width // 2, ty - tex.height // 2, tex.width, tex.height))
                
            else: # ── Circle Effect ──
                tex = self._get_circle_effect_texture(eff['color'], r)
                tex.alpha = eff['alpha']
                self.renderer.blit(tex, pygame.Rect(tx - r, ty - r, r*2, r*2))

    def _get_rank(self, score_ratio):
        if score_ratio >= 1.0: return "P"
        if score_ratio >= 0.95: return "AAA"
        if score_ratio >= 0.85: return "AA"
        if score_ratio >= 0.75: return "A"
        if score_ratio >= 0.65: return "B"
        if score_ratio >= 0.55: return "C"
        if score_ratio >= 0.45: return "D"
        return "E"

    def draw_result(self, stats):
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
        
        score_ai = calc_score(stats['ai_judgments']) if stats['mode'] == 'ai_multi' else 0
        ex_ai = calc_ex_score(stats['ai_judgments'])
        ratio_ai = min(1.0, ex_ai / max_ex)

        # Background tint
        self.renderer.draw_color = (10, 10, 20, 240)
        self.renderer.fill_rect((0, 0, self.width, self.height))

        # Title/Banner
        if stats['mode'] == 'ai_multi':
            p1_win = score_h >= score_ai
            win_txt = "YOU WIN!" if p1_win else "AI BOT WINS"
            win_color = (0, 255, 255) if p1_win else (255, 50, 50)
            bs_tex = self._get_text_texture(win_txt, True, win_color, size_override=self._s(60))
            bs_tex.alpha = 255
            self.renderer.blit(bs_tex, pygame.Rect(self.width // 2 - bs_tex.width // 2, self._s(20), bs_tex.width, bs_tex.height))
        else:
            t_tex = self._get_text_texture("RESULT", True, (255, 255, 255), size_override=self._s(50))
            t_tex.alpha = 255
            self.renderer.blit(t_tex, pygame.Rect(self.width // 2 - t_tex.width // 2, self._s(20), t_tex.width, t_tex.height))

        # ── Statistics Panel (Left) ──
        p1_x = self._sx(50)
        y = self._s(100)
        
        # Song Info
        title_surf = self._get_text_texture(stats['title'], True, (255, 255, 255), size_override=self._s(28))
        title_surf.alpha = 255
        self.renderer.blit(title_surf, pygame.Rect(p1_x, y, title_surf.width, title_surf.height))
        y += self._s(50)

        # Judgments List
        for key in JUDGMENT_ORDER:
            color = JUDGMENT_DEFS[key]["color"]
            text = self._get_text_texture(f"{key:<10} {stats['judgments'][key]:>4}", False, color, size_override=self._s(22))
            text.alpha = 255
            self.renderer.blit(text, pygame.Rect(p1_x, y, text.width, text.height))
            y += self._s(32)
        
        y += self._s(20)
        rank_h = self._get_rank(ratio_h)
        r_colors = {"P": (255, 255, 255), "AAA": (255, 255, 100), "AA": (200, 200, 200), "A": (150, 255, 150)}
        r_color = r_colors.get(rank_h, (150, 150, 150))
            
        r_tex = self._get_text_texture(rank_h, True, r_color, size_override=self._s(100))
        r_tex.alpha = 255
        self.renderer.blit(r_tex, pygame.Rect(p1_x + self._s(100), y, r_tex.width, r_tex.height))
            
        y += self._s(100)
        score_text = self._get_text_texture(f"SCORE: {score_h:,}", True, (255, 255, 0), size_override=self._s(32))
        score_text.alpha = 255
        self.renderer.blit(score_text, pygame.Rect(p1_x, y, score_text.width, score_text.height))
        y += self._s(40)
        ex_text = self._get_text_texture(f"EX: {ex_h}/{max_ex} ({ratio_h*100:.1f}%)", False, (200, 200, 255), size_override=self._s(20))
        ex_text.alpha = 255
        self.renderer.blit(ex_text, pygame.Rect(p1_x, y, ex_text.width, ex_text.height))
    
        if stats['mode'] == 'ai_multi':
            y += self._s(60)
            ai_title = self._get_text_texture("AI PERFORMANCE", True, (255, 100, 100), size_override=self._s(24))
            ai_title.alpha = 255
            self.renderer.blit(ai_title, pygame.Rect(p1_x, y, ai_title.width, ai_title.height))
            y += self._s(30)
            ai_score_txt = self._get_text_texture(f"SCORE: {score_ai:,}", False, (255, 150, 150), size_override=self._s(22))
            ai_score_txt.alpha = 255
            self.renderer.blit(ai_score_txt, pygame.Rect(p1_x, y, ai_score_txt.width, ai_score_txt.height))

        # ── Analytics Graphs (Timing Scatter Plot) ──
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
        t_label = self._get_text_texture("HIT TIMING (FAST/SLOW)", True, (200, 200, 200), size_override=self._s(16))
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

        if stats.get('ai_hit_history'):
            draw_hits(stats['ai_hit_history'], color_scale=0.4, size=1)
        draw_hits(stats.get('hit_history', []))

        f_info = self._get_text_texture("Press ENTER or ESC to Return", False, (150, 150, 150), size_override=self._s(18))
        f_info.alpha = 255
        self.renderer.blit(f_info, pygame.Rect(self.width // 2 - f_info.width // 2, self.height - self._s(40), f_info.width, f_info.height))
