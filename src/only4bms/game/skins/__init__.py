"""Note skin plugin system.

Each skin is a NoteSkinBase subclass that encapsulates texture generation and
unlock logic. Skins are registered at import time and queried by the renderer
and song-select UI without hardcoded if-chains.

To add a new skin:
  1. Create skins/myskin.py with a class inheriting NoteSkinBase.
  2. Register it here: register_skin(MyNoteSkin())
"""

class NoteSkinBase:
    id: str = ''
    ui_color: tuple = (200, 200, 200)       # color shown in UI
    unlock_challenge_id: str = ''           # challenge id that unlocks this skin ('' = always unlocked)
    unlock_toast_i18n_key: str = ''         # i18n key for unlock toast message

    def get_display_name(self) -> str:
        from only4bms.i18n import get as _t
        return _t(f'note_skin_{self.id}')

    def is_unlocked(self, challenge_manager) -> bool:
        return True

    # Texture getters — skin owns its own cache dicts
    def get_bar_texture(self, r, lane_w):
        raise NotImplementedError

    def get_circle_texture(self, r, lane_w):
        raise NotImplementedError

    def get_ln_body_texture(self, r, lane_w):
        raise NotImplementedError

    def render_effect(self, r, eff, tx, ty, lane_w):
        raise NotImplementedError


_registry: dict[str, NoteSkinBase] = {}


def register_skin(skin: NoteSkinBase) -> None:
    _registry[skin.id] = skin


def get_skin(skin_id: str) -> NoteSkinBase | None:
    """Return skin object for skin_id, or None for 'default' / unknown."""
    return _registry.get(skin_id)


def get_available_skins(challenge_manager) -> list[NoteSkinBase]:
    """Return list of skins that are currently unlocked."""
    return [s for s in _registry.values() if s.is_unlocked(challenge_manager)]


# Register built-in skins at import time so song_select_menu can query them
# before GameRenderer is ever created.
from .gold import GoldNoteSkin   # noqa: E402
from .blue import BlueNoteSkin   # noqa: E402

register_skin(GoldNoteSkin())
register_skin(BlueNoteSkin())
