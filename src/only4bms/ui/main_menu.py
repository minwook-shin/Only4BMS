import pygame
import sys

# ── Base (windowed) resolution ────────────────────────────────────────────
BASE_W, BASE_H = 800, 600

# ── Colors ────────────────────────────────────────────────────────────────
BG_COLOR = (20, 20, 30)
COLOR_SELECTED = (255, 255, 0)
COLOR_DEFAULT = (200, 200, 200)

class MainMenu:
    def __init__(self, settings, renderer, window):
        from pygame._sdl2.video import Texture
        self.settings = settings
        self.renderer = renderer
        self.window = window

        self.w, self.h = self.window.size
        self.sx, self.sy = self.w / BASE_W, self.h / BASE_H

        self.screen = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.texture = None

        pygame.display.set_caption("Only4BMS - Main Menu")
        self.clock = pygame.time.Clock()
        self.title_font = pygame.font.SysFont(None, self._s(80))
        self.font = pygame.font.SysFont(None, self._s(48))

        self.options = [
            ("SINGLE PLAYER", "SINGLE"),
            ("AI MULTI PLAYER", "AI_MULTI"),
            ("SETTINGS", "SETTINGS"),
            ("QUIT", "QUIT")
        ]
        self.selected_index = 0
        self.running = True
        self.action = "QUIT"

    def _s(self, v):
        return max(1, int(v * self.sy))

    def _cx(self, surface):
        return (self.w - surface.get_width()) // 2

    def run(self):
        from pygame._sdl2.video import Texture
        pygame.key.set_repeat(300, 50)
        while self.running:
            self._handle_events()
            self._draw()

            if not self.texture:
                self.texture = Texture.from_surface(self.renderer, self.screen)
            else:
                self.texture.update(self.screen)

            self.renderer.clear()
            self.renderer.blit(self.texture, pygame.Rect(0, 0, self.w, self.h))
            self.renderer.present()

            self.clock.tick(self.settings.get('fps', 60))

        pygame.key.set_repeat(0)
        return self.action

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.action = "QUIT"
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    self.selected_index = (self.selected_index - 1) % len(self.options)
                elif event.key == pygame.K_DOWN:
                    self.selected_index = (self.selected_index + 1) % len(self.options)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.action = self.options[self.selected_index][1]
                    self.running = False
                elif event.key == pygame.K_ESCAPE:
                    self.action = "QUIT"
                    self.running = False
            elif event.type == pygame.MOUSEMOTION:
                mx, my = event.pos
                self._update_hover(mx, my)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if self._update_hover(mx, my):
                    self.action = self.options[self.selected_index][1]
                    self.running = False

    def _update_hover(self, mx, my):
        start_y = self._s(250)
        spacing = self._s(70)
        for i, (label, _) in enumerate(self.options):
            surf = self.font.render(label, True, COLOR_DEFAULT)
            rect = surf.get_rect(topleft=(self._cx(surf), start_y + i * spacing))
            if rect.collidepoint(mx, my):
                self.selected_index = i
                return True
        return False

    def _draw(self):
        self.screen.fill(BG_COLOR)

        # Title
        title_surf = self.title_font.render("Only4BMS", True, (0, 255, 255))
        self.screen.blit(title_surf, (self._cx(title_surf), self._s(100)))

        # Options
        start_y = self._s(250)
        spacing = self._s(70)
        for i, (label, _) in enumerate(self.options):
            color = COLOR_SELECTED if i == self.selected_index else COLOR_DEFAULT
            text_str = f"> {label} <" if i == self.selected_index else label
            surf = self.font.render(text_str, True, color)
            self.screen.blit(surf, (self._cx(surf), start_y + i * spacing))
