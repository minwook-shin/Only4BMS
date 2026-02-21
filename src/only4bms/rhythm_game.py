import math
import os
import time
import pygame

# ── Judgment configuration (single source of truth) ──────────────────────
JUDGMENT_DEFS = {
    "PERFECT": {"threshold_ms": 60,  "color": (0, 255, 255), "display": "PERFECT!"},
    "GREAT":   {"threshold_ms": 130, "color": (0, 255, 0),   "display": "GREAT!"},
    "GOOD":    {"threshold_ms": 200, "color": (255, 255, 0),  "display": "GOOD"},
    "MISS":    {"threshold_ms": 200, "color": (255, 0, 0),    "display": "MISS"},
}
JUDGMENT_ORDER = ["PERFECT", "GREAT", "GOOD", "MISS"]

# ── Base (windowed) resolution ────────────────────────────────────────────
BASE_W, BASE_H = 800, 600
NUM_LANES = 4
LANE_W = 75
NOTE_H = 20
HIT_Y = 500
BG_COLOR = (20, 20, 20)
LANE_BG_ALPHA = 200
JUDGMENT_DISPLAY_MS = 500
SONG_END_PADDING_MS = 2000
EFFECT_EXPAND_SPEED = 2
EFFECT_FADE_SPEED = 15

# Hit zone pulse
HIT_ZONE_VISUAL_H = 30     # PERFECT zone visual height (px, before hw_mult)
GREAT_ZONE_VISUAL_H = 60   # GREAT zone visual height (px, before hw_mult)
HIT_ZONE_PULSE_PERIOD = 300.0
HIT_ZONE_ALPHA_MIN = 20
HIT_ZONE_ALPHA_RANGE = 50

# Loading screen
LOADING_BAR_W, LOADING_BAR_H = 500, 16

# Video extensions
VIDEO_EXTS = {'.mpg', '.mpeg', '.mp4', '.avi', '.wmv', '.mkv', '.webm'}
IMAGE_FALLBACK_EXTS = ['.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.bmp', '.BMP']


