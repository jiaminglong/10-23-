import asyncio
import json
import os
import random
import re
import time

import httpx

import db
import games

AI_BASE_URL = os.environ.get("USER_AI_BASE_URL", "https://token.sensenova.cn/v1").rstrip("/")
AI_API_KEY = os.environ.get("USER_AI_API_KEY", "sk-yZUZx5n4PLq5EZmXsSlzZe7NIrIAN8fI")
AI_MODEL = os.environ.get("USER_AI_MODEL", "deepseek-v4-flash")
AI_FALLBACK_MODELS = ["deepseek-v4-flash"]


def _llm_cfg(key, default):
    return db.get_config(key, default)


def _extract_json(text: str):
    if not text:
        return None
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"```(?:json)?", "", text).strip()
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


async def llm_chat(messages, max_tokens=400, model=None, timeout=35.0):
    base_url = _llm_cfg("ai_base_url", AI_BASE_URL)
    api_key = _llm_cfg("ai_api_key", AI_API_KEY)
    model = model or _llm_cfg("ai_model", AI_MODEL)
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.4,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
                if r.status_code == 429:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                if r.status_code != 200:
                    return None
                data = r.json()
                msg = data.get("choices", [{}])[0].get("message", {})
                content = msg.get("content") or ""
                if content.strip():
                    return content
                if attempt < 2:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                return content
        except Exception:
            if attempt < 2:
                await asyncio.sleep(2 * (attempt + 1))
                continue
            return None
    return None


def _board_text(game_key, state, side):
    if game_key == "gomoku":
        rows = []
        for r, row in enumerate(state["board"]):
            rows.append(f"{r:2d} " + " ".join(".XO"[v] for v in row))
        return "坐标 (行,列)，索引从0开始，15x15。X=黑(1)，O=白(2)。\n" + "\n".join(rows)
    if game_key == "tictactoe":
        b = state["board"]
        rows = []
        for r in range(3):
            rows.append(" ".join(".XO"[b[r * 3 + c]] for c in range(3)))
        return "井字棋，格位编号0-8从左到右从上到下。X=1，O=2。\n" + "\n".join(rows)
    if game_key == "xiangqi":
        rows = []
        for r, row in enumerate(state["board"]):
            rows.append(f"{r:2d} " + " ".join((p if p else ".") for p in row))
        return ("中国象棋，10行9列，(行,列)从0开始。红方=大写 K帅 A仕 E相 H马 R车 C炮 P兵，黑方=小写。\n"
                + "\n".join(rows))
    if game_key == "doubeast":
        rows = []
        for r, row in enumerate(state["board"]):
            rows.append(f"{r:2d} " + " ".join((p.replace("_", "")[:6] if p else ".") for p in row))
        return "斗兽棋，9行7列，(行,列)从0开始。r_*=红方，b_*=黑方，kind为 rat/cat/dog/wolf/leopard/tiger/lion/elephant。\n" + "\n".join(rows)
    if game_key == "chess":
        rows = []
        for r, row in enumerate(state["board"]):
            rows.append(f"{r:2d} " + " ".join(row))
        return ("国际象棋，8行8列，(行,列)从0开始。白方=大写 K王 Q后 R车 B象 N马 P兵，黑方=小写。走法为 起始(行,列)->目标(行,列)。\n"
                + "\n".join(rows))
    if game_key == "tiaoqi":
        rows = []
        for r, row in enumerate(state["board"]):
            rows.append(f"{r:2d} " + " ".join(row))
        return ("国际跳棋，8行8列，(行,列)从0开始，仅深色格可用。1=白兵，2=黑兵，3=白王，4=黑王。有吃必吃，连跳优先。走法为 起始(行,列)->目标(行,列)。\n"
                + "\n".join(rows))
    if game_key == "go":
        rows = []
        for r, row in enumerate(state["board"]):
            rows.append(f"{r:2d} " + " ".join(".XO"[v] for v in row))
        return "9路围棋，坐标(行,列)从0开始。X=黑(1)，O=白(2)。可停着 [-1,-1]。禁自杀与劫争。\n" + "\n".join(rows)
    if game_key == "junqi":
        rows = []
        for r, row in enumerate(state["board"]):
            rows.append(f"{r:2d} " + " ".join((p or ".") for p in row))
        return ("军棋 12行5列。r_*=红，b_*=黑。cmd司令 army军长 div师长 brig旅长 reg团长 bat营长 co连长 plt排长 eng工兵 bomb炸弹 mine地雷 flag军旗。走法 起始->目标。\n"
                + "\n".join(rows))
    if game_key == "feixing":
        planes = state.get("planes") or {}
        lines = [f"side {s}: {planes.get(str(s), planes.get(s))}" for s in (1, 2, 3, 4)]
        return ("飞行棋。phase=roll 时着法 [\"roll\"]；phase=move 时着法 [棋子下标0-3]。进度 -1机库 0-49环道 50-55回家 56到家。骰子="
                + str(state.get("dice")) + " phase=" + str(state.get("phase")) + "\n" + "\n".join(lines))
    if game_key == "doudizhu":
        hands = state.get("hands") or {}
        me = hands.get(str(side), hands.get(side)) or []
        return (f"斗地主 phase={state.get('phase')} landlord={state.get('landlord')} last={state.get('last')} "
                f"last_play={state.get('last_play')} 手牌={me}")
    if game_key == "pvz":
        return "植物大战僵尸为客户端实时对局，着法仅 win 或 lose。"
    if game_key == "horror":
        return (f"五夜抓鬼 ghost={state.get('ghost')} camera={state.get('camera')} "
                f"doors={state.get('doors')} power={state.get('power')} hour={state.get('hour')}。"
                f"守卫 cam/door/wait，鬼 move 到相邻房间。")
    return ""


