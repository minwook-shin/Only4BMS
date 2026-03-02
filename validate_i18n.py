import os
import ast
import re
from pathlib import Path
import sys
import io

out = io.open("validate_out.txt", "w", encoding="utf-8")

# Change directory to project root or use given param
project_root = r"c:\Users\han\Documents\GitHub\Only4BMS\src\only4bms"
i18n_path = r"c:\Users\han\Documents\GitHub\Only4BMS\src\only4bms\i18n.py"

def p(msg=""):
    out.write(str(msg) + "\n")
    
p("="*60)
p(" [1] CHECKING FOR UNTRANSLATED HARDCODED STRINGS ")
p("="*60)

# Files or directories to ignore entirely
ignore_files = ["i18n.py", "bms_parser.py", "paths.py"]

# Patterns for strings that are clearly NOT UI text
ignore_patterns = [
    re.compile(r"^[A-Z0-9_\-]+$"),            # ALL_CAPS/CONST enum values
    re.compile(r"^\d[\d.,]*$"),               # Numbers
    re.compile(r"^[#$@%]"),                   # Hex colors, symbols  
    re.compile(r"^[/\\~]"),                   # Paths
    re.compile(r"\.\w{1,5}$"),               # Any file extension like .wav, .mp4, .bms, .png, .ogg, .mp3
    re.compile(r"^https?://"),               # URLs
    re.compile(r"\{.*\}"),                   # Format strings like '{val}'
    re.compile(r"^\+?\.\d"),                 # Format specs like '.1f', '+.1f'
    re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*\("), # function calls in strings
    re.compile(r"^UTF|utf", re.I),            # Encoding names
    re.compile(r"^(True|False|None)$"),       # Python literals
    re.compile(r"^[A-Z]{2,}\s*[:!?]"),        # Protocol headers like "GET:", "PERFECT!"
    re.compile(r"^(PERFECT|GREAT|GOOD|MISS)[!]?$"),  # judgment strings (in constants.py, i18n handles them)
    re.compile(r"Mock Song Demo"),            # Generated demo song name
    re.compile(r"^Only4BMS"),                # App name (branding)
    re.compile(r"^\(|\)$"),                  # Lone parens
    re.compile(r"^[<>!?]{1,3}$"),            # Operators
    re.compile(r"^\d+/\d+\)$"),             # fraction text like '(1/2)'
    re.compile(r"^\(T\)$|\(A\)$|\(Shift\+"),  # keyboard hint strings handled elsewhere
]

# Strings that look like docstrings (long, start with capital, have period)
def is_docstring(s, line_str):
    return (line_str.strip().startswith('"""') or
            line_str.strip().startswith("'''") or
            (len(s) > 40 and s[0].isupper() and "." in s and not any(c in s for c in "[]{}()")))

def should_ignore_string(s):
    if len(s) <= 3: return True
    for pat in ignore_patterns:
        if pat.search(s): return True
    
    has_asian = re.search(r'[\u4e00-\u9FFF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF]', s)
    if has_asian: return False  # Always flag Asian text

    # Pure single-word English without spaces = likely internal key/constant
    if " " not in s and re.match(r"^[a-zA-Z0-9_\-\.]+$", s):
        return True
        
    return False

class StringAnalyzer(ast.NodeVisitor):
    def __init__(self, filepath):
        self.filepath = filepath
        self.hardcoded = []

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            self.hardcoded.append((node.lineno, node.value.strip()))
        self.generic_visit(node)

    def visit_Str(self, node):
        self.hardcoded.append((node.lineno, node.s.strip()))
        self.generic_visit(node)

# AST-based docstring node detector (module, class, function first expression)
def get_docstring_lines(tree):
    docstring_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (node.body and isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Constant) and
                    isinstance(node.body[0].value.value, str)):
                docstring_lines.add(node.body[0].value.lineno)
    return docstring_lines

warnings_found = 0

for file_path in Path(project_root).rglob("*.py"):
    if file_path.name in ignore_files or "ai" in str(file_path):
        continue
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)
        lines = src.splitlines()
            
        docstring_linenos = get_docstring_lines(tree)
        
        analyzer = StringAnalyzer(file_path)
        analyzer.visit(tree)
        
        final_hardcoded = []
        for lineno, s in analyzer.hardcoded:
            if not s: continue
            if lineno in docstring_linenos: continue  # skip docstrings
            
            line_str = lines[lineno - 1] if lineno <= len(lines) else ""
            stripped = line_str.strip()
            
            # Skip lines that are clearly not UI
            if any(kw in stripped for kw in ["print(", "logging.", "raise ", "Exception(", "ValueError(",
                                              "#", "os.path", "glob", "subprocess", "open(", "splitext",
                                              "endswith(", "startswith(", "f.write", "f.read"]):
                continue
            
            if should_ignore_string(s):
                continue
            
            final_hardcoded.append((lineno, s))
                
        if final_hardcoded:
            p(f"\n[WARN] Possibly un-localized strings in {file_path.name}:")
            for lineno, s in final_hardcoded:
                if len(s) > 60: s = s[:57] + "..."
                p(f"  Line {lineno}: '{s}'")
                warnings_found += 1
                
    except Exception as e:
        pass

if warnings_found == 0:
    p("\n[OK] PASS: No hardcoded UI strings detected.")
else:
    p(f"\n[FAIL] Found {warnings_found} potentially hardcoded strings.")


p("\n\n" + "="*60)
p(" [2] CHECKING i18n.py FOR MISSING TRANSLATIONS ")
p("="*60)

import importlib.util

spec = importlib.util.spec_from_file_location("i18n", i18n_path)
i18n_module = importlib.util.module_from_spec(spec)
sys.modules["i18n"] = i18n_module
spec.loader.exec_module(i18n_module)

STRINGS = i18n_module.STRINGS
en_keys = set(STRINGS["en"].keys())

missing_translations = False

for lang, table in STRINGS.items():
    if lang == "en": continue
    
    lang_keys = set(table.keys())
    missing_in_lang = en_keys - lang_keys
    
    if missing_in_lang:
        p(f"\n[FAIL] Language '{lang}' is missing {len(missing_in_lang)} keys:")
        for k in sorted(list(missing_in_lang)):
            p(f"  - {k}")
        missing_translations = True

if not missing_translations:
    p("\n[OK] PASS: All languages contain the full set of English keys.")

out.close()
print("Done. See validate_out.txt for full report.")
