"""
2-Key Mode Mod for Only4BMS
============================
Play any 4-lane BMS chart using only 2 keys.

Lane mapping:
  BMS lanes 0, 1  →  Left key  (default D)
  BMS lanes 2, 3  →  Right key (default K)

HP system:
  PERFECT  +1.0   GREAT  +0.5
  GOOD     -1.5   MISS   -10.0
  Start at 50 HP (max 100).  Reach 0 → FAIL.
"""

MOD_ID          = "two_key"
MOD_NAME        = "2-Key Mode"
MOD_DESCRIPTION = "Play 4-lane BMS charts with 2 keys. HP drains on MISS — fail on empty."
MOD_VERSION     = "1.0.0"


def get_display_name() -> str:
    from .i18n import t as _t
    return _t("menu_two_key")


def run(settings, renderer, window, **ctx):
    from .session import TwoKeySession
    TwoKeySession(settings, renderer, window, **ctx).run()
