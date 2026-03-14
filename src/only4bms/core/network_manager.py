import os
import requests
import socketio
import threading
import time

class NetworkManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NetworkManager, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.sio = socketio.Client()
        self.server_url = None

        self.lobby_state = {}
        self.player_id = None
        self.host_id = None
        self.is_connected = False
        self.join_error = None

        self.game_start_time = None
        self.match_settings = None
        self.opponent_state = None

        # True only after this client has sent 'ready' for the current round.
        # start_game signals received before we're ready are ignored — they
        # were triggered by the other player finishing first, not by both.
        self._ready_sent = False

        self._register_events()

    def _register_events(self):
        @self.sio.on('connect')
        def on_connect():
            print("Connected to server")
            self.is_connected = True

        @self.sio.on('disconnect')
        def on_disconnect():
            print("Disconnected from server")
            self.is_connected = False
            self.lobby_state = {}
            self.player_id = None
            self.host_id = None
            self.game_start_time = None
            self.match_settings = None
            self.opponent_state = None
            self._ready_sent = False

        @self.sio.on('error')
        def on_error(data):
            print(f"Network error: {data}")

        @self.sio.on('join_error')
        def on_join_error(data):
            self.join_error = data.get('message', 'Unknown error')
            print(f"Join error: {self.join_error}")
            self.disconnect()

        @self.sio.on('join_success')
        def on_join(data):
            self.join_error = None
            self.player_id = data.get('player_id')
            self.host_id = data.get('host_id')

        @self.sio.on('lobby_state')
        def on_lobby_state(data):
            self.lobby_state = data
            self.host_id = data.get('host_id')

        @self.sio.on('start_game')
        def on_start_game(data):
            if not self._ready_sent:
                # We haven't finished downloading yet — this start_game was
                # triggered by the other player, not by both being ready.
                # Ignore it; we'll get (or re-trigger) a fresh one after we
                # send our own 'ready'.
                print("[Net] Ignoring premature start_game (not yet ready)")
                return
            offset = data.get('start_time_offset', 3000)
            self.match_settings = data.get('match_settings', {})
            # Record the absolute time when we should actually unpause/start
            self.game_start_time = time.time() + (offset / 1000.0)

        @self.sio.on('opponent_score')
        def on_opponent_score(data):
            self.opponent_state = data

    def connect(self, url, player_name="Player"):
        if self.is_connected:
            self.disconnect()
            
        # Ensure it starts with http
        if not url.startswith("http"):
            url = "http://" + url
            
        self.server_url = url
        try:
            self.sio.connect(url, wait_timeout=3)
            return True
        except Exception as e:
            print(f"Failed to connect to {url}: {e}")
            return False

    def join_lobby(self, player_name="Player", password=""):
        if self.is_connected:
            self.join_error = None
            self.sio.emit('join', {'name': player_name, 'password': password})

    def disconnect(self):
        if self.is_connected:
            try:
                self.sio.disconnect()
            except:
                pass
            self.is_connected = False

    def select_song(self, song_id, bms_file, match_settings=None):
        if self.is_connected and self.player_id == self.host_id:
            payload = {'song_id': song_id, 'bms_file': bms_file}
            if match_settings is not None:
                payload['match_settings'] = match_settings
            self.sio.emit('select_song', payload)

    def send_ready(self):
        if self.is_connected:
            self._ready_sent = True
            self.sio.emit('ready')

    def send_score(self, judgments, combo):
        if self.is_connected:
            self.sio.emit('sync_score', {
                'judgments': judgments,
                'combo': combo
            })

    def get_server_songs(self):
        if not self.server_url: return []
        try:
            r = requests.get(f"{self.server_url}/api/songs", timeout=3)
            return r.json()
        except Exception as e:
            print(f"Failed to get server list: {e}")
            return []

    def download_song(self, song_id, cache_dir, progress_callback=None):
        if not self.server_url: return False
        
        try:
            r = requests.get(f"{self.server_url}/api/songs/{song_id}", timeout=3)
            if r.status_code != 200: return False
            
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
