import asyncio
import base64
import hashlib
import json
import os
import random
import re
import secrets
import time
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import ai
import db
import games
from security import create_session, drop_session, hash_password, session_user, verify_password

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="棋魂阁 - 联机棋类平台")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

REGIONS = [
    "北京市", "上海市", "天津市", "重庆市", "河北省", "山西省", "辽宁省", "吉林省", "黑龙江省",
    "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省", "河南省", "湖北省", "湖南省",
    "广东省", "海南省", "四川省", "贵州省", "云南省", "陕西省", "甘肃省", "青海省", "台湾省",
    "内蒙古自治区", "广西壮族自治区", "西藏自治区", "宁夏回族自治区", "新疆维吾尔自治区",
    "香港特别行政区", "澳门特别行政区",
]

SHOP_PACKAGES = [
    {"id": "p6", "rmb": 6, "diamonds": 600},
    {"id": "p30", "rmb": 30, "diamonds": 3000},
    {"id": "p68", "rmb": 68, "diamonds": 6800},
    {"id": "p128", "rmb": 128, "diamonds": 12800},
    {"id": "p328", "rmb": 328, "diamonds": 32800},
    {"id": "p648", "rmb": 648, "diamonds": 64800},
]

BOT_NAMES = [
    "棋魂小智", "青衫客", "落子无声", "半盏清茶", "楚河汉界", "黑白之间", "长夜未央", "闲敲棋子",
    "一苇渡江", "风起洛阳", "月下独酌", "南山棋叟", "北冥有鱼", "星落棋盘", "云间一局", "松风入局",
    "子夜听雨", "剑指中原", "踏雪寻梅", "临江仙客", "醉卧沙场", "清风徐来", "沧海一粟", "纵横十九道",
]

# 头像框目录：type = frame(边框) / dyn(动态头像)；price_currency = coins|diamonds
# css 为前端定义的边框 class 名（frame-xxx）；dyn 类为动态头像 GIF 预设 key
AVATAR_FRAMES = [
    {"id": "f_gold", "type": "frame", "name": "鎏金边框", "desc": "简约金色圆框", "price": 500, "currency": "coins", "css": "frame-gold"},
    {"id": "f_silver", "type": "frame", "name": "白银边框", "desc": "低调银灰细框", "price": 300, "currency": "coins", "css": "frame-silver"},
    {"id": "f_bronze", "type": "frame", "name": "古铜边框", "desc": "复古古铜色", "price": 200, "currency": "coins", "css": "frame-bronze"},
    {"id": "f_rainbow", "type": "frame", "name": "彩虹光环", "desc": "七彩流光圆环", "price": 2000, "currency": "coins", "css": "frame-rainbow"},
    {"id": "f_flame", "type": "frame", "name": "烈焰边框", "desc": "燃烧火焰特效", "price": 300, "currency": "diamonds", "css": "frame-flame"},
    {"id": "f_thunder", "type": "frame", "name": "雷光边框", "desc": "雷霆电光环绕", "price": 400, "currency": "diamonds", "css": "frame-thunder"},
    {"id": "f_crown", "type": "frame", "name": "王者皇冠", "desc": "尊贵皇冠王冠", "price": 800, "currency": "diamonds", "css": "frame-crown"},
    {"id": "f_glow", "type": "frame", "name": "星辉闪耀", "desc": "钻石般璀璨光晕", "price": 1200, "currency": "diamonds", "css": "frame-glow"},
]

# 动态头像 GIF 预设（type=dyn，通过 css 使用 CSS 动画模拟动态效果）
DYNAMIC_AVATARS = [
    {"id": "d_fire", "type": "dyn", "name": "火焰之心", "desc": "跃动火焰动态头像", "price": 300, "currency": "diamonds", "css": "dyn-fire"},
    {"id": "d_star", "type": "dyn", "name": "星辰流动", "desc": "星尘流光动态", "price": 300, "currency": "diamonds", "css": "dyn-star"},
    {"id": "d_bolt", "type": "dyn", "name": "雷霆脉冲", "desc": "电流脉冲动态", "price": 400, "currency": "diamonds", "css": "dyn-bolt"},
    {"id": "d_bubble", "type": "dyn", "name": "梦幻气泡", "desc": "漂浮气泡动态", "price": 250, "currency": "diamonds", "css": "dyn-bubble"},
]


def now():
    return int(time.time())


# ---------------- helpers ----------------

def gen_avatar(name: str, idx: int) -> str:
    colors = ["#5b8cff", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#06b6d4", "#ef4444", "#6366f1"]
    a, b = colors[idx % len(colors)], colors[(idx * 3 + 2) % len(colors)]
    ch = (name or "棋")[0]
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient></defs>'
        f'<rect width="96" height="96" rx="48" fill="url(#g)"/>'
        f'<text x="48" y="62" font-size="42" font-family="sans-serif" fill="#fff" text-anchor="middle">{ch}</text></svg>'
    )
    fname = f"bot_{idx}.svg"
    path = os.path.join(UPLOAD_DIR, fname)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
    return f"/api/uploads/{fname}"


def public_user(row):
    if not row:
        return None
    return {
        "id": row["id"], "name": row["name"], "avatar": row["avatar"] or "",
        "avatar_frame": row["avatar_frame"] or "",
        "level": row["level"], "region": row["region"] or "未设置",
        "bio": row["bio"] or "", "likes": row["likes_received"],
        "is_virtual": bool(row["is_virtual"]), "role": row["role"],
        "banned": bool(row["banned"]),
    }


def me_payload(row):
    data = public_user(row)
    data.update({
        "coins": row["coins"], "diamonds": row["diamonds"], "exp": row["exp"],
        "qq": row["qq"] or "", "phone": row["phone"] or "",
        "created_at": row["created_at"], "muted_until": row["muted_until"],
        "ranks": user_ranks(row["id"]),
        "settings": user_settings(row["id"]),
    })
    return data


def user_settings(uid):
    row = db.q1("SELECT * FROM settings WHERE user_id=?", (uid,))
    if not row:
        db.execute("INSERT OR IGNORE INTO settings (user_id) VALUES (?)", (uid,))
        row = db.q1("SELECT * FROM settings WHERE user_id=?", (uid,))
    return {
        "music_vol": row["music_vol"], "sfx_vol": row["sfx_vol"],
        "muted": bool(row["muted"]), "background": row["background"], "show_id": bool(row["show_id"]),
    }


def ensure_rank(uid, game):
    row = db.q1("SELECT * FROM game_ranks WHERE user_id=? AND game=?", (uid, game))
    if row:
        return row
    db.execute(
        "INSERT OR IGNORE INTO game_ranks (user_id, game, updated_at) VALUES (?,?,?)",
        (uid, game, now()),
    )
    return db.q1("SELECT * FROM game_ranks WHERE user_id=? AND game=?", (uid, game))


def rank_dict(row):
    return {
        "game": row["game"], "points": row["points"], "division": row["division"],
        "stars": row["stars"], "wins": row["wins"], "losses": row["losses"],
        "label": games.rank_label(row["division"], row["stars"]),
        "total_stars": (row["division"] - 1) * 3 + row["stars"],
    }


def user_ranks(uid):
    rows = db.q("SELECT * FROM game_ranks WHERE user_id=? ORDER BY game", (uid,))
    out = {}
    for r in rows:
        if games.GAMES.get(r["game"], {}).get("available"):
            out[r["game"]] = rank_dict(r)
    return out


def notify(uid, ntype, content, ref=""):
    db.execute(
        "INSERT INTO notifications (user_id, ntype, content, ref, created_at) VALUES (?,?,?,?,?)",
        (uid, ntype, content, str(ref), now()),
    )


def change_balance(uid, currency, delta, reason=""):
    if currency not in ("coins", "diamonds"):
        raise HTTPException(400, "货币类型错误")
    row = db.q1("SELECT coins, diamonds FROM users WHERE id=?", (uid,))
    if not row:
        raise HTTPException(404, "用户不存在")
    cur = row[currency]
    new = max(0, cur + int(delta))
    db.execute(f"UPDATE users SET {currency}=? WHERE id=?", (new, uid))
    db.execute(
        "INSERT INTO bills (user_id, currency, amount, balance_after, reason, created_at) VALUES (?,?,?,?,?,?)",
        (uid, currency, int(delta), new, reason, now()),
    )
    return new


def add_exp(uid, amount):
    row = db.q1("SELECT exp, level FROM users WHERE id=?", (uid,))
    if not row:
        return
    exp = row["exp"] + amount
    level = 1 + exp // 100
    db.execute("UPDATE users SET exp=?, level=? WHERE id=?", (exp, level, uid))


def client_token(authorization: Optional[str]):
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return authorization.strip()


def current_user(authorization: Optional[str] = Header(None)):
    row = session_user(client_token(authorization))
    if not row:
        raise HTTPException(401, "请先登录")
    if row["banned"]:
        raise HTTPException(403, "账号已被封禁")
    return row


def admin_user(user=Depends(current_user)):
    if user["role"] not in ("admin", "author"):
        raise HTTPException(403, "无权限")
    return user


def author_user(user=Depends(current_user)):
    if user["role"] != "author":
        raise HTTPException(403, "仅作者可用")
    return user


def optional_user(authorization: Optional[str] = Header(None)):
    row = session_user(client_token(authorization))
    if not row or row["banned"]:
        return None
    return row


def is_staff(row):
    return bool(row) and row["role"] in ("admin", "author")


def strip_virtual(d):
    if isinstance(d, dict):
        d.pop("is_virtual", None)
    return d


def muted(user):
    return user["muted_until"] and user["muted_until"] > now()


# ---------------- seed ----------------

def seed_virtual_players():
    existing = db.q1("SELECT COUNT(*) AS c FROM users WHERE is_virtual=1")
    if existing and existing["c"] >= len(BOT_NAMES):
        return
    for i, name in enumerate(BOT_NAMES):
        if db.q1("SELECT id FROM users WHERE name=?", (name,)):
            continue
        cur = db.execute(
            "INSERT INTO users (name, pass_hash, avatar, coins, diamonds, level, region, is_virtual, created_at) "
            "VALUES (?,?,?,?,?,?,?,1,?)",
            (name, hash_password(secrets.token_hex(8)), gen_avatar(name, i),
             random.randint(2000, 30000), random.randint(50, 2000),
             random.randint(5, 60), random.choice(REGIONS), now()),
        )
        uid = cur.lastrowid
        for g in ("gomoku", "tictactoe", "xiangqi", "doubeast"):
            div = random.randint(1, 10)
            st = random.randint(0, 2)
            db.execute(
                "INSERT OR IGNORE INTO game_ranks (user_id, game, points, division, stars, wins, losses, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (uid, g, random.randint(0, 99), div, st,
                 random.randint(10, 400), random.randint(10, 300), now()),
            )


def init():
    db.init_db()
    seed_virtual_players()


init()


# ---------------- auth ----------------

@app.post("/api/register")
def register(body: dict):
    name = (body.get("name") or "").strip()
    password = body.get("password") or ""
    password2 = body.get("password2") or password
    qq = (body.get("qq") or "").strip()
    phone = (body.get("phone") or "").strip()
    if not (2 <= len(name) <= 16):
        raise HTTPException(400, "昵称长度需为 2-16 个字符")
    if not re.match(r"^[\w\u4e00-\u9fa5\-]+$", name):
        raise HTTPException(400, "昵称只能包含中文、字母、数字、下划线")
    if len(password) < 6:
        raise HTTPException(400, "密码至少 6 位")
    if password != password2:
        raise HTTPException(400, "两次输入的密码不一致")
    if db.q1("SELECT id FROM users WHERE name=?", (name,)):
        raise HTTPException(400, "该昵称已被使用")
    cur = db.execute(
        "INSERT INTO users (name, pass_hash, qq, phone, coins, diamonds, level, created_at, last_login) "
        "VALUES (?,?,?,?,1000,100,1,?,?)",
        (name, hash_password(password), qq, phone, now(), now()),
    )
    uid = cur.lastrowid
    db.execute("INSERT OR IGNORE INTO settings (user_id) VALUES (?)", (uid,))
    for g in games.GAMES:
        if games.GAMES[g]["available"]:
            db.execute("INSERT OR IGNORE INTO game_ranks (user_id, game, updated_at) VALUES (?,?,?)", (uid, g, now()))
    db.execute(
        "INSERT INTO bills (user_id, currency, amount, balance_after, reason, created_at) VALUES (?,?,?,?,?,?)",
        (uid, "coins", 1000, 1000, "新玩家注册奖励", now()),
    )
    token = create_session(uid)
    row = db.q1("SELECT * FROM users WHERE id=?", (uid,))
    notify(uid, "system", "欢迎加入棋魂阁，已赠送 1000 金币！")
    return {"token": token, "user": me_payload(row)}


