import json
import os
from .. import paths

def get_default_challenges():
    """ 
    Hardcoded challenge definitions for distribution safety. 
    
    Supported conditions inside the "condition" dictionary:
    
    [General Check]
    - min_level (int): Minimum level of the BMS (e.g., 3, 7, 10).
    - mode (str): The game mode to which this applies ("ai_multi", "single", "course_stage", "course_end").
    - must_clear (bool): If True, implicitly fails the challenge if the player's HP reaches 0 (default: True).
    - must_win (bool): If True, only completes if the player beats the AI (only valid for "ai_multi").
    
    [Stat Check]
    - min_accuracy (float): Minimum overall accuracy percentage required (0.0 to 100.0).
    - min_combo (int): Minimum required max combo during the play.
    - min_notes (int): Total number of notes in the chart must be higher than this.
    
    [Judgment Specifics]
    - max_misses (int): The absolute maximum number of MISS judgments allowed.
    - max_goods (int): The maximum number of GOOD judgments allowed.
    - max_greats (int): The maximum number of GREAT judgments allowed.
    - min_perfects (int): The minimum number of PERFECT judgments required.
    - require_full_combo (bool): If True, fails instantly if there are any MISS judgments.
    - require_all_perfect (bool): If True, fails instantly if there are any MISS, GOOD, or GREAT judgments.
    
    [Course Mode Specifics]
    - min_hp (float): Minimum HP needed to complete the condition (for "course_stage").
    - min_difficulty (int): Minimum course difficulty index (0=BEG, 1=INT, 2=ADV, 3=ORD) (for "course_end").
    - min_score (int): Minimum total score accumulated across the course (for "course_end").
    """
    return [
        {
            "id": "clear_lv3",
            "condition": {"min_level": 3}
        },
        {
            "id": "clear_lv7",
            "condition": {"min_level": 7}
        },
        {
            "id": "clear_lv10",
            "condition": {"min_level": 10}
        },
        {
            "id": "combo_100_lv5",
            "condition": {"min_level": 5, "min_combo": 100}
        },
        {
            "id": "multi_win",
            "condition": {"must_win": True, "mode": "ai_multi"}
        },
        {
            "id": "course_clear",
            "condition": {"mode": "course_end"}
        },
        {
            "id": "course_full_hp",
            "condition": {"min_hp": 100.0, "mode": "course_stage"}
        },
        {
            "id": "course_advanced",
            "condition": {"min_difficulty": 2, "mode": "course_end"} # 0: BEG, 1: INT, 2: ADV, 3: ORD
        },
        {
            "id": "you_are_already_dead",
            "condition": {"mode": "ai_multi", "ai_difficulty": "hard"}
        },
        {
            "id": "vibe_coding",
            "condition": {"mode": "ai_multi", "max_accuracy": 49.9, "ai_min_accuracy": 99.0, "must_clear": False}
        },
        {
            "id": "ai_needs_time",
            "condition": {"mode": "ai_multi", "ai_paused": True, "must_clear": False}
        },
        {
            "id": "ai_wants_retry",
            "condition": {"mode": "ai_multi", "ai_restarted": True, "must_clear": False}
        },
        {
            "id": "compression_master",
            "condition": {"lanes_compressed": True, "must_clear": True}
        },
        {
            "id": "unprecedented_system",
            "condition": {"has_ln": True, "must_clear": True}
        },
        {
            "id": "bms_player",
            "condition": {"mode": "scan_complete", "min_bms_count": 1}
        },
        {
            "id": "unbreakable_spirit",
            "condition": {"mode": "course_end", "min_consecutive_courses": 2}
        },
        {
            "id": "mod_try",
            "condition": {"used_mod": True, "must_clear": False}
        },
        {
            "id": "judgment_artisan",
            "condition": {"speed_changed": True, "must_clear": False}
        },
        {
            "id": "trust_dfjk",
            "condition": {"used_dfjk": True, "must_clear": True}
        },
        {
            "id": "notes_are_mean",
            "condition": {"first_note_miss": True, "must_clear": False}
        },
        {
            "id": "aesthetics_of_zero",
            "condition": {"max_judgments": 0, "min_notes": 1, "must_clear": True}
        },
        {
            "id": "first_time_rhythm_game",
            "condition": {"max_accuracy": 49.9, "must_clear": True}
        }
    ]

