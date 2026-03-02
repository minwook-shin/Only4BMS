import pygame
from only4bms.i18n import get as _t
from only4bms import i18n as _i18n

class CourseMenu:
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
        
        # Options format: (Label lambda, Desc lambda, difficulty_str, duration_ms)
        self.options = [
            (lambda: _t("course_beg_title"), lambda: _t("course_beg_desc"), "BEGINNER", 30000),
            (lambda: _t("course_int_title"), lambda: _t("course_int_desc"), "INTERMEDIATE", 30000),
            (lambda: _t("course_adv_title"), lambda: _t("course_adv_desc"), "ADVANCED", 30000),
            (lambda: _t("course_ord_title"), lambda: _t("course_ord_desc"), "ORDEAL", 30000),
        ]
        self.selected_index = 0
        self.running = True
        self.result = None
        
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
                    self.result = ("QUIT", None, None)
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        self.selected_index = (self.selected_index - 1) % len(self.options)
                    elif event.key == pygame.K_DOWN:
                        self.selected_index = (self.selected_index + 1) % len(self.options)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        opt = self.options[self.selected_index]
                        if opt[2] is None:
                            self.result = ("QUIT", None, None)
                        else:
                            self.result = ("START", opt[2], opt[3])
                        self.running = False
                    elif event.key == pygame.K_ESCAPE:
                        self.result = ("QUIT", None, None)
                        self.running = False
                elif event.type == pygame.JOYHATMOTION:
                    vx, vy = event.value
                    if vy == 1:
                        self.selected_index = (self.selected_index - 1) % len(self.options)
                    elif vy == -1:
                        self.selected_index = (self.selected_index + 1) % len(self.options)
                elif event.type == pygame.JOYBUTTONDOWN:
                    if event.button == 0:
                        opt = self.options[self.selected_index]
                        if opt[2] is None:
                            self.result = ("QUIT", None, None)
                        else:
                            self.result = ("START", opt[2], opt[3])
                        self.running = False
                    elif event.button == 1:
                        self.result = ("QUIT", None, None)
                        self.running = False
            
            # Draw
            for y in range(self.h):
                grad = 1.0 - (y / self.h)
                c = [int(25 * grad), int(25 * grad), int(45 * grad + 25)]
                pygame.draw.line(self.screen, c, (0, y), (self.w, y))
                
            title = self.title_font.render(_t("menu_course"), True, (0, 255, 200))
            self.screen.blit(title, (self._cx(title), self._s(60)))
            
            panel_w, panel_h = self._s(500), self._s(380)
            px, py = (self.w - panel_w) // 2, (self.h - panel_h) // 2 + self._s(40)
            
            pygame.draw.rect(self.screen, (15, 15, 25, 230), (px, py, panel_w, panel_h), border_radius=10)
            pygame.draw.rect(self.screen, (0, 255, 200), (px, py, panel_w, panel_h), 2, border_radius=10)
            
            opt_y = py + self._s(20)
            spacing = self._s(82)
            
            for i, opt in enumerate(self.options):
                box_h = self._s(76)
                rect = pygame.Rect(px + self._s(10), opt_y + i * spacing, panel_w - self._s(20), box_h)
                
                if i == self.selected_index:
                    pygame.draw.rect(self.screen, (40, 50, 80, 225), rect, border_radius=5)
                    pygame.draw.rect(self.screen, (0, 255, 200), rect, 1, border_radius=5)
                    color = (0, 255, 200)
                else:
                    color = (180, 180, 200)
                    
                text = self.font.render(opt[0](), True, color)
                
                desc_text = opt[1]()
                if desc_text:
                    # Truncate description if too long for the box
                    max_w = panel_w - self._s(70)
                    while self.desc_font.size(desc_text)[0] > max_w and len(desc_text) > 5:
                        desc_text = desc_text[:-1]
                    if desc_text != opt[1]():
                        desc_text += "..."
                        
                    # Draw Title slightly higher to avoid overlap
                    self.screen.blit(text, (px + self._s(30), rect.top + self._s(6)))
                    # Draw Description below with enough margin
                    desc_surf = self.desc_font.render(desc_text, True, (130, 150, 170))
                    self.screen.blit(desc_surf, (px + self._s(35), rect.top + self._s(46)))
                else:
                    self.screen.blit(text, (px + self._s(30), rect.centery - text.get_height() // 2))

            # Back button hint (localized)
            back_hint_txt = _t("course_back_hint")
            back_hint = self.small_font.render(back_hint_txt, True, (100, 110, 140))
            self.screen.blit(back_hint, (px + panel_w - back_hint.get_width() - self._s(20), py + panel_h - self._s(35)))
                
            if not texture:
                texture = Texture.from_surface(self.renderer, self.screen)
            else:
                texture.update(self.screen)
                
            self.renderer.clear()
            self.renderer.blit(texture, pygame.Rect(0, 0, self.w, self.h))
            self.renderer.present()
            clock.tick(60)
            
        pygame.key.set_repeat(0)
        return self.result