@app.post("/api/login")
def login(body: dict):
    name = (body.get("name") or "").strip()
    password = body.get("password") or ""
    row = db.q1("SELECT * FROM users WHERE name=?", (name,))
    if not row and re.match(r"^[0-9]{5,}$", name):
        row = db.q1(
            "SELECT * FROM users WHERE (qq=? OR phone=?) AND is_virtual=0 ORDER BY id LIMIT 1",
            (name, name),
        )
    if not row or not verify_password(password, row["pass_hash"]):
        raise HTTPException(400, "昵称或密码错误")
    if row["banned"]:
        raise HTTPException(403, "账号已被封禁，请联系管理员")
    db.execute("UPDATE users SET last_login=? WHERE id=?", (now(), row["id"]))
    token = create_session(row["id"])
    row = db.q1("SELECT * FROM users WHERE id=?", (row["id"],))
    return {"token": token, "user": me_payload(row)}


@app.post("/api/logout")
def logout(authorization: Optional[str] = Header(None)):
    tok = client_token(authorization)
    if tok:
        drop_session(tok)
    return {"ok": True}


@app.post("/api/recover")
def recover(body: dict):
    name = (body.get("name") or "").strip()
    contact = (body.get("contact") or "").strip()
    new_password = body.get("new_password") or ""
    row = db.q1("SELECT * FROM users WHERE name=? AND is_virtual=0", (name,))
    if not row:
        raise HTTPException(400, "账号不存在")
    if not contact or contact not in (row["qq"], row["phone"]):
        raise HTTPException(400, "QQ号或手机号与该账号不匹配")
    if row["qq"] in ("", "无") and row["phone"] in ("", "无"):
        raise HTTPException(400, "该账号未绑定找回方式，请联系作者")
    if len(new_password) < 6:
        raise HTTPException(400, "新密码至少 6 位")
    db.execute("UPDATE users SET pass_hash=? WHERE id=?", (hash_password(new_password), row["id"]))
    db.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
    return {"ok": True, "message": "密码已重置，请重新登录"}


@app.post("/api/recover/find")
def recover_find(body: dict):
    contact = (body.get("contact") or "").strip()
    if not contact:
        raise HTTPException(400, "请输入 QQ 号或手机号")
    rows = db.q("SELECT name FROM users WHERE (qq=? OR phone=?) AND is_virtual=0", (contact, contact))
    if not rows:
        raise HTTPException(404, "未找到绑定该联系方式的账号")
    names = [r["name"] for r in rows]
    masked = [n[0] + "*" * max(1, len(n) - 2) + n[-1] for n in names]
    return {"accounts": masked, "count": len(names)}


# ---------------- profile ----------------

@app.get("/api/me")
def get_me(user=Depends(current_user)):
    return me_payload(user)


@app.post("/api/me/avatar")
def set_avatar(body: dict, user=Depends(current_user)):
    avatar = (body.get("avatar") or "").strip()
    if not avatar:
        raise HTTPException(400, "头像不能为空")
    db.execute("UPDATE users SET avatar=? WHERE id=?", (avatar, user["id"]))
    return {"ok": True, "avatar": avatar}


@app.post("/api/me/profile")
def update_profile(body: dict, user=Depends(current_user)):
    fields, args = [], []
    if "region" in body:
        region = (body.get("region") or "").strip()
        if region and len(region) > 20:
            raise HTTPException(400, "地区名称过长")
        fields.append("region=?")
        args.append(region)
    if "bio" in body:
        fields.append("bio=?")
        args.append((body.get("bio") or "")[:60])
    if "qq" in body:
        fields.append("qq=?")
        args.append((body.get("qq") or "").strip()[:20])
    if "phone" in body:
        phone = (body.get("phone") or "").strip()
        if phone and not re.match(r"^[0-9+\-]{5,20}$", phone):
            raise HTTPException(400, "手机号格式不正确")
        fields.append("phone=?")
        args.append(phone)
    if fields:
        args.append(user["id"])
        db.execute(f"UPDATE users SET {', '.join(fields)} WHERE id=?", tuple(args))
    row = db.q1("SELECT * FROM users WHERE id=?", (user["id"],))
    return me_payload(row)


@app.get("/api/me/settings")
def get_settings(user=Depends(current_user)):
    return user_settings(user["id"])


@app.post("/api/me/settings")
def save_settings(body: dict, user=Depends(current_user)):
    row = user_settings(user["id"])
    music = int(body.get("music_vol", row["music_vol"]))
    sfx = int(body.get("sfx_vol", row["sfx_vol"]))
    db.execute(
        "UPDATE settings SET music_vol=?, sfx_vol=?, muted=?, background=?, show_id=? WHERE user_id=?",
        (max(0, min(100, music)), max(0, min(100, sfx)),
         1 if body.get("muted", row["muted"]) else 0,
         (body.get("background", row["background"]) or "default")[:40],
         1 if body.get("show_id", row["show_id"]) else 0, user["id"]),
    )
    return user_settings(user["id"])


@app.get("/api/me/bills")
def bills(limit: int = 100, user=Depends(current_user)):
    rows = db.q("SELECT * FROM bills WHERE user_id=? ORDER BY id DESC LIMIT ?", (user["id"], min(limit, 300)))
    return db.rows_to_list(rows)


@app.get("/api/me/history")
def history(limit: int = 50, user=Depends(current_user)):
    rows = db.q(
        "SELECT m.*, u1.name AS p1_name, u2.name AS p2_name, u1.avatar AS p1_avatar, u2.avatar AS p2_avatar, "
        "u1.avatar_frame AS p1_frame, u2.avatar_frame AS p2_frame "
        "FROM matches m LEFT JOIN users u1 ON u1.id=m.p1 LEFT JOIN users u2 ON u2.id=m.p2 "
        "WHERE (m.p1=? OR m.p2=?) AND m.finished_at>0 ORDER BY m.id DESC LIMIT ?",
        (user["id"], user["id"], min(limit, 200)),
    )
    out = []
    for r in rows:
        d = dict(r)
        d["won"] = (d["winner"] == user["id"])
        d["draw"] = (d["result"] == "draw")
        out.append(d)
    return out


@app.get("/api/me/favorites")
def my_favorites(user=Depends(current_user)):
    rows = db.q(
        "SELECT p.*, u.name, u.avatar, u.avatar_frame, u.is_virtual FROM forum_favorites f "
        "JOIN forum_posts p ON p.id=f.post_id JOIN users u ON u.id=p.user_id "
        "WHERE f.user_id=? AND p.deleted=0 ORDER BY f.created_at DESC",
        (user["id"],),
    )
    return format_posts(rows, user["id"], is_staff(user))


@app.get("/api/me/likes")
def my_likes(user=Depends(current_user)):
    rows = db.q(
        "SELECT p.*, u.name, u.avatar, u.avatar_frame, u.is_virtual FROM forum_likes l "
        "JOIN forum_posts p ON p.id=l.post_id JOIN users u ON u.id=p.user_id "
        "WHERE l.user_id=? AND p.deleted=0 ORDER BY l.created_at DESC",
        (user["id"],),
    )
    return format_posts(rows, user["id"], is_staff(user))


# ---------------- public ----------------

@app.get("/api/games")
def list_games(user=Depends(current_user)):
    out = games.game_meta()
    ranks = user_ranks(user["id"])
    for g in out:
        g["my_rank"] = ranks.get(g["key"])
    return out


VIRTUAL_ONLINE = {"t": 0, "n": 0}


def stats_data():
    if time.time() - VIRTUAL_ONLINE["t"] > 60:
        VIRTUAL_ONLINE["n"] = random.randint(18, 46)
        VIRTUAL_ONLINE["t"] = time.time()
    real_online = sum(1 for uid in HUB.real_online if uid)
    reg = db.q1("SELECT SUM(is_virtual=0) AS real_c, SUM(is_virtual=1) AS virt_c FROM users")
    return {
        "online_real": real_online,
        "online_virtual": VIRTUAL_ONLINE["n"] + real_online,
        "online_total": real_online + VIRTUAL_ONLINE["n"],
        "registered_real": reg["real_c"] or 0,
        "registered_virtual": reg["virt_c"] or 0,
        "registered_total": (reg["real_c"] or 0) + (reg["virt_c"] or 0),
    }


def stats_payload(row):
    data = stats_data()
    if is_staff(row):
        return data
    return {"online_total": data["online_total"], "registered_total": data["registered_total"]}


@app.get("/api/stats")
def stats(user=Depends(optional_user)):
    return stats_payload(user)


@app.get("/api/rankings")
def rankings(type: str = "level", game: str = "", limit: int = 100, user=Depends(optional_user)):
    limit = min(max(1, limit), 100)
    staff = is_staff(user)

    def clean(rows):
        rows = [dict(r) for r in rows]
        return rows if staff else [strip_virtual(r) for r in rows]

    if type == "coins":
        rows = db.q(
            "SELECT id, name, avatar, avatar_frame, level, region, coins AS score, is_virtual FROM users "
            "WHERE is_virtual=0 OR is_virtual=1 ORDER BY coins DESC LIMIT ?", (limit,))
        return clean(rows)
    if type == "game" and game in games.GAMES:
        rows = db.q(
            "SELECT u.id, u.name, u.avatar, u.avatar_frame, u.level, u.region, u.is_virtual, r.points, r.division, r.stars, r.wins, r.losses "
            "FROM game_ranks r JOIN users u ON u.id=r.user_id WHERE r.game=? "
            "ORDER BY r.division DESC, r.stars DESC, r.points DESC LIMIT ?",
            (game, limit),
        )
        out = clean(rows)
        for d in out:
            d["label"] = games.rank_label(d["division"], d["stars"])
            d["accumulated"] = (d["division"] - 1) * 300 + d["stars"] * 100 + d["points"]
        return out
    rows = db.q(
        "SELECT id, name, avatar, avatar_frame, level, region, exp AS score, is_virtual FROM users ORDER BY level DESC, exp DESC LIMIT ?",
        (limit,))
    return clean(rows)


@app.get("/api/users/search")
def search_users(q: str = "", user=Depends(current_user)):
    q = (q or "").strip()
    if not q:
        return []
    rows = db.q(
        "SELECT * FROM users WHERE (name LIKE ? OR CAST(id AS TEXT)=? OR qq=? OR phone=?) AND is_virtual=0 LIMIT 20",
        (f"%{q}%", q, q, q),
    )
    return [public_user(r) for r in rows]


@app.get("/api/users/{uid}")
def get_user(uid: int, user=Depends(current_user)):
    row = db.q1("SELECT * FROM users WHERE id=?", (uid,))
    if not row:
        raise HTTPException(404, "用户不存在")
    data = public_user(row)
    if not is_staff(user):
        data.pop("is_virtual", None)
    data["ranks"] = user_ranks(uid)
    data["liked"] = bool(db.q1("SELECT 1 FROM user_likes WHERE user_id=? AND liker_id=?", (uid, user["id"])))
    return data


@app.post("/api/users/{uid}/like")
def like_user(uid: int, user=Depends(current_user)):
    if uid == user["id"]:
        raise HTTPException(400, "不能给自己点赞")
    if db.q1("SELECT 1 FROM user_likes WHERE user_id=? AND liker_id=?", (uid, user["id"])):
        db.execute("DELETE FROM user_likes WHERE user_id=? AND liker_id=?", (uid, user["id"]))
        db.execute("UPDATE users SET likes_received=MAX(0, likes_received-1) WHERE id=?", (uid,))
        return {"liked": False}
    db.execute("INSERT INTO user_likes (user_id, liker_id, created_at) VALUES (?,?,?)", (uid, user["id"], now()))
    db.execute("UPDATE users SET likes_received=likes_received+1 WHERE id=?", (uid,))
    notify(uid, "like", f"{user['name']} 点赞了你的主页")
    return {"liked": True}


# ---------------- uploads ----------------

@app.post("/api/upload")
def upload(body: dict, user=Depends(current_user)):
    data_url = body.get("data_url") or ""
    m = re.match(
        r"^data:(?P<mime>image/(?:png|jpeg|jpg|gif|webp)|video/(?:mp4|webm|quicktime|x-m4v));base64,(?P<b64>.+)$",
        data_url, re.S)
    if not m:
        raise HTTPException(400, "仅支持图片或视频文件")
    mime, b64 = m.group("mime"), m.group("b64")
    try:
        raw = base64.b64decode(b64, validate=True)
    except Exception:
        raise HTTPException(400, "文件数据损坏")
    is_video = mime.startswith("video")
    max_mb = 60 if is_video else 8
    if len(raw) > max_mb * 1024 * 1024:
        raise HTTPException(400, f"{'视频' if is_video else '图片'}不能超过 {max_mb}MB")
    sub = mime.split("/", 1)[1]
    ext = {"jpeg": "jpg", "jpg": "jpg", "png": "png", "gif": "gif", "webp": "webp",
           "mp4": "mp4", "webm": "webm", "quicktime": "mov", "x-m4v": "m4v"}.get(sub, sub)
    fname = f"{user['id']}_{int(time.time()*1000)}_{secrets.token_hex(4)}.{ext}"
    with open(os.path.join(UPLOAD_DIR, fname), "wb") as f:
        f.write(raw)
    return {"url": f"/api/uploads/{fname}", "type": "video" if is_video else "image"}


