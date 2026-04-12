_STRINGS = {
    "en": {
        "menu_two_key":         "2-Key Mode",
        "two_key_hint_play":    "ENTER  Play   ESC  Back   S  Settings",
        "two_key_subtitle":     "4-lane charts merged into 2 keys",
        "two_key_fail":         "FAILED",
        "two_key_hp":           "HP",
        "two_key_keys_hint":    "Left: {left}   Right: {right}",
    },
    "ko": {
        "menu_two_key":         "2키 모드",
        "two_key_hint_play":    "ENTER  플레이   ESC  뒤로   S  설정",
        "two_key_subtitle":     "4레인 채보를 2키로 플레이",
        "two_key_fail":         "실패",
        "two_key_hp":           "HP",
        "two_key_keys_hint":    "왼쪽: {left}   오른쪽: {right}",
    },
    "ja": {
        "menu_two_key":         "2キーモード",
        "two_key_hint_play":    "ENTER  プレイ   ESC  戻る   S  設定",
        "two_key_subtitle":     "4レーン譜面を2キーでプレイ",
        "two_key_fail":         "失敗",
        "two_key_hp":           "HP",
        "two_key_keys_hint":    "左: {left}   右: {right}",
    },
}


def t(key: str, **kwargs) -> str:
    from only4bms.i18n import get_language
    lang = get_language()
    table = _STRINGS.get(lang, _STRINGS["en"])
    s = table.get(key) or _STRINGS["en"].get(key, key)
    return s.format(**kwargs) if kwargs else s
