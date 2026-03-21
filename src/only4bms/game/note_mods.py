"""Note modifier (lane scrambler) plugin registry.

To add a new mod:
  1. Define apply_fn(notes: list, num_lanes: int) -> None  (mutates in-place)
  2. Call register_mod('MyMod', apply_fn)
"""
import random as _random

_registry: dict[str, callable] = {}


def register_mod(mod_id: str, apply_fn) -> None:
    _registry[mod_id] = apply_fn


def get_mod_ids() -> list[str]:
    """Returns ['None'] + all registered mod ids in registration order."""
    return ['None'] + list(_registry.keys())


def apply_mod(mod_id: str, notes: list, num_lanes: int) -> None:
    """Apply mod_id to notes in-place. No-op for 'None' or unknown ids."""
    if mod_id in _registry:
        _registry[mod_id](notes, num_lanes)


def _mirror(notes, num_lanes):
    for n in notes:
        n['lane'] = (num_lanes - 1) - n['lane']


def _random_mod(notes, num_lanes):
    mapping = list(range(num_lanes))
    _random.shuffle(mapping)
    for n in notes:
        n['lane'] = mapping[n['lane']]


register_mod('Mirror', _mirror)
register_mod('Random', _random_mod)