app.mount("/api/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ---------------- realtime hub ----------------

class Hub:
    def __init__(self):
        self.conns = {}
        self.real_online = set()
        self.matches = {}
        self.queues = {}
        self.queue_tasks = {}
        self.rooms = {}

    async def send(self, uid, data):
        for ws in list(self.conns.get(uid, [])):
            try:
                await ws.send_text(json.dumps(data, ensure_ascii=False))
            except Exception:
                pass

    async def send_match(self, match, data):
        for side, uid in match["players"].items():
            await self.send(uid, data)

    async def broadcast_state(self, match):
        hist = match["history"][-6:]
        for side, uid in match["players"].items():
            st = match["state"]
            row = db.q1("SELECT role FROM users WHERE id=?", (uid,))
            reveal = bool(row and row["role"] in ("author", "admin"))
            if match["game"] == "junqi":
                st = games.junqi_mask(st, side, reveal_all=reveal)
            elif match["game"] == "doudizhu":
                st = games.doudizhu_mask(st, side, reveal_all=reveal)
            elif match["game"] == "horror":
                st = games.horror_mask(st, side, reveal_all=reveal)
            await self.send(uid, {
                "type": "state", "match_id": match["id"], "game": match["game"],
                "state": st, "turn": match["turn"], "history": hist,
            })

    async def broadcast_all(self, data):
        for uid in list(self.conns.keys()):
            await self.send(uid, data)


HUB = Hub()


def bot_pick(game_key, stars_min=1, stars_max=100):
    rows = db.q("SELECT * FROM users WHERE is_virtual=1 ORDER BY RANDOM() LIMIT 20")
    if not rows:
        return None
    return random.choice(rows)


def bot_stars_for(bot, game):
    r = ensure_rank(bot["id"], game)
    return max(5, min(100, 12 + (r["division"] - 1) * 7 + r["stars"] * 2 + random.randint(0, 8)))


def seat_count(game_key):
    return int(games.GAMES[game_key].get("max_players") or 2)


def next_side(match, side):
    st_turn = match["state"].get("turn") if isinstance(match.get("state"), dict) else None
    if st_turn:
        return int(st_turn)
    n = max(match["players"]) if match["players"] else 2
    nxt = int(side) % n + 1
    for _ in range(n):
        if nxt in match["players"]:
            return nxt
        nxt = nxt % n + 1
    return 1


def fill_bots(game_key, human_ids, stars):
    ids = list(human_ids)
    n = seat_count(game_key)
    ai_sides = {}
    used = set(ids)
    while len(ids) < n:
        rows = db.q("SELECT * FROM users WHERE is_virtual=1 ORDER BY RANDOM() LIMIT 40")
        bot = next((r for r in (rows or []) if r["id"] not in used), None)
        if not bot:
            break
        ids.append(bot["id"])
        used.add(bot["id"])
        ai_sides[len(ids)] = stars
    return ids, ai_sides


async def start_match(game_key, mode, player_ids, ai_stars=None, room_code=None, side_of_ai=None, ai_sides=None):
    if not isinstance(player_ids, (list, tuple)):
        raise TypeError("player_ids")
    g = games.GAMES[game_key]
    state = g["new"]()
    pids = list(player_ids)
    while len(pids) < 2:
        pids.append(0)
    cur = db.execute(
        "INSERT INTO matches (game, mode, p1, p2, p3, p4, created_at) VALUES (?,?,?,?,?,?,?)",
        (game_key, mode, pids[0], pids[1], pids[2] if len(pids) > 2 else 0, pids[3] if len(pids) > 3 else 0, now()),
    )
    mid = cur.lastrowid
    players = {i + 1: uid for i, uid in enumerate(player_ids)}
    sides = dict(ai_sides or {})
    if side_of_ai is not None and ai_stars is not None:
        sides[int(side_of_ai)] = ai_stars
    elif ai_stars is not None and not sides:
        for s, uid in players.items():
            row = db.q1("SELECT is_virtual FROM users WHERE id=?", (uid,))
            if row and row["is_virtual"]:
                sides[s] = ai_stars
    match = {
        "id": mid, "game": game_key, "mode": mode,
        "players": players,
        "state": state, "turn": int(state.get("turn") or 1), "history": [], "finished": False,
        "ai_sides": sides,
        "room_code": room_code,
    }
    HUB.matches[mid] = match
    seats = {}
    for s, uid in players.items():
        seats[str(s)] = public_user(db.q1("SELECT * FROM users WHERE id=?", (uid,)))
    for side, uid in match["players"].items():
        opp = next((u for s, u in match["players"].items() if s != side), 0)
        opp_row = db.q1("SELECT * FROM users WHERE id=?", (opp,)) if opp else None
        await HUB.send(uid, {
            "type": "matched", "match_id": mid, "game": game_key, "mode": mode,
            "side": side, "opponent": public_user(opp_row),
            "seats": seats,
            "your_name": (db.q1("SELECT name FROM users WHERE id=?", (uid,)) or {"name": ""})["name"],
            "ai_stars": match["ai_sides"].get(side) or (ai_stars if side != 1 else None),
            "ai_sides": match["ai_sides"],
        })
    await HUB.broadcast_state(match)
    if match["game"] != "pvz" and match["turn"] in match["ai_sides"]:
        asyncio.create_task(ai_turn_later(mid))
    return match


async def ai_turn_later(mid):
    match = HUB.matches.get(mid)
    if not match or match["finished"]:
        return
    side = match["turn"]
    if side not in match["ai_sides"]:
        return
    await asyncio.sleep(random.uniform(0.7, 1.6))
    match = HUB.matches.get(mid)
    if not match or match["finished"] or match["turn"] != side:
        return
    stars = match["ai_sides"][side]
    try:
        mv = await ai.ai_choose_move(match["game"], match["state"], side, stars)
    except Exception:
        mv = None
    if mv is None:
        if match["game"] == "pvz":
            return
        await finish_match(match, None)
        return
    try:
        await apply_move(match, side, mv)
    except Exception:
        pass


async def apply_move(match, side, move):
    if match["finished"]:
        return
    g = games.GAMES[match["game"]]
    ok, state, result = g["move"](match["state"], move, side)
    if not ok:
        await HUB.send(match["players"][side], {"type": "error", "msg": "非法着法"})
        return
    match["state"] = state
    match["history"].append({"side": side, "move": move, "t": now()})
    if result:
        await finish_match(match, result)
        return
    match["turn"] = next_side(match, side)
    await HUB.broadcast_state(match)
    if match["turn"] in match["ai_sides"]:
        asyncio.create_task(ai_turn_later(match["id"]))


def _empty_cell(game):
    if game in ("chess", "tiaoqi"):
        return "."
    if game in ("gomoku", "go", "tictactoe"):
        return 0
    return ""


def _cell_empty(game, p):
    if game in ("gomoku", "go", "tictactoe"):
        return not p
    return (not p) or p == "."


async def author_god_move(match, side, move):
    if match["finished"]:
        return
    game = match["game"]
    uid = match["players"][side]
    if game in ("feixing", "doudizhu", "pvz", "horror"):
        fn = {
            "feixing": games.feixing_move,
            "doudizhu": games.doudizhu_move,
            "pvz": games.pvz_move,
            "horror": games.horror_move,
        }[game]
        use_god = game in ("doudizhu", "pvz", "horror")
        if game == "feixing":
            try:
                raw = list(move) if not isinstance(move, (str, int, float)) else [move]
            except Exception:
                raw = []
            use_god = len(raw) >= 2 and str(raw[0]) not in ("roll", "pass")
        ok, state, result = fn(match["state"], move, side, god=use_god)
        if not ok:
            await HUB.send(uid, {"type": "error", "msg": "非法着法"})
            return
        match["state"] = state
        match["history"].append({"side": side, "move": move, "t": now()})
        if result:
            await finish_match(match, result)
            return
        match["turn"] = next_side(match, side)
        await HUB.broadcast_state(match)
        if match["turn"] in match["ai_sides"]:
            asyncio.create_task(ai_turn_later(match["id"]))
        return
    try:
        if game == "tictactoe" and not isinstance(move, (list, tuple)):
            mv = [int(move)]
        else:
            mv = [int(x) for x in move]
    except Exception:
        await HUB.send(uid, {"type": "error", "msg": "非法着法"})
        return
    board = match["state"]["board"]
    result = None
    if game == "tictactoe":
        if len(mv) == 1:
            idx = mv[0]
        elif len(mv) == 2:
            idx = mv[0] * 3 + mv[1]
        else:
            await HUB.send(uid, {"type": "error", "msg": "非法着法"})
            return
        if not (0 <= idx < 9):
            await HUB.send(uid, {"type": "error", "msg": "坐标越界"})
            return
        board[idx] = side
        match["state"]["last"] = idx
        match["state"]["moves"] = match["state"].get("moves", 0) + 1
        w = games._ttt_winner(board)
        if w:
            result = f"win:{w}"
        elif match["state"]["moves"] >= 9:
            result = "draw"
    elif game in ("gomoku", "go"):
        if len(mv) != 2:
            await HUB.send(uid, {"type": "error", "msg": "需要2个坐标"})
            return
        if game == "go" and mv == [-1, -1]:
            ok, state, result = games.go_move(match["state"], mv, side)
            if not ok:
                await HUB.send(uid, {"type": "error", "msg": "非法着法"})
                return
            match["state"] = state
        else:
            r, c = mv
            n = 15 if game == "gomoku" else 9
            if not (0 <= r < n and 0 <= c < n):
                await HUB.send(uid, {"type": "error", "msg": "坐标越界"})
                return
            board[r][c] = side
            match["state"]["last"] = [r, c]
            match["state"]["moves"] = match["state"].get("moves", 0) + 1
            if game == "go":
                match["state"]["passes"] = 0
                match["state"]["ko"] = None
            if game == "gomoku" and games._gomoku_win(board, r, c, side):
                result = f"win:{side}"
    else:
        if len(mv) != 4:
            await HUB.send(uid, {"type": "error", "msg": "需要4个坐标"})
            return
        fr, fc, tr, tc = mv
        rows = len(board)
        cols = len(board[0]) if rows else 0
        if not (0 <= fr < rows and 0 <= tr < rows and 0 <= fc < cols and 0 <= tc < cols):
            await HUB.send(uid, {"type": "error", "msg": "坐标越界"})
            return
        p = board[fr][fc]
        if _cell_empty(game, p):
            await HUB.send(uid, {"type": "error", "msg": "起点无棋子"})
            return
        captured = board[tr][tc]
        board[tr][tc] = p
        board[fr][fc] = _empty_cell(game)
        match["state"]["last"] = [fr, fc, tr, tc]
        match["state"]["moves"] = match["state"].get("moves", 0) + 1
        if game in ("chess", "xiangqi") and captured and str(captured).upper() == "K":
            result = f"win:{side}"
        elif game == "junqi" and captured and captured not in (".", "?", "") and games._jq_kind(captured) == "flag":
            result = f"win:{side}"
        elif game == "doubeast" and games.DB_DENS.get((tr, tc)) == 3 - side:
            result = f"win:{side}"
        elif game == "tiaoqi":
            opp = 3 - side
            if not any(games._ck_side(board[r][c]) == opp for r in range(8) for c in range(8)):
                result = f"win:{side}"
    match["history"].append({"side": side, "move": list(mv) if isinstance(mv, list) else mv, "t": now()})
    if result:
        await finish_match(match, result)
        return
    match["turn"] = next_side(match, side)
    await HUB.broadcast_state(match)
    if match["turn"] in match["ai_sides"]:
        asyncio.create_task(ai_turn_later(match["id"]))


async def finish_match(match, result):
    if match["finished"]:
        return
    match["finished"] = True
    winner_sides = set()
    if result and result.startswith("win:"):
        for part in result.split(":", 1)[1].split(","):
            try:
                winner_sides.add(int(part))
            except Exception:
                pass
    winner_side = next(iter(winner_sides), 0)
    winner_id = match["players"].get(winner_side, 0) if winner_side else 0
    winner_ids = [match["players"][s] for s in winner_sides if s in match["players"]]
    db.execute(
        "UPDATE matches SET winner=?, result=?, finished_at=? WHERE id=?",
        (winner_id or 0, result or "abort", now(), match["id"]),
    )
    summary = {"type": "game_over", "match_id": match["id"], "result": result or "abort",
               "winner": winner_id, "winners": winner_ids, "ranks": {}, "coins": {}}
    mult = int(db.get_config("coin_event_multiplier", "1") or 1)
    for side, uid in match["players"].items():
        won = side in winner_sides
        draw = result == "draw"
        if match["mode"] == "ranked":
            row = ensure_rank(uid, match["game"])
            pts, div, stars, delta = games.apply_ranked_result(
                row["points"], row["division"], row["stars"],
                won if not draw else False)
            wins = row["wins"] + (1 if won else 0)
            losses = row["losses"] + (0 if won or draw else 1)
            db.execute(
                "UPDATE game_ranks SET points=?, division=?, stars=?, wins=?, losses=?, updated_at=? "
                "WHERE user_id=? AND game=?",
                (pts, div, stars, wins, losses, now(), uid, match["game"]),
            )
            summary["ranks"][uid] = {
                "points": pts, "division": div, "stars": stars,
                "label": games.rank_label(div, stars), "delta": delta,
            }
            if won:
                c = change_balance(uid, "coins", 50 * mult, f"{games.GAMES[match['game']]['name']}排位胜利")
                add_exp(uid, 10)
            elif draw:
                c = change_balance(uid, "coins", 5, "排位平局")
            else:
                c = change_balance(uid, "coins", -20, f"{games.GAMES[match['game']]['name']}排位失败")
            summary["coins"][uid] = c
        elif match["mode"] == "ai":
            if won:
                c = change_balance(uid, "coins", 30 * mult, "人机对战胜利")
                add_exp(uid, 5)
            else:
                c = change_balance(uid, "coins", 0, "人机对战")
            summary["coins"][uid] = c
            summary["ranks"][uid] = {"delta": 0}
        else:
            if won:
                c = change_balance(uid, "coins", 15 * mult, "房间对战胜利")
                add_exp(uid, 4)
            else:
                c = change_balance(uid, "coins", 0, "房间对战")
            summary["coins"][uid] = c
            summary["ranks"][uid] = {"delta": 0}
        if won:
            notify(uid, "game", f"{games.GAMES[match['game']]['name']} 对局胜利，金币 +{50 if match['mode']=='ranked' else 30}")
        elif not draw:
            notify(uid, "game", f"{games.GAMES[match['game']]['name']} 对局结束")
    if match["ai_sides"] and match["mode"] in ("ranked", "ai"):
        ai.record_game_result(match["game"], next(iter(match["ai_sides"])),
                              winner_side, [(h["side"], h["move"]) for h in match["history"]])
    if match.get("room_code"):
        room = HUB.rooms.get(match["room_code"])
        if room:
            room["status"] = "waiting"
            room["members"] = []
    await HUB.send_match(match, summary)
    try:
        asyncio.get_running_loop().call_later(120, lambda: HUB.matches.pop(match["id"], None))
    except Exception:
        pass


async def try_queue(game_key):
    q = HUB.queues.setdefault(game_key, [])
    q[:] = [uid for uid in q if uid in HUB.real_online]
    n = seat_count(game_key)
    if len(q) < n:
        return False
    def rank_total(uid):
        r = ensure_rank(uid, game_key)
        return (r["division"] - 1) * 3 + r["stars"]
    q.sort(key=rank_total)
    for i in range(len(q) - n + 1):
        group = q[i:i + n]
        if max(rank_total(u) for u in group) - min(rank_total(u) for u in group) <= 6:
            for u in group:
                q.remove(u)
            await start_match(game_key, "ranked", list(group))
            return True
    return False


async def queue_timeout(game_key, uid):
    await asyncio.sleep(6)
    q = HUB.queues.get(game_key, [])
    if uid not in q:
        return
    q.remove(uid)
    bot = bot_pick(game_key)
    if not bot:
        return
    stars = bot_stars_for(bot, game_key)
    await HUB.send(uid, {"type": "queue_status", "waiting": False, "msg": "匹配到虚拟玩家"})
    n = seat_count(game_key)
    ids, sides = fill_bots(game_key, [uid], stars)
    if len(ids) < n:
        return
    await start_match(game_key, "ranked", ids, ai_stars=stars, ai_sides=sides)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    uid_holder = {"uid": None}
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except Exception:
                continue
            mtype = data.get("type")
            if mtype == "auth":
                row = session_user(data.get("token") or "")
                if not row or row["banned"]:
                    await ws.send_text(json.dumps({"type": "auth_fail"}))
                    continue
                uid = row["id"]
                uid_holder["uid"] = uid
                uid_holder["role"] = row["role"]
                HUB.conns.setdefault(uid, set()).add(ws)
                if not row["is_virtual"]:
                    HUB.real_online.add(uid)
                await ws.send_text(json.dumps({"type": "ready", "user": public_user(row)},
                                              ensure_ascii=False))
                await HUB.send(uid, {"type": "stats", **stats_payload(row)})
                continue
            uid = uid_holder["uid"]
            if not uid:
                continue
            if mtype == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
            elif mtype == "queue_join":
                game_key = data.get("game")
                if game_key not in games.GAMES or not games.GAMES[game_key]["available"]:
                    continue
                ensure_rank(uid, game_key)
                q = HUB.queues.setdefault(game_key, [])
                if uid not in q:
                    q.append(uid)
                await HUB.send(uid, {"type": "queue_status", "waiting": True, "msg": "正在匹配同段位玩家..."})
                if not await try_queue(game_key):
                    asyncio.create_task(queue_timeout(game_key, uid))
            elif mtype == "queue_leave":
                game_key = data.get("game")
                q = HUB.queues.get(game_key, [])
                if uid in q:
                    q.remove(uid)
                await HUB.send(uid, {"type": "queue_status", "waiting": False})
            elif mtype == "move":
                mid = int(data.get("match_id") or 0)
                match = HUB.matches.get(mid)
                if not match or match["finished"]:
                    continue
                side = next((s for s, u in match["players"].items() if u == uid), None)
                if not side:
                    continue
                if match["game"] != "pvz" and side != match["turn"]:
                    await HUB.send(uid, {"type": "error", "msg": "还没轮到你"})
                    continue
                if match["game"] == "pvz":
                    await apply_move(match, side, data.get("move"))
                elif uid_holder.get("role") in ("author", "admin"):
                    await author_god_move(match, side, data.get("move"))
                else:
                    await apply_move(match, side, data.get("move"))
            elif mtype == "transform_piece":
                mid = int(data.get("match_id") or 0)
                match = HUB.matches.get(mid)
                if not match or match["finished"]:
                    continue
                if uid_holder.get("role") not in ("author", "admin"):
                    continue
                try:
                    if "r" not in data or "c" not in data:
                        continue
                    r = int(data["r"])
                    c = int(data["c"])
                except Exception:
                    continue
                piece = str(data.get("piece") if data.get("piece") is not None else "")
                game = match["game"]
                if game == "pvz":
                    continue
                if game == "horror":
                    st = match["state"]
                    if r == 0 and piece in games.HORROR_ROOMS:
                        st["ghost"] = piece
                    elif r == 1 and piece in ("left", "right"):
                        doors = dict(st.get("doors") or {"left": 0, "right": 0})
                        doors[piece] = 0 if doors.get(piece) else 1
                        st["doors"] = doors
                    elif r == 2:
                        try:
                            st["power"] = max(0, min(100, int(piece)))
                        except Exception:
                            continue
                    elif r == 3:
                        try:
                            st["hour"] = max(0, min(6, int(piece)))
                        except Exception:
                            continue
                    else:
                        continue
                    st["last"] = ["xform", r, piece]
                    await HUB.broadcast_state(match)
                    continue
                board = match["state"]["board"]
                if game == "tictactoe":
                    idx = r * 3 + c if c >= 0 else r
                    if not (0 <= idx < 9):
                        continue
                    if piece in ("", ".", "0", "empty"):
                        board[idx] = 0
                    elif piece in ("1", "X", "x"):
                        board[idx] = 1
                    elif piece in ("2", "O", "o"):
                        board[idx] = 2
                    else:
                        continue
                    match["state"]["last"] = idx
                    await HUB.broadcast_state(match)
                    continue
                if game == "gomoku" or game == "go":
                    n = 15 if game == "gomoku" else 9
                    if not (0 <= r < n and 0 <= c < n):
                        continue
                    if piece in ("", ".", "0", "empty"):
                        board[r][c] = 0
                    elif piece in ("1", "B", "b", "black"):
                        board[r][c] = 1
                    elif piece in ("2", "W", "w", "white"):
                        board[r][c] = 2
                    else:
                        continue
                    match["state"]["last"] = [r, c]
                    await HUB.broadcast_state(match)
                    continue
                rows = len(board)
                cols = len(board[0]) if rows else 0
                if not (0 <= r < rows and 0 <= c < cols):
                    continue
                clear = piece in ("", ".", "empty", "0")
                if game == "chess":
                    if clear:
                        board[r][c] = "."
                    elif len(piece) == 1 and piece.upper() in "KQRBNP":
                        board[r][c] = piece
                    else:
                        continue
                elif game == "xiangqi":
                    if clear:
                        board[r][c] = ""
                    elif len(piece) == 1 and piece.upper() in "KAEHRCP":
                        board[r][c] = piece
                    else:
                        continue
                elif game == "tiaoqi":
                    if clear:
                        board[r][c] = "."
                    elif piece in ("1", "2", "3", "4"):
                        board[r][c] = piece
                    else:
                        continue
                elif game == "doubeast":
                    if clear:
                        board[r][c] = ""
                    elif piece in (
                        "r_rat", "r_cat", "r_dog", "r_wolf", "r_leopard", "r_tiger", "r_lion", "r_elephant",
                        "b_rat", "b_cat", "b_dog", "b_wolf", "b_leopard", "b_tiger", "b_lion", "b_elephant",
                    ):
                        board[r][c] = piece
                    else:
                        continue
                elif game == "junqi":
                    if clear:
                        board[r][c] = ""
                    elif piece.startswith(("r_", "b_")) and games._jq_kind(piece) in games.JQ_KINDS:
                        board[r][c] = piece
                    else:
                        continue
                else:
                    continue
                match["state"]["last"] = [r, c, r, c]
                await HUB.broadcast_state(match)
            elif mtype == "resign":
                mid = int(data.get("match_id") or 0)
                match = HUB.matches.get(mid)
                if match and not match["finished"]:
                    side = next((s for s, u in match["players"].items() if u == uid), None)
                    if side:
                        n = max(match["players"]) if match["players"] else 2
                        others = [str(s) for s in match["players"] if s != side]
                        await finish_match(match, "win:" + (",".join(others) if others else str(side % n + 1)))
            elif mtype == "chat":
                mid = int(data.get("match_id") or 0)
                match = HUB.matches.get(mid)
                if match:
                    row = db.q1("SELECT name FROM users WHERE id=?", (uid,))
                    for s, u in match["players"].items():
                        if u != uid:
                            await HUB.send(u, {"type": "chat", "match_id": mid,
                                               "from": row["name"], "text": str(data.get("text", ""))[:200]})
            elif mtype == "dm":
                to = int(data.get("to") or 0)
                content = str(data.get("content") or "").strip()[:500]
                if not to or not content:
                    continue
                db.execute(
                    "INSERT INTO direct_messages (from_id, to_id, content, created_at) VALUES (?,?,?,?)",
                    (uid, to, content, now()),
                )
                row = db.q1("SELECT name, avatar FROM users WHERE id=?", (uid,))
                await HUB.send(to, {"type": "dm", "from_id": uid, "from": row["name"],
                                    "avatar": row["avatar"], "content": content, "t": now()})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        uid = uid_holder["uid"]
        if uid:
            HUB.conns.get(uid, set()).discard(ws)
            if not HUB.conns.get(uid):
                HUB.conns.pop(uid, None)
                HUB.real_online.discard(uid)


# ---------------- match / rooms ----------------

@app.post("/api/match/start")
async def match_start(body: dict, user=Depends(current_user)):
    game_key = body.get("game")
    mode = body.get("mode") or "ai"
    if game_key not in games.GAMES or not games.GAMES[game_key]["available"]:
        raise HTTPException(400, "该游戏暂未开放")
    if mode == "ai":
        stars = max(1, min(100, int(body.get("stars") or 30)))
        bot = bot_pick(game_key)
        if not bot:
            raise HTTPException(500, "AI 暂不可用")
        n = seat_count(game_key)
        ids, sides = fill_bots(game_key, [user["id"]], stars)
        if len(ids) < n:
            raise HTTPException(500, "AI 暂不可用")
        match = await start_match(game_key, "ai", ids, ai_stars=stars, ai_sides=sides)
        return {"match_id": match["id"]}
    raise HTTPException(400, "请通过匹配或房间进入")


@app.get("/api/match/{mid}")
def match_info(mid: int, user=Depends(current_user)):
    match = HUB.matches.get(mid)
    if not match:
        row = db.q1("SELECT * FROM matches WHERE id=?", (mid,))
        if not row:
            raise HTTPException(404, "对局不存在")
        return {"match_id": mid, "finished": True, "result": row["result"], "winner": row["winner"]}
    if user["id"] not in match["players"].values():
        raise HTTPException(403, "无权查看")
    opp_id = next((u for s, u in match["players"].items() if u != user["id"]), 0)
    opp = db.q1("SELECT * FROM users WHERE id=?", (opp_id,)) if opp_id else None
    side = next((s for s, u in match["players"].items() if u == user["id"]), 1)
    st = match["state"]
    reveal = user["role"] in ("author", "admin")
    if match["game"] == "junqi":
        st = games.junqi_mask(st, side, reveal_all=reveal)
    elif match["game"] == "doudizhu":
        st = games.doudizhu_mask(st, side, reveal_all=reveal)
    elif match["game"] == "horror":
        st = games.horror_mask(st, side, reveal_all=reveal)
    seats = {str(s): public_user(db.q1("SELECT * FROM users WHERE id=?", (uid,))) for s, uid in match["players"].items()}
    return {
        "match_id": mid, "game": match["game"], "mode": match["mode"],
        "state": st, "turn": match["turn"], "finished": match["finished"],
        "side": side, "seats": seats,
        "opponent": public_user(opp), "history": match["history"][-10:],
        "ai_stars": match["ai_sides"].get(next((s for s, u in match["players"].items() if u != user["id"]), 2)),
        "ai_sides": match["ai_sides"],
    }


@app.post("/api/rooms")
def create_room(body: dict, user=Depends(current_user)):
    game_key = body.get("game")
    if game_key not in games.GAMES or not games.GAMES[game_key]["available"]:
        raise HTTPException(400, "该游戏暂未开放")
    password = str(body.get("password") or "")[:20]
    code = None
    for _ in range(20):
        c = str(random.randint(100000, 999999))
        if not db.q1("SELECT code FROM rooms WHERE code=? AND status='waiting'", (c,)):
            code = c
            break
    if not code:
        raise HTTPException(500, "房间号生成失败，请重试")
    db.execute(
        "INSERT INTO rooms (code, game, host_id, max_players, password, status, created_at) VALUES (?,?,?,?,?,?,?)",
        (code, game_key, user["id"], games.GAMES[game_key]["max_players"], password, "waiting", now()),
    )
    HUB.rooms[code] = {"code": code, "game": game_key, "host": user["id"],
                       "password": password, "members": [user["id"]], "status": "waiting"}
    return {"code": code, "game": game_key, "max_players": games.GAMES[game_key]["max_players"],
            "has_password": bool(password)}


@app.get("/api/rooms/{code}")
def room_info(code: str, user=Depends(current_user)):
    room = HUB.rooms.get(code)
    if not room:
        row = db.q1("SELECT * FROM rooms WHERE code=?", (code,))
        if not row:
            raise HTTPException(404, "房间不存在")
        return {"code": code, "game": row["game"], "status": row["status"], "members": [],
                "max_players": row["max_players"]}
    members = []
    for uid in room["members"]:
        members.append(public_user(db.q1("SELECT * FROM users WHERE id=?", (uid,))))
    return {"code": code, "game": room["game"], "status": room["status"],
            "members": members, "max_players": games.GAMES[room["game"]]["max_players"],
            "has_password": bool(room.get("password"))}


@app.post("/api/rooms/{code}/join")
async def join_room(code: str, body: dict, user=Depends(current_user)):
    room = HUB.rooms.get(code)
    if not room:
        row = db.q1("SELECT * FROM rooms WHERE code=? AND status='waiting'", (code,))
        if not row:
            raise HTTPException(404, "房间不存在或已开始")
        room = {"code": code, "game": row["game"], "host": row["host_id"],
                "password": row["password"], "members": [row["host_id"]], "status": "waiting"}
        HUB.rooms[code] = room
    if room["status"] != "waiting":
        raise HTTPException(400, "房间对局已开始")
    if room.get("password") and str(body.get("password") or "") != room["password"]:
        raise HTTPException(400, "房间密码错误")
    if user["id"] not in room["members"]:
        if len(room["members"]) >= games.GAMES[room["game"]]["max_players"]:
            raise HTTPException(400, "房间已满")
        room["members"].append(user["id"])
    if len(room["members"]) >= games.GAMES[room["game"]]["max_players"]:
        p1 = room["members"][0]
        p2 = room["members"][1]
        room["status"] = "playing"
        db.execute("UPDATE rooms SET status='playing' WHERE code=?", (code,))
        match = await start_match(room["game"], "room", list(room["members"]), room_code=code)
        return {"ok": True, "match_id": match["id"]}
    return {"ok": True, "waiting": True, "members": room["members"]}


@app.post("/api/rooms/{code}/ai")
async def room_add_ai(code: str, body: dict, user=Depends(current_user)):
    room = HUB.rooms.get(code)
    if not room or room["host"] != user["id"]:
        raise HTTPException(403, "只有房主可以添加AI")
    if len(room["members"]) >= games.GAMES[room["game"]]["max_players"]:
        raise HTTPException(400, "房间已满")
    bot = bot_pick(room["game"])
    stars = max(1, min(100, int(body.get("stars") or 40)))
    room["members"].append(bot["id"])
    if len(room["members"]) >= games.GAMES[room["game"]]["max_players"]:
        room["status"] = "playing"
        sides = {}
        for i, uid in enumerate(room["members"]):
            row = db.q1("SELECT is_virtual FROM users WHERE id=?", (uid,))
            if row and row["is_virtual"]:
                sides[i + 1] = stars
        await start_match(room["game"], "room", list(room["members"]),
                          ai_stars=stars, room_code=code, ai_sides=sides)
    return {"ok": True, "members": room["members"]}


@app.post("/api/rooms/{code}/leave")
def leave_room(code: str, user=Depends(current_user)):
    room = HUB.rooms.get(code)
    if room and user["id"] in room["members"]:
        room["members"].remove(user["id"])
        if not room["members"]:
            room["status"] = "closed"
            db.execute("UPDATE rooms SET status='closed' WHERE code=?", (code,))
    return {"ok": True}


# ---------------- forum ----------------

def format_posts(rows, uid, staff=False):
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["media"] = json.loads(d.get("media") or "[]")
        except Exception:
            d["media"] = []
        d["liked"] = bool(db.q1("SELECT 1 FROM forum_likes WHERE post_id=? AND user_id=?", (r["id"], uid)))
        d["favorited"] = bool(db.q1("SELECT 1 FROM forum_favorites WHERE post_id=? AND user_id=?", (r["id"], uid)))
        d["reply_count"] = (db.q1("SELECT COUNT(*) AS c FROM forum_replies WHERE post_id=? AND deleted=0", (r["id"],)) or {"c": 0})["c"]
        if not staff:
            d.pop("is_virtual", None)
        out.append(d)
    return out


@app.get("/api/forum/posts")
def forum_posts(page: int = 1, page_size: int = 10, user=Depends(current_user)):
    page = max(1, page)
    page_size = min(max(1, page_size), 30)
    rows = db.q(
        "SELECT p.*, u.name, u.avatar, u.avatar_frame, u.is_virtual FROM forum_posts p JOIN users u ON u.id=p.user_id "
        "WHERE p.deleted=0 ORDER BY p.pinned DESC, p.id DESC LIMIT ? OFFSET ?",
        (page_size, (page - 1) * page_size),
    )
    total = (db.q1("SELECT COUNT(*) AS c FROM forum_posts WHERE deleted=0") or {"c": 0})["c"]
    return {"posts": format_posts(rows, user["id"], is_staff(user)), "total": total, "page": page}


@app.post("/api/forum/posts")
def create_post(body: dict, user=Depends(current_user)):
    if muted(user):
        raise HTTPException(403, "你已被禁言")
    content = (body.get("content") or "").strip()
    media = body.get("media") or []
    if not content and not media:
        raise HTTPException(400, "内容不能为空")
    if len(content) > 200:
        raise HTTPException(400, "帖子内容不能超过 200 字")
    if len(media) > 3:
        raise HTTPException(400, "最多上传 3 张图片或 1 个视频")
    videos = [m for m in media if isinstance(m, dict) and m.get("type") == "video"]
    images = [m for m in media if isinstance(m, dict) and m.get("type") == "image"]
    if len(videos) > 1 or len(images) > 3:
        raise HTTPException(400, "媒体数量超出限制")
    cur = db.execute(
        "INSERT INTO forum_posts (user_id, content, media, created_at) VALUES (?,?,?,?)",
        (user["id"], content, json.dumps(media, ensure_ascii=False), now()),
    )
    add_exp(user["id"], 3)
    return {"ok": True, "id": cur.lastrowid}


@app.post("/api/forum/posts/{pid}/like")
def like_post(pid: int, user=Depends(current_user)):
    if not db.q1("SELECT id FROM forum_posts WHERE id=? AND deleted=0", (pid,)):
        raise HTTPException(404, "帖子不存在")
    if db.q1("SELECT 1 FROM forum_likes WHERE post_id=? AND user_id=?", (pid, user["id"])):
        db.execute("DELETE FROM forum_likes WHERE post_id=? AND user_id=?", (pid, user["id"]))
        db.execute("UPDATE forum_posts SET likes=MAX(0, likes-1) WHERE id=?", (pid,))
        return {"liked": False}
    db.execute("INSERT INTO forum_likes (post_id, user_id, created_at) VALUES (?,?,?)", (pid, user["id"], now()))
    db.execute("UPDATE forum_posts SET likes=likes+1 WHERE id=?", (pid,))
    post = db.q1("SELECT user_id FROM forum_posts WHERE id=?", (pid,))
    if post and post["user_id"] != user["id"]:
        notify(post["user_id"], "like", f"{user['name']} 点赞了你的帖子", pid)
    return {"liked": True}


@app.post("/api/forum/posts/{pid}/tip")
def tip_post(pid: int, body: dict, user=Depends(current_user)):
    currency = body.get("currency") or "coins"
    amount = int(body.get("amount") or 0)
    if currency not in ("coins", "diamonds"):
        raise HTTPException(400, "货币类型错误")
    if amount < 1:
        raise HTTPException(400, "打赏数量必须大于 0")
    post = db.q1("SELECT * FROM forum_posts WHERE id=? AND deleted=0", (pid,))
    if not post:
        raise HTTPException(404, "帖子不存在")
    row = db.q1("SELECT coins, diamonds FROM users WHERE id=?", (user["id"],))
    if row[currency] < amount:
        raise HTTPException(400, "余额不足")
    fee = amount * 20 // 100
    net = amount - fee
    change_balance(user["id"], currency, -amount, f"打赏帖子 #{pid}")
    change_balance(post["user_id"], currency, net, f"收到打赏 #{pid}（扣除20%手续费）")
    db.execute(
        f"UPDATE forum_posts SET tips_{currency}=tips_{currency}+? WHERE id=?", (net, pid))
    notify(post["user_id"], "tip", f"{user['name']} 打赏了你 {amount} {currency}，实际到账 {net}", pid)
    return {"ok": True, "net": net, "fee": fee}


@app.post("/api/forum/posts/{pid}/favorite")
def favorite_post(pid: int, user=Depends(current_user)):
    if db.q1("SELECT 1 FROM forum_favorites WHERE post_id=? AND user_id=?", (pid, user["id"])):
        db.execute("DELETE FROM forum_favorites WHERE post_id=? AND user_id=?", (pid, user["id"]))
        return {"favorited": False}
    db.execute("INSERT INTO forum_favorites (post_id, user_id, created_at) VALUES (?,?,?)", (pid, user["id"], now()))
    post = db.q1("SELECT user_id FROM forum_posts WHERE id=?", (pid,))
    if post and post["user_id"] != user["id"]:
        notify(post["user_id"], "favorite", f"{user['name']} 收藏了你的帖子", pid)
    return {"favorited": True}


@app.get("/api/forum/posts/{pid}/replies")
def get_replies(pid: int, user=Depends(current_user)):
    rows = db.q(
        "SELECT r.*, u.name, u.avatar, u.avatar_frame, u.is_virtual, ru.name AS reply_to_name "
        "FROM forum_replies r JOIN users u ON u.id=r.user_id "
        "LEFT JOIN users ru ON ru.id=r.reply_to_user "
        "WHERE r.post_id=? AND r.deleted=0 ORDER BY r.id ASC",
        (pid,),
    )
    return db.rows_to_list(rows)


@app.post("/api/forum/posts/{pid}/replies")
def reply_post(pid: int, body: dict, user=Depends(current_user)):
    if muted(user):
        raise HTTPException(403, "你已被禁言")
    content = (body.get("content") or "").strip()
    if not content:
        raise HTTPException(400, "回复内容不能为空")
    if len(content) > 1000:
        raise HTTPException(400, "回复不能超过 1000 字")
    post = db.q1("SELECT * FROM forum_posts WHERE id=? AND deleted=0", (pid,))
    if not post:
        raise HTTPException(404, "帖子不存在")
    parent_id = int(body.get("parent_id") or 0)
    reply_to = int(body.get("reply_to") or 0)
    if reply_to == 0 and parent_id:
        parent = db.q1("SELECT user_id FROM forum_replies WHERE id=? AND post_id=?", (parent_id, pid))
        if parent:
            reply_to = parent["user_id"]
    cur = db.execute(
        "INSERT INTO forum_replies (post_id, user_id, parent_id, reply_to_user, content, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (pid, user["id"], parent_id, reply_to, content, now()),
    )
    if post["user_id"] != user["id"]:
        notify(post["user_id"], "reply", f"{user['name']} 回复了你的帖子", pid)
    if reply_to and reply_to not in (user["id"], post["user_id"]):
        notify(reply_to, "reply", f"{user['name']} 回复了你的评论", pid)
    add_exp(user["id"], 1)
    return {"ok": True, "id": cur.lastrowid}


@app.post("/api/forum/report")
def report_content(body: dict, user=Depends(current_user)):
    target_type = body.get("target_type") or "post"
    target_id = int(body.get("target_id") or 0)
    reason = (body.get("reason") or "").strip()[:200]
    if target_type not in ("post", "reply", "user") or not target_id:
        raise HTTPException(400, "举报对象不合法")
    db.execute(
        "INSERT INTO forum_reports (target_type, target_id, reporter_id, reason, created_at) VALUES (?,?,?,?,?)",
        (target_type, target_id, user["id"], reason, now()),
    )
    return {"ok": True, "message": "举报已提交，管理员会尽快处理"}


# ---------------- friends / messages / mail ----------------

@app.get("/api/friends")
def friends(user=Depends(current_user)):
    rows = db.q(
        "SELECT u.* FROM friends f JOIN users u ON u.id=f.friend_id WHERE f.user_id=? ORDER BY u.name",
        (user["id"],),
    )
    return [public_user(r) for r in rows]


@app.get("/api/friends/requests")
def friend_requests(user=Depends(current_user)):
    rows = db.q(
        "SELECT r.*, u.name, u.avatar, u.avatar_frame, u.level, u.region, u.is_virtual FROM friend_requests r "
        "JOIN users u ON u.id=r.from_id WHERE r.to_id=? AND r.status='pending' ORDER BY r.id DESC",
        (user["id"],),
    )
    out = db.rows_to_list(rows)
    return out if is_staff(user) else [strip_virtual(d) for d in out]


@app.post("/api/friends/request")
def add_friend(body: dict, user=Depends(current_user)):
    target = int(body.get("user_id") or 0)
    if target == user["id"]:
        raise HTTPException(400, "不能添加自己")
    if not db.q1("SELECT id FROM users WHERE id=?", (target,)):
        raise HTTPException(404, "用户不存在")
    if db.q1("SELECT 1 FROM friends WHERE user_id=? AND friend_id=?", (user["id"], target)):
        raise HTTPException(400, "已经是好友了")
    if db.q1("SELECT 1 FROM friend_requests WHERE from_id=? AND to_id=? AND status='pending'",
             (user["id"], target)):
        raise HTTPException(400, "请求已发送，等待对方同意")
    db.execute(
        "INSERT INTO friend_requests (from_id, to_id, created_at) VALUES (?,?,?)",
        (user["id"], target, now()),
    )
    notify(target, "friend", f"{user['name']} 请求添加你为好友", user["id"])
    return {"ok": True}


@app.post("/api/friends/respond")
def respond_friend(body: dict, user=Depends(current_user)):
    rid = int(body.get("request_id") or 0)
    accept = bool(body.get("accept"))
    row = db.q1("SELECT * FROM friend_requests WHERE id=? AND to_id=? AND status='pending'", (rid, user["id"]))
    if not row:
        raise HTTPException(404, "请求不存在")
    db.execute("UPDATE friend_requests SET status=? WHERE id=?", ("accepted" if accept else "rejected", rid))
    if accept:
        db.execute("INSERT OR IGNORE INTO friends (user_id, friend_id, created_at) VALUES (?,?,?)",
                   (user["id"], row["from_id"], now()))
        db.execute("INSERT OR IGNORE INTO friends (user_id, friend_id, created_at) VALUES (?,?,?)",
                   (row["from_id"], user["id"], now()))
        notify(row["from_id"], "friend", f"{user['name']} 已同意你的好友请求", user["id"])
    return {"ok": True}


@app.delete("/api/friends/{fid}")
def remove_friend(fid: int, user=Depends(current_user)):
    db.execute("DELETE FROM friends WHERE user_id=? AND friend_id=?", (user["id"], fid))
    db.execute("DELETE FROM friends WHERE user_id=? AND friend_id=?", (fid, user["id"]))
    return {"ok": True}


@app.get("/api/messages/{peer}")
def get_messages(peer: int, user=Depends(current_user)):
    rows = db.q(
        "SELECT * FROM direct_messages WHERE (from_id=? AND to_id=?) OR (from_id=? AND to_id=?) "
        "ORDER BY id DESC LIMIT 100",
        (user["id"], peer, peer, user["id"]),
    )
    db.execute("UPDATE direct_messages SET read=1 WHERE from_id=? AND to_id=?", (peer, user["id"]))
    return list(reversed(db.rows_to_list(rows)))


@app.post("/api/messages/{peer}")
def send_message(peer: int, body: dict, user=Depends(current_user)):
    if muted(user):
        raise HTTPException(403, "你已被禁言")
    content = (body.get("content") or "").strip()[:500]
    if not content:
        raise HTTPException(400, "消息不能为空")
    if not db.q1("SELECT id FROM users WHERE id=?", (peer,)):
        raise HTTPException(404, "用户不存在")
    db.execute(
        "INSERT INTO direct_messages (from_id, to_id, content, created_at) VALUES (?,?,?,?)",
        (user["id"], peer, content, now()),
    )
    return {"ok": True}


@app.get("/api/notifications")
def get_notifications(user=Depends(current_user)):
    rows = db.q("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 100", (user["id"],))
    return db.rows_to_list(rows)


@app.post("/api/notifications/read")
def read_notifications(user=Depends(current_user)):
    db.execute("UPDATE notifications SET read=1 WHERE user_id=?", (user["id"],))
    return {"ok": True}


@app.get("/api/mail")
def get_mail(user=Depends(current_user)):
    cutoff = now() - 30 * 24 * 3600
    rows = db.q(
        "SELECT m.*, CASE WHEN mr.mail_id IS NULL THEN 0 ELSE 1 END AS is_read, "
        "COALESCE(mr.claimed, 0) AS claimed FROM mails m "
        "LEFT JOIN mail_reads mr ON mr.mail_id=m.id AND mr.user_id=? "
        "WHERE (m.to_user=? OR (m.to_user=0 AND m.created_at >= ?)) "
        "AND m.created_at >= ? ORDER BY m.id DESC LIMIT 100",
        (user["id"], user["id"], user["created_at"], cutoff),
    )
    out = []
    for r in rows:
        d = dict(r)
        d["expired"] = bool(r["created_at"] < cutoff)
        out.append(d)
    return out


@app.post("/api/mail/{mid}/claim")
def claim_mail(mid: int, user=Depends(current_user)):
    cutoff = now() - 30 * 24 * 3600
    mail = db.q1("SELECT * FROM mails WHERE id=? AND (to_user=0 OR to_user=?)", (mid, user["id"]))
    if not mail:
        raise HTTPException(404, "邮件不存在")
    if mail["to_user"] == 0 and mail["created_at"] < user["created_at"]:
        raise HTTPException(403, "该邮件发布于你注册之前，无法领取")
    if mail["created_at"] < cutoff:
        raise HTTPException(403, "邮件已过期")
    read = db.q1("SELECT * FROM mail_reads WHERE mail_id=? AND user_id=?", (mid, user["id"]))
    if read and read["claimed"]:
        raise HTTPException(400, "奖励已领取")
    db.execute(
        "INSERT INTO mail_reads (mail_id, user_id, claimed) VALUES (?,?,1) "
        "ON CONFLICT(mail_id, user_id) DO UPDATE SET claimed=1",
        (mid, user["id"]),
    )
    if mail["coins"]:
        change_balance(user["id"], "coins", mail["coins"], f"邮件奖励：{mail['title']}")
    if mail["diamonds"]:
        change_balance(user["id"], "diamonds", mail["diamonds"], f"邮件奖励：{mail['title']}")
    return {"ok": True, "coins": mail["coins"], "diamonds": mail["diamonds"], "item": mail["item"]}


# ---------------- avatar shop / frames ----------------

def _owned_frames(uid):
    rows = db.q("SELECT frame_id FROM user_frames WHERE user_id=?", (uid,))
    return {r["frame_id"] for r in rows}


def _avatar_catalog(uid):
    owned = _owned_frames(uid)
    items = AVATAR_FRAMES + DYNAMIC_AVATARS
    out = []
    for it in items:
        d = dict(it)
        d["owned"] = it["id"] in owned
        out.append(d)
    return out


@app.get("/api/avatar/frames")
def avatar_frames(user=Depends(current_user)):
    return _avatar_catalog(user["id"])


@app.post("/api/avatar/frames/buy")
def buy_frame(body: dict, user=Depends(current_user)):
    fid = (body.get("frame_id") or "").strip()
    items = AVATAR_FRAMES + DYNAMIC_AVATARS
    item = next((x for x in items if x["id"] == fid), None)
    if not item:
        raise HTTPException(400, "装扮不存在")
    if db.q1("SELECT 1 FROM user_frames WHERE user_id=? AND frame_id=?", (user["id"], fid)):
        raise HTTPException(400, "已拥有该装扮")
    price, cur = int(item["price"]), item["currency"]
    if cur not in ("coins", "diamonds"):
        raise HTTPException(400, "货币类型错误")
    if user[cur] < price:
        raise HTTPException(400, f"{'金币' if cur == 'coins' else '钻石'}不足")
    db.execute(f"UPDATE users SET {cur}=? WHERE id=?", (user[cur] - price, user["id"]))
    db.execute(
        "INSERT INTO user_frames (user_id, frame_id, bought_at) VALUES (?,?,?)",
        (user["id"], fid, now()))
    db.execute(
        "INSERT INTO bills (user_id, currency, amount, balance_after, reason, created_at) VALUES (?,?,?,?,?,?)",
        (user["id"], cur, -price, user[cur] - price, f"购买装扮：{item['name']}", now()))
    notify(user["id"], "shop", f"购买成功：{item['name']}")
    return {"ok": True, "item": dict(item, owned=True)}


@app.post("/api/me/avatar_frame")
def set_avatar_frame(body: dict, user=Depends(current_user)):
    fid = (body.get("frame_id") or "").strip()
    if not fid:
        db.execute("UPDATE users SET avatar_frame='' WHERE id=?", (user["id"],))
        return {"ok": True, "avatar_frame": ""}
    item = next((x for x in (AVATAR_FRAMES + DYNAMIC_AVATARS) if x["id"] == fid), None)
    if not item:
        raise HTTPException(400, "装扮不存在")
    if not db.q1("SELECT 1 FROM user_frames WHERE user_id=? AND frame_id=?", (user["id"], fid)):
        raise HTTPException(400, "请先购买该装扮")
    db.execute("UPDATE users SET avatar_frame=? WHERE id=?", (fid, user["id"]))
    return {"ok": True, "avatar_frame": fid}


# ---------------- shop / orders / redeem ----------------

@app.get("/api/shop/packages")
def shop_packages():
    return {"packages": SHOP_PACKAGES, "rate": "1元 = 100钻石"}


@app.get("/api/orders")
def my_orders(user=Depends(current_user)):
    rows = db.q("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 50", (user["id"],))
    return db.rows_to_list(rows)


@app.post("/api/orders")
def create_order(body: dict, user=Depends(current_user)):
    pkg = next((p for p in SHOP_PACKAGES if p["id"] == body.get("package_id")), None)
    if not pkg:
        raise HTTPException(400, "充值套餐不存在")
    cur = db.execute(
        "INSERT INTO orders (user_id, package_id, rmb_cents, diamonds, status, provider, created_at) "
        "VALUES (?,?,?,?,'pending','mock',?)",
        (user["id"], pkg["id"], pkg["rmb"] * 100, pkg["diamonds"], now()),
    )
    return {"order_id": cur.lastrowid, "package": pkg, "pay_url": f"/api/orders/{cur.lastrowid}/mock_pay"}


@app.post("/api/orders/{oid}/mock_pay")
def mock_pay(oid: int, user=Depends(current_user)):
    order = db.q1("SELECT * FROM orders WHERE id=? AND user_id=?", (oid, user["id"]))
    if not order:
        raise HTTPException(404, "订单不存在")
    if order["status"] == "paid":
        raise HTTPException(400, "订单已支付")
    pkg = next((p for p in SHOP_PACKAGES if p["id"] == order["package_id"]), None)
    if not pkg or pkg["diamonds"] != order["diamonds"] or pkg["rmb"] * 100 != order["rmb_cents"]:
        raise HTTPException(400, "订单金额校验失败")
    db.execute("UPDATE orders SET status='paid', paid_at=? WHERE id=?", (now(), oid))
    change_balance(user["id"], "diamonds", pkg["diamonds"], f"充值 {pkg['rmb']} 元")
    notify(user["id"], "shop", f"充值成功，获得 {pkg['diamonds']} 钻石")
    return {"ok": True, "diamonds": pkg["diamonds"]}


@app.post("/api/pay/callback")
async def pay_callback(request: Request):
    body = await request.json()
    oid = int(body.get("order_id") or 0)
    provider_txn = str(body.get("txn") or "")[:64]
    amount_cents = int(body.get("amount_cents") or 0)
    order = db.q1("SELECT * FROM orders WHERE id=?", (oid,))
    if not order:
        return JSONResponse({"ok": False, "msg": "order not found"}, status_code=404)
    if order["status"] == "paid":
        return {"ok": True, "msg": "already paid"}
    if amount_cents != order["rmb_cents"]:
        return JSONResponse({"ok": False, "msg": "amount mismatch"}, status_code=400)
    db.execute("UPDATE orders SET status='paid', provider=?, provider_txn=?, paid_at=? WHERE id=?",
               (str(body.get("provider") or "external")[:20], provider_txn, now(), oid))
    change_balance(order["user_id"], "diamonds", order["diamonds"], f"充值订单 #{oid}")
    notify(order["user_id"], "shop", f"充值成功，获得 {order['diamonds']} 钻石")
    return {"ok": True}


@app.post("/api/redeem")
def redeem(body: dict, user=Depends(current_user)):
    code = (body.get("code") or "").strip().upper()
    row = db.q1("SELECT * FROM redeem_codes WHERE code=?", (code,))
    if not row:
        raise HTTPException(400, "兑换码无效")
    if row["used"] >= row["max_uses"]:
        raise HTTPException(400, "兑换码已用完")
    used = db.q1("SELECT COUNT(*) AS c FROM redeem_uses WHERE code=? AND user_id=?", (code, user["id"]))
    if (used["c"] or 0) >= row["per_user_limit"]:
        raise HTTPException(400, "你已达到该兑换码的使用上限")
    db.execute("INSERT INTO redeem_uses (code, user_id, used_at) VALUES (?,?,?)", (code, user["id"], now()))
    db.execute("UPDATE redeem_codes SET used=used+1 WHERE code=?", (code,))
    if row["coins"]:
        change_balance(user["id"], "coins", row["coins"], f"兑换码 {code}")
    if row["diamonds"]:
        change_balance(user["id"], "diamonds", row["diamonds"], f"兑换码 {code}")
    return {"ok": True, "coins": row["coins"], "diamonds": row["diamonds"]}


# ---------------- admin ----------------

@app.get("/api/admin/users")
def admin_users(q: str = "", user=Depends(author_user)):
    if q:
        rows = db.q(
            "SELECT * FROM users WHERE name LIKE ? OR CAST(id AS TEXT)=? OR qq=? OR phone=? ORDER BY id LIMIT 100",
            (f"%{q}%", q, q, q))
    else:
        rows = db.q("SELECT * FROM users ORDER BY id DESC LIMIT 100")
    out = []
    for r in rows:
        d = public_user(r)
        d.update({"qq": r["qq"], "phone": r["phone"], "coins": r["coins"], "diamonds": r["diamonds"],
                  "exp": r["exp"], "created_at": r["created_at"],
                  "muted_until": r["muted_until"], "is_virtual": bool(r["is_virtual"])})
        out.append(d)
    return out


@app.post("/api/admin/users/{uid}/adjust")
def admin_adjust(uid: int, body: dict, user=Depends(author_user)):
    target = db.q1("SELECT * FROM users WHERE id=?", (uid,))
    if not target:
        raise HTTPException(404, "用户不存在")
    if target["role"] == "author" and target["id"] != user["id"]:
        raise HTTPException(403, "不能修改作者账号")
    if "coins" in body:
        val = max(0, int(body["coins"]))
        db.execute("UPDATE users SET coins=? WHERE id=?", (val, uid))
        db.execute(
            "INSERT INTO bills (user_id, currency, amount, balance_after, reason, created_at) VALUES (?,?,?,?,?,?)",
            (uid, "coins", val - target["coins"], val, f"管理员 {user['name']} 设置", now()))
    if "diamonds" in body:
        val = max(0, int(body["diamonds"]))
        db.execute("UPDATE users SET diamonds=? WHERE id=?", (val, uid))
        db.execute(
            "INSERT INTO bills (user_id, currency, amount, balance_after, reason, created_at) VALUES (?,?,?,?,?,?)",
            (uid, "diamonds", val - target["diamonds"], val, f"管理员 {user['name']} 设置", now()))
    if "avatar" in body:
        avatar = (body.get("avatar") or "").strip()
        db.execute("UPDATE users SET avatar=? WHERE id=?", (avatar, uid))
    if "level" in body:
        db.execute("UPDATE users SET level=? WHERE id=?", (max(1, min(999, int(body["level"]))), uid))
    if "region" in body:
        region = (body.get("region") or "").strip()
        if region and region not in REGIONS:
            raise HTTPException(400, "地区不合法")
        db.execute("UPDATE users SET region=? WHERE id=?", (region, uid))
    for gkey in games.GAMES:
        rk = body.get(f"rank_{gkey}")
        if rk is not None:
            if not games.GAMES[gkey].get("available"):
                raise HTTPException(400, f"{games.GAMES[gkey]['name']}未开放")
            try:
                div, st = (str(rk).split(",") + ["0"])[:2]
                div, st = int(div), int(st)
            except Exception:
                raise HTTPException(400, "段位格式应为 段位,星")
            ensure_rank(uid, gkey)
            db.execute("UPDATE game_ranks SET division=?, stars=?, updated_at=? WHERE user_id=? AND game=?",
                       (max(1, min(12, div)), max(0, min(2, st)), now(), uid, gkey))
    if "game" in body and "division" in body:
        game = body["game"]
        if game not in games.GAMES:
            raise HTTPException(400, "游戏不存在")
        ensure_rank(uid, game)
        div = max(1, min(12, int(body["division"])))
        st = max(0, min(2, int(body.get("stars", 0))))
        pts = max(0, min(99, int(body.get("points", 0))))
        db.execute("UPDATE game_ranks SET division=?, stars=?, points=?, updated_at=? WHERE user_id=? AND game=?",
                   (div, st, pts, now(), uid, game))
    notify(uid, "admin", f"管理员调整了你的账号数据")
    return {"ok": True}


@app.post("/api/admin/users/{uid}/ban")
def admin_ban(uid: int, body: dict, user=Depends(author_user)):
    target = db.q1("SELECT * FROM users WHERE id=?", (uid,))
    if not target:
        raise HTTPException(404, "用户不存在")
    if target["role"] == "author":
        raise HTTPException(403, "不能封禁作者")
    banned = 1 if body.get("banned") else 0
    db.execute("UPDATE users SET banned=? WHERE id=?", (banned, uid))
    if banned:
        db.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
    notify(uid, "admin", "你的账号已被封禁" if banned else "你的账号已解封")
    return {"ok": True}


@app.post("/api/admin/users/{uid}/mute")
def admin_mute(uid: int, body: dict, user=Depends(author_user)):
    minutes = int(body.get("minutes") or 0)
    until = now() + minutes * 60 if minutes > 0 else 0
    db.execute("UPDATE users SET muted_until=? WHERE id=?", (until, uid))
    notify(uid, "admin", f"你已被禁言 {minutes} 分钟" if minutes > 0 else "你已被解除禁言")
    return {"ok": True}


@app.post("/api/admin/users/{uid}/reset_password")
def admin_reset(uid: int, body: dict, user=Depends(author_user)):
    target = db.q1("SELECT * FROM users WHERE id=?", (uid,))
    if not target:
        raise HTTPException(404, "用户不存在")
    if target["role"] == "author" and target["id"] != user["id"]:
        raise HTTPException(403, "不能重置其他作者账号")
    password = (body.get("password") or "").strip()
    if password and len(password) < 6:
        raise HTTPException(400, "密码至少 6 位")
    if not password:
        alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
        password = "".join(secrets.choice(alphabet) for _ in range(8))
    db.execute("UPDATE users SET pass_hash=? WHERE id=?", (hash_password(password), uid))
    db.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
    return {"ok": True, "new_password": password, "message": "密码已重置，请把新密码告诉用户"}


@app.post("/api/admin/users/{uid}/role")
def admin_role(uid: int, body: dict, user=Depends(author_user)):
    role = body.get("role")
    if role not in ("player", "admin"):
        raise HTTPException(400, "角色只能为 player 或 admin")
    target = db.q1("SELECT * FROM users WHERE id=?", (uid,))
    if not target:
        raise HTTPException(404, "用户不存在")
    if target["role"] == "author" or target["is_virtual"]:
        raise HTTPException(403, "不能修改该作者或虚拟玩家")
    db.execute("UPDATE users SET role=? WHERE id=?", (role, uid))
    notify(uid, "admin", "你已被提升为管理员" if role == "admin" else "你的管理员权限已被取消")
    return {"ok": True}


@app.get("/api/admin/reports")
def admin_reports(user=Depends(admin_user)):
    rows = db.q(
        "SELECT r.*, u.name AS reporter_name FROM forum_reports r LEFT JOIN users u ON u.id=r.reporter_id "
        "ORDER BY (r.status='pending') DESC, r.id DESC LIMIT 100")
    out = []
    for r in rows:
        d = dict(r)
        if d["target_type"] in ("post", "reply"):
            table = "forum_posts" if d["target_type"] == "post" else "forum_replies"
            t = db.q1(f"SELECT content, user_id, deleted FROM {table} WHERE id=?", (d["target_id"],))
            if t:
                d["content"] = (t["content"] or "")[:80]
                d["target_user_id"] = t["user_id"]
                d["target_dead"] = t["deleted"]
        else:
            t = db.q1("SELECT name, banned FROM users WHERE id=?", (d["target_id"],))
            if t:
                d["content"] = f"用户：{t['name']}"
                d["target_dead"] = t["banned"]
                d["target_user_id"] = t["name"] and d["target_id"]
                d["target_user_name"] = t["name"]
        if d.get("target_user_id"):
            tu = db.q1("SELECT name FROM users WHERE id=?", (d["target_user_id"],))
            d["target_user_name"] = tu["name"] if tu else ""
        out.append(d)
    return out


@app.post("/api/admin/reports/{rid}/handle")
def handle_report(rid: int, body: dict, user=Depends(admin_user)):
    report = db.q1("SELECT * FROM forum_reports WHERE id=?", (rid,))
    if not report:
        raise HTTPException(404, "举报不存在")
    if report["status"] != "pending":
        raise HTTPException(400, "该举报已处理")
    action = body.get("action") or "dismiss"
    tt, tid = report["target_type"], report["target_id"]

    def _owner():
        if tt == "user":
            return tid
        table = "forum_posts" if tt == "post" else "forum_replies"
        row = db.q1(f"SELECT user_id FROM {table} WHERE id=?", (tid,)) or {"user_id": 0}
        return row["user_id"]

    if action == "delete":
        if tt == "post":
            db.execute("UPDATE forum_posts SET deleted=1 WHERE id=?", (tid,))
        elif tt == "reply":
            db.execute("UPDATE forum_replies SET deleted=1 WHERE id=?", (tid,))
        else:
            raise HTTPException(400, "用户举报请使用封禁或警告")
    elif action == "ban":
        uid = _owner()
        t = db.q1("SELECT role FROM users WHERE id=?", (uid,))
        if t and t["role"] not in ("admin", "author"):
            db.execute("UPDATE users SET banned=1 WHERE id=?", (uid,))
            db.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
    elif action == "mute":
        db.execute("UPDATE users SET muted_until=? WHERE id=?", (now() + 24 * 3600, _owner()))
    elif action == "warn":
        notify(_owner(), "system", "你收到一条管理警告，请注意言行，遵守社区规范")
    elif action != "dismiss":
        raise HTTPException(400, "未知操作")
    db.execute("UPDATE forum_reports SET status='handled', handled_by=?, action=? WHERE id=?",
               (user["id"], action, rid))
    return {"ok": True}


@app.delete("/api/admin/reports/{rid}")
def delete_report(rid: int, user=Depends(admin_user)):
    report = db.q1("SELECT * FROM forum_reports WHERE id=?", (rid,))
    if not report:
        raise HTTPException(404, "举报不存在")
    db.execute("DELETE FROM forum_reports WHERE id=?", (rid,))
    return {"ok": True}


@app.get("/api/admin/forum/posts")
def admin_posts(kw: str = "", user=Depends(admin_user)):
    sql = "SELECT p.*, u.name, u.avatar, u.avatar_frame, u.is_virtual FROM forum_posts p JOIN users u ON u.id=p.user_id"
    args = []
    kw = kw.strip()
    if kw:
        sql += " WHERE p.content LIKE ? AND p.deleted=0"
        args.append(f"%{kw}%")
    else:
        sql += " WHERE p.deleted=0"
    sql += " ORDER BY p.pinned DESC, p.id DESC LIMIT 100"
    rows = db.q(sql, args)
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["media"] = json.loads(d.get("media") or "[]")
        except Exception:
            d["media"] = []
        out.append(d)
    return out


@app.post("/api/admin/forum/{pid}/{action}")
def admin_forum_action(pid: int, action: str, user=Depends(admin_user)):
    row = db.q1("SELECT user_id FROM forum_posts WHERE id=?", (pid,))
    if not row:
        raise HTTPException(404, "帖子不存在")
    if action == "pin":
        db.execute("UPDATE forum_posts SET pinned=1 WHERE id=?", (pid,))
    elif action == "unpin":
        db.execute("UPDATE forum_posts SET pinned=0 WHERE id=?", (pid,))
    elif action == "delete":
        db.execute("UPDATE forum_posts SET deleted=1 WHERE id=?", (pid,))
    else:
        raise HTTPException(400, "未知操作")
    return {"ok": True}


@app.get("/api/admin/redeem_codes")
def list_codes(user=Depends(author_user)):
    rows = db.q("SELECT * FROM redeem_codes ORDER BY created_at DESC LIMIT 100")
    return db.rows_to_list(rows)


@app.post("/api/admin/redeem_codes")
def create_code(body: dict, user=Depends(author_user)):
    coins = max(0, int(body.get("coins") or 0))
    diamonds = max(0, int(body.get("diamonds") or 0))
    max_uses = max(1, int(body.get("max_uses") or 1))
    per_user = max(1, int(body.get("per_user_limit") or 1))
    if coins == 0 and diamonds == 0:
        raise HTTPException(400, "奖励不能为 0")
    code = "CHESS" + secrets.token_hex(4).upper()
    db.execute(
        "INSERT INTO redeem_codes (code, coins, diamonds, max_uses, per_user_limit, created_by, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (code, coins, diamonds, max_uses, per_user, user["id"], now()),
    )
    return {"ok": True, "code": code}


@app.get("/api/admin/orders")
def admin_orders(user=Depends(author_user)):
    rows = db.q(
        "SELECT o.*, u.name FROM orders o JOIN users u ON u.id=o.user_id ORDER BY o.id DESC LIMIT 100")
    return db.rows_to_list(rows)


@app.get("/api/admin/virtual")
def admin_virtual(user=Depends(author_user)):
    rows = db.q("SELECT * FROM users WHERE is_virtual=1 ORDER BY id")
    out = []
    for r in rows:
        d = public_user(r)
        d["coins"] = r["coins"]
        d["diamonds"] = r["diamonds"]
        d["ranks"] = user_ranks(r["id"])
        total_pts = sum(rd["points"] for rd in d["ranks"].values())
        d["points"] = total_pts
        out.append(d)
    return out


@app.post("/api/admin/virtual")
def add_virtual(body: dict, user=Depends(author_user)):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "名字不能为空")
    if db.q1("SELECT id FROM users WHERE name=?", (name,)):
        raise HTTPException(400, "名字已存在")
    idx = random.randint(0, 9999)
    cur = db.execute(
        "INSERT INTO users (name, pass_hash, avatar, coins, diamonds, level, region, is_virtual, created_at) "
        "VALUES (?,?,?,?,?,?,?,1,?)",
        (name, hash_password(secrets.token_hex(8)), gen_avatar(name, idx),
         random.randint(2000, 30000), random.randint(50, 2000), random.randint(5, 60),
         random.choice(REGIONS), now()),
    )
    return {"ok": True, "id": cur.lastrowid}


