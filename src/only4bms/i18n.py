"""
Internationalization (i18n) module for Only4BMS.
All translations are embedded in this single file for PyInstaller compatibility.
"""
import locale
import sys

# ── Supported Languages ──────────────────────────────────────────────────
LANGUAGES = {
    "en": "English",
    "ko": "한국어",
    "ja": "日本語",
    "zh": "中文(简体)",
    "th": "ไทย",
    "pt": "Português",
    "id": "Bahasa Indonesia",
    "es": "Español",
    "fr": "Français",
    "it": "Italiano",
    "de": "Deutsch",
}

LANGUAGE_CODES = list(LANGUAGES.keys())

# ── Global State ─────────────────────────────────────────────────────────
_current_lang = "en"

# ── CJK-aware Font List ─────────────────────────────────────────────────
FONT_NAME = "Outfit, Malgun Gothic, Yu Gothic, Microsoft YaHei, Leelawadee UI, Roboto, sans-serif"

# ── Centralized Font Sizes (base 800x600) ───────────────────────────────
# All sizes are for BASE resolution and will be scaled by each component.
# Change values here to adjust fonts globally in one place.
FONT_SIZES = {
    # Main Menu
    "menu_title":       76,
    "menu_option":      36,
    "menu_small":       20,

    # Settings / Key Config / Calibration menus
    "ui_title":         38,
    "ui_body":          27,
    "ui_small":         18,

    # Song Select
    "select_title":     38,
    "select_body":      27,
    "select_bold":      32,
    "select_small":     18,

    # In-Game HUD (renderer)
    "hud_normal":       36,
    "hud_bold":         42,
    "hud_ai_label":     18,

    # Loading screen
    "loading_title":    42,
    "loading_info":     26,
    "loading_label":    24,
}


import pygame as _pg
_font_cache: dict[tuple, "_pg.font.Font"] = {}


def font(size_key: str, scale: float, bold: bool = False) -> "_pg.font.Font":
    """Return a cached pygame Font for *size_key* scaled by *scale*.

    Usage:  ``f = i18n.font("ui_body", self._sy, bold=True)``
    """
    base = FONT_SIZES.get(size_key, 24)
    px = max(1, int(base * scale))
    key = (px, bold)
    if key not in _font_cache:
        _font_cache[key] = _pg.font.SysFont(FONT_NAME, px, bold=bold)
    return _font_cache[key]


def detect_system_language() -> str:
    """Detect the OS UI language and return a matching language code."""
    try:
        if sys.platform == "win32":
            import ctypes
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            # Primary language ID is the low 10 bits
            primary = lang_id & 0x3FF
            _WIN_PRIMARY_MAP = {
                0x12: "ko",  # Korean
                0x11: "ja",  # Japanese
                0x04: "zh",  # Chinese
                0x1E: "th",  # Thai
                0x16: "pt",  # Portuguese
                0x21: "id",  # Indonesian
                0x0A: "es",  # Spanish
                0x0C: "fr",  # French
                0x10: "it",  # Italian
                0x07: "de",  # German
                0x09: "en",  # English
            }
            detected = _WIN_PRIMARY_MAP.get(primary)
            if detected and detected in LANGUAGES:
                return detected
    except Exception:
        pass

    # Fallback: use locale module
    try:
        lang_str = locale.getdefaultlocale()[0]  # e.g. 'ko_KR', 'ja_JP'
        if lang_str:
            prefix = lang_str[:2].lower()
            if prefix in LANGUAGES:
                return prefix
    except Exception:
        pass

    return "en"


def set_language(code: str):
    """Set the active language. Falls back to 'en' if code is unknown."""
    global _current_lang
    if code == "auto":
        _current_lang = detect_system_language()
    elif code in LANGUAGES:
        _current_lang = code
    else:
        _current_lang = "en"


def get_language() -> str:
    """Return the current language code."""
    return _current_lang


def get(key: str) -> str:
    """Return the translated string for *key* in the current language.
    Falls back to English, then to the raw key itself.
    """
    lang_table = STRINGS.get(_current_lang, STRINGS["en"])
    return lang_table.get(key, STRINGS["en"].get(key, key))


# ── Translation Tables ───────────────────────────────────────────────────

