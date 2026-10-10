import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import DB_PATH


def utcnow():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(path=None):
    path = path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
 id INTEGER PRIMARY KEY, day TEXT UNIQUE NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
 plan TEXT NOT NULL, turn INTEGER NOT NULL DEFAULT 0, world TEXT NOT NULL DEFAULT '{}',
 recap TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS suggestions (
 id INTEGER PRIMARY KEY, day TEXT NOT NULL, member TEXT NOT NULL,
 query TEXT NOT NULL, topic TEXT NOT NULL, title TEXT NOT NULL,
 url TEXT NOT NULL, snippet TEXT NOT NULL, source_score REAL NOT NULL,
 nm_score REAL, nm_mode TEXT NOT NULL, rank_score REAL NOT NULL,
 UNIQUE(day, member, url)
);
CREATE TABLE IF NOT EXISTS turns (
 id INTEGER PRIMARY KEY, episode_id INTEGER NOT NULL REFERENCES episodes(id),
 number INTEGER NOT NULL, kind TEXT NOT NULL, speaker TEXT NOT NULL,
 line TEXT NOT NULL, action TEXT NOT NULL DEFAULT '', target TEXT NOT NULL DEFAULT '',
 delta REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
 UNIQUE(episode_id,number,kind)
);
CREATE TABLE IF NOT EXISTS member_state (
 episode_id INTEGER NOT NULL REFERENCES episodes(id), member TEXT NOT NULL,
 state TEXT NOT NULL, PRIMARY KEY(episode_id,member)
);
CREATE TABLE IF NOT EXISTS relationships (
 member TEXT NOT NULL, other TEXT NOT NULL, baseline REAL NOT NULL DEFAULT 0,
 current REAL NOT NULL DEFAULT 0, PRIMARY KEY(member,other)
);
CREATE TABLE IF NOT EXISTS reviews (
 episode_id INTEGER PRIMARY KEY REFERENCES episodes(id), review TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS learned_notes (
 id INTEGER PRIMARY KEY, agent TEXT NOT NULL, episode_id INTEGER NOT NULL,
 score REAL NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS theme_scores (
 query TEXT PRIMARY KEY, attempts INTEGER NOT NULL, total REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS nm_examples (
 episode_id INTEGER PRIMARY KEY REFERENCES episodes(id), text TEXT NOT NULL
);
"""


def initialize(db):
    db.executescript(SCHEMA)


def obj(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def val(value):
    return json.loads(value)
