import pygame
import cv2
import numpy as np
import threading
import time

# ── Performance Constants ────────────────────────────────────────────────
MAX_VID_W = 1024  # Cap decoding resolution (720p-ish) for balance
MAX_QUEUE_SIZE = 2
_SEEK_TOLERANCE = 5  # Frames


class VideoPlayer:
    """Optimized video decoder using a background thread and resolution capping."""

    def __init__(self, filepath, target_size=(800, 600)):
        self.cap = cv2.VideoCapture(filepath)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Target display size
        self.target_w, self.target_h = target_size
        
        # Calculate intermediate decode size (cap for performance)
        orig_w = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1
        orig_h = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1
        
        # We will decode at a size that fills the target width, but capped at MAX_VID_W
        self.render_w = min(int(orig_w), self.target_w, MAX_VID_W)
        self.render_h = int(orig_h * self.render_w / orig_w)
        
        # Optimization: We decode at a smaller size to save CPU time.
        # The GPU will handle the final upscale to target_size during rendering.
        self.final_w = self.render_w
        self.final_h = self.render_h

        # Threading state
        self.running = True
        self.lock = threading.Lock()
        self.target_frame_idx = 0
        self.last_decoded_idx = -1
        self.current_surface = None
        self.next_surface = None
        
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def get_frame(self, time_ms):
        """Request a frame for a given timestamp. Main thread never blocks."""
        if not self.cap.isOpened() or self.fps <= 0:
            return None

        target = min(int(time_ms / 1000.0 * self.fps), self.total_frames - 1)
        
        with self.lock:
            self.target_frame_idx = target
            # If the worker has a new frame ready, swap it in
            if self.next_surface is not None:
                self.current_surface = self.next_surface
                self.next_surface = None
                
        return self.current_surface

    def _worker(self):
        """Background thread for decoding and scaling."""
        while self.running:
            with self.lock:
                target = self.target_frame_idx
                last = self.last_decoded_idx
            
            # Decide if we need to decode
            if target <= last:
                time.sleep(0.005) # Chill
                continue
                
            # If target is far ahead or behind, seek
            if target < last or target > last + _SEEK_TOLERANCE:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, target)
                self.last_decoded_idx = target - 1
                last = target - 1

            # Read next frame
            ret, frame = self.cap.read()
            if ret:
                surf = self._convert(frame)
                with self.lock:
                    self.next_surface = surf
                    self.last_decoded_idx += 1
            else:
                # Loop or stop
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.last_decoded_idx = -1
                time.sleep(0.1)

    def _convert(self, frame):
        """BGR -> RGB, Resize to final target size, -> Pygame Surface."""
        # Scale to final display size in background thread (OpenCV is very fast at this)
        resized = cv2.resize(frame, (self.final_w, self.final_h), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # frombuffer is faster than surfarray and doesn't require transpose if using 'RGB'
        # We don't use .convert_alpha() here because it requires a display context (No display mode error)
        return pygame.image.frombuffer(rgb.tobytes(), (self.final_w, self.final_h), 'RGB')

    def release(self):
        """Cleanup."""
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=0.1)
        if self.cap.isOpened():
            self.cap.release()
