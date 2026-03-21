"""ui/components.py — Glassmorphism design system
visual language for Only4BMS.

All draw functions target a pygame.Surface (SRCALPHA-capable).
Caller is responsible for supplying a scale factor `sy` where needed.
"""
import pygame
import math

# ── Colour Palette ─────────────────────────────────────────────────────────
# Backgrounds
C_BG_TOP    = (10,  10,  28)
C_BG_MID    = ( 8,   6,  22)
C_BG_BOT    = ( 5,   4,  14)

# Glass surfaces (SRCALPHA)
C_GLASS_FILL   = (255, 255, 255, 12)
C_GLASS_HOVER  = (255, 255, 255, 22)
C_GLASS_SELECT = (  0, 212, 255, 18)   # cyan tint
C_GLASS_CAT    = (180,  80, 255, 10)   # purple tint for category

# Borders
C_BORDER_DIM    = (255, 255, 255, 32)
C_BORDER_ACCENT = (  0, 212, 255, 200)
C_BORDER_PURPLE = (180,  80, 255, 160)
C_BORDER_CAT    = (  0, 212, 255,  55)

# Text
C_TEXT_PRIMARY  = (232, 240, 255)
C_TEXT_SECONDARY= (140, 155, 195)
C_TEXT_DIM      = ( 70,  85, 125)
C_TEXT_ACCENT   = (  0, 212, 255)   # cyan
C_TEXT_PURPLE   = (200, 120, 255)   # purple

# Glow
C_GLOW_CYAN   = (  0, 212, 255)
C_GLOW_PURPLE = (180,  80, 255)

# Legacy aliases (imported by calibration_menu / key_config_menu)
COLOR_ACCENT      = C_GLOW_CYAN
COLOR_SELECTED_BG = ( 40,  50,  80, 225)
COLOR_TEXT_PRIMARY = C_TEXT_PRIMARY
COLOR_PANEL_BG    = ( 15,  15,  25, 230)
BASE_W, BASE_H    = 800, 600