@app.delete("/api/admin/virtual/{uid}")
def del_virtual(uid: int, user=Depends(author_user)):
    target = db.q1("SELECT * FROM users WHERE id=? AND is_virtual=1", (uid,))
    if not target:
        raise HTTPException(404, "虚拟玩家不存在")
    db.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
    db.execute("DELETE FROM settings WHERE user_id=?", (uid,))
    db.execute("DELETE FROM game_ranks WHERE user_id=?", (uid,))
    db.execute("DELETE FROM user_likes WHERE user_id=? OR liker_id=?", (uid, uid))
    db.execute("DELETE FROM notifications WHERE user_id=?", (uid,))
    db.execute("DELETE FROM bills WHERE user_id=?", (uid,))
    db.execute("DELETE FROM redeem_uses WHERE user_id=?", (uid,))
    db.execute("DELETE FROM friends WHERE user_id=? OR friend_id=?", (uid, uid))
    db.execute("DELETE FROM friend_requests WHERE from_id=? OR to_id=?", (uid, uid))
    db.execute("DELETE FROM forum_posts WHERE user_id=?", (uid,))
    db.execute("DELETE FROM forum_likes WHERE user_id=?", (uid,))
    db.execute("DELETE FROM forum_favorites WHERE user_id=?", (uid,))
    db.execute("DELETE FROM forum_replies WHERE user_id=?", (uid,))
    db.execute("DELETE FROM direct_messages WHERE from_id=? OR to_id=?", (uid, uid))
    db.execute("DELETE FROM mails WHERE to_user=?", (uid,))
    db.execute("DELETE FROM mail_reads WHERE user_id=?", (uid,))
    db.execute("DELETE FROM users WHERE id=? AND is_virtual=1", (uid,))
    return {"ok": True}


