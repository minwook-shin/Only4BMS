import pygame
import sys
import math
import random
from only4bms.i18n import get as _t
from only4bms import i18n as _i18n
from .components import (
    make_bg_cache, draw_glass_panel, draw_outer_glow,
    draw_glow_text, draw_modal, draw_modal_button,
    C_TEXT_ACCENT, C_TEXT_PRIMARY, C_TEXT_SECONDARY, C_TEXT_DIM,
    C_TEXT_PURPLE, C_GLOW_CYAN, C_GLOW_PURPLE,
    C_GLASS_FILL, C_GLASS_HOVER, C_GLASS_SELECT,
    C_BORDER_DIM, C_BORDER_ACCENT,
    # Legacy exports
    COLOR_ACCENT, COLOR_SELECTED_BG, COLOR_TEXT_PRIMARY,
    COLOR_PANEL_BG, BASE_W, BASE_H,
)

COLOR_MOD_ACCENT      = C_GLOW_PURPLE
COLOR_TEXT_SECONDARY  = C_TEXT_SECONDARY
COLOR_HOVERED_BG      = ( 35,  35,  60, 160)
COLOR_MOD_SELECTED_BG = ( 50,  30,  80, 225)
COLOR_MOD_HOVERED_BG  = ( 40,  25,  65, 160)

_ITEM_SPACING_BASE = 58
_ITEM_H_BASE       = 50
_PANEL_W_BASE      = 380
_PANEL_PAD_TOP     = 16
_PANEL_PAD_BOT     = 12
_TITLE_Y_BASE      = 52
_TITLE_MARGIN      = 20


