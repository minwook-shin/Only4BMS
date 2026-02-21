import os
import pygame
import pytest

@pytest.fixture(autouse=True, scope="session")
def setup_headless_pygame():
    # Set SDL to use a dummy video and audio driver for headless testing
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    
    # Initialize pygame modules safely
    pygame.init()
    try:
        pygame.mixer.init()
    except Exception:
        pass # Fine if it fails in dummy mode
        
    yield
    
    pygame.quit()
