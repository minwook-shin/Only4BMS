import math
import random
import pygame
from pygame._sdl2.video import Texture
from ..constants import NOTE_H
from . import NoteSkinBase


class GoldNoteSkin(NoteSkinBase):
    id = 'gold'
    ui_color = (255, 215, 0)
    unlock_challenge_id = 'perfect_player'
    unlock_toast_i18n_key = 'skin_unlocked_toast'

    def __init__(self):
        self._bar_cache = {}
        self._circle_cache = {}
        self._ln_cache = {}
        self._effect_cache = {}
        self._ambient_cache = {}   # (facing, w, h) -> Texture

    def is_unlocked(self, challenge_manager) -> bool:
        return challenge_manager.is_golden_skin_unlocked()

    # ── Ambient Lane Glow ────────────────────────────────────────────────────

    def draw_lane_ambient(self, r, left_x, right_x, current_time, fade_mult):
        if fade_mult <= 0:
            return
        # Slow golden heartbeat — period ~2s, breathes between dim and bright
        pulse = (math.sin(current_time / 1000.0) + 1) / 2   # 0..1
        alpha = int(fade_mult * (38 + 22 * pulse))
        if alpha <= 0:
            return

        left_w  = left_x
        right_w = r.width - right_x
        h = r.height

        if left_w > 8:
            key = ('L', left_w, h)
            if key not in self._ambient_cache:
                self._ambient_cache[key] = self._build_ambient(r, left_w, h, bright_right=True)
            tex = self._ambient_cache[key]
            tex.alpha = alpha
            r.renderer.blit(tex, pygame.Rect(0, 0, left_w, h))

        if right_w > 8:
            key = ('R', right_w, h)
            if key not in self._ambient_cache:
                self._ambient_cache[key] = self._build_ambient(r, right_w, h, bright_right=False)
            tex = self._ambient_cache[key]
            tex.alpha = alpha
            r.renderer.blit(tex, pygame.Rect(right_x, 0, right_w, h))

    def _build_ambient(self, r, w, h, bright_right: bool):
        """Build a gradient panel with baked metallic sheen streaks.
        bright_right=True → bright end on the right (touching lane), fades left."""
        surf = pygame.Surface((w, h), pygame.SRCALPHA)

        # Horizontal gradient: transparent → warm amber → gold at lane edge
        grad_row = pygame.Surface((w, 1), pygame.SRCALPHA)
        for x in range(w):
            t = x / max(w - 1, 1) if bright_right else 1.0 - x / max(w - 1, 1)
            a = int(255 * (t ** 2.0))          # quadratic: very dim far out, rich near lane
            gc = int(160 + 60 * t)             # amber(160) → gold(220) near lane
            grad_row.set_at((x, 0), (255, gc, 0, a))
        surf.blit(pygame.transform.scale(grad_row, (w, h)), (0, 0))

        # Baked horizontal metallic sheen streaks (fixed seed → same every run)
        rng = random.Random(0xAA55)
        for _ in range(h // 20 + 6):
            sy    = rng.randint(0, h - 1)
            sa    = rng.randint(40, 110)
            sw    = rng.randint(w // 3, w)
            sx    = w - sw if bright_right else 0
            pygame.draw.line(surf, (255, 235, 140, sa), (sx, sy), (sx + sw - 1, sy), 1)

        return Texture.from_surface(r.renderer, surf)

    # ── Textures ──────────────────────────────────────────────────────────────

    def get_bar_texture(self, r, lane_w):
        if lane_w not in self._bar_cache:
            bw, bh = int(lane_w * 0.8), int(r._s(NOTE_H) * 1.5)
            glow_r = r._s(4)
            surf = pygame.Surface((bw + glow_r * 2, bh + glow_r * 2), pygame.SRCALPHA)

            for gr in range(glow_r, 0, -1):
                alpha = int(50 * (1.0 - gr / glow_r))
                pygame.draw.rect(surf, (255, 180, 0, alpha),
                                 (glow_r - gr, glow_r - gr, bw + gr * 2, bh + gr * 2), border_radius=gr)

            inner = pygame.Surface((bw, bh), pygame.SRCALPHA)
            for yy in range(bh):
                ratio = yy / max(1, bh)
                if ratio < 0.2:
                    v = ratio / 0.2
                    rc, gc, bc = 255, int(220 + 35 * v), int(140 + 60 * v)
                elif ratio > 0.8:
                    v = (ratio - 0.8) / 0.2
                    rc, gc, bc = int(180 - 60 * v), int(120 - 40 * v), 0
                else:
                    v = (ratio - 0.2) / 0.6
                    rc, gc, bc = int(255 - 85 * v), int(200 - 80 * v), int(30 * v)
                pygame.draw.line(inner, (rc, gc, bc, 255), (0, yy), (bw, yy))

            pygame.draw.line(inner, (255, 255, 220, 200), (1, 1), (bw - 2, 1))
            pygame.draw.line(inner, (255, 255, 255, 120), (0, bh // 3), (bw, bh // 3))
            pygame.draw.line(inner, (255, 255, 200, 120), (1, 0), (1, bh))
            pygame.draw.line(inner, (140, 90, 0, 150), (bw - 2, 0), (bw - 2, bh))

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
                alpha = int(45 * (1.0 - gr / glow_r))
                pygame.draw.circle(surf, (255, 160, 0, alpha), (cx, cy), cr + gr)

            pygame.draw.circle(surf, (180, 120, 0, 255), (cx, cy), cr)
            pygame.draw.circle(surf, (255, 200, 0, 255), (cx, cy), cr - 2)
            pygame.draw.circle(surf, (255, 255, 180, 150), (cx, cy), cr - 1, 2)

            hx, hy = cx - cr // 3.2, cy - cr // 3.2
            pygame.draw.circle(surf, (255, 180, 0, 220), (int(hx), int(hy)), cr // 2.5)
            pygame.draw.circle(surf, (255, 230, 50, 240), (int(hx), int(hy)), cr // 4)
            pygame.draw.circle(surf, (255, 255, 220, 255), (int(hx), int(hy)), cr // 6)
            pygame.draw.circle(surf, (255, 255, 255, 255), (int(hx), int(hy)), r._s(2))
            pygame.draw.circle(surf, (255, 255, 200, 100), (cx, cy), cr - 1, 1)
            pygame.draw.circle(surf, (255, 150, 0, 80), (cx, cy), cr - 3, 1)

            self._circle_cache[lane_w] = Texture.from_surface(r.renderer, surf)
        return self._circle_cache[lane_w]

    def get_ln_body_texture(self, r, lane_w):
        if lane_w not in self._ln_cache:
            surf = pygame.Surface((lane_w, 1), pygame.SRCALPHA)
            margin = int(lane_w * 0.12)
            pygame.draw.rect(surf, (255, 200, 0, 150), (margin, 0, lane_w - margin * 2, 1))
            pygame.draw.rect(surf, (255, 215, 0, 255), (margin, 0, 1, 1))
            pygame.draw.rect(surf, (255, 215, 0, 255), (lane_w - margin - 1, 0, 1, 1))
            self._ln_cache[lane_w] = Texture.from_surface(r.renderer, surf)
        return self._ln_cache[lane_w]

    def _get_effect_texture(self, r, lane_w):
        if lane_w not in self._effect_cache:
            size = r._s(150)
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            cx, cy = size // 2, size // 2

            pygame.draw.circle(surf, (255, 200, 0, 25), (cx, cy), r._s(40))
            pygame.draw.circle(surf, (255, 255, 200, 15), (cx, cy), r._s(60))

            for _ in range(45):
                angle = random.uniform(0, math.pi * 2)
                dist = random.uniform(size * 0.05, size * 0.48)
                px, py = int(cx + math.cos(angle) * dist), int(cy + math.sin(angle) * dist)
                is_streak = random.random() < 0.35
                fw = random.randint(r._s(12), r._s(30)) if is_streak else random.randint(r._s(5), r._s(12))
                fh = random.randint(1, r._s(2)) if is_streak else random.randint(r._s(4), r._s(10))
                shade = random.choice([(255,215,0),(255,180,0),(255,255,50),(220,150,0),(255,230,100),(255,255,255)])
                shard = pygame.Surface((fw, fh), pygame.SRCALPHA)
                shard.fill((*shade, random.randint(180, 255)))
                rot = math.degrees(-angle) if is_streak else random.uniform(0, 360)
                rotated = pygame.transform.rotate(shard, rot)
                rw, rh = rotated.get_size()
                surf.blit(rotated, (px - rw // 2, py - rh // 2))

            pygame.draw.circle(surf, (255, 255, 255, 180), (cx, cy), r._s(6))
            pygame.draw.circle(surf, (255, 215, 0, 80), (cx, cy), r._s(12), r._s(1))
            self._effect_cache[lane_w] = Texture.from_surface(r.renderer, surf)
        return self._effect_cache[lane_w]

    def render_effect(self, r, eff, tx, ty, lane_w):
        tex = self._get_effect_texture(r, lane_w)
        tex.alpha = eff['alpha']
        base_size = r._s(150)
        life_ratio = eff['alpha'] / 255.0
        scale = 0.3 + (1.0 - life_ratio) * 4.0 if life_ratio > 0.8 else 0.7 + (1.0 - life_ratio) * 1.5
        ew = eh = int(base_size * scale)
        r.renderer.blit(tex, pygame.Rect(tx - ew // 2, ty - eh // 2, ew, eh))
