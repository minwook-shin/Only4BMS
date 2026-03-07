import eventlet
eventlet.monkey_patch()

import os
import json
from flask import Flask, request, jsonify, send_file
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'only4bms_secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

SONGS_DIR = os.path.join(os.path.dirname(__file__), "songs")
SERVER_PASSWORD = os.environ.get("SERVER_PASSWORD", "password")  # Try changing this to require a password!

# In-memory lobby state
lobby = {
    "players": {}, # sid -> {"id": 1 or 2, "name": "Player 1"}
    "host_id": None,
    "selected_song_id": None,
    "selected_bms_file": None,
    "match_settings": {},
    "ready_players": set()
}

def get_available_songs():
    songs = []
    if not os.path.exists(SONGS_DIR):
        os.makedirs(SONGS_DIR)
        return songs
        
    for dirname in os.listdir(SONGS_DIR):
        dir_path = os.path.join(SONGS_DIR, dirname)
        if os.path.isdir(dir_path):
            meta_path = os.path.join(dir_path, "metadata.json")
            if os.path.exists(meta_path):
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                    meta['id'] = dirname
                    songs.append(meta)
            else:
                songs.append({
                    "id": dirname,
                    "title": dirname,
                    "artist": "Unknown",
                    "level": "??",
                    "bpm": "120"
                })
    return songs

@app.route('/api/songs', methods=['GET'])
def list_songs():
    return jsonify(get_available_songs())

@app.route('/api/songs/<song_id>', methods=['GET'])
def get_song_manifest(song_id):
    song_dir = os.path.join(SONGS_DIR, song_id)
    if not os.path.exists(song_dir):
        return jsonify({"error": "Song not found"}), 404
        
    files = []
    for f in os.listdir(song_dir):
        if os.path.isfile(os.path.join(song_dir, f)) and f != "metadata.json":
            files.append(f)
            
    return jsonify({
        "id": song_id,
        "files": files
    })

@app.route('/api/songs/<song_id>/download/<filename>', methods=['GET'])
def download_file(song_id, filename):
    file_path = os.path.join(SONGS_DIR, song_id, filename)
    if not os.path.exists(file_path):
        return "File not found", 404
    return send_file(file_path)

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")
    if request.sid in lobby['players']:
        p_id = lobby['players'][request.sid]['id']
        del lobby['players'][request.sid]
        
        if p_id == lobby['host_id']:
            lobby['host_id'] = None
            lobby['selected_song_id'] = None
            lobby['selected_bms_file'] = None
            lobby['match_settings'] = {}
            if lobby['players']:
                first_sid = list(lobby['players'].keys())[0]
                lobby['host_id'] = lobby['players'][first_sid]['id']
                
        if p_id in lobby['ready_players']:
            lobby['ready_players'].remove(p_id)
            
        broadcast_lobby_state()

@socketio.on('join')
def handle_join(data):
    name = data.get('name', f"Player {len(lobby['players'])+1}")
    password = data.get('password', "")
    
    if SERVER_PASSWORD and password != SERVER_PASSWORD:
        emit('join_error', {'message': 'Invalid password!'})
        return
        
    if len(lobby['players']) >= 2:
        emit('join_error', {'message': 'Lobby is full'})
        return
        
    assigned_id = 1
    existing_ids = [p['id'] for p in lobby['players'].values()]
    if 1 in existing_ids:
        assigned_id = 2
        
    lobby['players'][request.sid] = {
        "id": assigned_id,
        "name": name
    }
    
    if lobby['host_id'] is None:
        lobby['host_id'] = assigned_id
        
    emit('join_success', {'player_id': assigned_id, 'host_id': lobby['host_id']})
    broadcast_lobby_state()

def broadcast_lobby_state():
    players_list = list(lobby['players'].values())
    socketio.emit('lobby_state', {
        'players': players_list,
        'host_id': lobby['host_id'],
        'selected_song_id': lobby['selected_song_id'],
        'selected_bms_file': lobby['selected_bms_file'],
        'ready_players': list(lobby['ready_players'])
    })

@socketio.on('select_song')
def handle_select_song(data):
    if request.sid not in lobby['players']: return
    p_id = lobby['players'][request.sid]['id']
    
    if p_id == lobby['host_id']:
        lobby['selected_song_id'] = data.get('song_id')
        lobby['selected_bms_file'] = data.get('bms_file')
        lobby['match_settings'] = data.get('match_settings', {})
        lobby['ready_players'].clear()
        broadcast_lobby_state()

@socketio.on('ready')
def handle_ready():
    if request.sid not in lobby['players']: return
    p_id = lobby['players'][request.sid]['id']
    
    lobby['ready_players'].add(p_id)
    broadcast_lobby_state()
    
    if len(lobby['ready_players']) == 2 and len(lobby['players']) == 2:
        print("Both players ready! Starting game...")
        lobby['ready_players'].clear()
        
        match_settings = lobby.get('match_settings', {})
        socketio.emit('start_game', {
            'start_time_offset': 5000,
            'match_settings': match_settings
        })
        
        lobby['selected_song_id'] = None
        lobby['selected_bms_file'] = None
        lobby['match_settings'] = {}
        broadcast_lobby_state()

@socketio.on('sync_score')
def handle_sync_score(data):
    if request.sid not in lobby['players']: return
    emit('opponent_score', data, broadcast=True, include_self=False)

if __name__ == '__main__':
    print("Starting Only4BMS Example Multiplayer Server on port 5000...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
