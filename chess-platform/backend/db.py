import json
import os
import sqlite3
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "chess.db")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "uploads"), exist_ok=True)

_lock = threading.RLock()
_conn = None


def get_conn():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


def q(sql, args=()):
    with _lock:
        cur = get_conn().execute(sql, args)
        return cur.fetchall()


def q1(sql, args=()):
    rows = q(sql, args)
    return rows[0] if rows else None


def execute(sql, args=()):
    with _lock:
        conn = get_conn()
        cur = conn.execute(sql, args)
        conn.commit()
        return cur


def executemany(sql, seq):
    with _lock:
        conn = get_conn()
        conn.executemany(sql, seq)
        conn.commit()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    pass_hash TEXT NOT NULL,
    qq TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    avatar TEXT DEFAULT '',
    coins INTEGER DEFAULT 0,
    diamonds INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    exp INTEGER DEFAULT 0,
    region TEXT DEFAULT '',
    bio TEXT DEFAULT '',
    likes_received INTEGER DEFAULT 0,
    role TEXT DEFAULT 'player',
    banned INTEGER DEFAULT 0,
    muted_until INTEGER DEFAULT 0,
    is_virtual INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT 0,
    last_login INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at INTEGER DEFAULT 0,
    expires_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS settings (
    user_id INTEGER PRIMARY KEY,
    music_vol INTEGER DEFAULT 60,
    sfx_vol INTEGER DEFAULT 80,
    muted INTEGER DEFAULT 0,
    background TEXT DEFAULT 'default',
    show_id INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    currency TEXT NOT NULL,
    amount INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    reason TEXT DEFAULT '',
    created_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS game_ranks (
    user_id INTEGER NOT NULL,
    game TEXT NOT NULL,
    points INTEGER DEFAULT 0,
    division INTEGER DEFAULT 1,
    stars INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    updated_at INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, game)
);
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game TEXT NOT NULL,
    mode TEXT NOT NULL,
    p1 INTEGER NOT NULL,
    p2 INTEGER NOT NULL,
    p3 INTEGER DEFAULT 0,
    p4 INTEGER DEFAULT 0,
    winner INTEGER DEFAULT 0,
    result TEXT DEFAULT '',
    created_at INTEGER DEFAULT 0,
    finished_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS rooms (
    code TEXT PRIMARY KEY,
    game TEXT NOT NULL,
    host_id INTEGER NOT NULL,
    max_players INTEGER DEFAULT 2,
    password TEXT DEFAULT '',
    status TEXT DEFAULT 'waiting',
    created_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS forum_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    content TEXT DEFAULT '',
    media TEXT DEFAULT '[]',
    likes INTEGER DEFAULT 0,
    tips_coins INTEGER DEFAULT 0,
    tips_diamonds INTEGER DEFAULT 0,
    pinned INTEGER DEFAULT 0,
    deleted INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS forum_likes (
    post_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at INTEGER DEFAULT 0,
    PRIMARY KEY (post_id, user_id)
);
CREATE TABLE IF NOT EXISTS forum_favorites (
    post_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at INTEGER DEFAULT 0,
    PRIMARY KEY (post_id, user_id)
);
CREATE TABLE IF NOT EXISTS forum_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    parent_id INTEGER DEFAULT 0,
    reply_to_user INTEGER DEFAULT 0,
    content TEXT DEFAULT '',
    deleted INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS forum_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    reporter_id INTEGER NOT NULL,
    reason TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    handled_by INTEGER DEFAULT 0,
    action TEXT DEFAULT '',
    created_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS friends (
    user_id INTEGER NOT NULL,
    friend_id INTEGER NOT NULL,
    created_at INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, friend_id)
);
CREATE TABLE IF NOT EXISTS friend_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id INTEGER NOT NULL,
    to_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS direct_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id INTEGER NOT NULL,
    to_id INTEGER NOT NULL,
    content TEXT DEFAULT '',
    mtype TEXT DEFAULT 'text',
    created_at INTEGER DEFAULT 0,
    read INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    ntype TEXT DEFAULT 'system',
    content TEXT DEFAULT '',
    ref TEXT DEFAULT '',
    created_at INTEGER DEFAULT 0,
    read INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS mails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    to_user INTEGER DEFAULT 0,
    title TEXT DEFAULT '',
    content TEXT DEFAULT '',
    coins INTEGER DEFAULT 0,
    diamonds INTEGER DEFAULT 0,
    item TEXT DEFAULT '',
    created_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS mail_reads (
    mail_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    claimed INTEGER DEFAULT 0,
    PRIMARY KEY (mail_id, user_id)
);
CREATE TABLE IF NOT EXISTS redeem_codes (
    code TEXT PRIMARY KEY,
    coins INTEGER DEFAULT 0,
    diamonds INTEGER DEFAULT 0,
    max_uses INTEGER DEFAULT 1,
    per_user_limit INTEGER DEFAULT 1,
    used INTEGER DEFAULT 0,
    created_by INTEGER DEFAULT 0,
    created_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS redeem_uses (
    code TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    used_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    package_id TEXT NOT NULL,
    rmb_cents INTEGER NOT NULL,
    diamonds INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    provider TEXT DEFAULT 'mock',
    provider_txn TEXT DEFAULT '',
    created_at INTEGER DEFAULT 0,
    paid_at INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS user_likes (
    user_id INTEGER NOT NULL,
    liker_id INTEGER NOT NULL,
    created_at INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, liker_id)
);
CREATE TABLE IF NOT EXISTS ai_training (
    game TEXT NOT NULL,
    pattern TEXT NOT NULL,
    plays INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    updated_at INTEGER DEFAULT 0,
    PRIMARY KEY (game, pattern)
);
CREATE TABLE IF NOT EXISTS user_frames (
    user_id INTEGER NOT NULL,
    frame_id TEXT NOT NULL,
    bought_at INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, frame_id)
);
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_bills_user ON bills(user_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_posts_time ON forum_posts(deleted, pinned DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_replies_post ON forum_replies(post_id, id);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_dm_pair ON direct_messages(from_id, to_id, id);
CREATE INDEX IF NOT EXISTS idx_matches_user ON matches(p1, p2, id DESC);
"""


def now():
    return int(time.time())


REGIONS_FALLBACK = [
    "北京市", "上海市", "天津市", "重庆市", "河北省", "山西省", "辽宁省", "吉林省", "黑龙江省",
    "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省", "河南省", "湖北省", "湖南省",
    "广东省", "海南省", "四川省", "贵州省", "云南省", "陕西省", "甘肃省", "青海省",
    "内蒙古自治区", "广西壮族自治区", "宁夏回族自治区", "新疆维吾尔自治区",
]


def patch_virtual_regions():
    """为地区为空的所有虚拟玩家随机分配地区"""
    rows = q("SELECT id FROM users WHERE is_virtual=1 AND (region IS NULL OR region='' OR region='未设置')")
    if not rows:
        return 0
    import random
    for r in rows:
        execute("UPDATE users SET region=? WHERE id=?", (random.choice(REGIONS_FALLBACK), r["id"]))
    return len(rows)


def init_db():
    with _lock:
        conn = get_conn()
        conn.executescript(SCHEMA)
        try:
            conn.execute("ALTER TABLE users ADD COLUMN avatar_frame TEXT DEFAULT ''")
        except Exception:
            pass
        for col in ("p3", "p4"):
            try:
                conn.execute(f"ALTER TABLE matches ADD COLUMN {col} INTEGER DEFAULT 0")
            except Exception:
                pass
        conn.commit()
    from security import hash_password

    author = q1("SELECT id FROM users WHERE name=?", ("jiaminglong",))
    if not author:
        execute(
            "INSERT INTO users (name, pass_hash, role, coins, diamonds, level, created_at) VALUES (?,?,?,?,?,?,?)",
            ("jiaminglong", hash_password("20120404q"), "author", 100000, 10000, 99, now()),
        )
    set_config_if_absent("coin_event_multiplier", "1")
    set_config_if_absent("ai_enabled", "1")
    set_config_if_absent("ai_model", "deepseek-v4-flash")
    set_config_if_absent("ai_base_url", "https://token.sensenova.cn/v1")
    set_config_if_absent("ai_api_key", "sk-yZUZx5n4PLq5EZmXsSlzZe7NIrIAN8fI")
    patch_virtual_regions()


def get_config(key, default=""):
    row = q1("SELECT value FROM config WHERE key=?", (key,))
    return row["value"] if row else default


def set_config(key, value):
    execute(
        "INSERT INTO config (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )


def set_config_if_absent(key, value):
    execute("INSERT OR IGNORE INTO config (key, value) VALUES (?,?)", (key, str(value)))


def row_to_dict(row):
    return dict(row) if row is not None else None


def rows_to_list(rows):
    return [dict(r) for r in rows]
