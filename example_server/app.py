import os
import json
import asyncio
from aiohttp import web

SONGS_DIR = os.path.join(os.path.dirname(__file__), "songs")
SERVER_PASSWORD = os.environ.get("SERVER_PASSWORD", "password")

# In-memory lobby state
lobby = {
    "players": {},      # ws -> {"id": 1 or 2, "name": "Player 1"}
    "host_id": None,
    "selected_song_id": None,
    "selected_bms_file": None,
    "match_settings": {},
    "ready_players": set()
}

# Track all connected WebSocket clients
connected_ws: dict[web.WebSocketResponse, None] = {}


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


# ── HTTP Endpoints ──────────────────────────────────────────

async def list_songs(request):
    return web.json_response(get_available_songs())


async def get_song_manifest(request):
    song_id = request.match_info['song_id']
    song_dir = os.path.join(SONGS_DIR, song_id)
    if not os.path.exists(song_dir):
        return web.json_response({"error": "Song not found"}, status=404)

    files = [
        f for f in os.listdir(song_dir)
        if os.path.isfile(os.path.join(song_dir, f)) and f != "metadata.json"
    ]
    return web.json_response({"id": song_id, "files": files})


async def download_file(request):
    song_id = request.match_info['song_id']
    filename = request.match_info['filename']
    file_path = os.path.join(SONGS_DIR, song_id, filename)
    if not os.path.exists(file_path):
        return web.Response(text="File not found", status=404)
    return web.FileResponse(file_path)


# ── WebSocket helpers ───────────────────────────────────────

async def send_json(ws, data):
    try:
        await ws.send_str(json.dumps(data))
    except Exception:
        pass


async def broadcast(data, exclude=None):
    for ws in list(connected_ws):
        if ws is not exclude and not ws.closed:
            await send_json(ws, data)


async def broadcast_all(data):
    for ws in list(connected_ws):
        if not ws.closed:
            await send_json(ws, data)


def lobby_state_payload():
    players_list = list(lobby['players'].values())
    return {
        'type': 'lobby_state',
        'players': players_list,
        'host_id': lobby['host_id'],
        'selected_song_id': lobby['selected_song_id'],
        'selected_bms_file': lobby['selected_bms_file'],
        'ready_players': list(lobby['ready_players'])
    }


async def broadcast_lobby_state():
    await broadcast_all(lobby_state_payload())


# ── WebSocket handler ──────────────────────────────────────

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    connected_ws[ws] = None
    print(f"Client connected: {id(ws)}")

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get('type')

                if msg_type == 'join':
                    await handle_join(ws, data)
                elif msg_type == 'select_song':
                    await handle_select_song(ws, data)
                elif msg_type == 'ready':
                    await handle_ready(ws)
                elif msg_type == 'sync_score':
                    await handle_sync_score(ws, data)

            elif msg.type in (web.WSMsgType.ERROR, web.WSMsgType.CLOSE):
                break
    finally:
        await handle_disconnect(ws)
        connected_ws.pop(ws, None)
        print(f"Client disconnected: {id(ws)}")

    return ws


async def handle_join(ws, data):
    name = data.get('name', f"Player {len(lobby['players']) + 1}")
    password = data.get('password', "")

    if SERVER_PASSWORD and password != SERVER_PASSWORD:
        await send_json(ws, {'type': 'join_error', 'message': 'Invalid password!'})
        return

    if len(lobby['players']) >= 2:
        await send_json(ws, {'type': 'join_error', 'message': 'Lobby is full'})
        return

    assigned_id = 1
    existing_ids = [p['id'] for p in lobby['players'].values()]
    if 1 in existing_ids:
        assigned_id = 2

    lobby['players'][ws] = {"id": assigned_id, "name": name}

    if lobby['host_id'] is None:
        lobby['host_id'] = assigned_id

    await send_json(ws, {
        'type': 'join_success',
        'player_id': assigned_id,
        'host_id': lobby['host_id']
    })
    await broadcast_lobby_state()


async def handle_disconnect(ws):
    if ws in lobby['players']:
        p_id = lobby['players'][ws]['id']
        del lobby['players'][ws]

        if p_id == lobby['host_id']:
            lobby['host_id'] = None
            lobby['selected_song_id'] = None
            lobby['selected_bms_file'] = None
            lobby['match_settings'] = {}
            if lobby['players']:
                first_ws = next(iter(lobby['players']))
                lobby['host_id'] = lobby['players'][first_ws]['id']

        if p_id in lobby['ready_players']:
            lobby['ready_players'].remove(p_id)

        await broadcast_lobby_state()


async def handle_select_song(ws, data):
    if ws not in lobby['players']:
        return
    p_id = lobby['players'][ws]['id']

    if p_id == lobby['host_id']:
        lobby['selected_song_id'] = data.get('song_id')
        lobby['selected_bms_file'] = data.get('bms_file')
        lobby['match_settings'] = data.get('match_settings', {})
        lobby['ready_players'].clear()
        await broadcast_lobby_state()


async def handle_ready(ws):
    if ws not in lobby['players']:
        return
    p_id = lobby['players'][ws]['id']

    lobby['ready_players'].add(p_id)
    await broadcast_lobby_state()

    if len(lobby['ready_players']) == 2 and len(lobby['players']) == 2:
        print("Both players ready! Starting game...")
        lobby['ready_players'].clear()

        match_settings = lobby.get('match_settings', {})
        await broadcast_all({
            'type': 'start_game',
            'start_time_offset': 5000,
            'match_settings': match_settings
        })

        lobby['selected_song_id'] = None
        lobby['selected_bms_file'] = None
        lobby['match_settings'] = {}
        await broadcast_lobby_state()


async def handle_sync_score(ws, data):
    if ws not in lobby['players']:
        return
    payload = {
        'type': 'opponent_score',
        'judgments': data.get('judgments', {}),
        'combo': data.get('combo', 0)
    }
    await broadcast(payload, exclude=ws)


# ── App setup ──────────────────────────────────────────────

app = web.Application()
app.router.add_get('/api/songs', list_songs)
app.router.add_get('/api/songs/{song_id}', get_song_manifest)
app.router.add_get('/api/songs/{song_id}/download/{filename}', download_file)
app.router.add_get('/ws', websocket_handler)

if __name__ == '__main__':
    print("Starting Only4BMS Example Multiplayer Server on port 5000...")
    web.run_app(app, host='0.0.0.0', port=5000)
