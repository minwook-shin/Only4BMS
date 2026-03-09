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
        self._ws = None
        self._ws_thread = None
        self.server_url = None  # HTTP base URL (e.g. "http://host:port")

        self.lobby_state = {}
        self.player_id = None
        self.host_id = None
        self.is_connected = False
        self.join_error = None

        self.game_start_time = None
        self.match_settings = None
        self.opponent_state = None

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return

        msg_type = data.get('type')

        if msg_type == 'join_error':
            self.join_error = data.get('message', 'Unknown error')
            print(f"Join error: {self.join_error}")
            self.disconnect()

        elif msg_type == 'join_success':
            self.join_error = None
            self.player_id = data.get('player_id')
            self.host_id = data.get('host_id')

        elif msg_type == 'lobby_state':
            self.lobby_state = data
            self.host_id = data.get('host_id')

        elif msg_type == 'start_game':
            offset = data.get('start_time_offset', 3000)
            self.match_settings = data.get('match_settings', {})
            self.game_start_time = time.time() + (offset / 1000.0)

        elif msg_type == 'opponent_score':
            self.opponent_state = data

    def _on_open(self, ws):
        print("Connected to server")
        self.is_connected = True

    def _on_close(self, ws, close_status_code, close_msg):
        print("Disconnected from server")
        self.is_connected = False
        self.lobby_state = {}
        self.player_id = None
        self.host_id = None
        self.game_start_time = None
        self.match_settings = None
        self.opponent_state = None

    def _on_error(self, ws, error):
        print(f"Network error: {error}")

    def _send(self, data):
        if self._ws and self.is_connected:
            try:
                self._ws.send(json.dumps(data))
            except Exception:
                pass

    def connect(self, url, player_name="Player"):
        if self.is_connected:
            self.disconnect()

        # Build HTTP and WS URLs
        if not url.startswith("http"):
            url = "http://" + url
        self.server_url = url

        ws_url = url.replace("http://", "ws://").replace("https://", "wss://")
        if not ws_url.endswith("/ws"):
            ws_url = ws_url.rstrip("/") + "/ws"

        try:
            self._ws = websocket.WebSocketApp(
                ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_close=self._on_close,
                on_error=self._on_error,
            )
            self._ws_thread = threading.Thread(
                target=self._ws.run_forever,
                daemon=True,
            )
            self._ws_thread.start()

            # Wait for connection (up to 3 seconds)
            deadline = time.time() + 3
            while not self.is_connected and time.time() < deadline:
                time.sleep(0.05)

            return self.is_connected
        except Exception as e:
            print(f"Failed to connect to {url}: {e}")
            return False

    def join_lobby(self, player_name="Player", password=""):
        if self.is_connected:
            self.join_error = None
            self._send({'type': 'join', 'name': player_name, 'password': password})

    def disconnect(self):
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
        self.is_connected = False

    def select_song(self, song_id, bms_file, match_settings=None):
        if self.is_connected and self.player_id == self.host_id:
            payload = {'type': 'select_song', 'song_id': song_id, 'bms_file': bms_file}
            if match_settings is not None:
                payload['match_settings'] = match_settings
            self._send(payload)

    def send_ready(self):
        if self.is_connected:
            self._send({'type': 'ready'})

    def send_score(self, judgments, combo):
        if self.is_connected:
            self._send({'type': 'sync_score', 'judgments': judgments, 'combo': combo})

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
            r = requests.get(f"{self.server_url}/api/songs/{song_id}", timeout=3)
            if r.status_code != 200:
                return False

            manifest = r.json()
            song_dir = os.path.join(cache_dir, song_id)
            os.makedirs(song_dir, exist_ok=True)

            files = manifest.get('files', [])
            total_files = len(files)

            for index, filename in enumerate(files):
                file_url = f"{self.server_url}/api/songs/{song_id}/download/{filename}"
                fr = requests.get(file_url, stream=True)
                if fr.status_code == 200:
                    with open(os.path.join(song_dir, filename), 'wb') as f:
                        for chunk in fr.iter_content(chunk_size=8192):
                            f.write(chunk)

                if progress_callback:
                    progress_callback(index + 1, total_files)

            return True
        except Exception as e:
            print(f"Download failed: {e}")
            return False