def _lerp3(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ── Background ──────────────────────────────────────────────────────────────

def draw_bg(surf: pygame.Surface):
    """Three-stop dark gradient + faint top-center radial orb (Arcaea feel)."""
    w, h = surf.get_size()

    # Gradient
    for y in range(h):
        t = y / max(h - 1, 1)
        c = _lerp3(C_BG_TOP, C_BG_MID, min(1, t * 2)) if t < 0.5 \
            else _lerp3(C_BG_MID, C_BG_BOT, (t - 0.5) * 2)
        pygame.draw.line(surf, c, (0, y), (w, y))

    # Radial orb
    orb_r = int(min(w, h) * 0.42)
    orb = pygame.Surface((orb_r * 2, orb_r * 2), pygame.SRCALPHA)
    steps = max(1, orb_r // 20)
    for r in range(orb_r, 0, -steps):
        a = int(10 * (1.0 - r / orb_r))
        pygame.draw.circle(orb, (55, 18, 95, a), (orb_r, orb_r), r)
    surf.blit(orb, (w // 2 - orb_r, -orb_r // 2))

    # Horizontal scan-line shimmer (DJMAX signature)
    shimmer_y = h // 3
    scan = pygame.Surface((w, 1), pygame.SRCALPHA)
    for x in range(w):
        t = 1.0 - abs(x - w / 2) / (w / 2 + 1)
        scan.set_at((x, 0), (80, 200, 255, int(14 * t ** 1.2)))
    surf.blit(scan, (0, shimmer_y))


def make_bg_cache(w: int, h: int) -> pygame.Surface:
    """Pre-render the background once; blit every frame."""
    surf = pygame.Surface((w, h))
    draw_bg(surf)
    return surf


# ── Glass Panel ─────────────────────────────────────────────────────────────

def draw_glass_panel(surf: pygame.Surface, rect: pygame.Rect,
                     border_color=None, radius: int = 12,
                     fill_alpha: int = 12, highlight: bool = True):
    """Frosted-glass card: semi-transparent fill + thin border + top highlight."""
    if border_color is None:
        border_color = C_BORDER_DIM

    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(panel, (*C_GLASS_FILL[:3], fill_alpha),
                     (0, 0, *rect.size), border_radius=radius)
    surf.blit(panel, rect.topleft)
    pygame.draw.rect(surf, border_color, rect, 1, border_radius=radius)

    if highlight and rect.width > radius * 4 and rect.height > 8:
        hi_w = rect.width - radius * 2
        hi = pygame.Surface((hi_w, 1), pygame.SRCALPHA)
        for x in range(hi_w):
            t = 1.0 - abs(x - hi_w / 2) / (hi_w / 2 + 1)
            hi.set_at((x, 0), (255, 255, 255, int(22 * t)))
        surf.blit(hi, (rect.x + radius, rect.y + 1))


def draw_outer_glow(surf: pygame.Surface, rect: pygame.Rect,
                    color, radius: int = 10,
                    passes: int = 4, max_alpha: int = 35):
    """Soft outer glow for focused / selected elements."""
    for i in range(passes, 0, -1):
        expand = i * 2
        alpha  = int(max_alpha * (1.0 - i / (passes + 1)))
        gr = rect.inflate(expand * 2, expand * 2)
        pygame.draw.rect(surf, (*color[:3], alpha), gr, 1,
                         border_radius=radius + expand)


# ── Settings Row ─────────────────────────────────────────────────────────────

def draw_row(surf: pygame.Surface, rect: pygame.Rect,
             label: str, font,
             selected: bool = False, hovered: bool = False,
             value_text: str = None, value_font=None,
             radius: int = 8, pad_x: int = 20,
             accent: tuple = None):
    """Standard settings row: label left, chevron-value right."""
    if accent is None:
        accent = C_GLOW_CYAN

    if selected:
        fill_col   = C_GLASS_SELECT
        border_col = (*accent, 200)
        text_col   = C_TEXT_ACCENT
        draw_outer_glow(surf, rect, accent, radius, passes=4, max_alpha=32)
    elif hovered:
        fill_col   = C_GLASS_HOVER
        border_col = C_BORDER_DIM
        text_col   = C_TEXT_PRIMARY
    else:
        fill_col   = C_GLASS_FILL
        border_col = C_BORDER_DIM
        text_col   = C_TEXT_SECONDARY

    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(panel, fill_col, (0, 0, *rect.size), border_radius=radius)
    surf.blit(panel, rect.topleft)
    pygame.draw.rect(surf, border_col, rect, 1, border_radius=radius)

    # Left accent pip for selected
    if selected:
        pip_h = rect.height - 16
        pygame.draw.rect(surf, accent,
                         pygame.Rect(rect.x + 4, rect.y + 8, 3, pip_h),
                         border_radius=2)

    lbl = font.render(label, True, text_col)
    surf.blit(lbl, (rect.x + pad_x + (7 if selected else 0),
                    rect.centery - lbl.get_height() // 2))

    if value_text is not None and value_font is not None:
        val_col = C_TEXT_ACCENT if selected else C_TEXT_SECONDARY
        val = value_font.render(f"◀  {value_text}  ▶", True, val_col)
        surf.blit(val, (rect.right - val.get_width() - pad_x,
                        rect.centery - val.get_height() // 2))


# ── Category Header ──────────────────────────────────────────────────────────

def draw_category(surf: pygame.Surface, rect: pygame.Rect,
                  label: str, font):
    """Section divider: purple vertical pip + label + fading rule."""
    pip_h = max(4, rect.height - 14)
    pygame.draw.rect(surf, C_GLOW_PURPLE,
                     pygame.Rect(rect.x, rect.y + (rect.height - pip_h) // 2,
                                 3, pip_h), border_radius=2)

    txt = font.render(label, True, C_TEXT_PURPLE)
    tx  = rect.x + 14
    ty  = rect.centery - txt.get_height() // 2
    surf.blit(txt, (tx, ty))

    rule_x = tx + txt.get_width() + 10
    rule_y = rect.centery
    rule_w = rect.right - rule_x
    if rule_w > 4:
        rule = pygame.Surface((rule_w, 1), pygame.SRCALPHA)
        for x in range(rule_w):
            t = 1.0 - x / rule_w
            rule.set_at((x, 0), (*C_GLOW_PURPLE, int(45 * t)))
        surf.blit(rule, (rule_x, rule_y))


# ── Pill Button ──────────────────────────────────────────────────────────────

def draw_pill_button(surf: pygame.Surface, rect: pygame.Rect,
                     label: str, font,
                     hovered: bool = False, accent: tuple = None):
    """Small action pill button (Calibrate, Key Config, …)."""
    if accent is None:
        accent = C_GLOW_CYAN

    fill_a   = 30 if hovered else 10
    border_a = 220 if hovered else 90
    r        = rect.height // 2

    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(panel, (*accent, fill_a), (0, 0, *rect.size),
                     border_radius=r)
    surf.blit(panel, rect.topleft)
    pygame.draw.rect(surf, (*accent, border_a), rect, 1, border_radius=r)

    if hovered:
        draw_outer_glow(surf, rect, accent, radius=r, passes=3, max_alpha=25)

    txt_col = C_TEXT_ACCENT if hovered else C_TEXT_SECONDARY
    txt = font.render(label, True, txt_col)
    surf.blit(txt, txt.get_rect(center=rect.center))


# ── Glow Text ─────────────────────────────────────────────────────────────────

def draw_glow_text(surf: pygame.Surface, text: str, font,
                   color, glow_color, pos: tuple,
                   anchor: str = 'topleft', glow_radius: int = 4):
    """Text with layered soft glow behind it."""
    main = font.render(text, True, color)
    w, h = main.get_size()

    if   anchor == 'center':   x, y = pos[0] - w // 2, pos[1] - h // 2
    elif anchor == 'topright': x, y = pos[0] - w,       pos[1]
    elif anchor == 'midleft':  x, y = pos[0],            pos[1] - h // 2
    else:                      x, y = pos  # topleft

    glow = font.render(text, True, glow_color)
    for g in range(glow_radius, 0, -1):
        alpha = int(65 * (1.0 - g / glow_radius))
        gs = pygame.Surface((w + g * 2, h + g * 2), pygame.SRCALPHA)
        gs.blit(glow, (g, g))
        gs.set_alpha(alpha)
        surf.blit(gs, (x - g, y - g))

    surf.blit(main, (x, y))


# ── Hint Bar ──────────────────────────────────────────────────────────────────

def draw_hint_bar(surf: pygame.Surface, text: str, font,
                  y_bottom: int, w: int):
    """Full-width translucent hint strip at the bottom."""
    bar_h = font.get_height() + 14
    bar   = pygame.Surface((w, bar_h), pygame.SRCALPHA)
    bar.fill((0, 0, 0, 55))
    surf.blit(bar, (0, y_bottom - bar_h))
    pygame.draw.line(surf, (*C_GLOW_CYAN, 25),
                     (0, y_bottom - bar_h), (w, y_bottom - bar_h), 1)
    txt = font.render(text, True, C_TEXT_DIM)
    surf.blit(txt, txt.get_rect(center=(w // 2, y_bottom - bar_h // 2)))


# ── Scrollbar ─────────────────────────────────────────────────────────────────

def draw_scrollbar(surf: pygame.Surface, x: int, y: int, h: int,
                   ratio_start: float, ratio_end: float):
    """Slim right-aligned scrollbar."""
    bar_w = 3
    pygame.draw.rect(surf, (*C_BORDER_DIM[:3], 18),
                     pygame.Rect(x, y, bar_w, h), border_radius=2)
    thumb_y = y + int(h * ratio_start)
    thumb_h = max(24, int(h * (ratio_end - ratio_start)))
    pygame.draw.rect(surf, (*C_GLOW_CYAN, 160),
                     pygame.Rect(x, thumb_y, bar_w, thumb_h), border_radius=2)


# ── Overlay ───────────────────────────────────────────────────────────────────

def draw_modal(surf: pygame.Surface, rect: pygame.Rect,
               title: str, title_font, radius: int = 14,
               accent: tuple = None):
    """Dark glass modal dialog shell."""
    if accent is None:
        accent = C_GLOW_PURPLE

    # Dim overlay
    dim = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 210))
    surf.blit(dim, (0, 0))

    # Solid dark base — ensures the panel is clearly readable
    base = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(base, (10, 8, 22, 235), (0, 0, *rect.size), border_radius=radius)
    surf.blit(base, rect.topleft)

    # Glass sheen on top
    draw_glass_panel(surf, rect, border_color=(*accent, 190),
                     radius=radius, fill_alpha=18)

    # Accent top strip
    strip = pygame.Surface((rect.width - 2, 3), pygame.SRCALPHA)
    for x in range(strip.get_width()):
        t = 1.0 - abs(x - strip.get_width() / 2) / (strip.get_width() / 2 + 1)
        strip.set_at((x, 0), (*C_GLOW_PURPLE, int(200 * t)))
        strip.set_at((x, 1), (*C_GLOW_PURPLE, int(80 * t)))
        strip.set_at((x, 2), (*C_GLOW_PURPLE, int(20 * t)))
    surf.blit(strip, (rect.x + 1, rect.y + radius))

    draw_glow_text(surf, title, title_font,
                   (*accent[:3],) if len(accent) >= 3 else C_TEXT_PURPLE,
                   accent,
                   (rect.centerx, rect.y + 28),
                   anchor='center', glow_radius=3)

    # Divider
    div_y = rect.y + 54
    pygame.draw.line(surf, (*accent[:3], 50),
                     (rect.x + 16, div_y), (rect.right - 16, div_y), 1)
    return div_y  # caller can place content below this


def draw_modal_button(surf: pygame.Surface, rect: pygame.Rect,
                      label: str, font,
                      selected: bool = False, hovered: bool = False,
                      accent: tuple = None):
    """Compact button for modal dialogs."""
    if accent is None:
        accent = C_GLOW_PURPLE
    if selected or hovered:
        fill_a   = 30
        border_a = 200
        txt_col  = accent
        draw_outer_glow(surf, rect, accent, radius=6, passes=3, max_alpha=28)
    else:
        fill_a   = 10
        border_a = 80
        txt_col  = C_TEXT_SECONDARY

    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(panel, (*accent, fill_a), (0, 0, *rect.size), border_radius=6)
    surf.blit(panel, rect.topleft)
    pygame.draw.rect(surf, (*accent, border_a), rect, 1, border_radius=6)

    txt = font.render(label, True, txt_col)
    surf.blit(txt, txt.get_rect(center=rect.center))