class RhythmGame:
    def __init__(self, notes, bgms, bgas, wav_map, bmp_map, title, settings, metadata=None, renderer=None, window=None):
        self.renderer = renderer
        self.window = window
        
        # We now assume a Window and Renderer are always provided
        self.width, self.h_orig = self.window.size
        self.height = self.h_orig
        self.renderer.draw_blend_mode = 1  # BLENDMODE_BLEND

        self.sx, self.sy = self.width / BASE_W, self.height / BASE_H
        pygame.display.set_caption(f"Playing - {title}")
        self.clock = pygame.time.Clock()

        # Data
        self.notes = notes
        self.bgms = bgms
        self.bgas = bgas
        self.wav_map = wav_map
        self.bmp_map = bmp_map
        self.title = title
        self.settings = settings
        self.metadata = metadata or {}
        
        # GPU Textures
        self.textures = {} 
        self.bga_texture = None # Reusable for video/dynamic BGA
        self.offscreen_hud = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.hud_texture = None

        # Assets
        self.sounds = {}
        self.images = {}
        self.videos = {}
        self.current_bga_img = None
        self.cover_img = None  # stagefile/banner fallback
        self.bga_dark_surface = None  # Cached for performance

        # Lane layout (scaled, centered)
        self.keys = [pygame.K_d, pygame.K_f, pygame.K_j, pygame.K_k]
        self.lane_w = self._sx(LANE_W)
        self.note_h = self._s(NOTE_H)
        self.hit_y = self._s(HIT_Y)
        start_x = (self.width - NUM_LANES * self.lane_w) // 2
        self.lane_x = [start_x + i * self.lane_w for i in range(NUM_LANES)]
        self.lane_total_w = NUM_LANES * self.lane_w
        self.speed = self.settings.get('speed', 0.5) * self.sy  # scale speed with resolution
        self.hw_mult = self.settings.get('hit_window_mult', 1.0)

        # Timing
        self.start_time = 0
        self.max_time = max(
            (self.notes[-1]['time_ms'] if self.notes else 0),
            (self.bgms[-1]['time_ms'] if self.bgms else 0),
            (self.bgas[-1]['time_ms'] if self.bgas else 0),
        )

        # State
        self.state = "PLAYING"
        self.paused_at = 0
        self.countdown_start = 0
        self._pause_buttons = []
        self.last_bga_surface = None
        self.last_bga_blit_time = 0
        self.judgments = {k: 0 for k in JUDGMENT_ORDER}
        self.combo = 0
        self.max_combo = 0
        self.effects = []
        self.lane_pressed = [False] * NUM_LANES

        # UI (scaled fonts)
        self.font = pygame.font.SysFont(None, self._s(48))
        self.loading_title_font = pygame.font.SysFont(None, self._s(50))
        self.loading_info_font = pygame.font.SysFont(None, self._s(30))
        self.loading_label_font = pygame.font.SysFont(None, self._s(28))
        
        self.judgment_text = ""
        self.judgment_timer = 0
        self.judgment_color = (255, 255, 255)
        self.last_loading_update = 0

        self.load_assets()
        self._precreate_surfaces()

    def _precreate_surfaces(self):
        """Pre-create surfaces used every frame to avoid allocations."""
        perfect_h = max(4, self._s(int(HIT_ZONE_VISUAL_H * self.hw_mult)))
        great_h = max(4, self._s(int(GREAT_ZONE_VISUAL_H * self.hw_mult)))

        self.cached_hit_zone = pygame.Surface((self.lane_total_w, perfect_h), pygame.SRCALPHA)
        self.cached_hit_zone.fill((255, 40, 40, 255)) # Alpha managed during blit

        self.cached_lane_glow = pygame.Surface((self.lane_w, self.height), pygame.SRCALPHA)
        self.cached_lane_glow.fill((100, 180, 255, 18))

        self.cached_gs = pygame.Surface((self.lane_w, great_h), pygame.SRCALPHA)
        self.cached_gs.fill((0, 255, 0, 28))

        self.cached_ps = pygame.Surface((self.lane_w, perfect_h), pygame.SRCALPHA)
        self.cached_ps.fill((0, 255, 255, 45))

    def _s(self, v):
        """Scale a base-600 Y value."""
        return max(1, int(v * self.sy))

    def _sx(self, v):
        """Scale a base-800 X value."""
        return max(1, int(v * self.sx))

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _scale_to_width(surface, target_w):
        """Scale a surface to fit target_w, maintaining aspect ratio."""
        w, h = surface.get_size()
        scale = target_w / float(w)
        return pygame.transform.scale(surface, (target_w, int(h * scale)))

    def _play_sound(self, sample_id):
        """Play a sound by sample id if it exists."""
        snd = self.sounds.get(sample_id)
        if snd:
            snd.play()

    # ── Loading ──────────────────────────────────────────────────────────

    def _draw_loading(self, progress, total, status_text="", force=False):
        now = time.perf_counter()
        if not force and (now - self.last_loading_update < 0.033): # 30fps cap for loading screen
            return
        self.last_loading_update = now

        self.offscreen_hud.fill((10, 10, 15))
        cx, cy = self.width // 2, self.height // 2

        # Title
        surf = self.loading_title_font.render(self.title, True, (255, 255, 255))
        self.offscreen_hud.blit(surf, surf.get_rect(center=(cx, self._s(180))))

        # Metadata
        meta_fields = [
            ("artist", "Artist"), ("genre", "Genre"),
            ("bpm", "BPM"), ("level", "Level"), ("notes", "Notes"),
        ]
        y = self._s(230)
        for key, label in meta_fields:
            val = self.metadata.get(key)
            if val and str(val) not in ('Unknown', '0'):
                s = self.loading_info_font.render(f"{label}: {val}", True, (180, 200, 220))
                self.offscreen_hud.blit(s, s.get_rect(center=(cx, y)))
                y += self._s(32)

        # Status label
        lbl = self.loading_label_font.render(f"Loading... {status_text}", True, (180, 180, 180))
        self.offscreen_hud.blit(lbl, lbl.get_rect(center=(cx, self._s(400))))

        # Progress bar
        bar_w = self._sx(LOADING_BAR_W)
        bar_h = self._s(LOADING_BAR_H)
        bar_x = (self.width - bar_w) // 2
        bar_y = self._s(440)
        pygame.draw.rect(self.offscreen_hud, (50, 50, 60),
                         (bar_x, bar_y, bar_w, bar_h), border_radius=8)
        fill_w = int(bar_w * progress / max(total, 1))
        if fill_w > 0:
            pygame.draw.rect(self.offscreen_hud, (0, 200, 255),
                             (bar_x, bar_y, fill_w, bar_h), border_radius=8)

        pct = int(100 * progress / max(total, 1))
        pct_s = self.loading_label_font.render(f"{pct}%", True, (200, 200, 200))
        self.offscreen_hud.blit(pct_s, pct_s.get_rect(center=(cx, bar_y + bar_h + self._s(20))))

        from pygame._sdl2.video import Texture
        if not self.hud_texture:
            self.hud_texture = Texture.from_surface(self.renderer, self.offscreen_hud)
        else:
            self.hud_texture.update(self.offscreen_hud)
        self.renderer.clear()
        self.renderer.blit(self.hud_texture, pygame.Rect(0, 0, self.width, self.height))
        self.renderer.present()
            
        pygame.event.pump()

    def load_assets(self):
        from .video_player import VideoPlayer

        total = len(self.wav_map) + len(self.bmp_map)
        count = 0
        self._draw_loading(0, total, "audio")

        # Audio
        vol = self.settings.get('volume', 0.3)
        for wav_id, filepath in self.wav_map.items():
            if os.path.exists(filepath):
                try:
                    snd = pygame.mixer.Sound(filepath)
                    snd.set_volume(vol)
                    self.sounds[wav_id] = snd
                except Exception as e:
                    print(f"Warning: Could not load sound {filepath}: {e}")
                    self.sounds[wav_id] = None
            else:
                self.sounds[wav_id] = None
            count += 1
            self._draw_loading(count, total, "audio")

        # BGA (images & videos)
        for bmp_id, filepath in self.bmp_map.items():
            ext = os.path.splitext(filepath)[1].lower()
            loaded = False

            if os.path.exists(filepath) and ext in VIDEO_EXTS:
                try:
                    self.videos[bmp_id] = VideoPlayer(filepath, target_size=(self.width, self.height))
                    loaded = True
                except Exception as e:
                    print(f"Warning: Could not load video {filepath}: {e}")
            elif os.path.exists(filepath):
                loaded = self._try_load_image(bmp_id, filepath)

            if not loaded:
                base = os.path.splitext(filepath)[0]
                for fb_ext in IMAGE_FALLBACK_EXTS:
                    alt = base + fb_ext
                    if os.path.exists(alt) and self._try_load_image(bmp_id, alt):
                        loaded = True
                        break

            if not loaded:
                self.images[bmp_id] = None
            else:
                # Convert to Texture for GPU (if it was an image)
                if bmp_id in self.images and self.images[bmp_id]:
                    from pygame._sdl2.video import Texture
                    self.textures[bmp_id] = Texture.from_surface(self.renderer, self.images[bmp_id])

            count += 1
            self._draw_loading(count, total, "media")

        # Final update to ensure 100% is shown
        self._draw_loading(total, total, "ready", force=True)

        # Load cover image (stagefile or banner) as BGA fallback
        for key in ('stagefile', 'banner'):
            path = self.metadata.get(key)
            if path and os.path.exists(path):
                try:
                    img = pygame.image.load(path)
                    self.cover_img = self._scale_to_width(img, self.width)
                    from pygame._sdl2.video import Texture
                    self.cover_texture = Texture.from_surface(self.renderer, self.cover_img)
                    break
                except Exception as e:
                    print(f"Warning: Could not load cover {path}: {e}")

        # Pre-create darken surface for BGA
        self.bga_dark_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.bga_dark_surface.fill((0, 0, 0, 120))
        from pygame._sdl2.video import Texture
        self.bga_dark_texture = Texture.from_surface(self.renderer, self.bga_dark_surface)

    def _try_load_image(self, bmp_id, filepath):
        """Try to load and scale an image. Returns True on success."""
        try:
            # We don't use .convert_alpha() here because it might fail without a display mode
            # Texture.from_surface will handle the conversion/upload correctly
            img = pygame.image.load(filepath)
            self.images[bmp_id] = self._scale_to_width(img, self.width)
            return True
        except Exception as e:
            print(f"Warning: Could not load image {filepath}: {e}")
            self.images[bmp_id] = None
            return False

    # ── Judgment ──────────────────────────────────────────────────────────

    def set_judgment(self, key, lane_idx=None):
        """Register a judgment by key (PERFECT/GREAT/GOOD/MISS)."""
        j = JUDGMENT_DEFS[key]
        self.judgment_text = j["display"]
        self.judgment_color = j["color"]
        self.judgment_timer = pygame.time.get_ticks() + JUDGMENT_DISPLAY_MS

        self.judgments[key] += 1

        if key in ("PERFECT", "GREAT"):
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
        elif key == "MISS":
            self.combo = 0

        if lane_idx is not None:
            self.effects.append({
                'x': self.lane_x[lane_idx] + self.lane_w // 2,
                'y': self.hit_y,
                'radius': self._s(24),  # Increased from 10 to 24 for better impact
                'color': j["color"],
                'alpha': 255,
            })

    # ── Input & Hit Processing ───────────────────────────────────────────

    def start(self):
        self.start_time = time.perf_counter()
        self.run()

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            for i, key in enumerate(self.keys):
                if event.key == key:
                    self.lane_pressed[i] = True
                    self.process_hit(i)
        elif event.type == pygame.KEYUP:
            for i, key in enumerate(self.keys):
                if event.key == key:
                    self.lane_pressed[i] = False

    def process_hit(self, lane):
        current_time = (time.perf_counter() - self.start_time) * 1000.0
        max_window = JUDGMENT_DEFS["GOOD"]["threshold_ms"] * self.hw_mult
        closest, min_diff = None, float('inf')

        for note in self.notes:
            if note['lane'] == lane and 'hit' not in note and 'miss' not in note:
                diff = abs(note['time_ms'] - current_time)
                if diff < min_diff and diff <= max_window:
                    min_diff = diff
                    closest = note

        if closest:
            closest['hit'] = True
            for sid in closest['sample_ids']:
                self._play_sound(sid)

            # Determine judgment from thresholds
            for key in ("PERFECT", "GREAT", "GOOD"):
                if min_diff <= JUDGMENT_DEFS[key]["threshold_ms"] * self.hw_mult:
                    self.set_judgment(key, lane)
                    break

    # ── Game Loop ─────────────────────────────────────────────────────────

    def run(self):
        running = True
        while running:
            current_time = (time.perf_counter() - self.start_time) * 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if self.state == "PLAYING":
                        if event.key == pygame.K_ESCAPE:
                            self._pause(current_time)
                        else:
                            self.handle_input(event)
                    elif self.state == "PAUSED":
                        if event.key == pygame.K_ESCAPE:
                            self._resume()
                        elif event.key == pygame.K_q:
                            running = False
                    elif self.state == "COUNTDOWN":
                        if event.key == pygame.K_ESCAPE:
                            self._pause(self.paused_at)
                    elif self.state == "RESULT":
                        if event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                            running = False
                elif event.type == pygame.KEYUP:
                    if self.state == "PLAYING":
                        self.handle_input(event)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.state == "PAUSED":
                        self._handle_pause_click(event.pos)

            # ── Drawing ──────────────────────────────────────────────────
            self.renderer.draw_color = (0, 0, 0, 255)
            self.renderer.clear()

            if self.state == "PLAYING":
                self._update(current_time)
                self._draw_playing(current_time)
            elif self.state == "PAUSED":
                self._draw_playing(self.paused_at)
                self._draw_paused()
            elif self.state == "COUNTDOWN":
                # Countdown logic
                elapsed = time.perf_counter() - self.countdown_start
                cd = 3.0 - elapsed
                if cd <= 0:
                    self._finish_resume()
                else:
                    self._draw_playing(self.paused_at)
                    self._draw_countdown(int(cd) + 1)
            elif self.state == "RESULT":
                self._draw_result()
            elif self.state == "QUIT":
                running = False
                continue

            # Final presentation
            # Upload HUD/Surface stuff that was drawn to self.offscreen_hud
            if not self.hud_texture:
                from pygame._sdl2.video import Texture
                self.hud_texture = Texture.from_surface(self.renderer, self.offscreen_hud)
            else:
                self.hud_texture.update(self.offscreen_hud)
            
            self.renderer.blit(self.hud_texture, pygame.Rect(0, 0, self.width, self.height))
            self.renderer.present()
            # Clear offscreen_hud for next frame
            self.offscreen_hud.fill((0, 0, 0, 0))

            self.clock.tick(self.settings.get('fps', 60))

        pygame.mixer.stop()
        for vp in self.videos.values():
            if vp:
                vp.release()

    # ── Update Logic ─────────────────────────────────────────────────────
    # ── Pause / Resume ────────────────────────────────────────────────────

    def _pause(self, current_time):
        self.paused_at = current_time
        self.state = "PAUSED"
        pygame.mixer.pause()

    def _resume(self):
        """Start countdown before resuming."""
        self.state = "COUNTDOWN"
        self.countdown_start = time.perf_counter()

    def _finish_resume(self):
        """Actual resumption after countdown."""
        # Shift start_time so current_time resumes from paused_at
        pause_duration_sec = time.perf_counter() - self.start_time - (self.paused_at / 1000.0)
        self.start_time += pause_duration_sec
        self.state = "PLAYING"
        self.lane_pressed = [False] * NUM_LANES
        pygame.mixer.unpause()

    def _handle_pause_click(self, pos):
        mx, my = pos
        for rect, action in self._pause_buttons:
            if rect.collidepoint(mx, my):
                if action == "RESUME":
                    self._resume()
                elif action == "QUIT":
                    self.state = "QUIT"

    def _draw_paused(self):
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.offscreen_hud.blit(overlay, (0, 0))
        cx, cy = self.width // 2, self.height // 2

        font = pygame.font.SysFont(None, self._s(64))
        t = font.render("PAUSED", True, (255, 255, 255))
        self.offscreen_hud.blit(t, t.get_rect(center=(cx, cy - self._s(60))))

        mx, my = pygame.mouse.get_pos()
        btn_font = pygame.font.SysFont(None, self._s(48))
        self._pause_buttons = []
        labels = [("Resume", "RESUME"), ("Quit", "QUIT")]
        
        # Calculate total width for centering
        spacing = self._sx(40)
        total_w = 0
        render_data = [] # (label, action, surface)
        for label, action in labels:
            surf = btn_font.render(f"[ {label} ]", True, (200, 200, 200))
            w = surf.get_width()
            total_w += w
            render_data.append((label, action, surf))
        total_w += spacing * (len(labels) - 1)

        bx = cx - total_w // 2
        for label, action, base_surf in render_data:
            rect = base_surf.get_rect(topleft=(bx, cy + self._s(10)))
            hovered = rect.collidepoint(mx, my)
            color = (255, 255, 100) if hovered else (200, 200, 200)
            
            # Re-render with hover color if needed
            final_surf = btn_font.render(f"[ {label} ]", True, color) if hovered else base_surf
            
            self.offscreen_hud.blit(final_surf, rect)
            self._pause_buttons.append((rect, action))
            bx += base_surf.get_width() + spacing
            
        info = pygame.font.SysFont(None, self._s(32))
        hint = info.render("ESC to Resume | Q to Quit", True, (150, 150, 150))
        self.offscreen_hud.blit(hint, hint.get_rect(center=(cx, cy + self._s(120))))

    def _draw_countdown(self, val):
        """Show a countdown overlay (3, 2, 1)."""
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        self.offscreen_hud.blit(overlay, (0, 0))
        
        cx, cy = self.width // 2, self.height // 2
        font = pygame.font.SysFont(None, self._s(200))
        text = font.render(str(val), True, (255, 255, 100))
        self.offscreen_hud.blit(text, text.get_rect(center=(cx, cy)))

    # ── Update Logic ─────────────────────────────────────────────────────

    def _update(self, current_time):
        miss_window = JUDGMENT_DEFS["MISS"]["threshold_ms"] * self.hw_mult

        # Auto-miss
        for note in self.notes:
            if 'hit' not in note and 'miss' not in note:
                if current_time - note['time_ms'] > miss_window:
                    note['miss'] = True
                    self.set_judgment("MISS", note['lane'])

        # Background music
        for bgm in self.bgms:
            if 'played' not in bgm and current_time >= bgm['time_ms']:
                bgm['played'] = True
                self._play_sound(bgm['sample_id'])

        # BGA triggers
        for bga in self.bgas:
            if 'played' not in bga and current_time >= bga['time_ms']:
                bga['played'] = True
                self.current_bga_img = bga['bmp_id']

        # Song end check
        if current_time > self.max_time + SONG_END_PADDING_MS:
            self.state = "RESULT"

    # ── Drawing ──────────────────────────────────────────────────────────

    def _draw_playing(self, current_time):
        self.offscreen_hud.fill((0, 0, 0, 0)) # Transparent
            
        W, H = self.width, self.height

        # BGA
        self._draw_bga(current_time)

        # Lane backdrop & Separators
        self.renderer.draw_color = (60, 60, 60, 100) # Dark gray for boundaries
        # Far left edge
        self.renderer.draw_line((self.lane_x[0], 0), (self.lane_x[0], H))
        
        for i, x in enumerate(self.lane_x):
            self.renderer.draw_color = (30, 30, 30, LANE_BG_ALPHA)
            self.renderer.fill_rect((x, 0, self.lane_w, H))
            # Right separator for this lane
            self.renderer.draw_color = (60, 60, 60, 100)
            self.renderer.draw_line((x + self.lane_w, 0), (x + self.lane_w, H))

        # Judgment constants & Pulse
        perfect_h = max(4, self._s(int(HIT_ZONE_VISUAL_H * self.hw_mult)))
        great_h = max(4, self._s(int(GREAT_ZONE_VISUAL_H * self.hw_mult)))
        pulse = (math.sin(current_time / HIT_ZONE_PULSE_PERIOD) + 1) / 2
        hit_alpha = int(HIT_ZONE_ALPHA_MIN + pulse * HIT_ZONE_ALPHA_RANGE)

        # 2.5D Physical Judgment Bar
        # 1. Base Shadow (slightly larger)
        self.renderer.draw_color = (0, 0, 0, 150)
        self.renderer.fill_rect((self.lane_x[0] - 2, self.hit_y - perfect_h // 2, self.lane_total_w + 4, perfect_h + 2))
        
        # 2. Main Body (pulsing)
        self.renderer.draw_color = (255, 40, 40, hit_alpha)
        self.renderer.fill_rect((self.lane_x[0], self.hit_y - perfect_h // 2, self.lane_total_w, perfect_h))

        # 3. Center Glow Line (Red accent)
        # Using a fixed y offset for the line to be perfectly centered on hit_y
        self.renderer.draw_color = (255, 80, 80, min(255, hit_alpha + 150))
        self.renderer.fill_rect((self.lane_x[0], self.hit_y - 1, self.lane_total_w, 2))

        # Lane press glow
        for i, pressed in enumerate(self.lane_pressed):
            if pressed:
                # Lane flow
                self.renderer.draw_color = (100, 180, 255, 18)
                self.renderer.fill_rect((self.lane_x[i], 0, self.lane_w, H))
                # Hit zone glows
                self.renderer.draw_color = (0, 255, 0, 28)
                self.renderer.fill_rect((self.lane_x[i], self.hit_y - great_h // 2, self.lane_w, great_h))
                self.renderer.draw_color = (0, 255, 255, 45)
                self.renderer.fill_rect((self.lane_x[i], self.hit_y - perfect_h // 2, self.lane_w, perfect_h))

        # Hit effects
        self._draw_effects()

        # Judgment text
        if pygame.time.get_ticks() < self.judgment_timer:
            js = self.font.render(self.judgment_text, True, self.judgment_color)
            self.offscreen_hud.blit(js, js.get_rect(center=(W // 2, H // 2 - self._s(50))))

        # Combo
        if self.combo > 0:
            cs = self.font.render(str(self.combo), True, (255, 255, 255))
            self.offscreen_hud.blit(cs, cs.get_rect(center=(W // 2, H // 2 + self._s(20))))

        # Notes (with 2.5D styling)
        for note in self.notes:
            if 'hit' not in note and 'miss' not in note:
                td = note['time_ms'] - current_time
                y = (self.hit_y - self.note_h) - td * self.speed
                
                if -self.note_h <= y <= H:
                    color = (0, 255, 255) if len(note['sample_ids']) == 1 else (200, 255, 255)
                    nx, ny = self.lane_x[note['lane']], int(y)
                    
                    # 1. Bottom Shadow (Thickness)
                    shadow_h = 4
                    self.renderer.draw_color = (0, 0, 0, 180)
                    self.renderer.fill_rect((nx, ny + self.note_h - shadow_h, self.lane_w, shadow_h))
                    
                    # 2. Main Note Body
                    self.renderer.draw_color = color
                    self.renderer.fill_rect((nx, ny, self.lane_w, self.note_h - 2))
                    
                    # 3. Top Highlight (Glass/Plastic look)
                    self.renderer.draw_color = (255, 255, 255, 120)
                    self.renderer.fill_rect((nx, ny, self.lane_w, 2))

    def _draw_bga(self, current_time):
        bid = self.current_bga_img
        now = time.perf_counter()
        
        # Determine source surface (only needed for software or video Texture update)
        new_frame_arrived = False
        if bid and (now - self.last_bga_blit_time) > 0.016:
            if bid in self.videos and self.videos[bid]:
                new_img = self.videos[bid].get_frame(current_time)
                if new_img:
                    self.last_bga_surface = new_img
                    self.last_bga_blit_time = now
                    new_frame_arrived = True
            elif bid in self.images and self.images[bid]:
                if self.last_bga_surface != self.images[bid]:
                    self.last_bga_surface = self.images[bid]
                    new_frame_arrived = True
            else:
                self.last_bga_surface = None

        # Draw logic: GPU
        tex = None
        if not bid and hasattr(self, 'cover_texture'):
            tex = self.cover_texture
        elif bid in self.textures:
            tex = self.textures[bid]
        elif self.last_bga_surface:
            # Video or dynamic: update reusable bga_texture
            from pygame._sdl2.video import Texture
            if not self.bga_texture:
                self.bga_texture = Texture.from_surface(self.renderer, self.last_bga_surface)
                self.bga_updated_once = True
            elif new_frame_arrived:
                self.bga_texture.update(self.last_bga_surface)
            tex = self.bga_texture
        
        if tex:
            # Center and scale BGA
            tw, th = tex.width, tex.height
            # Scale to fill screen width while maintaining aspect ratio
            scaled_h = int(th * self.width / tw)
            self.renderer.blit(tex, pygame.Rect(0, (self.height - scaled_h) // 2, self.width, scaled_h))
            
            # Darken if necessary
            if not bid and hasattr(self, 'bga_dark_texture'):
                self.renderer.blit(self.bga_dark_texture, pygame.Rect(0, 0, self.width, self.height))

    def _draw_effects(self):
        for eff in self.effects[:]:
            eff['radius'] += EFFECT_EXPAND_SPEED
            eff['alpha'] -= EFFECT_FADE_SPEED
            if eff['alpha'] <= 0:
                self.effects.remove(eff)
            else:
                r = eff['radius']
                # 2.5D Layered Effect: Outer Fading Ring + Inner Solid Core
                # Outer ring
                surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(surf, (*eff['color'], eff['alpha']),
                                   (r, r), r, max(1, r // 4))
                
                # Inner glowing core (smaller, higher alpha)
                core_r = max(1, r // 2)
                core_alpha = min(255, eff['alpha'] * 2)
                pygame.draw.circle(surf, (255, 255, 255, core_alpha // 2),
                                   (r, r), core_r)
                
                self.offscreen_hud.blit(surf, (eff['x'] - r, eff['y'] - r))

    def _draw_result(self):
        # Background: Cover image if available, else dark blue
        if self.cover_img:
            self.offscreen_hud.blit(self.cover_img, (0, (self.height - self.cover_img.get_height()) // 2))
            darken = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            darken.fill((0, 0, 0, 180)) # Darker for result screen
            self.offscreen_hud.blit(darken, (0, 0))
        else:
            self.offscreen_hud.fill((20, 20, 35))

        res_font = pygame.font.SysFont(None, self._s(64))
        t = res_font.render("RESULT", True, (255, 255, 255))
        self.offscreen_hud.blit(t, t.get_rect(center=(self.width // 2, self._s(80))))

        y = self._s(180)
        for key in JUDGMENT_ORDER:
            color = JUDGMENT_DEFS[key]["color"]
            text = self.font.render(f"{key}: {self.judgments[key]}", True, color)
            self.offscreen_hud.blit(text, (self._sx(80), y))
            y += self._s(50)

        ct = self.font.render(f"MAX COMBO: {self.max_combo}", True, (200, 200, 255))
        self.offscreen_hud.blit(ct, (self._sx(80), y + self._s(20)))

        # ── Song Info (Right Side) ───────────────────────────────────────
        right_x = self._sx(440)
        y = self._s(180)
        
        meta_font = pygame.font.SysFont(None, self._s(40))
        small_meta_font = pygame.font.SysFont(None, self._s(28))
        
        # Title
        t_surf = meta_font.render(self.title, True, (255, 255, 255))
        self.offscreen_hud.blit(t_surf, (right_x, y))
        y += self._s(50)
        
        # Other Meta
        for key, label in [("artist", "Artist"), ("genre", "Genre"), ("level", "Level")]:
            val = self.metadata.get(key)
            if val and str(val) not in ('Unknown', '0'):
                s = small_meta_font.render(f"{label}: {val}", True, (200, 220, 240))
                self.offscreen_hud.blit(s, (right_x, y))
                y += self._s(32)

        info_font = pygame.font.SysFont(None, self._s(24))
        it = info_font.render("Press ENTER or ESC to Return", True, (150, 150, 150))
        self.offscreen_hud.blit(it, it.get_rect(center=(self.width // 2, self.height - self._s(50))))
