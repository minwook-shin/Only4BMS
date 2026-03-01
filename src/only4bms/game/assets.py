import os
import pygame
from only4bms.i18n import get as _t, FONT_NAME
from only4bms import i18n as _i18n
from .constants import VIDEO_EXTS, IMAGE_FALLBACK_EXTS, LOADING_BAR_W, LOADING_BAR_H
from .video_player import VideoPlayer
from pygame._sdl2.video import Texture

class AssetLoader:
    def __init__(self, renderer, window, title, metadata, settings):
        self.renderer = renderer
        self.window = window
        self.width, self.height = window.size
        self.title = title
        self.metadata = metadata or {}
        self.settings = settings
        
        self.sounds = {}
        self.images = {}
        self.videos = {}
        self.textures = {}
        self.cover_texture = None
        self.bga_dark_texture = None
        
        # Surfaces used during loading
        self.offscreen_hud = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.hud_texture = None
        self.last_loading_update = 0
        
        # Scaling helpers (moved here for loading screen)
        self.sx = self.width / 800.0
        self.sy = self.height / 600.0
        
        # Fonts for loading
        self.loading_title_font = _i18n.font("loading_title", self.sy)
        self.loading_info_font = _i18n.font("loading_info", self.sy)
        self.loading_label_font = _i18n.font("loading_label", self.sy)

    def _s(self, v): return int(v * self.sy)
    def _sx(self, v): return int(v * self.sx)

    def _draw_loading(self, progress, total, status_text="", force=False):
        import time
        now = time.perf_counter()
        if not force and (now - self.last_loading_update < 0.033):
            return
        self.last_loading_update = now

        self.offscreen_hud.fill((10, 10, 15))
        cx, cy = self.width // 2, self.height // 2

        # Title
        surf = self.loading_title_font.render(self.title, True, (255, 255, 255))
        self.offscreen_hud.blit(surf, surf.get_rect(center=(cx, self._s(180))))

        # Metadata
        meta_fields = [("artist", _t("loading_artist")), ("genre", _t("loading_genre")), ("bpm", _t("loading_bpm")), ("level", _t("loading_level")), ("notes", _t("loading_notes"))]
        y = self._s(230)
        for key, label in meta_fields:
            val = self.metadata.get(key)
            if val and str(val) not in ('Unknown', '0'):
                s = self.loading_info_font.render(f"{label}: {val}", True, (180, 200, 220))
                self.offscreen_hud.blit(s, s.get_rect(center=(cx, y)))
                y += self._s(32)

        # Status
        lbl = self.loading_label_font.render(_t("loading").format(status=status_text), True, (180, 180, 180))
        self.offscreen_hud.blit(lbl, lbl.get_rect(center=(cx, self._s(400))))

        # Bar
        bar_w, bar_h = self._sx(LOADING_BAR_W), self._s(LOADING_BAR_H)
        bar_x, bar_y = (self.width - bar_w) // 2, self._s(440)
        pygame.draw.rect(self.offscreen_hud, (50, 50, 60), (bar_x, bar_y, bar_w, bar_h), border_radius=8)
        fill_w = int(bar_w * progress / max(total, 1))
        if fill_w > 0:
            pygame.draw.rect(self.offscreen_hud, (0, 200, 255), (bar_x, bar_y, fill_w, bar_h), border_radius=8)

        pct = int(100 * progress / max(total, 1))
        pct_s = self.loading_label_font.render(f"{pct}%", True, (200, 200, 200))
        self.offscreen_hud.blit(pct_s, pct_s.get_rect(center=(cx, bar_y + bar_h + self._s(20))))

        if not self.hud_texture:
            self.hud_texture = Texture.from_surface(self.renderer, self.offscreen_hud)
        else:
            self.hud_texture.update(self.offscreen_hud)
            
        self.renderer.clear()
        self.renderer.blit(self.hud_texture, pygame.Rect(0, 0, self.width, self.height))
        self.renderer.present()
        pygame.event.pump()

    def _try_load_image(self, bmp_id, filepath):
        try:
            img = pygame.image.load(filepath).convert_alpha()
            self.images[bmp_id] = img
            return True
        except:
            return False

    def _scale_to_width(self, surface, target_w):
        w, h = surface.get_size()
        target_h = int(h * target_w / w)
        return pygame.transform.smoothscale(surface, (target_w, target_h))

    def load(self, wav_map, bmp_map):
        total = len(wav_map) + len(bmp_map)
        count = 0
        self._draw_loading(0, total, "audio")

        vol = self.settings.get('volume', 0.3)
        for wav_id, filepath in wav_map.items():
            if os.path.exists(filepath):
                try:
                    snd = pygame.mixer.Sound(filepath)
                    snd.set_volume(vol)
                    self.sounds[wav_id] = snd
                except:
                    self.sounds[wav_id] = None
            else:
                self.sounds[wav_id] = None
            count += 1
            self._draw_loading(count, total, "audio")

        for bmp_id, filepath in bmp_map.items():
            ext = os.path.splitext(filepath)[1].lower()
            loaded = False
            if os.path.exists(filepath) and ext in VIDEO_EXTS:
                try:
                    self.videos[bmp_id] = VideoPlayer(filepath, target_size=(self.width, self.height))
                    loaded = True
                except: pass
            elif os.path.exists(filepath):
                loaded = self._try_load_image(bmp_id, filepath)

            if not loaded:
                base = os.path.splitext(filepath)[0]
                for fb_ext in IMAGE_FALLBACK_EXTS:
                    alt = base + fb_ext
                    if os.path.exists(alt) and self._try_load_image(bmp_id, alt):
                        loaded = True
                        break
            
            if loaded and bmp_id in self.images and self.images[bmp_id]:
                self.textures[bmp_id] = Texture.from_surface(self.renderer, self.images[bmp_id])
            
            count += 1
            self._draw_loading(count, total, "media")

        for key in ('stagefile', 'banner'):
            path = self.metadata.get(key)
            if path and os.path.exists(path):
                try:
                    img = pygame.image.load(path)
                    cover_img = self._scale_to_width(img, self.width)
                    self.cover_texture = Texture.from_surface(self.renderer, cover_img)
                    break
                except: pass

        dark = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        dark.fill((0, 0, 0, 120))
        self.bga_dark_texture = Texture.from_surface(self.renderer, dark)
        self._draw_loading(total, total, "ready", force=True)
