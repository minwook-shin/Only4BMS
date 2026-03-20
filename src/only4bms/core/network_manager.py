import os
import json
import requests
import threading
import time
import websocket


class NetworkManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NetworkManager, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.ws = None
        self.server_url = None

        self.lobby_state = {}
        self.player_id = None
        self.host_id = None
        self.is_connected = False
        self.join_error = None

        self.game_start_time = None
        self.match_settings = None
        self.opponent_state = None

        # Set to True when opponent emits an in_game_ready sync_score signal,
        # meaning they have finished loading and are about to start the game loop.
        self.opponent_in_game = False

        # True only after this client has sent 'ready' for the current round.
        # start_game signals received before we're ready are ignored — they
        # were triggered by the other player finishing first, not by both.
        self._ready_sent = False

    def _handle_message(self, data):
        msg_type = data.get("type")

        if msg_type == "join_error":
            self.join_error = data.get("message", "Unknown error")
            print(f"Join error: {self.join_error}")
            self.disconnect()

        elif msg_type == "join_success":
            self.join_error = None
            self.player_id = data.get("player_id")
            self.host_id = data.get("host_id")

        elif msg_type == "lobby_state":
            self.lobby_state = data
            self.host_id = data.get("host_id")

        elif msg_type == "start_game":
            if not self._ready_sent:
                # We haven't finished downloading yet — this start_game was
                # triggered by the other player, not by both being ready.
                # Ignore it; we'll get (or re-trigger) a fresh one after we
                # send our own 'ready'.
                print("[Net] Ignoring premature start_game (not yet ready)")
                return
            offset = data.get("start_time_offset", 3000)
            self.match_settings = data.get("match_settings", {})
            # Record the absolute time when we should actually unpause/start
            self.game_start_time = time.time() + (offset / 1000.0)

        elif msg_type == "opponent_score":
            if data.get("in_game_ready"):
                self.opponent_in_game = True
                return  # handshake-only packet; don't overwrite score state
            self.opponent_state = data

        elif msg_type == "error":
            print(f"Network error: {data}")

    def connect(self, url, player_name="Player"):
        if self.is_connected:
            self.disconnect()

        if not url.startswith(("http://", "https://", "ws://", "wss://")):
            url = "http://" + url

        self.server_url = url
        ws_url = url.replace("https://", "wss://").replace("http://", "ws://") + "/ws"

        connected_event = threading.Event()

        def on_open(ws):
            self.is_connected = True
            print("Connected to server")
            connected_event.set()

        def on_message(ws, message):
            try:
                data = json.loads(message)
            except Exception:
                return
            self._handle_message(data)

        def on_error(ws, error):
            print(f"WebSocket error: {error}")
            connected_event.set()

        def on_close(ws, close_status_code, close_msg):
            print("Disconnected from server")
            self.is_connected = False
            self.lobby_state = {}
            self.player_id = None
            self.host_id = None
            self.game_start_time = None
            self.match_settings = None
            self.opponent_state = None
            self.opponent_in_game = False
            self._ready_sent = False

        self.ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )

        t = threading.Thread(target=self.ws.run_forever)
        t.daemon = True
        t.start()

        connected_event.wait(timeout=3)
        return self.is_connected

    def _ws_send(self, data):
        if self.ws and self.is_connected:
            try:
                self.ws.send(json.dumps(data))
            except Exception as e:
                print(f"Send error: {e}")

    def join_lobby(self, player_name="Player", password=""):
        if self.is_connected:
            self.join_error = None
            self._ws_send({"type": "join", "name": player_name, "password": password})

    def disconnect(self):
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        self.is_connected = False

    def select_song(self, song_id, bms_file, match_settings=None):
        if self.is_connected and self.player_id == self.host_id:
            payload = {"type": "select_song", "song_id": song_id, "bms_file": bms_file}
            if match_settings is not None:
                payload["match_settings"] = match_settings
            self._ws_send(payload)

    def send_ready(self):
        if self.is_connected:
            self._ready_sent = True
            self._ws_send({"type": "ready"})

    def send_in_game_ready(self):
        """Signal to opponent that this client has finished loading and is ready
        to start the game loop. Must be called after all assets are loaded."""
        if self.is_connected:
            self._ws_send({"type": "sync_score", "in_game_ready": True, "judgments": {}, "combo": 0})

    def send_score(self, judgments, combo):
        if self.is_connected:
            self._ws_send({"type": "sync_score", "judgments": judgments, "combo": combo})

    def get_server_songs(self):
        if not self.server_url:
            return []
        try:
            r = requests.get(f"{self.server_url}/api/songs", timeout=3)
            return r.json()
        except Exception as e:
            print(f"Failed to get server list: {e}")
            return []

    def download_song(self, song_id, cache_dir, progress_callback=None):
        if not self.server_url:
            return False

        try:
            with requests.Session() as session:
                r = session.get(f"{self.server_url}/api/songs/{song_id}", timeout=3)
                if r.status_code != 200:
                    return False

                manifest = r.json()
                song_dir = os.path.join(cache_dir, song_id)
                os.makedirs(song_dir, exist_ok=True)

                files = manifest.get("files", [])
                total_files = len(files)

                for index, filename in enumerate(files):
                    file_url = f"{self.server_url}/api/songs/{song_id}/download/{filename}"
                    fr = session.get(file_url, stream=True)
                    if fr.status_code == 200:
                        with open(os.path.join(song_dir, filename), "wb") as f:
                            for chunk in fr.iter_content(chunk_size=8192):
                                f.write(chunk)

                    if progress_callback:
                        progress_callback(index + 1, total_files)

            return True
        except Exception as e:
            print(f"Download failed: {e}")
            return False