class ChallengeManager:
    def __init__(self):
        self.progress_file = os.path.join(paths.DATA_PATH, "user_progress.json")
        self.challenges = get_default_challenges()
        self.completed_ids = set()
        self.load_progress()

    def load_progress(self):
        """ Load user progress. """
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.completed_ids = set(data.get('completed', []))
            except Exception as e:
                print(f"Error loading progress: {e}")
                self.completed_ids = set()

    def save_progress(self):
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump({'completed': list(self.completed_ids)}, f, indent=4)
        except Exception as e:
            print(f"Error saving progress: {e}")

    def check_challenges(self, result_stats):
        newly_completed = []
        
        # Track consecutive courses
        current_mode = result_stats.get('mode')
        if current_mode == 'course_end':
            if not result_stats.get('failed', False):
                self.consecutive_courses = getattr(self, 'consecutive_courses', 0) + 1
            else:
                self.consecutive_courses = 0
            result_stats['consecutive_courses'] = self.consecutive_courses
        elif current_mode in ('single', 'ai_multi'):
            self.consecutive_courses = 0
            result_stats['consecutive_courses'] = 0
            
        for challenge in self.challenges:
            cid = challenge['id']
            if cid in self.completed_ids:
                continue
            
            if self._evaluate(challenge, result_stats):
                self.completed_ids.add(cid)
                newly_completed.append(challenge)
        
        if newly_completed:
            self.save_progress()
        return newly_completed

    def _evaluate(self, challenge, stats):
        cond = challenge.get('condition', {})
        
        # Mode check
        required_mode = cond.get('mode')
        current_mode = stats.get('mode')
        
        # Special course modes
        if required_mode == "course_end" and current_mode != "course_end":
            return False
        if required_mode == "course_stage" and current_mode != "course_stage":
            return False
        
        if required_mode and required_mode not in ("course_end", "course_stage") and current_mode != required_mode:
            return False

        # Level check
        min_level = cond.get('min_level', 0)
        if min_level > 0:
            level_str = str(stats.get('level', '0'))
            try:
                level = int(''.join(filter(str.isdigit, level_str)))
            except:
                level = 0
            if level < min_level:
                return False
            
        # Accuracy check (min/max)
        min_acc = cond.get('min_accuracy', 0.0)
        if stats.get('accuracy', 0.0) < min_acc:
            return False
            
        max_acc = cond.get('max_accuracy', 100.0)
        if stats.get('accuracy', 0.0) > max_acc:
            return False
            
        # AI specific accuracy check
        ai_min_acc = cond.get('ai_min_accuracy', 0.0)
        if ai_min_acc > 0.0 and stats.get('ai_accuracy', 0.0) < ai_min_acc:
            return False

        # Clear check
        # 'must_clear': defaults to True when evaluating clear conditions
        if cond.get('must_clear', True) and stats.get('failed', False):
            return False
            
        # Specific failed check
        if cond.get('failed') is True and not stats.get('failed', False):
            return False
            
        # Combo check
        min_combo = cond.get('min_combo', 0)
        if stats.get('max_combo', 0) < min_combo:
            return False

        # Note count check
        min_notes = cond.get('min_notes', 0)
        if stats.get('total_notes', 0) < min_notes:
            return False

        # Custom win check
        if cond.get('must_win', False) and not stats.get('must_win', False):
            return False

        # Course specific: HP check
        min_hp = cond.get('min_hp', 0.0)
        if min_hp > 0 and stats.get('hp', 0.0) < min_hp:
            return False
            
        # Course specific: Consecutive clears
        min_consecutive = cond.get('min_consecutive_courses', 0)
        if min_consecutive > 0 and stats.get('consecutive_courses', 0) < min_consecutive:
            return False
            
        # Special Booleans
        for flag in ['ai_paused', 'ai_restarted', 'lanes_compressed', 'has_ln', 
                     'speed_changed', 'first_note_miss']:
            if cond.get(flag) is True and not stats.get(flag, False):
                return False
                
        # Used keys
        if 'used_dfjk' in cond:
            if cond['used_dfjk'] != stats.get('used_dfjk'):
                return False
                
        # Used mod
        if cond.get('used_mod') is True and stats.get('note_mod', 'None') == 'None':
            return False
            
        # AI Difficulty
        req_diff = cond.get('ai_difficulty')
        if req_diff and stats.get('ai_diff', 'normal') != req_diff:
            return False
            
        # BMS scan completion
        min_bms = cond.get('min_bms_count', 0)
        if min_bms > 0 and stats.get('total_songs', 0) < min_bms:
            return False

        # Course specific: Difficulty index check
        min_diff_idx = cond.get('min_difficulty', -1)
        if min_diff_idx >= 0:
            diff_map = {"BEGINNER": 0, "INTERMEDIATE": 1, "ADVANCED": 2, "ORDEAL": 3}
            curr_diff = diff_map.get(stats.get('difficulty', ''), -1)
            if curr_diff < min_diff_idx:
                return False

        # Course specific: Minimum Total Score
        min_score = cond.get('min_score', 0)
        if min_score > 0 and stats.get('total_score', 0) < min_score:
            return False

        # Judgment limits
        judgments = stats.get('judgments', {})
        total_hits = sum(judgments.values())
        
        max_judgs = cond.get('max_judgments', -1)
        if max_judgs >= 0 and total_hits > max_judgs:
            return False
            
        max_misses = cond.get('max_misses', -1)
        if max_misses >= 0 and judgments.get("MISS", 0) > max_misses:
            return False
            
        max_goods = cond.get('max_goods', -1)
        if max_goods >= 0 and judgments.get("GOOD", 0) > max_goods:
            return False
            
        max_greats = cond.get('max_greats', -1)
        if max_greats >= 0 and judgments.get("GREAT", 0) > max_greats:
            return False
            
        min_perfs = cond.get('min_perfects', 0)
        if min_perfs > 0 and judgments.get("PERFECT", 0) < min_perfs:
            return False
            
        # Strict Combo Flags
        if cond.get('require_full_combo', False):
            if judgments.get("MISS", 0) > 0:
                return False
                
        if cond.get('require_all_perfect', False):
            if judgments.get("MISS", 0) > 0 or judgments.get("GOOD", 0) > 0 or judgments.get("GREAT", 0) > 0:
                return False

        return True
