import pygame
import math
import time
from only4bms.i18n import get as _t
from only4bms import i18n as _i18n
from ..game.challenge import ChallengeManager

class ChallengeMenu:
    def __init__(self, settings, renderer, window):
        self.settings = settings
        self.renderer = renderer
        self.window = window
        self.w, self.h = window.size
        self.sx, self.sy = self.w / 800.0, self.h / 600.0
        
        self.screen = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.font = _i18n.font("menu_option", self.sy)
        self.title_font = _i18n.font("menu_title", self.sy, bold=True)
        self.small_font = _i18n.font("menu_small", self.sy)
        self.desc_font = _i18n.font("menu_small", self.sy)
        
        self.manager = ChallengeManager()
        # Build display list: regular challenges + hidden section (if applicable)
        self._rebuild_options()
        self.selected_index = 0
        self.scroll_offset = 0
        self.running = True
        
    def _rebuild_options(self):
        """Build the visible option list based on completion state."""
        self.regular_challenges = self.manager.get_visible_challenges()
        self.hidden_challenges = self.manager.get_hidden_challenges()
        self.show_hidden = self.manager.all_regular_completed()
        
        if self.show_hidden:
            self.options = self.regular_challenges + self.hidden_challenges
        else:
            self.options = self.regular_challenges[:]

    def _s(self, v): return max(1, int(v * self.sy))
    def _cx(self, surf): return (self.w - surf.get_width()) // 2
    
    def run(self):
        from pygame._sdl2.video import Texture
        clock = pygame.time.Clock()
        texture = None
        pygame.key.set_repeat(300, 50)
        
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        self.selected_index = (self.selected_index - 1) % len(self.options)
                    elif event.key == pygame.K_DOWN:
                        self.selected_index = (self.selected_index + 1) % len(self.options)
                    elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                        self.running = False
                elif event.type == pygame.JOYHATMOTION:
                    vx, vy = event.value
                    if vy == 1:
                        self.selected_index = (self.selected_index - 1) % len(self.options)
                    elif vy == -1:
                        self.selected_index = (self.selected_index + 1) % len(self.options)
                elif event.type == pygame.JOYBUTTONDOWN:
                    if event.button == 1: # B
                        self.running = False
            
            # Auto-scroll logic
            visible_count = 5
            if self.selected_index < self.scroll_offset:
                self.scroll_offset = self.selected_index
            elif self.selected_index >= self.scroll_offset + visible_count:
                self.scroll_offset = self.selected_index - visible_count + 1

            # Draw
            # Gradient background
            for y in range(self.h):
                grad = 1.0 - (y / self.h)
                c = [int(30 * grad), int(15 * grad), int(35 * grad + 20)]
                pygame.draw.line(self.screen, c, (0, y), (self.w, y))
                
            title = self.title_font.render(_t("menu_challenge"), True, (255, 200, 0))
            self.screen.blit(title, (self._cx(title), self._s(40)))
            
            panel_w, panel_h = self._s(600), self._s(420)
            px, py = (self.w - panel_w) // 2, (self.h - panel_h) // 2 + self._s(40)
            
            pygame.draw.rect(self.screen, (20, 15, 25, 230), (px, py, panel_w, panel_h), border_radius=10)
            pygame.draw.rect(self.screen, (255, 200, 0), (px, py, panel_w, panel_h), 2, border_radius=10)
            
            spacing = self._s(80)
            lang = _i18n.get_language()
            if lang not in ('ko', 'en'): lang = 'en'

            num_regular = len(self.regular_challenges)
            t_now = time.time()

            for i in range(visible_count):
                idx = i + self.scroll_offset
                if idx >= len(self.options): break
                
                challenge = self.options[idx]
                is_completed = challenge['id'] in self.manager.completed_ids
                is_hidden = challenge.get('hidden', False)
                
                box_h = self._s(72)
                rect = pygame.Rect(px + self._s(10), py + self._s(15) + i * spacing, panel_w - self._s(20), box_h)
                
                if is_hidden:
                    # Golden shimmer background for hidden challenge
                    shimmer = (math.sin(t_now * 3.0) + 1) / 2
                    gold_r = int(80 + 40 * shimmer)
                    gold_g = int(60 + 30 * shimmer)
                    gold_b = int(10 + 10 * shimmer)
                    pygame.draw.rect(self.screen, (gold_r, gold_g, gold_b, 200), rect, border_radius=5)
                    
                    # Gold border with pulse
                    border_alpha = int(180 + 75 * shimmer)
                    gold_border = (255, 215, 0)
                    pygame.draw.rect(self.screen, gold_border, rect, 2, border_radius=5)
                    
                    # Selection highlight
                    if idx == self.selected_index:
                        pygame.draw.rect(self.screen, (255, 215, 0, 40), rect, border_radius=5)
                        pygame.draw.rect(self.screen, (255, 230, 100), rect, 3, border_radius=5)
                    
                    # "★ HIDDEN" label
                    hidden_label = self.small_font.render(_t("challenge_hidden_label"), True, (255, 215, 0))
                    self.screen.blit(hidden_label, (rect.left + self._s(20), rect.top + self._s(2)))
                else:
                    # Selection highlight (regular)
                    if idx == self.selected_index:
                        pygame.draw.rect(self.screen, (60, 50, 20, 225), rect, border_radius=5)
                        pygame.draw.rect(self.screen, (255, 200, 0), rect, 2, border_radius=5)
                
                # Completion status bg
                if is_hidden:
                    status_color = (255, 215, 0) if is_completed else (180, 150, 60)
                else:
                    status_color = (0, 255, 100) if is_completed else (150, 150, 150)
                
                # Title
                title_key = f"ch_{challenge['id']}_title"
                title_color = (255, 215, 0) if (is_hidden and is_completed) else (status_color if is_completed else (200, 200, 200))
                title_surf = self.font.render(_t(title_key), True, title_color)
                title_y_off = self._s(5) if not is_hidden else self._s(18)
                self.screen.blit(title_surf, (rect.left + self._s(20), rect.top + title_y_off))
                
                # Description
                desc_key = f"ch_{challenge['id']}_desc"
                desc_color = (200, 180, 100) if is_hidden else (160, 160, 170)
                desc_surf = self.desc_font.render(_t(desc_key), True, desc_color)
                desc_y_off = self._s(42) if not is_hidden else self._s(50)
                self.screen.blit(desc_surf, (rect.left + self._s(25), rect.top + desc_y_off))
                
                # Status Label
                if is_hidden:
                    if is_completed:
                        status_label = _t("challenge_completed")
                        # Gold sparkle text
                        sparkle_r = int(255 - 30 * shimmer)
                        sparkle_g = int(215 - 20 * shimmer)
                        status_surf = self.small_font.render(status_label, True, (sparkle_r, sparkle_g, 0))
                    else:
                        status_label = _t("challenge_locked")
                        status_surf = self.small_font.render(status_label, True, (180, 150, 60))
                else:
                    status_label = _t("challenge_completed") if is_completed else _t("challenge_locked")
                    status_surf = self.small_font.render(status_label, True, status_color)
                self.screen.blit(status_surf, (rect.right - status_surf.get_width() - self._s(20), rect.centery - status_surf.get_height() // 2))

            # Scroll indicator
            if len(self.options) > visible_count:
                bar_h = panel_h - self._s(40)
                scroll_bar_h = max(20, bar_h * visible_count // len(self.options))
                scroll_y = py + self._s(20) + (bar_h - scroll_bar_h) * self.scroll_offset // (len(self.options) - visible_count)
                pygame.draw.rect(self.screen, (50, 50, 70), (px + panel_w - self._s(8), py + self._s(20), self._s(4), bar_h), border_radius=2)
                pygame.draw.rect(self.screen, (255, 200, 0), (px + panel_w - self._s(8), scroll_y, self._s(4), scroll_bar_h), border_radius=2)

            # Back button hint
            back_hint_txt = _t("course_back_hint")
            back_hint = self.small_font.render(back_hint_txt, True, (100, 110, 140))
            self.screen.blit(back_hint, (px + panel_w - back_hint.get_width() - self._s(20), py + panel_h - self._s(30)))
                
            # Draw Progress Bar & Completion Text (regular challenges only)
            total_challenges = len(self.regular_challenges)
            completed_challenges = len([c for c in self.regular_challenges if c['id'] in self.manager.completed_ids])
            progress_ratio = completed_challenges / total_challenges if total_challenges > 0 else 0
            
            bar_w = self._s(350)
            bar_h = self._s(12)
            bx = (self.w - bar_w) // 2
            by = py + panel_h + self._s(20)
            
            pygame.draw.rect(self.screen, (50, 50, 70), (bx, by, bar_w, bar_h), border_radius=6)
            if progress_ratio > 0:
                bar_color = (0, 255, 100) if progress_ratio == 1.0 else (255, 200, 0)
                pygame.draw.rect(self.screen, bar_color, (bx, by, int(bar_w * progress_ratio), bar_h), border_radius=6)
                
            progress_text = f"{completed_challenges} / {total_challenges} ({int(progress_ratio * 100)}%)"
            progress_surf = self.desc_font.render(progress_text, True, (200, 200, 200))
            self.screen.blit(progress_surf, (bx + bar_w + self._s(10), by - self._s(5)))
            
            if progress_ratio == 1.0:
                congrats_str = _t("challenge_all_cleared")
                congrats_surf = self.small_font.render(congrats_str, True, (0, 255, 100))
                bounce_y = int(math.sin(t_now * 5) * 5)
                self.screen.blit(congrats_surf, (bx - congrats_surf.get_width() - self._s(15), by - self._s(6) + bounce_y))
                
            if not texture:
                texture = Texture.from_surface(self.renderer, self.screen)
            else:
                texture.update(self.screen)
                
            self.renderer.clear()
            self.renderer.blit(texture, pygame.Rect(0, 0, self.w, self.h))
            self.renderer.present()
            clock.tick(60)
            
        pygame.key.set_repeat(0)

