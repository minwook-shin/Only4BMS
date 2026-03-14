"""
Online Multiplay — mod-local translations.
All strings used by multiplayer_menu.py and extension.py.
"""

_STRINGS = {
    "en": {
        "menu_online_multi": "ONLINE MULTIPLAYER",
        "mp_enter_server": "Enter Server Address:",
        "mp_connect_hint": "Press ENTER to connect (Esc to cancel)",
        "mp_connecting": "Connecting to server{dots}",
        "mp_waiting_opponent": "Waiting for opponent...",
        "mp_press_enter_song": "Press ENTER to Select Song",
        "mp_waiting_host": "Waiting for Host to choose a song...",
        "mp_fetching_songs": "Fetching songs...",
        "mp_choose_hint": "Use UP/DOWN and ENTER to choose",
        "mp_checking_diff": "Checking difficulties...",
        "mp_select_diff": "Select Difficulty:",
        "mp_diff_hint": "UP/DOWN to select | ENTER to confirm | ESC to go back",
        "mp_downloading": "Downloading Assets...",
        "mp_download_prog": "{cur} / {tot} files",
        "mp_ready_waiting": "Ready! Waiting for server to start game...",
        "mp_starting_in": "Starting in {rem}s",
        "mp_loading_sync": "Loading assets... waiting for opponent",
        "mp_host": "HOST",
        "mp_guest": "GUEST",
        "mp_you": "You",
        "mp_player": "Player",
        "mp_you_win": "YOU WIN",
        "mp_you_lose": "OPPONENT WINS",
        "mp_draw": "DRAW",
        "mp_opponent": "OPPONENT",
    },
    "ko": {
        "menu_online_multi": "온라인 멀티 플레이",
        "mp_enter_server": "서버 주소 입력:",
        "mp_connect_hint": "ENTER 키로 접속 (ESC로 취소)",
        "mp_connecting": "서버에 연결 중{dots}",
        "mp_waiting_opponent": "상대방을 기다리는 중...",
        "mp_press_enter_song": "ENTER 키를 눌러 곡 선택",
        "mp_waiting_host": "호스트가 곡을 고르기를 기다리는 중...",
        "mp_fetching_songs": "곡 목록 가져오는 중...",
        "mp_choose_hint": "위/아래 방향키와 ENTER로 선택",
        "mp_checking_diff": "난이도 확인 중...",
        "mp_select_diff": "난이도 선택:",
        "mp_diff_hint": "위/아래 방향키로 선택 | ENTER로 확인 | ESC로 돌아가기",
        "mp_downloading": "에셋 다운로드 중...",
        "mp_download_prog": "{cur} / {tot} 파일",
        "mp_ready_waiting": "준비 완료! 서버가 시작하기를 기다리는 중...",
        "mp_starting_in": "{rem}초 후 시작",
        "mp_loading_sync": "에셋 로딩 중... 상대방을 기다리는 중",
        "mp_host": "호스트",
        "mp_guest": "게스트",
        "mp_you": "나",
        "mp_player": "플레이어",
        "mp_you_win": "승리",
        "mp_you_lose": "패배",
        "mp_draw": "무승부",
        "mp_opponent": "상대",
    },
    "ja": {
        "menu_online_multi": "オンラインマルチプレイ",
        "mp_enter_server": "サーバーアドレス入力:",
        "mp_connect_hint": "ENTERで接続 (ESCでキャンセル)",
        "mp_connecting": "サーバーに接続中{dots}",
        "mp_waiting_opponent": "対戦相手を待っています...",
        "mp_press_enter_song": "ENTERで曲を選択",
        "mp_waiting_host": "ホストが曲を選ぶのを待っています...",
        "mp_fetching_songs": "曲一覧を取得中...",
        "mp_choose_hint": "上下キーとENTERで選択",
        "mp_checking_diff": "難易度を確認中...",
        "mp_select_diff": "難易度を選択:",
        "mp_diff_hint": "上下で選択 | ENTERで確定 | ESCで戻る",
        "mp_downloading": "アセットダウンロード中...",
        "mp_download_prog": "{cur} / {tot} ファイル",
        "mp_ready_waiting": "準備完了！サーバーの開始を待っています...",
        "mp_starting_in": "{rem}秒後に開始",
        "mp_loading_sync": "アセット読み込み中...相手を待っています",
        "mp_host": "ホスト",
        "mp_guest": "ゲスト",
        "mp_you": "あなた",
        "mp_player": "プレイヤー",
        "mp_you_win": "あなたの勝利",
        "mp_you_lose": "相手の勝利",
        "mp_draw": "引き分け",
        "mp_opponent": "相手",
    },
}


def t(key: str, **kwargs) -> str:
    """Return the translated string for *key* in the current host language."""
    from only4bms.i18n import get_language
    lang = get_language()
    table = _STRINGS.get(lang, _STRINGS.get("en", {}))
    s = table.get(key) or _STRINGS.get("en", {}).get(key, key)
    return s.format(**kwargs) if kwargs else s