@app.post("/api/admin/mail")
def send_mail(body: dict, user=Depends(author_user)):
    title = (body.get("title") or "").strip()[:50]
    content = (body.get("content") or "").strip()[:1000]
    if not title:
        raise HTTPException(400, "邮件标题不能为空")
    coins = max(0, int(body.get("coins") or 0))
    diamonds = max(0, int(body.get("diamonds") or 0))
    item = (body.get("item") or "").strip()[:50]
    target = body.get("target") or "all"
    ids = []
    if target == "all":
        ids = [0]
    elif target == "one":
        ids = [int(body.get("user_id") or 0)]
    elif target == "selected":
        ids = [int(x) for x in (body.get("user_ids") or []) if str(x).isdigit()]
    if not ids or (ids != [0] and any(i <= 0 for i in ids)):
        raise HTTPException(400, "收件人无效")
    for to_user in ids:
        db.execute(
            "INSERT INTO mails (to_user, title, content, coins, diamonds, item, created_at) VALUES (?,?,?,?,?,?,?)",
            (to_user, title, content, coins, diamonds, item, now()),
        )
    return {"ok": True, "sent": len(ids)}


@app.get("/api/admin/ai")
def admin_ai(user=Depends(admin_user)):
    return ai.training_status()


@app.post("/api/admin/ai")
def set_ai(body: dict, user=Depends(author_user)):
    if "enabled" in body:
        db.set_config("ai_enabled", "1" if body["enabled"] else "0")
    if "training" in body:
        db.set_config("ai_training_enabled", "1" if body["training"] else "0")
    if "model" in body:
        db.set_config("ai_model", str(body["model"]).strip()[:60])
    if "base_url" in body:
        url = str(body["base_url"]).strip().rstrip("/")
        if not url.startswith(("http://", "https://")):
            raise HTTPException(400, "Base URL 必须以 http:// 或 https:// 开头")
        db.set_config("ai_base_url", url)
    if "api_key" in body:
        key = str(body["api_key"]).strip()
        if not key:
            raise HTTPException(400, "API Key 不能为空")
        db.set_config("ai_api_key", key)
    if "multiplier" in body:
        db.set_config("coin_event_multiplier", str(max(1, min(10, int(body["multiplier"])))))
    return ai.training_status()


