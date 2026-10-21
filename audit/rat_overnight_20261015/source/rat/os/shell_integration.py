"""
rat.os.shell_integration — Deep Terminal Shell Integration (ZSH & Bash).
Injects intelligent natural language file finding, auto-cd, and keybindings directly into the user's terminal.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ZSH_SHELL_SCRIPT = """# === rat macOS Intelligent Shell Integration ===
# Add this to your ~/.zshrc or ~/.bash_profile:
# eval "$(rat init-shell)"

function rat() {
    local python_bin="%PYTHON_BIN%"
    local repo_main="%REPO_MAIN%"

    if [ "$#" -eq 0 ]; then
        "$python_bin" "$repo_main"
        return $?
    fi

    local cmd="$1"
    shift

    case "$cmd" in
        cd)
            # Smart cd into the directory of the best matching file
            local target_path=$("$python_bin" -c "
import sys
from rat.crawler.db import Database
from rat.engine.hybrid_search import SearchEngine
from rat.config import config
engine = SearchEngine(Database(config.db_path))
res = engine.search('$*', limit=1, use_vector=False)
if res['results']:
    import os
    p = res['results'][0].file_path
    print(os.path.dirname(p) if os.path.isfile(p) else p)
" 2>/dev/null)
            if [ -n "$target_path" ] && [ -d "$target_path" ]; then
                echo "📂 Chuyển tới: $target_path"
                cd "$target_path"
            else
                echo "⚠️ Không tìm thấy thư mục phù hợp cho: $*"
            fi
            ;;
        open)
            # Open the best matching file
            "$python_bin" "$repo_main" search "$*" -o
            ;;
        finder)
            # Reveal best matching file in Finder
            "$python_bin" "$repo_main" search "$*" -f
            ;;
        ask)
            # Ask AI about a file
            "$python_bin" "$repo_main" ask "$@"
            ;;
        dedup)
            # Check duplicate files
            "$python_bin" "$repo_main" dedup
            ;;
        index)
            # Reindex files
            "$python_bin" "$repo_main" index "$@"
            ;;
        *)
            # Default: Search with rich terminal table
            "$python_bin" "$repo_main" search "$cmd $*"
            ;;
    esac
}

# Optional: Ctrl + G widget for terminal fuzzy search
function _rat_fuzzy_widget() {
    local query
    read -r "query?🔍 Tìm kiếm với RAT: "
    if [ -n "$query" ]; then
        local found=$("%PYTHON_BIN%" -c "
from rat.crawler.db import Database
from rat.engine.hybrid_search import SearchEngine
from rat.config import config
engine = SearchEngine(Database(config.db_path))
res = engine.search('$query', limit=1, use_vector=False)
if res['results']:
    print(res['results'][0].file_path)
" 2>/dev/null)
        if [ -n "$found" ]; then
            LBUFFER+="$found"
        fi
    fi
    zle reset-prompt
}

if [[ -n "$ZSH_VERSION" ]]; then
    zle -N _rat_fuzzy_widget
    bindkey '^G' _rat_fuzzy_widget
fi
# === End of rat Shell Integration ===
"""


def generate_shell_init_script() -> str:
    """Generate custom shell initialization script with absolute paths."""
    python_bin = sys.executable
    repo_main = str(Path(__file__).resolve().parent.parent.parent / "main.py")
    script = ZSH_SHELL_SCRIPT.replace("%PYTHON_BIN%", python_bin).replace("%REPO_MAIN%", repo_main)
    return script


def install_to_user_zshrc() -> bool:
    """Safely append rat shell integration to ~/.zshrc if not already present."""
    zshrc_path = Path.home() / ".zshrc"
    marker = "# === rat macOS Intelligent Shell Integration ==="

    try:
        content = ""
        if zshrc_path.exists():
            content = zshrc_path.read_text(encoding="utf-8")

        if marker in content:
            return True  # Already installed

        script = generate_shell_init_script()
        with open(zshrc_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n{script}\n")
        return True
    except Exception:
        return False