STRINGS = {
    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  ENGLISH (default / fallback)                                      ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    "en": {
        # Main Menu
        "menu_single": "SINGLE PLAYER",
        "menu_ai_multi": "AI MULTI PLAYER",
        "menu_settings": "SETTINGS",
        "menu_quit": "QUIT",
        "quit_confirm": "Quit Game?",
        "yes": "YES",
        "no": "NO",

        # Settings Menu
        "settings_title": "SYSTEM SETTINGS",
        "calibrate": "CALIBRATE",
        "key_config": "KEY CONFIG",
        "cat_system": "SYSTEM",
        "cat_audio": "AUDIO",
        "cat_gameplay": "GAMEPLAY",
        "fps_limit": "FPS Limit",
        "input_polling": "Input Polling (Hz)",
        "fullscreen": "Fullscreen",
        "audio_device": "Audio Device",
        "volume": "Global Volume",
        "sample_rate": "Sample Rate (Hz)",
        "audio_buffer": "Audio Buffer",
        "audio_channels": "Audio Channels",
        "visual_offset": "Visual Offset (ms)",
        "hit_window_mult": "Hit Window Multiplier",
        "judge_delay": "Judge Delay (ms)",
        "language": "Language",

        # Song Select
        "music_selection": "MUSIC SELECTION",
        "reload": "Reload (R)",
        "search_bms": "Search BMS (B)",
        "settings_btn": "Settings (S)",
        "no_bms_files": "No BMS files found in 'bms/' directory.",
        "scanning": "Scanning songs...",
        "gameplay_options": "GAMEPLAY OPTIONS",
        "speed_label": "SPEED",
        "player_note": "PLAYER NOTE",
        "ai_note": "AI NOTE",
        "note_mod_label": "NOTE MOD (M)",
        "ai_diff_label": "AI",
        "search_web_title": "Search Web (bmssearch.net)",
        "search_hint": "Type query and press ENTER to search directly on your browser.",
        "guide_title": "Browser Opened! To play a new song:",
        "guide_step1": "1. Download the track from the opened website.",
        "guide_step2": "2. Extract the downloaded ZIP or RAR file.",
        "guide_step3": "3. Move the extracted folder into the 'bms' directory.",
        "guide_step4": "4. Press F5 closely after this overlay to reload songs.",
        "guide_close": "(Press ENTER or ESC or Click to close)",

        # Calibration
        "calibration_title": "OFFSET CALIBRATION",
        "tap_to_beat": "Tap SPACE to the beat!",
        "cal_hint": "[SPACE] Tap | [Y] Apply -> Judge Delay | [V] Apply -> Visual Offset | [ESC] Back",
        "avg_offset": "Avg Offset",
        "applied_judge": "Applied {val} to Judge Delay!",
        "applied_visual": "Applied {val} to Visual Offset!",
        "cal_last_avg": "Last: {last} | Avg: {avg}",

        # Key Config
        "key_config_title": "KEY CONFIG",
        "key_help": "Press ENTER or Click to rebind. ESC to return.",
        "joystick_connected": "Joysticks Connected: {n}",
        "lane_n": "Lane {n}",
        "waiting_input": "??? (Waiting for input...)",

        # In-Game
        "speed_display": "SPEED x{val}",
        "fast": "FAST",
        "slow": "SLOW",
        "ai_vision": "AI Vision",
        "paused": "PAUSED",
        "resume_hint": "ESC / TAB to Resume",
        "quit_hint": "Q / ENTER to Quit",

        # Result Screen
        "result_title": "RESULT",
        "you_win": "YOU WIN!",
        "ai_wins": "AI BOT WINS",
        "score_label": "SCORE: {val}",
        "ex_label": "EX: {ex}/{max} ({pct}%)",
        "ai_performance": "AI PERFORMANCE",
        "hit_timing": "HIT TIMING (FAST/SLOW)",
        "return_hint": "Press ENTER or ESC to Return",

        # Loading
        "loading": "Loading... {status}",
        "loading_artist": "Artist",
        "loading_genre": "Genre",
        "loading_bpm": "BPM",
        "loading_level": "Level",
        "loading_notes": "Notes",

        # Judgments (display text)
        "judgment_perfect": "PERFECT!",
        "judgment_great": "GREAT!",
        "judgment_good": "GOOD",
        "judgment_miss": "MISS",
    },

    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  KOREAN (한국어)                                                    ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    "ko": {
        "menu_single": "싱글 플레이",
        "menu_ai_multi": "AI 멀티 플레이",
        "menu_settings": "설정",
        "menu_quit": "종료",
        "quit_confirm": "게임을 종료할까요?",
        "yes": "예",
        "no": "아니오",

        "settings_title": "시스템 설정",
        "calibrate": "보정",
        "key_config": "키 설정",
        "cat_system": "시스템",
        "cat_audio": "오디오",
        "cat_gameplay": "게임플레이",
        "fps_limit": "FPS 제한",
        "input_polling": "입력 폴링 (Hz)",
        "fullscreen": "전체 화면",
        "audio_device": "오디오 장치",
        "volume": "전체 볼륨",
        "sample_rate": "샘플링 레이트 (Hz)",
        "audio_buffer": "오디오 버퍼",
        "audio_channels": "오디오 채널",
        "visual_offset": "비주얼 오프셋 (ms)",
        "hit_window_mult": "판정 범위 배율",
        "judge_delay": "판정 딜레이 (ms)",
        "language": "언어",

        "music_selection": "곡 선택",
        "reload": "새로고침 (R)",
        "search_bms": "BMS 검색 (B)",
        "settings_btn": "설정 (S)",
        "no_bms_files": "'bms/' 디렉토리에 BMS 파일이 없습니다.",
        "scanning": "곡 검색 중...",
        "gameplay_options": "게임플레이 옵션",
        "speed_label": "속도",
        "player_note": "플레이어 노트",
        "ai_note": "AI 노트",
        "note_mod_label": "노트 모드 (M)",
        "ai_diff_label": "AI",
        "search_web_title": "웹 검색 (bmssearch.net)",
        "search_hint": "검색어를 입력하고 ENTER를 눌러 브라우저에서 검색하세요.",
        "guide_title": "브라우저가 열렸습니다! 새 곡을 플레이하려면:",
        "guide_step1": "1. 열린 웹사이트에서 곡을 다운로드합니다.",
        "guide_step2": "2. 다운로드한 ZIP 또는 RAR 파일을 압축 해제합니다.",
        "guide_step3": "3. 압축 해제한 폴더를 'bms' 디렉토리로 이동합니다.",
        "guide_step4": "4. 이 오버레이를 닫은 후 F5를 눌러 곡을 새로고침합니다.",
        "guide_close": "(ENTER, ESC 또는 클릭으로 닫기)",

        "calibration_title": "오프셋 보정",
        "tap_to_beat": "비트에 맞춰 SPACE를 누르세요!",
        "cal_hint": "[SPACE] 탭 | [Y] 판정 딜레이 적용 | [V] 비주얼 오프셋 적용 | [ESC] 뒤로",
        "avg_offset": "평균 오프셋",
        "applied_judge": "판정 딜레이에 {val} 적용!",
        "applied_visual": "비주얼 오프셋에 {val} 적용!",
        "cal_last_avg": "이번: {last} | 평균: {avg}",

        "key_config_title": "키 설정",
        "key_help": "ENTER 또는 클릭으로 변경. ESC로 돌아가기.",
        "joystick_connected": "조이스틱 연결: {n}개",
        "lane_n": "레인 {n}",
        "waiting_input": "??? (입력 대기 중...)",

        "speed_display": "속도 x{val}",
        "fast": "빠름",
        "slow": "느림",
        "ai_vision": "AI 시야",
        "paused": "일시정지",
        "resume_hint": "ESC / TAB: 계속",
        "quit_hint": "Q / ENTER: 종료",

        "result_title": "결과",
        "you_win": "승리!",
        "ai_wins": "AI 봇 승리",
        "score_label": "점수: {val}",
        "ex_label": "EX: {ex}/{max} ({pct}%)",
        "ai_performance": "AI 성적",
        "hit_timing": "타이밍 분포 (빠름/느림)",
        "return_hint": "ENTER 또는 ESC를 눌러 돌아가기",

        "loading": "로딩 중... {status}",
        "loading_artist": "아티스트",
        "loading_genre": "장르",
        "loading_bpm": "BPM",
        "loading_level": "레벨",
        "loading_notes": "노트",

        "judgment_perfect": "PERFECT!",
        "judgment_great": "GREAT!",
        "judgment_good": "GOOD",
        "judgment_miss": "MISS",
    },

    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  JAPANESE (日本語)                                                  ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    "ja": {
        "menu_single": "シングルプレイ",
        "menu_ai_multi": "AIマルチプレイ",
        "menu_settings": "設定",
        "menu_quit": "終了",
        "quit_confirm": "ゲームを終了しますか？",
        "yes": "はい",
        "no": "いいえ",

        "settings_title": "システム設定",
        "calibrate": "キャリブレーション",
        "key_config": "キー設定",
        "cat_system": "システム",
        "cat_audio": "オーディオ",
        "cat_gameplay": "ゲームプレイ",
        "fps_limit": "FPS制限",
        "input_polling": "入力ポーリング (Hz)",
        "fullscreen": "フルスクリーン",
        "audio_device": "オーディオデバイス",
        "volume": "全体音量",
        "sample_rate": "サンプルレート (Hz)",
        "audio_buffer": "オーディオバッファ",
        "audio_channels": "オーディオチャンネル",
        "visual_offset": "ビジュアルオフセット (ms)",
        "hit_window_mult": "判定幅倍率",
        "judge_delay": "判定ディレイ (ms)",
        "language": "言語",

        "music_selection": "楽曲選択",
        "reload": "リロード (R)",
        "search_bms": "BMS検索 (B)",
        "settings_btn": "設定 (S)",
        "no_bms_files": "'bms/' ディレクトリにBMSファイルが見つかりません。",
        "scanning": "楽曲をスキャン中...",
        "gameplay_options": "ゲームプレイオプション",
        "speed_label": "スピード",
        "player_note": "プレイヤーノート",
        "ai_note": "AIノート",
        "note_mod_label": "ノートMOD (M)",
        "ai_diff_label": "AI",
        "search_web_title": "Web検索 (bmssearch.net)",
        "search_hint": "検索語を入力してENTERで検索します。",
        "guide_title": "ブラウザが開きました！新しい曲をプレイするには：",
        "guide_step1": "1. 開いたサイトから曲をダウンロード。",
        "guide_step2": "2. ダウンロードしたZIP/RARを展開。",
        "guide_step3": "3. 展開したフォルダを 'bms' ディレクトリに移動。",
        "guide_step4": "4. F5を押して曲をリロード。",
        "guide_close": "(ENTER / ESC / クリックで閉じる)",

        "calibration_title": "オフセットキャリブレーション",
        "tap_to_beat": "ビートに合わせてSPACEを押してください！",
        "cal_hint": "[SPACE] タップ | [Y] 判定ディレイ適用 | [V] ビジュアルオフセット適用 | [ESC] 戻る",
        "avg_offset": "平均オフセット",
        "applied_judge": "判定ディレイに {val} を適用！",
        "applied_visual": "ビジュアルオフセットに {val} を適用！",
        "cal_last_avg": "今回: {last} | 平均: {avg}",

        "key_config_title": "キー設定",
        "key_help": "ENTERまたはクリックで変更。ESCで戻る。",
        "joystick_connected": "ジョイスティック接続: {n}",
        "lane_n": "レーン {n}",
        "waiting_input": "??? (入力待ち...)",

        "speed_display": "SPEED x{val}",
        "fast": "速い",
        "slow": "遅い",
        "ai_vision": "AIビジョン",
        "paused": "ポーズ",
        "resume_hint": "ESC / TAB: 再開",
        "quit_hint": "Q / ENTER: 終了",

        "result_title": "リザルト",
        "you_win": "勝利！",
        "ai_wins": "AIボット勝利",
        "score_label": "スコア: {val}",
        "ex_label": "EX: {ex}/{max} ({pct}%)",
        "ai_performance": "AIパフォーマンス",
        "hit_timing": "タイミング分布 (速/遅)",
        "return_hint": "ENTERまたはESCで戻る",

        "loading": "ロード中... {status}",
        "loading_artist": "アーティスト",
        "loading_genre": "ジャンル",
        "loading_bpm": "BPM",
        "loading_level": "レベル",
        "loading_notes": "ノーツ",

        "judgment_perfect": "PERFECT!",
        "judgment_great": "GREAT!",
        "judgment_good": "GOOD",
        "judgment_miss": "MISS",
    },

    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  CHINESE SIMPLIFIED (中文简体)                                      ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    "zh": {
        "menu_single": "单人模式",
        "menu_ai_multi": "AI对战模式",
        "menu_settings": "设置",
        "menu_quit": "退出",
        "quit_confirm": "确定退出游戏？",
        "yes": "是",
        "no": "否",

        "settings_title": "系统设置",
        "calibrate": "校准",
        "key_config": "按键设置",
        "cat_system": "系统",
        "cat_audio": "音频",
        "cat_gameplay": "游戏",
        "fps_limit": "FPS限制",
        "input_polling": "输入轮询 (Hz)",
        "fullscreen": "全屏",
        "audio_device": "音频设备",
        "volume": "总音量",
        "sample_rate": "采样率 (Hz)",
        "audio_buffer": "音频缓冲",
        "audio_channels": "音频声道",
        "visual_offset": "视觉偏移 (ms)",
        "hit_window_mult": "判定范围倍率",
        "judge_delay": "判定延迟 (ms)",
        "language": "语言",

        "music_selection": "选曲",
        "reload": "刷新 (R)",
        "search_bms": "搜索BMS (B)",
        "settings_btn": "设置 (S)",
        "no_bms_files": "'bms/' 目录中未找到BMS文件。",
        "scanning": "扫描歌曲中...",
        "gameplay_options": "游戏选项",
        "speed_label": "速度",
        "player_note": "玩家音符",
        "ai_note": "AI音符",
        "note_mod_label": "音符MOD (M)",
        "ai_diff_label": "AI",
        "search_web_title": "网页搜索 (bmssearch.net)",
        "search_hint": "输入关键词并按ENTER在浏览器中搜索。",
        "guide_title": "浏览器已打开！要游玩新歌曲：",
        "guide_step1": "1. 从打开的网站下载歌曲。",
        "guide_step2": "2. 解压下载的ZIP或RAR文件。",
        "guide_step3": "3. 将解压的文件夹移动到 'bms' 目录。",
        "guide_step4": "4. 按F5重新加载歌曲。",
        "guide_close": "(按ENTER、ESC或点击关闭)",

        "calibration_title": "偏移校准",
        "tap_to_beat": "按节拍按SPACE！",
        "cal_hint": "[SPACE] 点击 | [Y] 应用到判定延迟 | [V] 应用到视觉偏移 | [ESC] 返回",
        "avg_offset": "平均偏移",
        "applied_judge": "已将 {val} 应用到判定延迟！",
        "applied_visual": "已将 {val} 应用到视觉偏移！",
        "cal_last_avg": "本次: {last} | 平均: {avg}",

        "key_config_title": "按键设置",
        "key_help": "按ENTER或点击绑定按键。ESC返回。",
        "joystick_connected": "已连接手柄: {n}",
        "lane_n": "轨道 {n}",
        "waiting_input": "??? (等待输入...)",

        "speed_display": "速度 x{val}",
        "fast": "快",
        "slow": "慢",
        "ai_vision": "AI视野",
        "paused": "暂停",
        "resume_hint": "ESC / TAB: 继续",
        "quit_hint": "Q / ENTER: 退出",

        "result_title": "结算",
        "you_win": "你赢了！",
        "ai_wins": "AI机器人获胜",
        "score_label": "分数: {val}",
        "ex_label": "EX: {ex}/{max} ({pct}%)",
        "ai_performance": "AI表现",
        "hit_timing": "时序分布 (快/慢)",
        "return_hint": "按ENTER或ESC返回",

        "loading": "加载中... {status}",
        "loading_artist": "艺术家",
        "loading_genre": "风格",
        "loading_bpm": "BPM",
        "loading_level": "等级",
        "loading_notes": "音符",

        "judgment_perfect": "PERFECT!",
        "judgment_great": "GREAT!",
        "judgment_good": "GOOD",
        "judgment_miss": "MISS",
    },

    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  THAI (ไทย)                                                        ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    "th": {
        "menu_single": "เล่นคนเดียว",
        "menu_ai_multi": "เล่นกับ AI",
        "menu_settings": "ตั้งค่า",
        "menu_quit": "ออก",
        "quit_confirm": "ออกจากเกม?",
        "yes": "ใช่",
        "no": "ไม่",

        "settings_title": "ตั้งค่าระบบ",
        "calibrate": "ปรับจูน",
        "key_config": "ตั้งค่าปุ่ม",
        "cat_system": "ระบบ",
        "cat_audio": "เสียง",
        "cat_gameplay": "เกมเพลย์",
        "fps_limit": "จำกัด FPS",
        "input_polling": "อัตราอินพุต (Hz)",
        "fullscreen": "เต็มจอ",
        "audio_device": "อุปกรณ์เสียง",
        "volume": "ระดับเสียงรวม",
        "sample_rate": "อัตราสุ่ม (Hz)",
        "audio_buffer": "บัฟเฟอร์เสียง",
        "audio_channels": "ช่องเสียง",
        "visual_offset": "ออฟเซ็ตภาพ (ms)",
        "hit_window_mult": "ตัวคูณหน้าต่างตี",
        "judge_delay": "ดีเลย์การตัดสิน (ms)",
        "language": "ภาษา",

        "music_selection": "เลือกเพลง",
        "reload": "โหลดใหม่ (R)",
        "search_bms": "ค้นหา BMS (B)",
        "settings_btn": "ตั้งค่า (S)",
        "no_bms_files": "ไม่พบไฟล์ BMS ในโฟลเดอร์ 'bms/'",
        "scanning": "กำลังสแกนเพลง...",
        "gameplay_options": "ตัวเลือกเกมเพลย์",
        "speed_label": "ความเร็ว",
        "player_note": "โน้ตผู้เล่น",
        "ai_note": "โน้ต AI",
        "note_mod_label": "โน้ต MOD (M)",
        "ai_diff_label": "AI",
        "search_web_title": "ค้นหาเว็บ (bmssearch.net)",
        "search_hint": "พิมพ์คำค้นหาแล้วกด ENTER เพื่อค้นหา",
        "guide_title": "เปิดเบราว์เซอร์แล้ว! เล่นเพลงใหม่:",
        "guide_step1": "1. ดาวน์โหลดเพลงจากเว็บที่เปิด",
        "guide_step2": "2. แตกไฟล์ ZIP หรือ RAR ที่ดาวน์โหลด",
        "guide_step3": "3. ย้ายโฟลเดอร์ไปที่ 'bms/'",
        "guide_step4": "4. กด F5 เพื่อโหลดเพลงใหม่",
        "guide_close": "(กด ENTER, ESC หรือคลิกเพื่อปิด)",

        "calibration_title": "ปรับจูนออฟเซ็ต",
        "tap_to_beat": "กด SPACE ตามจังหวะ!",
        "cal_hint": "[SPACE] แตะ | [Y] ใช้กับดีเลย์ | [V] ใช้กับออฟเซ็ต | [ESC] กลับ",
        "avg_offset": "ออฟเซ็ตเฉลี่ย",
        "applied_judge": "นำ {val} ไปใช้กับดีเลย์การตัดสิน!",
        "applied_visual": "นำ {val} ไปใช้กับออฟเซ็ตภาพ!",
        "cal_last_avg": "ล่าสุด: {last} | เฉลี่ย: {avg}",

        "key_config_title": "ตั้งค่าปุ่ม",
        "key_help": "กด ENTER หรือคลิกเพื่อเปลี่ยน ESC เพื่อกลับ",
        "joystick_connected": "จอยสติ๊กเชื่อมต่อ: {n}",
        "lane_n": "เลน {n}",
        "waiting_input": "??? (รอการกด...)",

        "speed_display": "ความเร็ว x{val}",
        "fast": "เร็ว",
        "slow": "ช้า",
        "ai_vision": "AI Vision",
        "paused": "หยุดชั่วคราว",
        "resume_hint": "ESC / TAB: เล่นต่อ",
        "quit_hint": "Q / ENTER: ออก",

        "result_title": "ผลลัพธ์",
        "you_win": "คุณชนะ!",
        "ai_wins": "AI ชนะ",
        "score_label": "คะแนน: {val}",
        "ex_label": "EX: {ex}/{max} ({pct}%)",
        "ai_performance": "ผลงาน AI",
        "hit_timing": "การกระจายจังหวะ (เร็ว/ช้า)",
        "return_hint": "กด ENTER หรือ ESC เพื่อกลับ",

        "loading": "กำลังโหลด... {status}",
        "loading_artist": "ศิลปิน",
        "loading_genre": "แนว",
        "loading_bpm": "BPM",
        "loading_level": "ระดับ",
        "loading_notes": "โน้ต",

        "judgment_perfect": "PERFECT!",
        "judgment_great": "GREAT!",
        "judgment_good": "GOOD",
        "judgment_miss": "MISS",
    },

    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  PORTUGUESE (Português)                                            ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    "pt": {
        "menu_single": "UM JOGADOR",
        "menu_ai_multi": "MULTIJOGADOR IA",
        "menu_settings": "CONFIGURAÇÕES",
        "menu_quit": "SAIR",
        "quit_confirm": "Sair do jogo?",
        "yes": "SIM",
        "no": "NÃO",

        "settings_title": "CONFIGURAÇÕES DO SISTEMA",
        "calibrate": "CALIBRAR",
        "key_config": "TECLAS",
        "cat_system": "SISTEMA",
        "cat_audio": "ÁUDIO",
        "cat_gameplay": "JOGABILIDADE",
        "fps_limit": "Limite de FPS",
        "input_polling": "Taxa de entrada (Hz)",
        "fullscreen": "Tela cheia",
        "audio_device": "Dispositivo de áudio",
        "volume": "Volume geral",
        "sample_rate": "Taxa de amostra (Hz)",
        "audio_buffer": "Buffer de áudio",
        "audio_channels": "Canais de áudio",
        "visual_offset": "Offset visual (ms)",
        "hit_window_mult": "Multiplicador de janela",
        "judge_delay": "Atraso de julgamento (ms)",
        "language": "Idioma",

        "music_selection": "SELEÇÃO DE MÚSICA",
        "reload": "Recarregar (R)",
        "search_bms": "Buscar BMS (B)",
        "settings_btn": "Configurações (S)",
        "no_bms_files": "Nenhum arquivo BMS encontrado em 'bms/'.",
        "scanning": "Procurando músicas...",
        "gameplay_options": "OPÇÕES DE JOGO",
        "speed_label": "VELOCIDADE",
        "player_note": "NOTA DO JOGADOR",
        "ai_note": "NOTA DA IA",
        "note_mod_label": "MOD DE NOTA (M)",
        "ai_diff_label": "IA",
        "search_web_title": "Busca web (bmssearch.net)",
        "search_hint": "Digite sua busca e pressione ENTER.",
        "guide_title": "Navegador aberto! Para jogar uma nova música:",
        "guide_step1": "1. Baixe a faixa do site aberto.",
        "guide_step2": "2. Extraia o arquivo ZIP ou RAR.",
        "guide_step3": "3. Mova a pasta extraída para 'bms/'.",
        "guide_step4": "4. Pressione F5 para recarregar músicas.",
        "guide_close": "(Pressione ENTER, ESC ou clique para fechar)",

        "calibration_title": "CALIBRAÇÃO DE OFFSET",
        "tap_to_beat": "Pressione ESPAÇO no ritmo!",
        "cal_hint": "[ESPAÇO] Toque | [Y] Aplicar atraso | [V] Aplicar offset | [ESC] Voltar",
        "avg_offset": "Offset médio",
        "applied_judge": "{val} aplicado ao atraso de julgamento!",
        "applied_visual": "{val} aplicado ao offset visual!",
        "cal_last_avg": "Último: {last} | Média: {avg}",

        "key_config_title": "CONFIGURAR TECLAS",
        "key_help": "Pressione ENTER ou clique para rebindar. ESC para voltar.",
        "joystick_connected": "Joysticks conectados: {n}",
        "lane_n": "Faixa {n}",
        "waiting_input": "??? (Aguardando entrada...)",

        "speed_display": "VELOC. x{val}",
        "fast": "RÁPIDO",
        "slow": "LENTO",
        "ai_vision": "Visão IA",
        "paused": "PAUSADO",
        "resume_hint": "ESC / TAB: Retomar",
        "quit_hint": "Q / ENTER: Sair",

        "result_title": "RESULTADO",
        "you_win": "VOCÊ VENCEU!",
        "ai_wins": "IA VENCEU",
        "score_label": "PONTOS: {val}",
        "ex_label": "EX: {ex}/{max} ({pct}%)",
        "ai_performance": "DESEMPENHO DA IA",
        "hit_timing": "TEMPORIZAÇÃO (RÁPIDO/LENTO)",
        "return_hint": "Pressione ENTER ou ESC para voltar",

        "loading": "Carregando... {status}",
        "loading_artist": "Artista",
        "loading_genre": "Gênero",
        "loading_bpm": "BPM",
        "loading_level": "Nível",
        "loading_notes": "Notas",

        "judgment_perfect": "PERFECT!",
        "judgment_great": "GREAT!",
        "judgment_good": "GOOD",
        "judgment_miss": "MISS",
    },

    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  INDONESIAN (Bahasa Indonesia)                                     ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    "id": {
        "menu_single": "PEMAIN TUNGGAL",
        "menu_ai_multi": "MULTI PEMAIN AI",
        "menu_settings": "PENGATURAN",
        "menu_quit": "KELUAR",
        "quit_confirm": "Keluar dari game?",
        "yes": "YA",
        "no": "TIDAK",

        "settings_title": "PENGATURAN SISTEM",
        "calibrate": "KALIBRASI",
        "key_config": "ATUR TOMBOL",
        "cat_system": "SISTEM",
        "cat_audio": "AUDIO",
        "cat_gameplay": "GAMEPLAY",
        "fps_limit": "Batas FPS",
        "input_polling": "Polling Input (Hz)",
        "fullscreen": "Layar Penuh",
        "audio_device": "Perangkat Audio",
        "volume": "Volume",
        "sample_rate": "Sample Rate (Hz)",
        "audio_buffer": "Buffer Audio",
        "audio_channels": "Saluran Audio",
        "visual_offset": "Offset Visual (ms)",
        "hit_window_mult": "Pengali Jendela Hit",
        "judge_delay": "Delay Penilaian (ms)",
        "language": "Bahasa",

        "music_selection": "PILIH LAGU",
        "reload": "Muat Ulang (R)",
        "search_bms": "Cari BMS (B)",
        "settings_btn": "Pengaturan (S)",
        "no_bms_files": "Tidak ada file BMS di folder 'bms/'.",
        "scanning": "Memindai lagu...",
        "gameplay_options": "OPSI GAMEPLAY",
        "speed_label": "KECEPATAN",
        "player_note": "NOT PEMAIN",
        "ai_note": "NOT AI",
        "note_mod_label": "MOD NOT (M)",
        "ai_diff_label": "AI",
        "search_web_title": "Cari Web (bmssearch.net)",
        "search_hint": "Ketik pencarian lalu tekan ENTER.",
        "guide_title": "Browser terbuka! Untuk memainkan lagu baru:",
        "guide_step1": "1. Unduh lagu dari situs yang terbuka.",
        "guide_step2": "2. Ekstrak file ZIP atau RAR.",
        "guide_step3": "3. Pindahkan folder ke 'bms/'.",
        "guide_step4": "4. Tekan F5 untuk memuat ulang lagu.",
        "guide_close": "(Tekan ENTER, ESC atau klik untuk menutup)",

        "calibration_title": "KALIBRASI OFFSET",
        "tap_to_beat": "Tekan SPACE sesuai ketukan!",
        "cal_hint": "[SPACE] Ketuk | [Y] Terapkan delay | [V] Terapkan offset | [ESC] Kembali",
        "avg_offset": "Offset rata-rata",
        "applied_judge": "{val} diterapkan ke delay penilaian!",
        "applied_visual": "{val} diterapkan ke offset visual!",
        "cal_last_avg": "Terakhir: {last} | Rata-rata: {avg}",

        "key_config_title": "ATUR TOMBOL",
        "key_help": "Tekan ENTER atau klik untuk mengubah. ESC untuk kembali.",
        "joystick_connected": "Joystick terhubung: {n}",
        "lane_n": "Jalur {n}",
        "waiting_input": "??? (Menunggu input...)",

        "speed_display": "KECEP. x{val}",
        "fast": "CEPAT",
        "slow": "LAMBAT",
        "ai_vision": "Penglihatan AI",
        "paused": "DIJEDA",
        "resume_hint": "ESC / TAB: Lanjut",
        "quit_hint": "Q / ENTER: Keluar",

        "result_title": "HASIL",
        "you_win": "ANDA MENANG!",
        "ai_wins": "AI MENANG",
        "score_label": "SKOR: {val}",
        "ex_label": "EX: {ex}/{max} ({pct}%)",
        "ai_performance": "PERFORMA AI",
        "hit_timing": "DISTRIBUSI TIMING (CEPAT/LAMBAT)",
        "return_hint": "Tekan ENTER atau ESC untuk kembali",

        "loading": "Memuat... {status}",
        "loading_artist": "Artis",
        "loading_genre": "Genre",
        "loading_bpm": "BPM",
        "loading_level": "Level",
        "loading_notes": "Not",

        "judgment_perfect": "PERFECT!",
        "judgment_great": "GREAT!",
        "judgment_good": "GOOD",
        "judgment_miss": "MISS",
    },

    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  SPANISH (Español)                                                 ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    "es": {
        "menu_single": "UN JUGADOR",
        "menu_ai_multi": "MULTIJUGADOR IA",
        "menu_settings": "AJUSTES",
        "menu_quit": "SALIR",
        "quit_confirm": "¿Salir del juego?",
        "yes": "SÍ",
        "no": "NO",

        "settings_title": "AJUSTES DEL SISTEMA",
        "calibrate": "CALIBRAR",
        "key_config": "TECLAS",
        "cat_system": "SISTEMA",
        "cat_audio": "AUDIO",
        "cat_gameplay": "JUEGO",
        "fps_limit": "Límite de FPS",
        "input_polling": "Tasa de entrada (Hz)",
        "fullscreen": "Pantalla completa",
        "audio_device": "Dispositivo de audio",
        "volume": "Volumen general",
        "sample_rate": "Tasa de muestreo (Hz)",
        "audio_buffer": "Búfer de audio",
        "audio_channels": "Canales de audio",
        "visual_offset": "Offset visual (ms)",
        "hit_window_mult": "Multiplicador de ventana",
        "judge_delay": "Retardo de juicio (ms)",
        "language": "Idioma",

        "music_selection": "SELECCIÓN DE MÚSICA",
        "reload": "Recargar (R)",
        "search_bms": "Buscar BMS (B)",
        "settings_btn": "Ajustes (S)",
        "no_bms_files": "No se encontraron archivos BMS en 'bms/'.",
        "scanning": "Buscando canciones...",
        "gameplay_options": "OPCIONES DE JUEGO",
        "speed_label": "VELOCIDAD",
        "player_note": "NOTA JUGADOR",
        "ai_note": "NOTA IA",
        "note_mod_label": "MOD NOTA (M)",
        "ai_diff_label": "IA",
        "search_web_title": "Buscar en web (bmssearch.net)",
        "search_hint": "Escribe tu búsqueda y presiona ENTER.",
        "guide_title": "¡Navegador abierto! Para jugar una nueva canción:",
        "guide_step1": "1. Descarga la pista del sitio abierto.",
        "guide_step2": "2. Extrae el archivo ZIP o RAR descargado.",
        "guide_step3": "3. Mueve la carpeta extraída a 'bms/'.",
        "guide_step4": "4. Presiona F5 para recargar canciones.",
        "guide_close": "(Presiona ENTER, ESC o clic para cerrar)",

        "calibration_title": "CALIBRACIÓN DE OFFSET",
        "tap_to_beat": "¡Presiona ESPACIO al ritmo!",
        "cal_hint": "[ESPACIO] Toque | [Y] Aplicar retardo | [V] Aplicar offset | [ESC] Volver",
        "avg_offset": "Offset promedio",
        "applied_judge": "¡{val} aplicado al retardo de juicio!",
        "applied_visual": "¡{val} aplicado al offset visual!",
        "cal_last_avg": "Último: {last} | Promedio: {avg}",

        "key_config_title": "CONFIGURAR TECLAS",
        "key_help": "Presiona ENTER o clic para reasignar. ESC para volver.",
        "joystick_connected": "Joysticks conectados: {n}",
        "lane_n": "Carril {n}",
        "waiting_input": "??? (Esperando entrada...)",

        "speed_display": "VELOC. x{val}",
        "fast": "RÁPIDO",
        "slow": "LENTO",
        "ai_vision": "Visión IA",
        "paused": "PAUSA",
        "resume_hint": "ESC / TAB: Reanudar",
        "quit_hint": "Q / ENTER: Salir",

        "result_title": "RESULTADO",
        "you_win": "¡GANASTE!",
        "ai_wins": "IA GANA",
        "score_label": "PUNTOS: {val}",
        "ex_label": "EX: {ex}/{max} ({pct}%)",
        "ai_performance": "RENDIMIENTO IA",
        "hit_timing": "TEMPORIZACIÓN (RÁPIDO/LENTO)",
        "return_hint": "Presiona ENTER o ESC para volver",

        "loading": "Cargando... {status}",
        "loading_artist": "Artista",
        "loading_genre": "Género",
        "loading_bpm": "BPM",
        "loading_level": "Nivel",
        "loading_notes": "Notas",

        "judgment_perfect": "PERFECT!",
        "judgment_great": "GREAT!",
        "judgment_good": "GOOD",
        "judgment_miss": "MISS",
    },

    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  FRENCH (Français)                                                 ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    "fr": {
        "menu_single": "SOLO",
        "menu_ai_multi": "MULTI IA",
        "menu_settings": "PARAMÈTRES",
        "menu_quit": "QUITTER",
        "quit_confirm": "Quitter le jeu ?",
        "yes": "OUI",
        "no": "NON",

        "settings_title": "PARAMÈTRES SYSTÈME",
        "calibrate": "CALIBRER",
        "key_config": "TOUCHES",
        "cat_system": "SYSTÈME",
        "cat_audio": "AUDIO",
        "cat_gameplay": "JEU",
        "fps_limit": "Limite FPS",
        "input_polling": "Taux d'entrée (Hz)",
        "fullscreen": "Plein écran",
        "audio_device": "Périphérique audio",
        "volume": "Volume général",
        "sample_rate": "Fréquence (Hz)",
        "audio_buffer": "Tampon audio",
        "audio_channels": "Canaux audio",
        "visual_offset": "Décalage visuel (ms)",
        "hit_window_mult": "Multiplicateur de fenêtre",
        "judge_delay": "Délai de jugement (ms)",
        "language": "Langue",

        "music_selection": "SÉLECTION MUSICALE",
        "reload": "Recharger (R)",
        "search_bms": "Chercher BMS (B)",
        "settings_btn": "Paramètres (S)",
        "no_bms_files": "Aucun fichier BMS trouvé dans 'bms/'.",
        "scanning": "Recherche de morceaux...",
        "gameplay_options": "OPTIONS DE JEU",
        "speed_label": "VITESSE",
        "player_note": "NOTE JOUEUR",
        "ai_note": "NOTE IA",
        "note_mod_label": "MOD NOTE (M)",
        "ai_diff_label": "IA",
        "search_web_title": "Recherche web (bmssearch.net)",
        "search_hint": "Tapez votre recherche et appuyez sur ENTRÉE.",
        "guide_title": "Navigateur ouvert ! Pour jouer un nouveau morceau :",
        "guide_step1": "1. Téléchargez le morceau depuis le site.",
        "guide_step2": "2. Extrayez le fichier ZIP ou RAR.",
        "guide_step3": "3. Déplacez le dossier dans 'bms/'.",
        "guide_step4": "4. Appuyez sur F5 pour recharger.",
        "guide_close": "(Appuyez sur ENTRÉE, ÉCHAP ou cliquez pour fermer)",

        "calibration_title": "CALIBRATION DE L'OFFSET",
        "tap_to_beat": "Appuyez sur ESPACE au rythme !",
        "cal_hint": "[ESPACE] Tap | [Y] Appliquer délai | [V] Appliquer offset | [ÉCHAP] Retour",
        "avg_offset": "Offset moyen",
        "applied_judge": "{val} appliqué au délai de jugement !",
        "applied_visual": "{val} appliqué à l'offset visuel !",
        "cal_last_avg": "Dernier: {last} | Moy: {avg}",

        "key_config_title": "CONFIG. TOUCHES",
        "key_help": "Appuyez sur ENTRÉE ou cliquez pour modifier. ÉCHAP pour revenir.",
        "joystick_connected": "Joysticks connectés : {n}",
        "lane_n": "Piste {n}",
        "waiting_input": "??? (En attente d'entrée...)",

        "speed_display": "VITESSE x{val}",
        "fast": "RAPIDE",
        "slow": "LENT",
        "ai_vision": "Vision IA",
        "paused": "PAUSE",
        "resume_hint": "ÉCHAP / TAB : Reprendre",
        "quit_hint": "Q / ENTRÉE : Quitter",

        "result_title": "RÉSULTAT",
        "you_win": "VICTOIRE !",
        "ai_wins": "L'IA GAGNE",
        "score_label": "SCORE : {val}",
        "ex_label": "EX : {ex}/{max} ({pct}%)",
        "ai_performance": "PERFORMANCE IA",
        "hit_timing": "TIMING (RAPIDE/LENT)",
        "return_hint": "Appuyez sur ENTRÉE ou ÉCHAP pour revenir",

        "loading": "Chargement... {status}",
        "loading_artist": "Artiste",
        "loading_genre": "Genre",
        "loading_bpm": "BPM",
        "loading_level": "Niveau",
        "loading_notes": "Notes",

        "judgment_perfect": "PERFECT!",
        "judgment_great": "GREAT!",
        "judgment_good": "GOOD",
        "judgment_miss": "MISS",
    },

    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  ITALIAN (Italiano)                                                ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    "it": {
        "menu_single": "GIOCATORE SINGOLO",
        "menu_ai_multi": "MULTI IA",
        "menu_settings": "IMPOSTAZIONI",
        "menu_quit": "ESCI",
        "quit_confirm": "Uscire dal gioco?",
        "yes": "SÌ",
        "no": "NO",

        "settings_title": "IMPOSTAZIONI DI SISTEMA",
        "calibrate": "CALIBRA",
        "key_config": "TASTI",
        "cat_system": "SISTEMA",
        "cat_audio": "AUDIO",
        "cat_gameplay": "GIOCO",
        "fps_limit": "Limite FPS",
        "input_polling": "Polling input (Hz)",
        "fullscreen": "Schermo intero",
        "audio_device": "Dispositivo audio",
        "volume": "Volume generale",
        "sample_rate": "Frequenza (Hz)",
        "audio_buffer": "Buffer audio",
        "audio_channels": "Canali audio",
        "visual_offset": "Offset visivo (ms)",
        "hit_window_mult": "Moltiplicatore finestra",
        "judge_delay": "Ritardo giudizio (ms)",
        "language": "Lingua",

        "music_selection": "SELEZIONE BRANI",
        "reload": "Ricarica (R)",
        "search_bms": "Cerca BMS (B)",
        "settings_btn": "Impostazioni (S)",
        "no_bms_files": "Nessun file BMS trovato in 'bms/'.",
        "scanning": "Scansione brani...",
        "gameplay_options": "OPZIONI DI GIOCO",
        "speed_label": "VELOCITÀ",
        "player_note": "NOTA GIOCATORE",
        "ai_note": "NOTA IA",
        "note_mod_label": "MOD NOTA (M)",
        "ai_diff_label": "IA",
        "search_web_title": "Cerca sul web (bmssearch.net)",
        "search_hint": "Digita la ricerca e premi INVIO.",
        "guide_title": "Browser aperto! Per suonare un nuovo brano:",
        "guide_step1": "1. Scarica il brano dal sito aperto.",
        "guide_step2": "2. Estrai il file ZIP o RAR.",
        "guide_step3": "3. Sposta la cartella in 'bms/'.",
        "guide_step4": "4. Premi F5 per ricaricare i brani.",
        "guide_close": "(Premi INVIO, ESC o clicca per chiudere)",

        "calibration_title": "CALIBRAZIONE OFFSET",
        "tap_to_beat": "Premi SPAZIO a tempo!",
        "cal_hint": "[SPAZIO] Tap | [Y] Applica ritardo | [V] Applica offset | [ESC] Indietro",
        "avg_offset": "Offset medio",
        "applied_judge": "{val} applicato al ritardo di giudizio!",
        "applied_visual": "{val} applicato all'offset visivo!",
        "cal_last_avg": "Ultimo: {last} | Media: {avg}",

        "key_config_title": "CONFIGURAZIONE TASTI",
        "key_help": "Premi INVIO o clicca per rimappare. ESC per tornare.",
        "joystick_connected": "Joystick collegati: {n}",
        "lane_n": "Corsia {n}",
        "waiting_input": "??? (In attesa di input...)",

        "speed_display": "VELOC. x{val}",
        "fast": "VELOCE",
        "slow": "LENTO",
        "ai_vision": "Visione IA",
        "paused": "PAUSA",
        "resume_hint": "ESC / TAB: Riprendi",
        "quit_hint": "Q / INVIO: Esci",

        "result_title": "RISULTATO",
        "you_win": "HAI VINTO!",
        "ai_wins": "L'IA VINCE",
        "score_label": "PUNTEGGIO: {val}",
        "ex_label": "EX: {ex}/{max} ({pct}%)",
        "ai_performance": "PRESTAZIONI IA",
        "hit_timing": "TEMPISMO (VELOCE/LENTO)",
        "return_hint": "Premi INVIO o ESC per tornare",

        "loading": "Caricamento... {status}",
        "loading_artist": "Artista",
        "loading_genre": "Genere",
        "loading_bpm": "BPM",
        "loading_level": "Livello",
        "loading_notes": "Note",

        "judgment_perfect": "PERFECT!",
        "judgment_great": "GREAT!",
        "judgment_good": "GOOD",
        "judgment_miss": "MISS",
    },

    # ╔══════════════════════════════════════════════════════════════════════╗
    # ║  GERMAN (Deutsch)                                                  ║
    # ╚══════════════════════════════════════════════════════════════════════╝
    "de": {
        "menu_single": "EINZELSPIELER",
        "menu_ai_multi": "KI-MEHRSPIELER",
        "menu_settings": "EINSTELLUNGEN",
        "menu_quit": "BEENDEN",
        "quit_confirm": "Spiel beenden?",
        "yes": "JA",
        "no": "NEIN",

        "settings_title": "SYSTEMEINSTELLUNGEN",
        "calibrate": "KALIBRIEREN",
        "key_config": "TASTEN",
        "cat_system": "SYSTEM",
        "cat_audio": "AUDIO",
        "cat_gameplay": "GAMEPLAY",
        "fps_limit": "FPS-Limit",
        "input_polling": "Eingabeabtastung (Hz)",
        "fullscreen": "Vollbild",
        "audio_device": "Audiogerät",
        "volume": "Gesamtlautstärke",
        "sample_rate": "Abtastrate (Hz)",
        "audio_buffer": "Audiopuffer",
        "audio_channels": "Audiokanäle",
        "visual_offset": "Visueller Offset (ms)",
        "hit_window_mult": "Trefferfenster-Multiplikator",
        "judge_delay": "Bewertungsverzögerung (ms)",
        "language": "Sprache",

        "music_selection": "MUSIKAUSWAHL",
        "reload": "Neu laden (R)",
        "search_bms": "BMS suchen (B)",
        "settings_btn": "Einstellungen (S)",
        "no_bms_files": "Keine BMS-Dateien in 'bms/' gefunden.",
        "scanning": "Lieder werden gesucht...",
        "gameplay_options": "SPIELOPTIONEN",
        "speed_label": "GESCHWINDIGKEIT",
        "player_note": "SPIELERNOTE",
        "ai_note": "KI-NOTE",
        "note_mod_label": "NOTEN-MOD (M)",
        "ai_diff_label": "KI",
        "search_web_title": "Websuche (bmssearch.net)",
        "search_hint": "Suchbegriff eingeben und ENTER drücken.",
        "guide_title": "Browser geöffnet! Um ein neues Lied zu spielen:",
        "guide_step1": "1. Laden Sie den Track von der Website herunter.",
        "guide_step2": "2. Entpacken Sie die ZIP- oder RAR-Datei.",
        "guide_step3": "3. Verschieben Sie den Ordner nach 'bms/'.",
        "guide_step4": "4. Drücken Sie F5 zum Neuladen.",
        "guide_close": "(ENTER, ESC oder Klick zum Schließen)",

        "calibration_title": "OFFSET-KALIBRIERUNG",
        "tap_to_beat": "Drücken Sie LEERTASTE im Takt!",
        "cal_hint": "[LEERTASTE] Tap | [Y] Verzögerung | [V] Offset | [ESC] Zurück",
        "avg_offset": "Durchschnittl. Offset",
        "applied_judge": "{val} auf Bewertungsverzögerung angewendet!",
        "applied_visual": "{val} auf visuellen Offset angewendet!",
        "cal_last_avg": "Letzter: {last} | Durchschn.: {avg}",

        "key_config_title": "TASTENKONFIGURATION",
        "key_help": "ENTER oder Klick zum Ändern. ESC zum Zurückkehren.",
        "joystick_connected": "Joysticks verbunden: {n}",
        "lane_n": "Spur {n}",
        "waiting_input": "??? (Warte auf Eingabe...)",

        "speed_display": "GESCHW. x{val}",
        "fast": "SCHNELL",
        "slow": "LANGSAM",
        "ai_vision": "KI-Sicht",
        "paused": "PAUSIERT",
        "resume_hint": "ESC / TAB: Fortsetzen",
        "quit_hint": "Q / ENTER: Beenden",

        "result_title": "ERGEBNIS",
        "you_win": "DU GEWINNST!",
        "ai_wins": "KI GEWINNT",
        "score_label": "PUNKTE: {val}",
        "ex_label": "EX: {ex}/{max} ({pct}%)",
        "ai_performance": "KI-LEISTUNG",
        "hit_timing": "TIMING (SCHNELL/LANGSAM)",
        "return_hint": "ENTER oder ESC zum Zurückkehren",

        "loading": "Laden... {status}",
        "loading_artist": "Künstler",
        "loading_genre": "Genre",
        "loading_bpm": "BPM",
        "loading_level": "Stufe",
        "loading_notes": "Noten",

        "judgment_perfect": "PERFECT!",
        "judgment_great": "GREAT!",
        "judgment_good": "GOOD",
        "judgment_miss": "MISS",
    },
}
