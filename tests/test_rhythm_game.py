import pytest
from only4bms.rhythm_game import RhythmGame, JUDGMENT_ORDER, JUDGMENT_DEFS, NUM_LANES, LANE_W


from unittest.mock import MagicMock

@pytest.fixture
def sample_game():
    """Create a minimal RhythmGame instance with mock data and dummy renderer."""
    notes = [
        {"time_ms": 1000, "lane": 0, "sample_ids": ["01"]},
        {"time_ms": 2000, "lane": 1, "sample_ids": ["02"]},
        {"time_ms": 3000, "lane": 2, "sample_ids": ["01"]},
        {"time_ms": 4000, "lane": 3, "sample_ids": ["02"]},
    ]
    bgms = [{"time_ms": 500, "sample_id": "03"}]
    bgas = []
    wav_map = {}
    bmp_map = {}
    settings = {"fps": 60, "speed": 0.5, "volume": 0.3, "hit_window_mult": 1.0}
    
    # Mock Renderer and Window
    mock_window = MagicMock()
    mock_window.size = (800, 600)
    mock_renderer = MagicMock()
    
    game = RhythmGame(
        notes, bgms, bgas, wav_map, bmp_map, "Test Song", settings, 
        renderer=mock_renderer, window=mock_window
    )
    return game


def test_rhythm_game_initialization(sample_game):
    assert sample_game.state == "PLAYING"
    assert sample_game.combo == 0
    assert sample_game.max_combo == 0
    assert len(sample_game.notes) == 4
    assert sample_game.speed == 0.5