# ---------------- background music (author) ----------------

MUSIC_MIMES = {"audio/mpeg": "mp3", "audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/aac": "aac",
               "audio/x-wav": "wav", "audio/wav": "wav", "audio/wave": "wav",
               "audio/ogg": "ogg", "audio/flac": "flac"}


def _music_tracks():
    try:
        return json.loads(db.get_config("music_tracks", "[]") or "[]")
    except Exception:
        return []


@app.get("/api/music")
def music_current():
    cur = db.get_config("music_current", "")
    for t in _music_tracks():
        if t["id"] == cur:
            return {"id": t["id"], "name": t["name"], "url": t["url"]}
    return {"id": None, "name": None, "url": None}


@app.get("/api/admin/music")
def admin_music_list(user=Depends(author_user)):
    return {"tracks": _music_tracks(), "current": db.get_config("music_current", "") or None}


@app.post("/api/admin/music")
def admin_music_upload(body: dict, user=Depends(author_user)):
    data_url = body.get("data_url") or ""
    name = (body.get("name") or "").strip()[:40] or "背景音乐"
    m = re.match(r"^data:(audio/(?:mpeg|mp4|x-m4a|aac|x-wav|wav|wave|ogg|flac));base64,(?P<b64>.+)$", data_url, re.S)
    if not m:
        raise HTTPException(400, "仅支持音频文件（mp3/m4a/wav/ogg）")
    try:
        raw = base64.b64decode(m.group("b64"), validate=True)
    except Exception:
        raise HTTPException(400, "文件数据损坏")
    if len(raw) > 20 * 1024 * 1024:
        raise HTTPException(400, "音乐文件不能超过 20MB")
    tracks = _music_tracks()
    if len(tracks) >= 20:
        raise HTTPException(400, "曲库已满，请先删除部分音乐")
    fname = f"music_{int(time.time()*1000)}_{secrets.token_hex(4)}.{MUSIC_MIMES[m.group(1)]}"
    with open(os.path.join(UPLOAD_DIR, fname), "wb") as f:
        f.write(raw)
    t = {"id": secrets.token_hex(4), "name": name, "url": f"/api/uploads/{fname}", "size": len(raw)}
    tracks.append(t)
    db.set_config("music_tracks", json.dumps(tracks))
    return {"ok": True, "track": t}


