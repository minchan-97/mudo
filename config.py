import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("MUDO_DB", str(ROOT / "data" / "mudo.sqlite3")))
PROFILES_PATH = Path(os.environ.get("MUDO_PROFILES", str(Path(__file__).with_name("profiles.json"))))


def profiles():
    members = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    if not members or len({p["id"] for p in members}) != len(members):
        raise ValueError("멤버 id가 비었거나 중복되었습니다")
    return members