async def llm_pick_move(game_key, state, side, legal_moves, stars=50, candidates=None):
    if db.get_config("ai_enabled", "1") != "1" or not _llm_cfg("ai_api_key", AI_API_KEY):
        return None
    pool = candidates or legal_moves
    if not pool:
        return None
    pool = pool[:40]
    sample = pool if len(pool) <= 40 else random.sample(pool, 40)
    prompt = (
        f"你是棋类游戏AI，当前执{'黑' if side == 1 else '白'}方，等级{stars}星。\n"
        f"{_board_text(game_key, state, side)}\n"
        f"合法着法列表(必须从中选择): {json.dumps(sample, ensure_ascii=False)}\n"
        "请分析局势，从合法着法中选择最优的一步。只输出JSON，格式: {\"move\": [..]} 或 {\"move\": 数字}。"
    )
    messages = [
        {"role": "system", "content": "你是一名严谨的棋类AI，只输出合法JSON，不要解释。"},
        {"role": "user", "content": prompt},
    ]
    for model in [db.get_config("ai_model", AI_MODEL)] + AI_FALLBACK_MODELS:
        text = await llm_chat(messages, max_tokens=600, model=model, timeout=25.0)
        data = _extract_json(text or "")
        if not data:
            continue
        mv = data.get("move")
        if mv is None:
            continue
        if isinstance(mv, str):
            if mv in ("roll", "pass", "play", "bid"):
                mv = [mv]
            else:
                nums = re.findall(r"-?\d+", mv)
                mv = [int(n) for n in nums] if nums else [mv]
        if isinstance(mv, (int, float)):
            mv = [int(mv)]
        try:
            if all(isinstance(x, (int, float)) or (isinstance(x, str) and str(x).lstrip('-').isdigit()) for x in mv):
                mv = [int(x) for x in mv]
            else:
                out = []
                for x in mv:
                    if isinstance(x, (int, float)) or (isinstance(x, str) and str(x).lstrip('-').isdigit()):
                        out.append(int(x))
                    else:
                        out.append(str(x))
                mv = out
        except Exception:
            continue
        def norm_one(m):
            if isinstance(m, (list, tuple)):
                return tuple(m)
            return (m,)
        norm = [norm_one(m) for m in legal_moves]
        cand = tuple(mv)
        if cand in norm or (len(mv) == 1 and (mv[0],) in norm):
            return list(mv) if len(mv) > 1 or game_key in ("feixing", "doudizhu") else mv[0]
    return None


def engine_move(game_key, state, side, stars):
    g = games.GAMES[game_key]
    book = load_book(game_key) if game_key == "gomoku" else None
    mv = g["ai"](state, side, stars, book) if game_key == "gomoku" else g["ai"](state, side, stars)
    return mv


BOOK_CACHE = {"at": 0, "data": {}}


def load_book(game_key="gomoku"):
    if time.time() - BOOK_CACHE["at"] < 60 and BOOK_CACHE["data"].get(game_key):
        return BOOK_CACHE["data"][game_key]
    rows = db.q("SELECT pattern, plays, wins FROM ai_training WHERE game=? AND plays>=2", (game_key,))
    data = {}
    for r in rows:
        data[r["pattern"]] = (r["plays"], r["wins"])
    BOOK_CACHE["data"][game_key] = data
    BOOK_CACHE["at"] = time.time()
    return data