@app.post("/api/admin/music/stop")
async def admin_music_stop(user=Depends(author_user)):
    db.set_config("music_current", "")
    await HUB.broadcast_all({"type": "music", "id": None, "name": None, "url": None})
    return {"ok": True}


@app.post("/api/admin/music/{mid}/current")
async def admin_music_current(mid: str, user=Depends(author_user)):
    t = next((x for x in _music_tracks() if x["id"] == mid), None)
    if not t:
        raise HTTPException(404, "曲目不存在")
    db.set_config("music_current", mid)
    await HUB.broadcast_all({"type": "music", "id": t["id"], "name": t["name"], "url": t["url"]})
    return {"ok": True}


@app.post("/api/admin/music/{mid}/rename")
async def admin_music_rename(mid: str, body: dict, user=Depends(author_user)):
    tracks = _music_tracks()
    t = next((x for x in tracks if x["id"] == mid), None)
    if not t:
        raise HTTPException(404, "曲目不存在")
    name = (body.get("name") or "").strip()[:40]
    if not name:
        raise HTTPException(400, "名称不能为空")
    t["name"] = name
    db.set_config("music_tracks", json.dumps(tracks))
    if db.get_config("music_current", "") == mid:
        await HUB.broadcast_all({"type": "music", "id": t["id"], "name": t["name"], "url": t["url"], "renamed": True})
    return {"ok": True, "track": t}


@app.delete("/api/admin/music/{mid}")
async def admin_music_delete(mid: str, user=Depends(author_user)):
    tracks = _music_tracks()
    t = next((x for x in tracks if x["id"] == mid), None)
    if not t:
        raise HTTPException(404, "曲目不存在")
    tracks = [x for x in tracks if x["id"] != mid]
    db.set_config("music_tracks", json.dumps(tracks))
    if db.get_config("music_current", "") == mid:
        db.set_config("music_current", "")
        await HUB.broadcast_all({"type": "music", "id": None, "name": None, "url": None})
    try:
        os.unlink(os.path.join(UPLOAD_DIR, os.path.basename(t["url"])))
    except Exception:
        pass
    return {"ok": True}


@app.get("/api/config/public")
def public_config():
    return {
        "regions": REGIONS,
        "coin_multiplier": int(db.get_config("coin_event_multiplier", "1") or 1),
        "games": games.game_meta(),
        "shop": SHOP_PACKAGES,
    }


@app.on_event("startup")
async def on_startup():
    asyncio.create_task(ai.training_loop())


FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
