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
    def __init__(self, renderer, window_size):
        self.renderer = renderer
        self.width, self.height = window_size
        self.sx = self.width / BASE_W
        self.sy = self.height / BASE_H
        
        self.font = pygame.font.SysFont(None, self._s(48))
        self.offscreen_hud = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.hud_texture = None
        
        self.bga_texture = None # Video frame or static image
        self.bga_updated_once = False
        
    def _s(self, v): return int(v * self.sy)
    def _sx(self, v): return int(v * self.sx)

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
        lane_w = lx[1] - lx[0] if len(lx) > 1 else self._sx(75)
        note_h = self._s(NOTE_H)
        hit_y = self._s(HIT_Y)

        self.offscreen_hud.fill((0, 0, 0, 0))
        
        # Judgment Pulse
        perf_h = max(4, self._s(int(HIT_ZONE_VISUAL_H * hw)))
        great_h = max(4, self._s(int(GREAT_ZONE_VISUAL_H * hw)))
        pulse = (math.sin(current_time / HIT_ZONE_PULSE_PERIOD) + 1) / 2
        hit_alpha = int(HIT_ZONE_ALPHA_MIN + pulse * HIT_ZONE_ALPHA_RANGE)

        # Boundaries
        self.renderer.draw_color = (60, 60, 60, 100)
        self.renderer.draw_rect((lx[0] - 2, 0, ltw + 4, self.height))

        # Lane BG
        for i in range(NUM_LANES):
            self.renderer.draw_color = (30, 30, 30, LANE_BG_ALPHA) if not pressed[i] else (50, 50, 60, LANE_BG_ALPHA)
            self.renderer.fill_rect((lx[i], 0, lane_w, self.height))
            self.renderer.draw_color = (60, 60, 60, 100)
            self.renderer.draw_line((lx[i] + lane_w, 0), (lx[i] + lane_w, self.height))

        # Hit Zone
        self.renderer.draw_color = (0, 0, 0, 150)
        self.renderer.fill_rect((lx[0], hit_y, ltw, self.height - hit_y))
        self.renderer.draw_color = (255, 40, 40, hit_alpha)
        self.renderer.fill_rect((lx[0], hit_y - perf_h // 2, ltw, perf_h))
        self.renderer.draw_color = (255, 80, 80, min(255, hit_alpha + 150))
        self.renderer.draw_rect((lx[0], hit_y - perf_h // 2, ltw, perf_h))

        # Judgment / Combo Text
        if j_text and current_time - j_timer < 500:
            js = self.font.render(j_text, True, j_color)
            self.offscreen_hud.blit(js, js.get_rect(center=(lx[0] + ltw // 2, self.height // 2 - self._s(50))))
        if comb > 0:
            cs = self.font.render(str(comb), True, (255, 255, 255))
            self.offscreen_hud.blit(cs, cs.get_rect(center=(lx[0] + ltw // 2, self.height // 2 + self._s(20))))

        # Notes
        for note in notes:
            if 'hit' not in note and 'miss' not in note:
                td = note['time_ms'] - current_time
                y = (hit_y - note_h) - td * spd
                if -note_h <= y <= self.height:
                    color = (0, 255, 255) if len(note['sample_ids']) == 1 else (200, 255, 255)
                    is_auto = note.get('is_auto', False)
                    alpha = 60 if is_auto else 255
                    nx, ny = lx[note['lane']], int(y)
                    
                    self.renderer.draw_color = (0, 0, 0, int(180 * (alpha/255)))
                    self.renderer.fill_rect((nx, ny + note_h - 4, lane_w, 4))
                    self.renderer.draw_color = (*color, alpha)
                    self.renderer.fill_rect((nx, ny, lane_w, note_h - 2))
                    self.renderer.draw_color = (255, 255, 255, int(120 * (alpha/255)))
                    self.renderer.fill_rect((nx, ny, lane_w, 2))

        # HUD blit
        if not self.hud_texture:
            self.hud_texture = Texture.from_surface(self.renderer, self.offscreen_hud)
        else:
            self.hud_texture.update(self.offscreen_hud)
        self.renderer.blit(self.hud_texture, pygame.Rect(0, 0, self.width, self.height))

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
            tw, th = tex.width, tex.height
            scaled_h = int(th * self.width / tw)
            self.renderer.blit(tex, pygame.Rect(0, (self.height - scaled_h) // 2, self.width, scaled_h))
            if assets.bga_dark_texture:
                self.renderer.blit(assets.bga_dark_texture, pygame.Rect(0, 0, self.width, self.height))

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

    def draw_effects(self, effects_list, lanes_x, lane_w):
        for eff in effects_list[:]:
            from .constants import EFFECT_EXPAND_SPEED, EFFECT_FADE_SPEED
            eff['radius'] += EFFECT_EXPAND_SPEED
            eff['alpha'] -= EFFECT_FADE_SPEED
            if eff['alpha'] <= 0:
                effects_list.remove(eff)
                continue
            
            r = self._s(eff['radius'])
            surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*eff['color'], eff['alpha']), (r, r), r, self._s(3))
            core_r = max(1, r // 2)
            pygame.draw.circle(surf, (255, 255, 255, min(255, eff['alpha'] * 2)), (r, r), core_r)
            
            tex = Texture.from_surface(self.renderer, surf)
            tx = lanes_x[eff['lane']] + lane_w // 2 - r
            ty = self._s(500) - r
            self.renderer.blit(tex, pygame.Rect(tx, ty, r*2, r*2))

    def draw_result(self, stats):
        """
        stats keys:
        - mode (single/ai_multi)
        - title (str)
        - metadata (dict)
        - judgments (dict)
        - max_combo (int)
        - ai_judgments (dict, optional)
        - ai_max_combo (int, optional)
        - cover_texture (Texture, optional)
        """
        def calc_score(judgs):
            return judgs["PERFECT"] * 1000 + judgs["GREAT"] * 500 + judgs["GOOD"] * 200

        score_h = calc_score(stats['judgments'])
        score_ai = calc_score(stats['ai_judgments']) if stats['mode'] == 'ai_multi' else 0

        self.offscreen_hud.fill((20, 20, 35))
        if stats.get('cover_texture'):
            # This is tricky since we need a Surface for blitting to offscreen_hud if we want darkness
            # But the renderer is GPU based. 
            # For simplicity in result screen, we might just use solid colors or clear the main renderer.
            pass

        if stats['mode'] == 'ai_multi':
            title_font = pygame.font.SysFont(None, self._s(40), bold=True)
            t_surf = title_font.render(stats['title'], True, (255, 255, 255))
            self.offscreen_hud.blit(t_surf, t_surf.get_rect(center=(self.width // 2, self._s(30))))
            
            p1_win = score_h >= score_ai
            win_txt = "YOU WIN!" if p1_win else "AI BOT WINS"
            win_color = (0, 255, 255) if p1_win else (255, 50, 50)
            banner_font = pygame.font.SysFont(None, self._s(80), bold=True)
            bs = banner_font.render(win_txt, True, win_color)
            self.offscreen_hud.blit(bs, bs.get_rect(center=(self.width // 2, self._s(120))))
        else:
            res_font = pygame.font.SysFont(None, self._s(64))
            t = res_font.render("RESULT", True, (255, 255, 255))
            self.offscreen_hud.blit(t, t.get_rect(center=(self.width // 2, self._s(80))))

        y_start = self._s(220)
        y = y_start
        p1_x = self._sx(100)
        p1_title = self.font.render("PLAYER", True, (100, 200, 255))
        self.offscreen_hud.blit(p1_title, (p1_x, y - self._s(40)))

        for key in JUDGMENT_ORDER:
            color = JUDGMENT_DEFS[key]["color"]
            text = self.font.render(f"{key}: {stats['judgments'][key]}", True, color)
            self.offscreen_hud.blit(text, (p1_x, y))
            y += self._s(50)
            
        combo_text = self.font.render(f"MAX COMBO: {stats['max_combo']}", True, (255, 255, 255))
        self.offscreen_hud.blit(combo_text, (p1_x, y + self._s(20)))
        score_text = self.font.render(f"SCORE: {score_h:,}", True, (255, 255, 0))
        self.offscreen_hud.blit(score_text, (p1_x, y + self._s(70)))

        if stats['mode'] == 'ai_multi':
            y = y_start
            ai_x = self._sx(460)
            ai_title = self.font.render("AI BOT", True, (255, 100, 100))
            self.offscreen_hud.blit(ai_title, (ai_x, y - self._s(40)))
            for key in JUDGMENT_ORDER:
                color = JUDGMENT_DEFS[key]["color"]
                ai_text = self.font.render(f"{key}: {stats['ai_judgments'][key]}", True, color)
                self.offscreen_hud.blit(ai_text, (ai_x, y))
                y += self._s(50)
            ai_ct = self.font.render(f"MAX COMBO: {stats['ai_max_combo']}", True, (255, 255, 255))
            self.offscreen_hud.blit(ai_ct, (ai_x, y + self._s(20)))
            ai_score_text = self.font.render(f"SCORE: {score_ai:,}", True, (255, 255, 0))
            self.offscreen_hud.blit(ai_score_text, (ai_x, y + self._s(70)))
        else:
            right_x = self._sx(540)
            y = self._s(180)
            meta_font = pygame.font.SysFont(None, self._s(40))
            small_meta_font = pygame.font.SysFont(None, self._s(28))
            t_surf = meta_font.render(stats['title'], True, (255, 255, 255))
            self.offscreen_hud.blit(t_surf, (right_x, y))
            y += self._s(50)
            for key, label in [("artist", "Artist"), ("genre", "Genre"), ("level", "Level")]:
                val = stats['metadata'].get(key)
                if val and str(val) not in ('Unknown', '0'):
                    s = small_meta_font.render(f"{label}: {val}", True, (200, 220, 240))
                    self.offscreen_hud.blit(s, (right_x, y))
                    y += self._s(32)

        info_font = pygame.font.SysFont(None, self._s(24))
        it = info_font.render("Press ENTER or ESC to Return", True, (150, 150, 150))
        self.offscreen_hud.blit(it, it.get_rect(center=(self.width // 2, self.height - self._s(40))))

        if not self.hud_texture:
            self.hud_texture = Texture.from_surface(self.renderer, self.offscreen_hud)
        else:
            self.hud_texture.update(self.offscreen_hud)
        self.renderer.clear()
        self.renderer.blit(self.hud_texture, pygame.Rect(0, 0, self.width, self.height))
        self.renderer.present()