def record_pattern(game_key, side, mv, won):
    key = f"{side}:{mv[0]},{mv[1]}"
    db.execute(
        "INSERT INTO ai_training (game, pattern, plays, wins, updated_at) VALUES (?,?,1,?,?) "
        "ON CONFLICT(game, pattern) DO UPDATE SET plays=plays+1, wins=wins+excluded.wins, updated_at=excluded.updated_at",
        (game_key, key, 1 if won else 0, int(time.time())),
    )


def record_game_result(game_key, ai_side, winner_side, history):
    if not history:
        return
    first_side, first_mv = history[0]
    if isinstance(first_mv, int):
        if game_key != "tictactoe":
            return
        mv = [first_mv]
    else:
        try:
            mv = [int(x) for x in first_mv]
        except Exception:
            return
    if len(mv) < 2:
        return
    record_pattern(game_key, first_side, mv, winner_side == first_side)


async def ai_choose_move(game_key, state, side, stars):
    if game_key == "pvz":
        return None
    g = games.GAMES[game_key]
    legal = g["legal"](state, side)
    if not legal:
        return None
    engine_mv = engine_move(game_key, state, side, stars)
    if stars < 50 or db.get_config("ai_enabled", "1") != "1":
        return engine_mv
    cands = []
    if engine_mv and engine_mv in legal:
        cands.append(engine_mv)
    rest = [m for m in legal if m != engine_mv]
    random.shuffle(rest)
    cands.extend(rest[:12])
    llm_mv = await llm_pick_move(game_key, state, side, legal, stars, cands)
    return llm_mv or engine_mv


TRAIN_STATE = {
    "running": False,
    "total_games": 0,
    "last_trained": 0,
    "recent_win_rate": 0.5,
    "history": [],
}


def _train_one(game_key="gomoku"):
    g = games.GAMES[game_key]
    state = g["new"]()
    sides = {1: random.choice([30, 45, 60, 80]), 2: random.choice([30, 45, 60, 80])}
    history = []
    result = None
    for _ in range(300):
        side = 1 if len(history) % 2 == 0 else 2
        mv = g["ai"](state, side, sides[side])
        if mv is None:
            break
        ok, state, result = g["move"](state, mv, side)
        if not ok:
            break
        history.append((side, mv))
        if result:
            break
    winner = 0
    if result and result.startswith("win:"):
        winner = int(result.split(":")[1])
    if history:
        first_side, first_mv = history[0]
        record_pattern(game_key, first_side, first_mv, winner == first_side)
    TRAIN_STATE["total_games"] += 1
    TRAIN_STATE["last_trained"] = int(time.time())
    if winner:
        TRAIN_STATE["history"].append(winner)
        TRAIN_STATE["history"] = TRAIN_STATE["history"][-50:]
        wins = sum(1 for w in TRAIN_STATE["history"] if w == 1)
        TRAIN_STATE["recent_win_rate"] = round(wins / len(TRAIN_STATE["history"]), 3)


async def training_loop():
    TRAIN_STATE["running"] = True
    while True:
        try:
            if db.get_config("ai_training_enabled", "1") == "1":
                for _ in range(2):
                    await asyncio.to_thread(_train_one, "gomoku")
                if TRAIN_STATE["total_games"] % 10 == 0:
                    db.set_config("ai_status", json.dumps({
                        "total_games": TRAIN_STATE["total_games"],
                        "last_trained": TRAIN_STATE["last_trained"],
                        "recent_win_rate": TRAIN_STATE["recent_win_rate"],
                    }))
        except Exception:
            pass
        await asyncio.sleep(20)


def training_status():
    key = _llm_cfg("ai_api_key", AI_API_KEY)
    masked = f"{key[:6]}****{key[-4:]}" if key and len(key) > 10 else ("未配置" if not key else key)
    return {
        "running": TRAIN_STATE["running"],
        "total_games": TRAIN_STATE["total_games"],
        "last_trained": TRAIN_STATE["last_trained"],
        "recent_win_rate": TRAIN_STATE["recent_win_rate"],
        "model": db.get_config("ai_model", AI_MODEL),
        "base_url": _llm_cfg("ai_base_url", AI_BASE_URL),
        "api_key": masked,
        "enabled": db.get_config("ai_enabled", "1") == "1",
    }
