import os
import tempfile
import pytest
from only4bms.bms_parser import BMSParser

@pytest.fixture
def mock_bms_file():
    # Create a temporary valid BMS file
    fd, path = tempfile.mkstemp(suffix=".bms", text=True)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write("""#PLAYER 1
#TITLE Awesome BMS Song
#ARTIST Antigravity
#BPM 150
#PLAYLEVEL 7
#GENRE Happy Hardcore
#WAV01 kick.wav
#BMP01 bg.bmp
#00111:01000100
#00212:00010001
""")
    yield path
    # Cleanup
    os.remove(path)

def test_bms_parser_metadata(mock_bms_file):
    parser = BMSParser(mock_bms_file)
    title, artist, bpm, playlevel, genre, total_notes = parser.get_metadata()
    
    assert title == "Awesome BMS Song"
    assert artist == "Antigravity"
    assert bpm == 150.0
    assert playlevel == "7"
    assert genre == "Happy Hardcore"
    assert total_notes == 4  # 01000100 = 2 notes, 00010001 = 2 notes

def test_bms_parser_compression(mock_bms_file):
    # Overwrite mock file with many channels
    with open(mock_bms_file, 'w', encoding='utf-8') as f:
        f.write("""#BPM 120
#00111:0100
#00112:0001
#00115:0100
#00118:0001
#00222:0101
""")
    parser = BMSParser(mock_bms_file)
    notes, _, _, _ = parser.parse()
    
    # 01 on 11, 15, 22 (first part) = 3 notes at t=0
    # 01 on 12, 118, 22 (second part) = 3 notes at t=500
    # Total 6 notes expected
    assert len(notes) == 6
    
    # Verify they are distributed across lanes (LRU behavior)
    # At t=0, 3 notes should take 3 different lanes
    t0_notes = [n for n in notes if n['time_ms'] == 0]
    assert len(t0_notes) == 3
    lanes = {n['lane'] for n in t0_notes}
    assert len(lanes) == 3 # All different

def test_bms_parser_stacking():
    # Test more than 4 notes at same time
    with tempfile.NamedTemporaryFile(suffix=".bms", mode='w', delete=False) as f:
        f.write("""#BPM 120
#00111:01
#00112:01
#00113:01
#00114:01
#00115:01
""")
        path = f.name
    try:
        parser = BMSParser(path)
        notes, _, _, _ = parser.parse()
        # 5 notes at t=0. 4 lanes available.
        # Should result in 4 physical notes, one of which has 2 sample_ids.
        assert len(notes) == 4
        stacked = [n for n in notes if len(n['sample_ids']) > 1]
        assert len(stacked) == 1
        assert len(stacked[0]['sample_ids']) == 2
    finally:
        os.remove(path)
