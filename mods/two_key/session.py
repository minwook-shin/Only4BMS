"""
TwoKeySession
=============
Orchestrates the 2-Key Mode gameplay loop:

  1. Song selection  (SongSelectMenu, same as other mods)
  2. BMS parsing
  3. Note remapping  (4 lanes → 2)
  4. RhythmGame with num_lanes=2 and TwoKeyExtension

Lane merge rules
----------------
  BMS lanes 0, 1  →  merged lane 0  (left key)
  BMS lanes 2, 3  →  merged lane 1  (right key)

If two notes in the same source pair land at the exact same time on the
same merged lane, only one is kept as a hittable note; the other is
converted to `is_auto=True` so its keysound still plays automatically.

Key binding
-----------
  Left  key  = settings['keys'][0]  (default D)
  Right key  = settings['keys'][3]  (default K)

Both are taken from the player's existing 4-key binding so they don't
need to reconfigure anything for 2-key mode.
"""

import copy
import pygame

from only4bms.core.bms_parser import BMSParser
from only4bms.game.rhythm_game import RhythmGame
from only4bms.ui.song_select_menu import SongSelectMenu
from only4bms.ui.settings_menu import SettingsMenu
from .extension import TwoKeyExtension


def _remap_notes(notes: list) -> list:
    """Return a deep-copied, remapped note list.

    Lane mapping: 0,1 → 0 | 2,3 → 1
    Collision resolution: if two hittable notes would share the same
    (time_ms, new_lane), the later one in the list becomes auto-play so
    its sample still fires but requires no key press.
    """
    result = copy.deepcopy(notes)
    occupied: dict[tuple, bool] = {}   # (time_ms, new_lane) -> True

    for note in result:
        orig_lane = note.get("lane", 0)
        new_lane  = 0 if orig_lane < 2 else 1
        note["lane"] = new_lane

        if note.get("is_auto"):
            continue  # already auto — keep as-is

        key = (note["time_ms"], new_lane)
        if key in occupied:
            # Collision: keep sound, don't require a key press
            note["is_auto"] = True
        else:
            occupied[key] = True

    return result


class TwoKeySession:
    def __init__(self, settings, renderer, window, **ctx):
        self.settings  = settings
        self.renderer  = renderer
        self.window    = window
        self.init_mixer_fn     = ctx.get("init_mixer_fn")
        self.save_settings_fn  = ctx.get("save_settings_fn")
        self.challenge_manager = ctx.get("challenge_manager")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        cached_songs = None

        while True:
            ssm = SongSelectMenu(
                self.settings,
                renderer=self.renderer,
                window=self.window,
                mode="two_key",
                song_groups=cached_songs,
            )
            res = ssm.run()
            cached_songs = ssm.song_groups

            action, selected_song, note_mod = res

            if action in ("QUIT", "MENU") or not action:
                break

            if action == "SETTINGS":
                SettingsMenu(
                    self.settings,
                    renderer=self.renderer,
                    window=self.window,
                ).run()
                if self.save_settings_fn:
                    self.save_settings_fn(self.settings)
                continue

            if action == "PLAY" and selected_song:
                self._play(selected_song, note_mod)

    # ------------------------------------------------------------------
    # Internal: parse → remap → play
    # ------------------------------------------------------------------

    def _play(self, bms_path: str, note_mod: str) -> None:
        if self.init_mixer_fn:
            self.init_mixer_fn(self.settings)

        print(f"[2-Key] Loading {bms_path} …")
        parser = BMSParser(bms_path)
        notes, bgms, bgas, bmp_map, visual_timing_map, measures = parser.parse()

        if not notes and not bgms:
            print("[2-Key] No notes or BGM found — skipping.")
            return

        # Build 2-key settings: inherit from player's current 4-key binding.
        #   Primary  — F (keys[1]) → lane 0,  J (keys[2]) → lane 1
        #   Alias    — D (keys[0]) → lane 0,  K (keys[3]) → lane 1
        base_keys = self.settings.get("keys", [pygame.K_d, pygame.K_f, pygame.K_j, pygame.K_k])
        k_f = base_keys[1] if len(base_keys) > 1 else pygame.K_f
        k_j = base_keys[2] if len(base_keys) > 2 else pygame.K_j
        k_d = base_keys[0] if len(base_keys) > 0 else pygame.K_d
        k_k = base_keys[3] if len(base_keys) > 3 else pygame.K_k

        two_key_settings = dict(self.settings)
        two_key_settings["keys"] = [k_f, k_j]          # primary: F and J
        two_key_settings["key_aliases"] = {k_d: 0, k_k: 1}  # secondary: D=lane0, K=lane1
        two_key_settings["show_bga"] = 0                # horizontal renderer draws its own bg

        remapped_notes = _remap_notes(notes)

        metadata = {
            "artist":          parser.artist,
            "bpm":             parser.bpm,
            "level":           parser.playlevel,
            "genre":           parser.genre,
            "notes":           parser.total_notes,
            "stagefile":       parser.stagefile,
            "banner":          parser.banner,
            "total":           parser.total,
            "lanes_compressed": parser.lanes_compressed,
        }

        while True:
            game = RhythmGame(
                remapped_notes,
                bgms, bgas,
                parser.wav_map, bmp_map,
                parser.title,
                two_key_settings,
                visual_timing_map=visual_timing_map,
                measures=measures,
                mode="two_key",
                metadata=metadata,
                renderer=self.renderer,
                window=self.window,
                note_mod=note_mod,
                challenge_manager=self.challenge_manager,
                extension=TwoKeyExtension(),
                num_lanes=2,
            )
            result = game.run()

            if result.get("action") != "RESTART":
                break
            # Re-remap on restart (deepcopy was already done in _remap_notes)
            remapped_notes = _remap_notes(notes)
            if self.init_mixer_fn:
                self.init_mixer_fn(self.settings)
