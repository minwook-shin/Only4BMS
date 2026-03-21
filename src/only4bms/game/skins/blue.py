import math
import random
import pygame
from pygame._sdl2.video import Texture
from ..constants import NOTE_H
from . import NoteSkinBase


class BlueNoteSkin(NoteSkinBase):
    id = 'blue'
    ui_color = (0, 180, 255)
    unlock_challenge_id = 'forest_of_trials'
    unlock_toast_i18n_key = 'skin_unlocked_blue_toast'

    def __init__(self):
        self._bar_cache = {}
        self._circle_cache = {}
        self._ln_cache = {}
        self._effect_cache = {}

    def is_unlocked(self, challenge_manager) -> bool:
        return challenge_manager.is_blue_skin_unlocked()

    # ── Textures ──────────────────────────────────────────────────────────────

    def get_bar_texture(self, r, lane_w):
        if lane_w not in self._bar_cache:
            bw, bh = int(lane_w * 0.8), int(r._s(NOTE_H) * 1.5)
            glow_r = r._s(4)
            surf = pygame.Surface((bw + glow_r * 2, bh + glow_r * 2), pygame.SRCALPHA)

            for gr in range(glow_r, 0, -1):
                alpha = int(55 * (1.0 - gr / glow_r))
                pygame.draw.rect(surf, (0, 200, 255, alpha),
                                 (glow_r - gr, glow_r - gr, bw + gr * 2, bh + gr * 2), border_radius=gr)

            inner = pygame.Surface((bw, bh), pygame.SRCALPHA)
            for yy in range(bh):
                ratio = yy / max(1, bh)
                if ratio < 0.18:
                    v = ratio / 0.18
                    rc, gc, bc = int(80 + 60 * v), int(180 + 60 * v), 255
                elif ratio > 0.82:
                    v = (ratio - 0.82) / 0.18
                    rc, gc, bc = int(20 - 10 * v), int(60 - 30 * v), int(140 - 60 * v)
                else:
                    v = (ratio - 0.18) / 0.64
                    rc, gc, bc = int(30 + 20 * v), int(80 + 40 * v), int(255 - 80 * v)
                pygame.draw.line(inner, (rc, gc, bc, 255), (0, yy), (bw, yy))

            pygame.draw.line(inner, (180, 230, 255, 200), (1, 1), (bw - 2, 1))
            pygame.draw.line(inner, (255, 255, 255, 80), (0, bh // 3), (bw, bh // 3))
            pygame.draw.line(inner, (100, 200, 255, 120), (1, 0), (1, bh))
            pygame.draw.line(inner, (0, 50, 120, 150), (bw - 2, 0), (bw - 2, bh))

            surf.blit(inner, (glow_r, glow_r))
            self._bar_cache[lane_w] = Texture.from_surface(r.renderer, surf)
        return self._bar_cache[lane_w]

    def get_circle_texture(self, r, lane_w):
        if lane_w not in self._circle_cache:
            cr = int(lane_w * 0.44)
            glow_r = r._s(8)
            size = lane_w + glow_r * 2
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            cx, cy = size // 2, size // 2

            for gr in range(glow_r, 0, -2):
                alpha = int(50 * (1.0 - gr / glow_r))
                pygame.draw.circle(surf, (0, 200, 255, alpha), (cx, cy), cr + gr)

            pygame.draw.circle(surf, (0, 40, 160, 255), (cx, cy), cr)
            pygame.draw.circle(surf, (30, 100, 220, 255), (cx, cy), cr - 2)
            pygame.draw.circle(surf, (100, 200, 255, 160), (cx, cy), cr - 1, 2)

            hx, hy = cx - cr // 4, cy - cr // 4
            pygame.draw.circle(surf, (0, 150, 255, 180), (int(hx), int(hy)), cr // 2.5)
            pygame.draw.circle(surf, (100, 210, 255, 230), (int(hx), int(hy)), cr // 4)
            pygame.draw.circle(surf, (220, 240, 255, 255), (int(hx), int(hy)), cr // 6)
            pygame.draw.circle(surf, (255, 255, 255, 255), (int(hx), int(hy)), r._s(2))
            pygame.draw.circle(surf, (0, 40, 120, 200), (cx, cy), cr - 2, 2)
            pygame.draw.circle(surf, (0, 20, 80, 150), (cx, cy), cr, 1)

            self._circle_cache[lane_w] = Texture.from_surface(r.renderer, surf)
        return self._circle_cache[lane_w]

    def get_ln_body_texture(self, r, lane_w):
        if lane_w not in self._ln_cache:
            surf = pygame.Surface((lane_w, 1), pygame.SRCALPHA)
            margin = int(lane_w * 0.12)
            pygame.draw.rect(surf, (0, 150, 255, 130), (margin, 0, lane_w - margin * 2, 1))
            pygame.draw.rect(surf, (0, 200, 255, 255), (margin, 0, 1, 1))
            pygame.draw.rect(surf, (0, 200, 255, 255), (lane_w - margin - 1, 0, 1, 1))
            self._ln_cache[lane_w] = Texture.from_surface(r.renderer, surf)
        return self._ln_cache[lane_w]

    def _get_effect_texture(self, r, lane_w):
        if lane_w not in self._effect_cache:
            w, h = int(lane_w * 1.5), r._s(230)
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            cx = w // 2
            base_y = h - r._s(5)

            for gr in range(r._s(40), 0, -5):
                alpha = int(100 * (1.0 - gr / r._s(40)))
                pygame.draw.circle(surf, (0, 150, 255, alpha), (cx, base_y), gr)

            for _ in range(35):
                ww = random.randint(r._s(8), r._s(20))
                hh = random.randint(r._s(30), r._s(100))
                px = random.randint(r._s(2), w - r._s(2))
                py = base_y - random.randint(0, h - r._s(30))
                color = random.choice([(0, 180, 255), (100, 240, 255), (255, 255, 255)])
                wisp_pts = [(px - ww//2, py + hh//2), (px + ww//2, py + hh//2),
                            (px + random.randint(-4, 4), py - hh//2)]
                pygame.draw.polygon(surf, (*color, random.randint(80, 160)), wisp_pts)

            for _ in range(50):
                sw = random.randint(1, r._s(3))
                sh = random.randint(r._s(40), r._s(120))
                px = random.randint(r._s(5), w - r._s(5))
                py = base_y - random.randint(r._s(20), h - r._s(20))
                color = random.choice([(150, 255, 255), (255, 255, 255)])
                alpha = random.randint(150, 240)
                streak = pygame.Surface((sw, sh), pygame.SRCALPHA)
                for sy in range(sh):
                    s_alpha = int(alpha * (1.0 - sy / sh) ** 1.2)
                    pygame.draw.line(streak, (*color, s_alpha), (0, sy), (0, sy))
                surf.blit(streak, (px, py - sh))

            for _ in range(80):
                px = random.randint(r._s(2), w - r._s(2))
                py = base_y - random.random() * (h - r._s(10))
                ps = random.choice([r._s(1), r._s(2), r._s(3), r._s(4)])
                color = (255, 255, 255) if random.random() > 0.4 else (0, 255, 255)
                pygame.draw.circle(surf, (*color, 255), (px, py), ps)
                if ps >= r._s(2):
                    pygame.draw.circle(surf, (*color, 150), (px, py), ps * 2)

            for i in range(8):
                sh_w = r._s(20 - i * 2)
                sh_h = r._s(60 + i * 15)
                alpha = int(180 * (1.0 - i / 8.0))
                pygame.draw.ellipse(surf, (255, 255, 255, alpha),
                                    (cx - sh_w // 2, base_y - sh_h, sh_w, sh_h))

            self._effect_cache[lane_w] = Texture.from_surface(r.renderer, surf)
        return self._effect_cache[lane_w]

    def render_effect(self, r, eff, tx, ty, lane_w):
        import math as _math
        tex = self._get_effect_texture(r, lane_w)
        tex.alpha = eff['alpha']
        life_ratio = eff['alpha'] / 255.0
        scale_h = 0.4 + (1.0 - life_ratio) * 0.9
        scale_w = 0.9 + _math.sin((1.0 - life_ratio) * _math.pi) * 0.2
        ew = int(tex.width * scale_w)
        eh = int(tex.height * scale_h)
        r.renderer.blit(tex, pygame.Rect(tx - ew // 2, ty - eh + r._s(12), ew, eh))
