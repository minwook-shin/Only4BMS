# Only4BMS Multiplayer Server API

This document describes the API and WebSocket events required to build a custom online multiplayer server for Only4BMS.
The server must support retrieving songs via HTTP and real-time syncing via WebSocket.

## 1. HTTP Endpoints

You must host your `.bms` (or `.bme`/`.bml`) and `.wav` files on the server. The client downloads them before matching.

### `GET /api/songs`
Returns a list of all available songs on the server.
**Response Format (JSON):**
```json
[
  {
    "id": "song_01",
    "title": "Example Song",
    "artist": "Artist Name",
    "level": "5",
    "bpm": "120"
  }
]
```

### `GET /api/songs/<song_id>`
Returns the manifest of a specific song, detailing which files need to be downloaded.
**Response Format (JSON):**
```json
{
  "id": "song_01",
  "files": [
    "example.bms",
    "kick.wav",
    "snare.wav",
    "bg.jpg"
  ]
}
```

### `GET /api/songs/<song_id>/download/<filename>`
Returns the raw binary content of the requested file.

---

## 2. WebSocket Events

The game uses a WebSocket connection at `/ws` for real-time multiplayer logic.
All messages are JSON strings with a `"type"` field indicating the event type.

### Client -> Server Messages

*   `join`: Client connects to the lobby.
    ```json
    { "type": "join", "name": "Player 1", "password": "optional_server_password" }
    ```
*   `select_song`: Host selects a song and a specific difficulty (BMS file), alongside match settings.
    ```json
    { "type": "select_song", "song_id": "song_01", "bms_file": "hard.bms", "match_settings": {"speed": 2.0, "modifiers": ["RANDOM"]} }
    ```
*   `ready`: Client signals they have finished downloading the song and are ready to play.
    ```json
    { "type": "ready" }
    ```
*   `sync_score`: Client sends their current game state continuously.
    ```json
    { "type": "sync_score", "combo": 10, "judgments": {"PERFECT": 10, "GREAT": 0, "GOOD": 0, "MISS": 0} }
    ```

### Server -> Client Messages

*   `lobby_state`: Server broadcasts the current lobby status.
    ```json
    { "type": "lobby_state", "players": [{"id": 1, "name": "P1"}], "host_id": 1, "selected_song_id": "song_01", "selected_bms_file": "hard.bms", "ready_players": [1] }
    ```
*   `start_game`: Server commands clients to begin the rhythm game scene.
    ```json
    {
      "type": "start_game",
      "start_time_offset": 3000,
      "match_settings": {
        "speed": 5.0,
        "modifiers": ["RANDOM"],
        "buffs": ["HP_BOOST"],
        "debuffs": []
      }
    }
    ```
    (Wait `start_time_offset` ms before first note. If `match_settings` is omitted or values are missing, client will use local user preferences.)
*   `join_error`: Server rejects a join request (e.g., wrong password, full lobby).
    ```json
    { "type": "join_error", "message": "Invalid password" }
    ```
*   `join_success`: Server confirms a successful join.
    ```json
    { "type": "join_success", "player_id": 1, "host_id": 1 }
    ```
*   `opponent_score`: Server forwards the opponent's score to the client.
    ```json
    { "type": "opponent_score", "combo": 10, "judgments": {"PERFECT": 10, "GREAT": 0, "GOOD": 0, "MISS": 0} }
    ```