class MainMenu:
    def __init__(self, settings, renderer, window, mods=None):
        from pygame._sdl2.video import Texture
        self.settings = settings
        self.renderer = renderer
        self.window   = window
        self.mods     = mods or []

        self.w, self.h = self.window.size
        self.sx, self.sy = self.w / BASE_W, self.h / BASE_H

        self.screen  = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.texture = None
        self._bg     = make_bg_cache(self.w, self.h)

        pygame.display.set_caption("Only4BMS - Main Menu")
        self.clock      = pygame.time.Clock()
        self.title_font = _i18n.font("menu_title",  self.sy, bold=True)
        self.font       = _i18n.font("menu_option", self.sy * 0.85)
        self.small_font = _i18n.font("menu_small",  self.sy)

        # ── Menu items ──────────────────────────────────────────────────────
        self.options = [(lambda: _t("menu_single"), "SINGLE")]
        self.is_mod  = [False]
        if self.mods:
            self.options.append((lambda: _t("menu_mods"), "MODS"))
            self.is_mod.append(True)
        self.options += [
            (lambda: _t("menu_challenge"), "CHALLENGE"),
            (lambda: _t("menu_settings"),  "SETTINGS"),
            (lambda: _t("menu_quit"),       "QUIT"),
        ]
        self.is_mod += [False, False, False]

        self.selected_index = 0
        self.running        = True
        self.action         = "QUIT"

        self.show_quit_confirm = False
        self._quit_buttons     = []
        self.show_mods_popup   = False
        self.mods_popup_index  = 0
        self._mod_item_rects   = []

        self.ignore_confirm = (pygame.key.get_pressed()[pygame.K_RETURN] or
                               pygame.key.get_pressed()[pygame.K_SPACE])

        # ── Background particle notes ────────────────────────────────────────
        fps = self.settings.get("fps", 60)
        self.bg_speed = self.settings.get("speed", 1.0) * (1000.0 / fps)
        self.bg_notes = [
            {"lane": random.randint(0, 3), "y": random.uniform(-400, 0), "hit": False}
            for _ in range(10)
        ]
        self.bg_judgments = []
        self._anim_t      = 0.0   # continuous time for aurora

        self.version_str = self._detect_version()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _s(self, v):
        return max(1, int(v * self.sy))

    def _cx(self, surface):
        return (self.w - surface.get_width()) // 2

    def _detect_version(self):
        try:
            import tomllib, os
            curr = os.path.dirname(os.path.abspath(__file__))
            for _ in range(5):
                p = os.path.join(curr, "pyproject.toml")
                if os.path.exists(p):
                    with open(p, "rb") as f:
                        return f"v{tomllib.load(f)['project']['version']}"
                parent = os.path.dirname(curr)
                if parent == curr: break
                curr = parent
        except Exception:
            pass
        try:
            from importlib.metadata import version
            return f"v{version('only4bms')}"
        except Exception:
            return "OSS"

    def _layout(self):
        title_h    = self._s(76)
        title_bot  = self._s(_TITLE_Y_BASE) + title_h + self._s(_TITLE_MARGIN)
        available  = self.h - title_bot - self._s(50)
        n          = len(self.options)
        spacing    = max(self._s(40),
                         min(self._s(_ITEM_SPACING_BASE),
                             (available - self._s(_PANEL_PAD_TOP + _PANEL_PAD_BOT)) // n))
        panel_w    = self._s(_PANEL_W_BASE)
        panel_h    = self._s(_PANEL_PAD_TOP) + n * spacing + self._s(_PANEL_PAD_BOT)
        px         = (self.w - panel_w) // 2
        py         = title_bot
        return px, py, panel_w, panel_h, spacing, py + self._s(_PANEL_PAD_TOP)

    def _mods_popup_rect(self):
        pw = self._s(440)
        ph = self._s(80 + max(len(self.mods), 1) * 54 + 52)
        return pygame.Rect((self.w - pw) // 2, (self.h - ph) // 2, pw, ph)

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        from pygame._sdl2.video import Texture
        pygame.key.set_repeat(300, 50)
        pygame.event.clear()
        last_ms = pygame.time.get_ticks()

        while self.running:
            now_ms  = pygame.time.get_ticks()
            dt      = (now_ms - last_ms) / 1000.0
            last_ms = now_ms
            self._anim_t += dt

            self._handle_events()
            self._draw()
            if not self.texture:
                self.texture = Texture.from_surface(self.renderer, self.screen)
            else:
                self.texture.update(self.screen)
            self.renderer.clear()
            self.renderer.blit(self.texture, pygame.Rect(0, 0, self.w, self.h))
            self.renderer.present()
            self.clock.tick(self.settings.get("fps", 60))

        pygame.key.set_repeat(0)
        return self.action

    # ── Events ────────────────────────────────────────────────────────────────

    def _handle_events(self):
        from ..main import refresh_joysticks
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.action = "QUIT"; self.running = False
            elif event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                refresh_joysticks()
            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.ignore_confirm = False
            elif event.type == pygame.KEYDOWN:
                if self.show_mods_popup:
                    self._handle_mods_popup_key(event.key); continue
                if self.show_quit_confirm:
                    if   event.key == pygame.K_RETURN:
                        self.action = "QUIT"; self.running = False
                    elif event.key == pygame.K_ESCAPE:
                        self.show_quit_confirm = False
                    continue
                if   event.key == pygame.K_UP:
                    self.selected_index = (self.selected_index - 1) % len(self.options)
                elif event.key == pygame.K_DOWN:
                    self.selected_index = (self.selected_index + 1) % len(self.options)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if not self.ignore_confirm:
                        self._activate(self.options[self.selected_index][1])
                elif event.key == pygame.K_ESCAPE:
                    self.show_quit_confirm = True
            elif event.type == pygame.JOYBUTTONDOWN:
                if self.show_mods_popup:
                    if   event.button == 0: self._launch_mod(self.mods_popup_index)
                    elif event.button == 1: self.show_mods_popup = False
                    continue
                if self.show_quit_confirm:
                    if   event.button == 0: self.action = "QUIT"; self.running = False
                    elif event.button == 1: self.show_quit_confirm = False
                    continue
                if   event.button == 0: self._activate(self.options[self.selected_index][1])
                elif event.button == 1: self.show_quit_confirm = True
            elif event.type == pygame.JOYHATMOTION:
                vx, vy = event.value
                if vx == 0 and vy == 0: continue
                if self.show_mods_popup:
                    if vy ==  1: self.mods_popup_index = (self.mods_popup_index - 1) % len(self.mods)
                    if vy == -1: self.mods_popup_index = (self.mods_popup_index + 1) % len(self.mods)
                    continue
                if vy ==  1: self.selected_index = (self.selected_index - 1) % len(self.options)
                if vy == -1: self.selected_index = (self.selected_index + 1) % len(self.options)
            elif event.type == pygame.MOUSEMOTION:
                if self.show_mods_popup:
                    self._update_mods_hover(*event.pos); continue
                if not self.show_quit_confirm:
                    self._update_hover(*event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if self.show_mods_popup:
                    self._handle_mods_popup_click(mx, my); continue
                if self.show_quit_confirm:
                    self._handle_quit_click(mx, my); continue
                if self._update_hover(mx, my):
                    self._activate(self.options[self.selected_index][1])

    def _handle_mods_popup_key(self, key):
        if   key == pygame.K_ESCAPE: self.show_mods_popup = False
        elif key == pygame.K_UP:    self.mods_popup_index = (self.mods_popup_index - 1) % len(self.mods)
        elif key == pygame.K_DOWN:  self.mods_popup_index = (self.mods_popup_index + 1) % len(self.mods)
        elif key in (pygame.K_RETURN, pygame.K_SPACE): self._launch_mod(self.mods_popup_index)

    def _handle_mods_popup_click(self, mx, my):
        if not self._mods_popup_rect().collidepoint(mx, my):
            self.show_mods_popup = False; return
        for i, rect in enumerate(self._mod_item_rects):
            if rect.collidepoint(mx, my):
                if self.mods_popup_index == i: self._launch_mod(i)
                else: self.mods_popup_index = i
                return

    def _update_mods_hover(self, mx, my):
        for i, rect in enumerate(self._mod_item_rects):
            if rect.collidepoint(mx, my):
                self.mods_popup_index = i; return

    def _launch_mod(self, index):
        self.action = self.mods[index].action
        self.running = False

    def _activate(self, action):
        if   action == "QUIT": self.show_quit_confirm = True
        elif action == "MODS": self.mods_popup_index = 0; self.show_mods_popup = True
        else: self.action = action; self.running = False

    def _update_hover(self, mx, my):
        if self.show_quit_confirm: return False
        px, py, pw, ph, spacing, opt_start_y = self._layout()
        item_h = self._s(_ITEM_H_BASE)
        for i in range(len(self.options)):
            rect = pygame.Rect(px, opt_start_y + i * spacing, pw, item_h)
            if rect.collidepoint(mx, my):
                self.selected_index = i; return True
        return False

    def _handle_quit_click(self, mx, my):
        for rect, action in self._quit_buttons:
            if rect.collidepoint(mx, my):
                if action == "YES": self.action = "QUIT"; self.running = False
                else: self.show_quit_confirm = False

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self):
        mx, my = pygame.mouse.get_pos()
        self.screen.blit(self._bg, (0, 0))

        # ── Background lane animation ──
        self._draw_bg_animation()

        # ── Title with glow ──
        title_y = self._s(_TITLE_Y_BASE)
        draw_glow_text(self.screen, "Only4BMS", self.title_font,
                       C_TEXT_ACCENT, C_GLOW_CYAN,
                       (self.w // 2, title_y), anchor="center", glow_radius=6)

        # Thin accent line under title
        line_w = self._s(220)
        lx     = (self.w - line_w) // 2
        ly     = title_y + self._s(80)
        for x in range(line_w):
            t = 1.0 - abs(x - line_w / 2) / (line_w / 2 + 1)
            self.screen.set_at((lx + x, ly), (*C_GLOW_CYAN, int(80 * t)))

        # ── Menu panel ──
        px, py, pw, ph, spacing, opt_start_y = self._layout()
        draw_glass_panel(self.screen, pygame.Rect(px, py, pw, ph),
                         radius=16, fill_alpha=10, highlight=True)

        # ── Options ──
        item_h = self._s(_ITEM_H_BASE)
        for i, (label_fn, _) in enumerate(self.options):
            is_mod = self.is_mod[i]
            accent = C_GLOW_PURPLE if is_mod else C_GLOW_CYAN
            item_rect = pygame.Rect(px + self._s(10),
                                    opt_start_y + i * spacing,
                                    pw - self._s(20), item_h)

            if i == self.selected_index:
                fill_col   = (*accent, 20)
                border_col = (*accent, 200)
                txt_col    = accent
                draw_outer_glow(self.screen, item_rect, accent,
                                radius=8, passes=4, max_alpha=30)
                # Left pip
                pygame.draw.rect(self.screen, accent,
                                 pygame.Rect(item_rect.x + 4,
                                             item_rect.y + 8, 3,
                                             item_h - 16), border_radius=2)
            elif item_rect.collidepoint(mx, my):
                fill_col   = C_GLASS_HOVER
                border_col = C_BORDER_DIM
                txt_col    = C_TEXT_PRIMARY
            else:
                fill_col   = C_GLASS_FILL
                border_col = C_BORDER_DIM
                txt_col    = C_TEXT_SECONDARY

            panel = pygame.Surface(item_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(panel, fill_col, (0, 0, *item_rect.size), border_radius=8)
            self.screen.blit(panel, item_rect.topleft)
            pygame.draw.rect(self.screen, border_col, item_rect, 1, border_radius=8)

            lbl = self.font.render(label_fn(), True, txt_col)
            self.screen.blit(lbl, lbl.get_rect(center=item_rect.center))

        # ── Footer ──
        copy_surf = self.small_font.render("© 2026 Only4BMS", True, C_TEXT_DIM)
        ver_surf  = self.small_font.render(self.version_str, True, C_TEXT_DIM)
        self.screen.blit(copy_surf, (self._s(20), self.h - self._s(32)))
        self.screen.blit(ver_surf,  (self.w - ver_surf.get_width() - self._s(20),
                                     self.h - self._s(32)))

        # ── Overlays ──
        if self.show_quit_confirm:
            self._draw_quit_confirm(mx, my)
        elif self.show_mods_popup:
            self._draw_mods_popup(mx, my)

    # ── Overlays ─────────────────────────────────────────────────────────────

    def _draw_quit_confirm(self, mx, my):
        cx, cy = self.w // 2, self.h // 2
        mw, mh = self._s(380), self._s(200)
        modal_rect = pygame.Rect(cx - mw // 2, cy - mh // 2, mw, mh)
        draw_modal(self.screen, modal_rect,
                   _t("quit_confirm"), self.font)

        self._quit_buttons = []
        labels = [(_t("yes"), "YES"), (_t("no"), "NO")]
        total_w = self._s(200)
        bx = cx - total_w // 2
        btn_w, btn_h = self._s(88), self._s(40)
        for label, action in labels:
            btn_rect = pygame.Rect(bx, cy + self._s(40), btn_w, btn_h)
            draw_modal_button(self.screen, btn_rect, label, self.font,
                              hovered=btn_rect.collidepoint(mx, my))
            self._quit_buttons.append((btn_rect, action))
            bx += self._s(112)

    def _draw_mods_popup(self, mx, my):
        popup_rect = self._mods_popup_rect()
        px, py = popup_rect.x, popup_rect.y
        pw, ph = popup_rect.width, popup_rect.height
        div_y  = draw_modal(self.screen, popup_rect,
                             _t("menu_mods"), self.font)

        item_h       = self._s(46)
        item_spacing = self._s(52)
        list_top     = div_y + self._s(8)
        self._mod_item_rects = []

        for i, mod in enumerate(self.mods):
            name_fn   = mod.name_fn if mod.name_fn else (lambda n=mod.name: n)
            item_rect = pygame.Rect(px + self._s(12),
                                    list_top + i * item_spacing,
                                    pw - self._s(24), item_h)
            self._mod_item_rects.append(item_rect)
            draw_modal_button(self.screen, item_rect, name_fn(), self.font,
                              selected=(i == self.mods_popup_index),
                              hovered=item_rect.collidepoint(mx, my))

        # Hint
        hint_surf = self.small_font.render(_t("mods_popup_hint"), True, C_TEXT_DIM)
        hint_y    = py + ph - self._s(28)
        pygame.draw.line(self.screen, (*C_GLOW_PURPLE, 35),
                         (px + self._s(16), hint_y - self._s(6)),
                         (px + pw - self._s(16), hint_y - self._s(6)), 1)
        self.screen.blit(hint_surf, hint_surf.get_rect(centerx=px + pw // 2, top=hint_y))

    # ── Background animation ──────────────────────────────────────────────────

    def _draw_bg_animation(self):
        now  = pygame.time.get_ticks()
        hit_y_base = 500

        lane_w  = self._s(75)
        total_w = lane_w * 4
        start_x = (self.w - total_w) // 2
        hit_y   = self._s(hit_y_base)

        # Subtle lane tint
        lane_tint = pygame.Surface((total_w, self.h), pygame.SRCALPHA)
        lane_tint.fill((255, 255, 255, 5))
        self.screen.blit(lane_tint, (start_x, 0))

        # Lane dividers
        for i in range(5):
            lx = start_x + i * lane_w
            pygame.draw.line(self.screen, (*C_GLOW_CYAN, 8), (lx, 0), (lx, self.h), 1)

        # Hit zone glow
        pulse     = (math.sin(self._anim_t * 3.0) + 1) / 2
        hit_alpha = int(18 + pulse * 18)
        hz = pygame.Surface((total_w, self._s(24)), pygame.SRCALPHA)
        for y in range(hz.get_height()):
            t = 1.0 - y / hz.get_height()
            hz.fill((*C_GLOW_CYAN, int(hit_alpha * t)), (0, y, total_w, 1))
        self.screen.blit(hz, (start_x, hit_y - self._s(12)))

        # Update and draw falling notes
        for note in self.bg_notes:
            note["y"] += self.bg_speed
            if not note["hit"] and note["y"] >= hit_y_base:
                note["hit"] = True
                self.bg_judgments.append({"lane": note["lane"], "timer": now})
                if len(self.bg_judgments) > 12:
                    self.bg_judgments.pop(0)
            if note["y"] > BASE_H + 60:
                note["y"]   = random.uniform(-350, -40)
                note["lane"] = random.randint(0, 3)
                note["hit"] = False

        note_h = self._s(18)
        for note in self.bg_notes:
            if note["hit"]: continue
            nx = start_x + note["lane"] * lane_w + self._s(3)
            ny = int(note["y"] * self.sy)
            nw = lane_w - self._s(6)
            if ny + note_h < 0 or ny > self.h: continue
            # Body
            body = pygame.Surface((nw, note_h), pygame.SRCALPHA)
            body.fill((*C_GLOW_CYAN, 32))
            self.screen.blit(body, (nx, ny))
            # Top highlight
            pygame.draw.line(self.screen, (*C_GLOW_CYAN, 55), (nx, ny), (nx + nw, ny), 1)

        # Judgment flash effects
        for j in self.bg_judgments[:]:
            elapsed = now - j["timer"]
            if elapsed > 500:
                self.bg_judgments.remove(j); continue
            t_fade   = 1.0 - elapsed / 500.0
            flash_a  = int(28 * t_fade)
            fx       = start_x + j["lane"] * lane_w
            fl       = pygame.Surface((lane_w, hit_y), pygame.SRCALPHA)
            fl.fill((*C_GLOW_CYAN, flash_a))
            self.screen.blit(fl, (fx, 0))
