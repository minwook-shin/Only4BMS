import os
import json
import asyncio
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, FileResponse

app = FastAPI()

SONGS_DIR = os.path.join(os.path.dirname(__file__), "songs")
SERVER_PASSWORD = os.environ.get("SERVER_PASSWORD", "password")  # Try changing this to require a password!

# In-memory lobby state
lobby = {
    "players": {},  # ws -> {"id": 1 or 2, "name": "Player 1"}
    "host_id": None,
    "selected_song_id": None,
    "selected_bms_file": None,
    "match_settings": {},
    "ready_players": set()
}
lock = asyncio.Lock()


async def ws_send(ws: WebSocket, data: dict):
    try:
        await ws.send_json(data)
    except Exception:
        pass


async def broadcast_lobby_state():
    async with lock:
        players_list = list(lobby["players"].values())
        state = {
            "type": "lobby_state",
            "players": players_list,
            "host_id": lobby["host_id"],
            "selected_song_id": lobby["selected_song_id"],
            "selected_bms_file": lobby["selected_bms_file"],
            "ready_players": list(lobby["ready_players"])
        }
        clients = list(lobby["players"].keys())
    await asyncio.gather(*[ws_send(ws, state) for ws in clients])


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


@app.get("/api/songs")
async def list_songs():
    return get_available_songs()


@app.get("/api/songs/{song_id}")
async def get_song_manifest(song_id: str):
    song_dir = os.path.join(SONGS_DIR, song_id)
    if not os.path.exists(song_dir):
        return JSONResponse({"error": "Song not found"}, status_code=404)

    files = [
        f for f in os.listdir(song_dir)
        if os.path.isfile(os.path.join(song_dir, f)) and f != "metadata.json"
    ]
    return {"id": song_id, "files": files}


@app.get("/api/songs/{song_id}/download/{filename}")
async def download_file(song_id: str, filename: str):
    file_path = os.path.join(SONGS_DIR, song_id, filename)
    if not os.path.exists(file_path):
        return JSONResponse({"error": "File not found"}, status_code=404)
    return FileResponse(file_path)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    print("Client connected")
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            msg_type = data.get("type")
            if msg_type == "join":
                await handle_join(ws, data)
            elif msg_type == "select_song":
                await handle_select_song(ws, data)
            elif msg_type == "ready":
                await handle_ready(ws)
            elif msg_type == "sync_score":
                await handle_sync_score(ws, data)
    except WebSocketDisconnect:
        await handle_disconnect(ws)


async def handle_join(ws: WebSocket, data: dict):
    name = data.get("name", "Player")
    password = data.get("password", "")

    if SERVER_PASSWORD and password != SERVER_PASSWORD:
        await ws_send(ws, {"type": "join_error", "message": "Invalid password!"})
        return

    error_msg = None
    assigned_id = None
    host_id = None

    async with lock:
        if len(lobby["players"]) >= 2:
            error_msg = "Lobby is full"
        else:
            assigned_id = 1
            existing_ids = [p["id"] for p in lobby["players"].values()]
            if 1 in existing_ids:
                assigned_id = 2

            lobby["players"][ws] = {"id": assigned_id, "name": name}

            if lobby["host_id"] is None:
                lobby["host_id"] = assigned_id
            host_id = lobby["host_id"]

    if error_msg:
        await ws_send(ws, {"type": "join_error", "message": error_msg})
        return

    await ws_send(ws, {"type": "join_success", "player_id": assigned_id, "host_id": host_id})
    await broadcast_lobby_state()


async def handle_disconnect(ws: WebSocket):
    print("Client disconnected")
    async with lock:
        if ws not in lobby["players"]:
            return
        p_id = lobby["players"][ws]["id"]
        del lobby["players"][ws]

        if p_id == lobby["host_id"]:
            lobby["host_id"] = None
            lobby["selected_song_id"] = None
            lobby["selected_bms_file"] = None
            lobby["match_settings"] = {}
            if lobby["players"]:
                first_ws = list(lobby["players"].keys())[0]
                lobby["host_id"] = lobby["players"][first_ws]["id"]

        lobby["ready_players"].discard(p_id)

    await broadcast_lobby_state()


async def handle_select_song(ws: WebSocket, data: dict):
    async with lock:
        if ws not in lobby["players"]:
            return
        p_id = lobby["players"][ws]["id"]
        if p_id != lobby["host_id"]:
            return
        lobby["selected_song_id"] = data.get("song_id")
        lobby["selected_bms_file"] = data.get("bms_file")
        lobby["match_settings"] = data.get("match_settings", {})
        lobby["ready_players"].clear()

    await broadcast_lobby_state()


async def handle_ready(ws: WebSocket):
    should_start = False
    clients = []
    match_settings = {}

    async with lock:
        if ws not in lobby["players"]:
            return
        p_id = lobby["players"][ws]["id"]
        lobby["ready_players"].add(p_id)
        num_ready = len(lobby["ready_players"])
        num_players = len(lobby["players"])
        match_settings = dict(lobby.get("match_settings", {}))
        clients = list(lobby["players"].keys())
        should_start = num_ready == 2 and num_players == 2

    await broadcast_lobby_state()

    if should_start:
        print("Both players ready! Starting game...")
        start_msg = {
            "type": "start_game",
            "start_time_offset": 5000,
            "match_settings": match_settings
        }
        await asyncio.gather(*[ws_send(c, start_msg) for c in clients])

        async with lock:
            lobby["ready_players"].clear()
            lobby["selected_song_id"] = None
            lobby["selected_bms_file"] = None
            lobby["match_settings"] = {}

        await broadcast_lobby_state()


async def handle_sync_score(ws: WebSocket, data: dict):
    async with lock:
        if ws not in lobby["players"]:
            return
        others = [c for c in lobby["players"].keys() if c != ws]

    data["type"] = "opponent_score"
    await asyncio.gather(*[ws_send(c, data) for c in others])


if __name__ == '__main__':
    print("Starting Only4BMS Example Multiplayer Server on port 5000...")
    uvicorn.run(app, host='0.0.0.0', port=5000)
