"""Server-authoritative board games: gomoku, tictactoe, xiangqi, doubeast."""
import random
from collections import Counter, defaultdict

# ---------------- Gomoku ----------------

GOMOKU_SIZE = 15


def new_gomoku():
    return {"board": [[0] * GOMOKU_SIZE for _ in range(GOMOKU_SIZE)], "last": None, "moves": 0}


def _gomoku_win(board, r, c, side):
    dirs = [(1, 0), (0, 1), (1, 1), (1, -1)]
    for dr, dc in dirs:
        cnt = 1
        for s in (1, -1):
            rr, cc = r + dr * s, c + dc * s
            while 0 <= rr < GOMOKU_SIZE and 0 <= cc < GOMOKU_SIZE and board[rr][cc] == side:
                cnt += 1
                rr += dr * s
                cc += dc * s
        if cnt >= 5:
            return True
    return False


def gomoku_move(state, move, side):
    try:
        r, c = int(move[0]), int(move[1])
    except Exception:
        return False, state, None
    board = state["board"]
    if not (0 <= r < GOMOKU_SIZE and 0 <= c < GOMOKU_SIZE) or board[r][c] != 0:
        return False, state, None
    board[r][c] = side
    state["last"] = [r, c]
    state["moves"] = state.get("moves", 0) + 1
    if _gomoku_win(board, r, c, side):
        return True, state, f"win:{side}"
    if state["moves"] >= GOMOKU_SIZE * GOMOKU_SIZE:
        return True, state, "draw"
    return True, state, None


_PATTERN_SCORES = [(5, 1000000), (4, 100000), (3, 8000), (2, 400), (1, 10)]


def _gomoku_score(board, side):
    score = 0
    for r in range(GOMOKU_SIZE):
        for c in range(GOMOKU_SIZE):
            if board[r][c] != side:
                continue
            for dr, dc in ((1, 0), (0, 1), (1, 1), (1, -1)):
                pr, pc = r - dr, c - dc
                if 0 <= pr < GOMOKU_SIZE and 0 <= pc < GOMOKU_SIZE and board[pr][pc] == side:
                    continue
                run = 0
                rr, cc = r, c
                while 0 <= rr < GOMOKU_SIZE and 0 <= cc < GOMOKU_SIZE and board[rr][cc] == side:
                    run += 1
                    rr += dr
                    cc += dc
                for n, s in _PATTERN_SCORES:
                    if run >= n:
                        score += s
                        break
    return score


def _gomoku_candidates(board, radius=2):
    cands = set()
    for r in range(GOMOKU_SIZE):
        for c in range(GOMOKU_SIZE):
            if board[r][c] != 0:
                for dr in range(-radius, radius + 1):
                    for dc in range(-radius, radius + 1):
                        rr, cc = r + dr, c + dc
                        if 0 <= rr < GOMOKU_SIZE and 0 <= cc < GOMOKU_SIZE and board[rr][cc] == 0:
                            cands.add((rr, cc))
    if not cands:
        cands.add((GOMOKU_SIZE // 2, GOMOKU_SIZE // 2))
    return list(cands)


def _gomoku_ordered(board, side, opp):
    cands = _gomoku_candidates(board)
    scored = []
    for r, c in cands:
        board[r][c] = side
        attack = _gomoku_score(board, side)
        board[r][c] = opp
        defend = _gomoku_score(board, opp)
        board[r][c] = 0
        scored.append((attack * 1.1 + defend, r, c))
    scored.sort(reverse=True)
    return [(r, c) for _, r, c in scored]


def _gomoku_search(board, side, opp, depth, alpha, beta, root_side):
    if depth == 0:
        return _gomoku_score(board, root_side) - _gomoku_score(board, 3 - root_side)
    moves = _gomoku_ordered(board, side, opp)[:10]
    best = -10**9
    for r, c in moves:
        board[r][c] = side
        if _gomoku_win(board, r, c, side):
            board[r][c] = 0
            return 10**8 - depth
        val = -_gomoku_search(board, opp, side, depth - 1, -beta, -alpha, root_side)
        board[r][c] = 0
        if val > best:
            best = val
        alpha = max(alpha, val)
        if alpha >= beta:
            break
    return best


def gomoku_ai(state, side, stars=30, opening_book=None):
    board = state["board"]
    opp = 3 - side
    empty = sum(row.count(0) for row in board)
    if empty == GOMOKU_SIZE * GOMOKU_SIZE:
        return [GOMOKU_SIZE // 2, GOMOKU_SIZE // 2]
    depth = 1 if stars < 40 else (2 if stars < 75 else 2)
    noise = max(0.0, (60 - stars) / 60.0)
    moves = _gomoku_ordered(board, side, opp)
    if opening_book:
        for (r, c) in moves:
            key = f"{side}:{r},{c}"
            stat = opening_book.get(key)
            if stat and stat[0] >= 3 and stat[1] / max(1, stat[0]) > 0.55:
                return [r, c]
    best_val, best_moves = -10**9, []
    limit = 12 if depth >= 2 else 6
    for r, c in moves[:limit]:
        board[r][c] = side
        if _gomoku_win(board, r, c, side):
            board[r][c] = 0
            return [r, c]
        val = -_gomoku_search(board, opp, side, depth, -10**9, 10**9, side)
        board[r][c] = 0
        val += random.random() * noise * 20000
        if val > best_val + 1e-9:
            best_val, best_moves = val, [(r, c)]
        elif abs(val - best_val) <= 1e-9:
            best_moves.append((r, c))
    r, c = random.choice(best_moves)
    return [r, c]


def gomoku_legal(state, side):
    board = state["board"]
    return [[r, c] for r in range(GOMOKU_SIZE) for c in range(GOMOKU_SIZE) if board[r][c] == 0]


# ---------------- TicTacToe ----------------

def new_tictactoe():
    return {"board": [0] * 9, "last": None, "moves": 0}


_TTT_LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


def _ttt_winner(board):
    for a, b, c in _TTT_LINES:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return 0


def tictactoe_move(state, move, side):
    try:
        idx = int(move)
    except Exception:
        return False, state, None
    board = state["board"]
    if not (0 <= idx < 9) or board[idx] != 0:
        return False, state, None
    board[idx] = side
    state["last"] = idx
    state["moves"] = state.get("moves", 0) + 1
    w = _ttt_winner(board)
    if w:
        return True, state, f"win:{w}"
    if state["moves"] >= 9:
        return True, state, "draw"
    return True, state, None


def _ttt_minimax(board, side, me, depth=0):
    w = _ttt_winner(board)
    if w:
        return (10 - depth) if w == me else (depth - 10)
    if 0 not in board:
        return 0
    scores = []
    for i in range(9):
        if board[i] == 0:
            board[i] = side
            scores.append(_ttt_minimax(board, 3 - side, me, depth + 1))
            board[i] = 0
    return max(scores) if side == me else min(scores)


def tictactoe_ai(state, side, stars=30):
    board = state["board"]
    empties = [i for i in range(9) if board[i] == 0]
    if not empties:
        return None
    if stars < 20:
        return random.choice(empties)
    best, best_i = -100, None
    for i in empties:
        board[i] = side
        val = _ttt_minimax(board, 3 - side, side)
        board[i] = 0
        if val > best:
            best, best_i = val, i
    if best_i is None:
        best_i = random.choice(empties)
    return best_i


def tictactoe_legal(state, side):
    return [i for i in range(9) if state["board"][i] == 0]


# ---------------- Xiangqi ----------------
# board 10 rows x 9 cols. Red pieces uppercase letters: K A E H R C P, black lowercase.

XQ_INIT = [
    list("rheakaehr"),
    [""] * 9,
    ["", "c", "", "", "", "", "", "c", ""],
    ["p", "", "p", "", "p", "", "p", "", "p"],
    [""] * 9,
    [""] * 9,
    ["P", "", "P", "", "P", "", "P", "", "P"],
    ["", "C", "", "", "", "", "", "C", ""],
    [""] * 9,
    list("RHEAKAEHR"),
]

XQ_VALUES = {"K": 10000, "R": 900, "C": 450, "H": 400, "E": 200, "A": 200, "P": 100}


def new_xiangqi():
    return {"board": [row[:] for row in XQ_INIT], "last": None, "moves": 0}


def _xq_side(p):
    if not p:
        return 0
    return 1 if p.isupper() else 2


def _xq_in_palace(r, c, side):
    if not (3 <= c <= 5):
        return False
    return 7 <= r <= 9 if side == 1 else 0 <= r <= 2


def _xq_gen(board, side):
    moves = []
    for r in range(10):
        for c in range(9):
            p = board[r][c]
            if not p or _xq_side(p) != side:
                continue
            up = p.upper()
            if up == "K":
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    rr, cc = r + dr, c + dc
                    if _xq_in_palace(rr, cc, side) and _xq_side(board[rr][cc]) != side:
                        moves.append((r, c, rr, cc))
            elif up == "A":
                for dr, dc in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                    rr, cc = r + dr, c + dc
                    if _xq_in_palace(rr, cc, side) and _xq_side(board[rr][cc]) != side:
                        moves.append((r, c, rr, cc))
            elif up == "E":
                for dr, dc in ((2, 2), (2, -2), (-2, 2), (-2, -2)):
                    rr, cc = r + dr, c + dc
                    mr, mc = r + dr // 2, c + dc // 2
                    if not (0 <= rr < 10 and 0 <= cc < 9) or board[mr][mc]:
                        continue
                    if side == 1 and rr < 5:
                        continue
                    if side == 2 and rr > 4:
                        continue
                    if _xq_side(board[rr][cc]) != side:
                        moves.append((r, c, rr, cc))
            elif up == "H":
                for dr, dc, lr, lc in ((2, 1, 1, 0), (2, -1, 1, 0), (-2, 1, -1, 0), (-2, -1, -1, 0),
                                       (1, 2, 0, 1), (-1, 2, 0, 1), (1, -2, 0, -1), (-1, -2, 0, -1)):
                    rr, cc = r + dr, c + dc
                    if not (0 <= rr < 10 and 0 <= cc < 9):
                        continue
                    if board[r + lr][c + lc]:
                        continue
                    if _xq_side(board[rr][cc]) != side:
                        moves.append((r, c, rr, cc))
            elif up == "R":
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    rr, cc = r + dr, c + dc
                    while 0 <= rr < 10 and 0 <= cc < 9:
                        if board[rr][cc]:
                            if _xq_side(board[rr][cc]) != side:
                                moves.append((r, c, rr, cc))
                            break
                        moves.append((r, c, rr, cc))
                        rr += dr
                        cc += dc
            elif up == "C":
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    rr, cc = r + dr, c + dc
                    jumped = False
                    while 0 <= rr < 10 and 0 <= cc < 9:
                        target = board[rr][cc]
                        if not jumped:
                            if target:
                                jumped = True
                            else:
                                moves.append((r, c, rr, cc))
                        else:
                            if target:
                                if _xq_side(target) != side:
                                    moves.append((r, c, rr, cc))
                                break
                        rr += dr
                        cc += dc
            elif up == "P":
                forward = -1 if side == 1 else 1
                rr = r + forward
                if 0 <= rr < 10 and _xq_side(board[rr][c]) != side:
                    moves.append((r, c, rr, c))
                crossed = r <= 4 if side == 1 else r >= 5
                if crossed:
                    for dc in (1, -1):
                        cc = c + dc
                        if 0 <= cc < 9 and _xq_side(board[r][cc]) != side:
                            moves.append((r, c, r, cc))
    return moves


def _xq_find_king(board, side):
    target = "K" if side == 1 else "k"
    for r in range(10):
        for c in range(9):
            if board[r][c] == target:
                return r, c
    return None


def _xq_in_check(board, side):
    king = _xq_find_king(board, side)
    if not king:
        return True
    kr, kc = king
    for r, c, rr, cc in _xq_gen(board, 3 - side):
        if (rr, cc) == (kr, kc):
            return True
    opp_king = _xq_find_king(board, 3 - side)
    if opp_king and opp_king[1] == kc:
        r1, r2 = sorted((kr, opp_king[0]))
        if all(not board[r][kc] for r in range(r1 + 1, r2)):
            return True
    return False


def _xq_apply(board, mv):
    r, c, rr, cc = mv
    captured = board[rr][cc]
    board[rr][cc] = board[r][c]
    board[r][c] = ""
    return captured


def _xq_undo(board, mv, captured):
    r, c, rr, cc = mv
    board[r][c] = board[rr][cc]
    board[rr][cc] = captured


def xiangqi_move(state, move, side):
    try:
        mv = tuple(int(x) for x in move)
    except Exception:
        return False, state, None
    if len(mv) != 4:
        return False, state, None
    legal = _xq_gen(state["board"], side)
    if mv not in legal:
        return False, state, None
    board = state["board"]
    board = [row[:] for row in board]
    captured = _xq_apply(board, mv)
    if _xq_in_check(board, side):
        return False, state, None
    state["board"] = board
    state["last"] = list(mv)
    state["moves"] = state.get("moves", 0) + 1
    opp = 3 - side
    if captured.upper() == "K":
        return True, state, f"win:{side}"
    opp_moves = [m for m in _xq_gen(board, opp) if not _xq_after_check(board, m, opp)]
    if not opp_moves:
        return True, state, f"win:{side}"
    return True, state, None


def _xq_after_check(board, mv, side):
    b = [row[:] for row in board]
    _xq_apply(b, mv)
    return _xq_in_check(b, side)


def _xq_eval(board, side):
    total = 0
    for r in range(10):
        for c in range(9):
            p = board[r][c]
            if not p:
                continue
            val = XQ_VALUES.get(p.upper(), 0)
            total += val if _xq_side(p) == side else -val
    return total


def _xq_search(board, side, depth, alpha, beta, root):
    if depth == 0:
        return _xq_eval(board, root)
    moves = _xq_gen(board, side)
    moves.sort(key=lambda m: XQ_VALUES.get((board[m[2]][m[3]] or " ").upper(), 0), reverse=True)
    best = -10**9
    for mv in moves:
        captured = _xq_apply(board, mv)
        if _xq_in_check(board, side):
            _xq_undo(board, mv, captured)
            continue
        val = -_xq_search(board, 3 - side, depth - 1, -beta, -alpha, root)
        _xq_undo(board, mv, captured)
        if val > best:
            best = val
        alpha = max(alpha, val)
        if alpha >= beta:
            break
    return best if best > -10**9 else -10**6


def xiangqi_ai(state, side, stars=30):
    board = [row[:] for row in state["board"]]
    moves = _xq_gen(board, side)
    if not moves:
        return None
    import random as _r

    scored = []
    for mv in moves:
        captured = _xq_apply(board, mv)
        if _xq_in_check(board, side):
            _xq_undo(board, mv, captured)
            continue
        gain = XQ_VALUES.get(captured.upper(), 0) if captured else 0
        _xq_undo(board, mv, captured)
        scored.append((gain, mv))
    scored.sort(key=lambda x: x[0], reverse=True)
    depth = 1 if stars < 50 else 2
    if stars >= 85:
        depth = 2
    noise = max(0.0, (70 - stars) / 70.0)
    best_val, best = -10**9, None
    pool = scored[:14] if depth >= 2 else scored[:8]
    for gain, mv in pool:
        captured = _xq_apply(board, mv)
        if _xq_in_check(board, side):
            _xq_undo(board, mv, captured)
            continue
        val = -_xq_search(board, 3 - side, depth, -10**9, 10**9, side)
        _xq_undo(board, mv, captured)
        val += gain + random.random() * noise * 300
        if val > best_val:
            best_val, best = val, mv
    return list(best or moves[0])


def xiangqi_legal(state, side):
    board = state["board"]
    out = []
    for mv in _xq_gen(board, side):
        b = [row[:] for row in board]
        _xq_apply(b, mv)
        if not _xq_in_check(b, side):
            out.append(list(mv))
    return out


# ---------------- Doubeast (Jungle chess) ----------------
# 7 cols x 9 rows. Black (2) top, Red (1) bottom.
# pieces: rank values. r/R rat=1, cat=2, dog=3, wolf=4, leopard=5, tiger=6, lion=7, elephant=8
DB_INIT = [
    ["b_lion", "", "", "", "", "", "b_tiger"],
    ["", "b_dog", "", "", "", "b_cat", ""],
    ["b_rat", "", "b_leopard", "", "b_wolf", "", "b_elephant"],
    ["", "", "", "", "", "", ""],
    ["", "", "", "", "", "", ""],
    ["", "", "", "", "", "", ""],
    ["r_elephant", "", "r_wolf", "", "r_leopard", "", "r_rat"],
    ["", "r_cat", "", "", "", "r_dog", ""],
    ["r_tiger", "", "", "", "", "", "r_lion"],
]
DB_RANK = {"rat": 1, "cat": 2, "dog": 3, "wolf": 4, "leopard": 5, "tiger": 6, "lion": 7, "elephant": 8}
DB_RIVERS = {(3, 1), (3, 2), (3, 4), (3, 5), (4, 1), (4, 2), (4, 4), (4, 5), (5, 1), (5, 2), (5, 4), (5, 5)}
DB_TRAPS = {(0, 2), (0, 4), (1, 3), (8, 2), (8, 4), (7, 3)}
DB_DENS = {(0, 3): 2, (8, 3): 1}


def new_doubeast():
    return {"board": [row[:] for row in DB_INIT], "last": None, "moves": 0}


def _db_side(p):
    return 1 if p.startswith("r_") else 2


def _db_kind(p):
    return p.split("_", 1)[1]


def _db_can_capture(attacker, defender, atk_r, atk_c, def_r, def_c):
    if not attacker or not defender or _db_side(attacker) == _db_side(defender):
        return False
    ak, dk = _db_kind(attacker), _db_kind(defender)
    arank, drank = DB_RANK[ak], DB_RANK[dk]
    if (def_r, def_c) in DB_TRAPS:
        trap_owner = 2 if def_r <= 1 else 1
        if _db_side(defender) != trap_owner:
            return True
    if ak == "rat" and dk == "elephant":
        return True
    if ak == "elephant" and dk == "rat":
        return False
    in_water_atk = (atk_r, atk_c) in DB_RIVERS
    in_water_def = (def_r, def_c) in DB_RIVERS
    if in_water_atk and not in_water_def:
        return False
    if in_water_def and not in_water_atk:
        return False
    return arank >= drank


def _db_moves_from(board, r, c):
    p = board[r][c]
    if not p:
        return []
    side = _db_side(p)
    kind = _db_kind(p)
    out = []
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        rr, cc = r + dr, c + dc
        if not (0 <= rr < 9 and 0 <= cc < 7):
            continue
        target = board[rr][cc]
        if target and _db_side(target) == side:
            continue
        in_water_atk = (r, c) in DB_RIVERS
        in_water_dst = (rr, cc) in DB_RIVERS
        if in_water_dst and kind not in ("rat", "lion", "tiger"):
            continue
        if DB_DENS.get((rr, cc)) == side:
            continue
        if _db_can_capture(p, target, r, c, rr, cc):
            out.append((r, c, rr, cc))
        elif not target:
            out.append((r, c, rr, cc))
    if kind in ("lion", "tiger"):
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            steps = 0
            blocked = False
            while 0 <= rr < 9 and 0 <= cc < 7 and (rr, cc) in DB_RIVERS:
                if board[rr][cc] == "":
                    pass
                elif _db_kind(board[rr][cc]) == "rat":
                    blocked = True
                    break
                else:
                    blocked = True
                    break
                rr += dr
                cc += dc
                steps += 1
            if steps and not blocked and 0 <= rr < 9 and 0 <= cc < 7:
                target = board[rr][cc]
                if DB_DENS.get((rr, cc)) == side:
                    continue
                if not target:
                    out.append((r, c, rr, cc))
                elif _db_can_capture(p, target, r, c, rr, cc):
                    out.append((r, c, rr, cc))
    return out


def _db_gen(board, side):
    moves = []
    for r in range(9):
        for c in range(7):
            if board[r][c] and _db_side(board[r][c]) == side:
                moves.extend(_db_moves_from(board, r, c))
    return moves


def doubeast_move(state, move, side):
    try:
        mv = tuple(int(x) for x in move)
    except Exception:
        return False, state, None
    board = [row[:] for row in state["board"]]
    if mv not in _db_gen(board, side):
        return False, state, None
    r, c, rr, cc = mv
    target = board[rr][cc]
    board[rr][cc] = board[r][c]
    board[r][c] = ""
    state["board"] = board
    state["last"] = list(mv)
    state["moves"] = state.get("moves", 0) + 1
    if DB_DENS.get((rr, cc)) == 3 - side:
        return True, state, f"win:{side}"
    if target and _db_kind(target) == "lion" and _db_side(target) != side:
        pass
    opp = 3 - side
    if not any(board[r2][c2] and _db_side(board[r2][c2]) == opp for r2 in range(9) for c2 in range(7)):
        return True, state, f"win:{side}"
    if not _db_gen(board, opp):
        return True, state, f"win:{side}"
    return True, state, None


def _db_eval(board, side):
    score = 0
    for r in range(9):
        for c in range(7):
            p = board[r][c]
            if not p:
                continue
            s = _db_side(p)
            val = DB_RANK[_db_kind(p)] * 100
            if s == side:
                score += val + (8 - r if side == 1 else r)
            else:
                score -= val + (r if side == 1 else 8 - r)
    return score


def doubeast_ai(state, side, stars=30):
    board = [row[:] for row in state["board"]]
    moves = _db_gen(board, side)
    if not moves:
        return None
    depth = 1 if stars < 55 else 2
    noise = max(0.0, (60 - stars) / 60.0)
    best_val, best = -10**9, None
    for mv in moves:
        r, c, rr, cc = mv
        target = board[rr][cc]
        board[rr][cc] = board[r][c]
        board[r][c] = ""
        if DB_DENS.get((rr, cc)) == 3 - side:
            board[r][c] = board[rr][cc]
            board[rr][cc] = target
            return list(mv)
        val = -_db_eval(board, 3 - side)
        board[r][c] = board[rr][cc]
        board[rr][cc] = target
        val += random.random() * noise * 60
        if val > best_val:
            best_val, best = val, mv
    return list(best or moves[0])


def doubeast_legal(state, side):
    return [list(m) for m in _db_gen(state["board"], side)]


# ---------------- Registry ----------------

# ---------------- Chess (国际象棋) ----------------
# 8x8. board[r][c]: uppercase = white(1), lowercase = black(2).
# K=King Q=Queen R=Rook B=Bishop N=Knight P=Pawn ('.' empty)
CHESS_INIT = [
    list("rnbqkbnr"),
    list("pppppppp"),
    ['.'] * 8,
    ['.'] * 8,
    ['.'] * 8,
    ['.'] * 8,
    list("PPPPPPPP"),
    list("RNBQKBNR"),
]
CHESS_VALUES = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 20000}


def new_chess():
    return {"board": [row[:] for row in CHESS_INIT], "last": None, "moves": 0}


def _ch_side(p):
    if not p or p == '.':
        return 0
    return 1 if p.isupper() else 2


def _ch_in_bounds(r, c):
    return 0 <= r < 8 and 0 <= c < 8


def _ch_sliding(board, r, c, dirs, side, out, stop_at=None):
    for dr, dc in dirs:
        rr, cc = r + dr, c + dc
        while _ch_in_bounds(rr, cc):
            t = board[rr][cc]
            if t == '.':
                out.append((rr, cc))
            elif _ch_side(t) != side:
                out.append((rr, cc))
                break
            else:
                break
            rr += dr
            cc += dc


def _ch_gen_moves(board, r, c):
    p = board[r][c]
    if p == '.':
        return []
    side = _ch_side(p)
    up = p.upper()
    out = []
    def push(rr, cc):
        if _ch_in_bounds(rr, cc) and _ch_side(board[rr][cc]) != side:
            out.append((rr, cc))
    if up == "P":
        # white moves up (decreasing r), black down
        dr = -1 if side == 1 else 1
        start_r = 6 if side == 1 else 1
        rr = r + dr
        if _ch_in_bounds(rr, c) and board[rr][c] == '.':
            push(rr, c)
            if r == start_r and board[r + 2 * dr][c] == '.':
                push(r + 2 * dr, c)
        for dc in (-1, 1):
            rr, cc = r + dr, c + dc
            if _ch_in_bounds(rr, cc) and board[rr][cc] != '.' and _ch_side(board[rr][cc]) != side:
                push(rr, cc)
    elif up == "N":
        for dr, dc in ((2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)):
            push(r + dr, c + dc)
    elif up == "K":
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            push(r + dr, c + dc)
    elif up == "R":
        _ch_sliding(board, r, c, ((1, 0), (-1, 0), (0, 1), (0, -1)), side, out)
    elif up == "B":
        _ch_sliding(board, r, c, ((1, 1), (1, -1), (-1, 1), (-1, -1)), side, out)
    elif up == "Q":
        _ch_sliding(board, r, c, ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)), side, out)
    return out


def _ch_find_king(board, side):
    k = "K" if side == 1 else "k"
    for r in range(8):
        for c in range(8):
            if board[r][c] == k:
                return (r, c)
    return None


def _ch_in_check(board, side):
    king = _ch_find_king(board, side)
    if not king:
        return True
    kr, kc = king
    opp = 3 - side
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p == '.' or _ch_side(p) != opp:
                continue
            for (rr, cc) in _ch_gen_moves(board, r, c):
                if rr == kr and cc == kc:
                    return True
    return False


def _ch_apply(board, mv):
    (fr, fc, tr, tc) = mv
    captured = board[tr][tc]
    board[tr][tc] = board[fr][fc]
    board[fr][fc] = "."
    return captured


def _ch_undo(board, mv, captured):
    (fr, fc, tr, tc) = mv
    board[fr][fc] = board[tr][tc]
    board[tr][tc] = captured


def _ch_gen_all(board, side, legal_only=True):
    out = []
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p == '.' or _ch_side(p) != side:
                continue
            for (tr, tc) in _ch_gen_moves(board, r, c):
                mv = (r, c, tr, tc)
                if not legal_only:
                    out.append(mv)
                    continue
                b = [row[:] for row in board]
                _ch_apply(b, mv)
                if not _ch_in_check(b, side):
                    out.append(mv)
    return out


def chess_move(state, move, side):
    try:
        mv = tuple(int(x) for x in move)
    except Exception:
        return False, state, None
    if len(mv) != 4:
        return False, state, None
    board = state["board"]
    fr, fc, tr, tc = mv
    if not _ch_in_bounds(fr, fc) or not _ch_in_bounds(tr, tc):
        return False, state, None
    p = board[fr][fc]
    if p == '.' or _ch_side(p) != side:
        return False, state, None
    if (tr, tc) not in _ch_gen_moves(board, fr, fc):
        return False, state, None
    b = [row[:] for row in board]
    captured = _ch_apply(b, mv)
    if _ch_in_check(b, side):
        return False, state, None
    # Pawn promotion to queen at last rank
    pp = b[tr][tc]
    if pp == "P" and tr == 0:
        b[tr][tc] = "Q"
    elif pp == "p" and tr == 7:
        b[tr][tc] = "q"
    state["board"] = b
    state["last"] = list(mv)
    state["moves"] = state.get("moves", 0) + 1
    opp = 3 - side
    if captured.lower() == "k":
        return True, state, f"win:{side}"
    if _ch_in_check(b, opp) and not _ch_gen_all(b, opp):
        return True, state, f"win:{side}"
    if not _ch_gen_all(b, opp):
        return True, state, f"draw"
    return True, state, None


def _ch_eval(board, side):
    total = 0
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p == '.':
                continue
            val = CHESS_VALUES.get(p.upper(), 0)
            total += val if _ch_side(p) == side else -val
    return total


def _ch_search(board, side, depth, alpha, beta, root):
    if depth == 0:
        return _ch_eval(board, root)
    moves = _ch_gen_all(board, side)
    if not moves:
        return -10**9
    moves.sort(key=lambda m: CHESS_VALUES.get((board[m[2]][m[3]] or ".").upper(), 0), reverse=True)
    best = -10**9
    for mv in moves[:24]:
        captured = _ch_apply(board, mv)
        val = -_ch_search(board, 3 - side, depth - 1, -beta, -alpha, root)
        _ch_undo(board, mv, captured)
        if val > best:
            best = val
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break
    return best


def chess_ai(state, side, stars=30):
    board = [row[:] for row in state["board"]]
    moves = _ch_gen_all(board, side)
    if not moves:
        return None
    scored = []
    for mv in moves:
        b = [row[:] for row in board]
        captured = _ch_apply(b, mv)
        gain = CHESS_VALUES.get(captured.upper(), 0) if captured != '.' else 0
        _ch_undo(b, mv, captured)
        scored.append((gain, mv))
    scored.sort(key=lambda x: x[0], reverse=True)
    depth = 1 if stars < 45 else (2 if stars < 80 else 2)
    noise = max(0.0, (60 - stars) / 60.0)
    best_val, best = -10**9, None
    pool = scored[:16]
    for gain, mv in pool:
        b = [row[:] for row in board]
        _ch_apply(b, mv)
        val = -_ch_search(b, 3 - side, depth, -10**9, 10**9, side)
        val += gain + random.random() * noise * 500
        if val > best_val:
            best_val, best = val, mv
    return list(best or scored[0][1])


def chess_legal(state, side):
    return [list(mv) for mv in _ch_gen_all(state["board"], side)]


# ---------------- Checkers (国际跳棋) ----------------
# 8x8, only dark squares used. Black(2) top rows 0-2, White(1) bottom rows 5-7.
# board[r][c]: 1=white man, 2=black man, 3=white king, 4=black king, '.' empty
CHECKERS_INIT = [
    ['.', '2', '.', '2', '.', '2', '.', '2'],
    ['2', '.', '2', '.', '2', '.', '2', '.'],
    ['.', '2', '.', '2', '.', '2', '.', '2'],
    ['.'] * 8,
    ['.'] * 8,
    ['1', '.', '1', '.', '1', '.', '1', '.'],
    ['.', '1', '.', '1', '.', '1', '.', '1'],
    ['1', '.', '1', '.', '1', '.', '1', '.'],
]


def new_checkers():
    return {"board": [row[:] for row in CHECKERS_INIT], "last": None, "moves": 0}


def _ck_side(p):
    if p == '1' or p == '3':
        return 1
    if p == '2' or p == '4':
        return 2
    return 0


def _ck_is_king(p):
    return p == '3' or p == '4'


def _ck_dark(r, c):
    return (r + c) % 2 == 1


def _ck_jumps(board, r, c, side, path, out, captured_set):
    p = board[r][c]
    king = _ck_is_king(p)
    dirs = [(1, -1), (1, 1), (-1, -1), (-1, 1)] if king else ([( -1, -1), (-1, 1)] if side == 1 else [(1, -1), (1, 1)])
    jumped = False
    for dr, dc in dirs:
        mr, mc = r + dr, c + dc
        lr, lc = r + 2 * dr, c + 2 * dc
        if not _ck_in_bounds(lr, lc) or not _ck_dark(lr, lc):
            continue
        mid = board[mr][mc]
        if mid == '.' or _ck_side(mid) == side:
            continue
        if (mr, mc) in captured_set:
            continue
        if board[lr][lc] != '.':
            continue
        captured_set.add((mr, mc))
        board[lr][lc] = board[r][c]
        board[r][c] = '.'
        board[mr][mc] = '.'
        new_path = path + [(lr, lc)]
        further = _ck_jumps(board, lr, lc, side, new_path, out, captured_set)
        if not further:
            out.append(new_path)
        board[mr][mc] = mid
        board[r][c] = p
        board[lr][lc] = '.'
        captured_set.discard((mr, mc))
        jumped = True
    return jumped


def _ck_in_bounds(r, c):
    return 0 <= r < 8 and 0 <= c < 8


def _ck_gen_moves(board, r, c):
    p = board[r][c]
    if p == '.':
        return []
    side = _ck_side(p)
    king = _ck_is_king(p)
    out = []
    dirs = [(1, -1), (1, 1), (-1, -1), (-1, 1)] if king else ([( -1, -1), (-1, 1)] if side == 1 else [(1, -1), (1, 1)])
    for dr, dc in dirs:
        rr, cc = r + dr, c + dc
        if _ck_in_bounds(rr, cc) and _ck_dark(rr, cc) and board[rr][cc] == '.':
            out.append((r, c, rr, cc))
    return out


def _ck_all_jump_paths(board, side):
    paths = []
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p == '.' or _ck_side(p) != side:
                continue
            _ck_jumps([row[:] for row in board], r, c, side, [(r, c)], paths, set())
    return paths


def checkers_legal(state, side):
    board = state["board"]
    paths = _ck_all_jump_paths(board, side)
    if paths:
        return [[p[0][0], p[0][1], p[-1][0], p[-1][1]] for p in paths]  # (fr,fc,tr,tc) simple moves for UI
    out = []
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p == '.' or _ck_side(p) != side:
                continue
            for mv in _ck_gen_moves(board, r, c):
                out.append(list(mv))
    return out


def _ck_best_jump(paths):
    # longest path wins (most captures); tie-break by final row (promotion)
    if not paths:
        return None
    paths.sort(key=lambda p: (len(p) - 1, -p[-1][0]), reverse=True)
    return paths[0]


def _ck_apply_jump(board, path):
    """Apply multi-capture jump path: path is list of (r,c) from start to end."""
    captures = 0
    board = [row[:] for row in board]
    for i in range(len(path) - 1):
        r, c = path[i]
        nr, nc = path[i + 1]
        mr, mc = (r + nr) // 2, (c + nc) // 2
        board[mr][mc] = '.'
        board[nr][nc] = board[r][c]
        board[r][c] = '.'
        captures += 1
    return board, captures


def _ck_promote(board, r, c):
    p = board[r][c]
    if p == '1' and r == 0:
        board[r][c] = '3'
    elif p == '2' and r == 7:
        board[r][c] = '4'


def checkers_move(state, move, side):
    try:
        mv = [int(x) for x in move]
    except Exception:
        return False, state, None
    board = state["board"]
    fr, fc = mv[0], mv[1]
    tr, tc = mv[-2], mv[-1]
    if not _ck_in_bounds(fr, fc) or not _ck_in_bounds(tr, tc):
        return False, state, None
    p = board[fr][fc]
    if p == '.' or _ck_side(p) != side:
        return False, state, None
    # jumps mandatory
    paths = _ck_all_jump_paths(board, side)
    if paths:
        match = None
        for path in paths:
            if path[0] == (fr, fc) and path[-1] == (tr, tc):
                # verify capture count same as provided path length
                match = path
                break
        if match is None:
            return False, state, None
        nb, captures = _ck_apply_jump(board, match)
    else:
        if len(mv) != 4:
            return False, state, None
        simple = _ck_gen_moves(board, fr, fc)
        if not any(m[2] == tr and m[3] == tc for m in simple):
            return False, state, None
        nb = [row[:] for row in board]
        nb[tr][tc] = nb[fr][fc]
        nb[fr][fc] = '.'
    _ck_promote(nb, tr, tc)
    state["board"] = nb
    state["last"] = [fr, fc, tr, tc]
    state["moves"] = state.get("moves", 0) + 1
    opp = 3 - side
    opp_pieces = any(_ck_side(board[r][c]) == opp for r in range(8) for c in range(8))
    if not opp_pieces:
        return True, state, f"win:{side}"
    opp_moves = checkers_legal(state, opp)
    if not opp_moves:
        return True, state, f"win:{side}"
    return True, state, None


def _ck_eval(board, side):
    total = 0
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p == '.':
                continue
            s = _ck_side(p)
            v = 4 if _ck_is_king(p) else 2
            # positional: advancing rows slightly better
            v += 0.1 * ((7 - r) if s == 1 else r)
            total += v if s == side else -v
    return total


def _ck_search(board, side, depth, alpha, beta, root):
    if depth == 0:
        return _ck_eval(board, root)
    paths = _ck_all_jump_paths(board, side)
    if paths:
        moves = paths
    else:
        moves = []
        for r in range(8):
            for c in range(8):
                p = board[r][c]
                if p == '.' or _ck_side(p) != side:
                    continue
                for mv in _ck_gen_moves(board, r, c):
                    moves.append([(r, c), (mv[2], mv[3])])
    if not moves:
        return -10**9
    best = -10**9
    for path in moves[:16]:
        b = [row[:] for row in board]
        if isinstance(path[0], tuple):
            _ck_apply_jump(b, path)
            end = path[-1]
        else:
            (fr, fc), (tr, tc) = path
            b[tr][tc] = b[fr][fc]
            b[fr][fc] = '.'
            _ck_promote(b, tr, tc)
            end = (tr, tc)
        val = -_ck_search(b, 3 - side, depth - 1, -beta, -alpha, root)
        if val > best:
            best = val
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break
    return best


def checkers_ai(state, side, stars=30):
    board = state["board"]
    paths = _ck_all_jump_paths(board, side)
    if paths:
        best = max(paths, key=lambda q: len(q) - 1)
        return [best[0][0], best[0][1], best[-1][0], best[-1][1]]
    moves = []
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p == '.' or _ck_side(p) != side:
                continue
            for mv in _ck_gen_moves(board, r, c):
                moves.append(mv)
    if not moves:
        return None
    depth = 2 if stars >= 50 else 1
    noise = max(0.0, (60 - stars) / 60.0)
    best_val, best = -10**9, None
    for mv in moves[:16]:
        b = [row[:] for row in board]
        b[mv[2]][mv[3]] = b[mv[0]][mv[1]]
        b[mv[0]][mv[1]] = '.'
        _ck_promote(b, mv[2], mv[3])
        val = -_ck_search(b, 3 - side, depth, -10**9, 10**9, side) + random.random() * noise * 6
        if val > best_val:
            best_val, best = val, mv
    return list(best or moves[0])


# ---------------- Go 9-road ----------------

GO_SIZE = 9
GO_KOMI = 6.5


def new_go():
    return {"board": [[0] * GO_SIZE for _ in range(GO_SIZE)], "last": None, "moves": 0, "passes": 0, "ko": None}


def _go_neighbors(r, c):
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        rr, cc = r + dr, c + dc
        if 0 <= rr < GO_SIZE and 0 <= cc < GO_SIZE:
            yield rr, cc


def _go_group(board, r, c):
    color = board[r][c]
    if color == 0:
        return set(), set()
    stack = [(r, c)]
    seen = {(r, c)}
    libs = set()
    while stack:
        cr, cc = stack.pop()
        for nr, nc in _go_neighbors(cr, cc):
            v = board[nr][nc]
            if v == 0:
                libs.add((nr, nc))
            elif v == color and (nr, nc) not in seen:
                seen.add((nr, nc))
                stack.append((nr, nc))
    return seen, libs


def _go_try_place(board, r, c, side, ko):
    if not (0 <= r < GO_SIZE and 0 <= c < GO_SIZE) or board[r][c] != 0:
        return None
    if ko and list(ko) == [r, c]:
        return None
    b = [row[:] for row in board]
    b[r][c] = side
    opp = 3 - side
    captured = []
    for nr, nc in _go_neighbors(r, c):
        if b[nr][nc] == opp:
            grp, libs = _go_group(b, nr, nc)
            if not libs:
                captured.extend(grp)
    for cr, cc in captured:
        b[cr][cc] = 0
    grp, libs = _go_group(b, r, c)
    if not libs:
        return None
    ko_pt = None
    if len(captured) == 1 and len(grp) == 1:
        ko_pt = list(captured[0])
    return b, ko_pt, captured


def _go_area_score(board):
    area = {1: 0, 2: 0}
    seen = [[False] * GO_SIZE for _ in range(GO_SIZE)]
    for r in range(GO_SIZE):
        for c in range(GO_SIZE):
            if board[r][c]:
                area[board[r][c]] += 1
            elif not seen[r][c]:
                stack = [(r, c)]
                cells = 0
                border = set()
                seen[r][c] = True
                while stack:
                    cr, cc = stack.pop()
                    cells += 1
                    for nr, nc in _go_neighbors(cr, cc):
                        v = board[nr][nc]
                        if v == 0 and not seen[nr][nc]:
                            seen[nr][nc] = True
                            stack.append((nr, nc))
                        elif v:
                            border.add(v)
                if len(border) == 1:
                    area[next(iter(border))] += cells
    return area[1], area[2] + GO_KOMI


def _go_score_result(state):
    s1, s2 = _go_area_score(state["board"])
    return "win:1" if s1 > s2 else "win:2"


def go_move(state, move, side):
    try:
        mv = [int(x) for x in move]
    except Exception:
        return False, state, None
    if len(mv) != 2:
        return False, state, None
    r, c = mv
    if r == -1 and c == -1:
        state["passes"] = state.get("passes", 0) + 1
        state["last"] = [-1, -1]
        state["moves"] = state.get("moves", 0) + 1
        state["ko"] = None
        if state["passes"] >= 2:
            return True, state, _go_score_result(state)
        return True, state, None
    placed = _go_try_place(state["board"], r, c, side, state.get("ko"))
    if not placed:
        return False, state, None
    board, ko_pt, _ = placed
    state["board"] = board
    state["last"] = [r, c]
    state["moves"] = state.get("moves", 0) + 1
    state["passes"] = 0
    state["ko"] = ko_pt
    return True, state, None


def go_legal(state, side):
    out = [[-1, -1]]
    ko = state.get("ko")
    board = state["board"]
    for r in range(GO_SIZE):
        for c in range(GO_SIZE):
            if board[r][c] == 0 and _go_try_place(board, r, c, side, ko):
                out.append([r, c])
    return out


def go_ai(state, side, stars=30):
    legal = [m for m in go_legal(state, side) if m != [-1, -1]]
    if not legal:
        return [-1, -1]
    board = state["board"]
    opp = 3 - side
    scored = []
    for r, c in legal:
        placed = _go_try_place(board, r, c, side, state.get("ko"))
        cap = len(placed[2]) if placed else 0
        neigh = sum(1 for nr, nc in _go_neighbors(r, c) if board[nr][nc] == side)
        threat = sum(1 for nr, nc in _go_neighbors(r, c) if board[nr][nc] == opp)
        center = -abs(r - 4) - abs(c - 4)
        scored.append((cap * 50 + neigh * 3 + threat * 2 + center + random.random(), r, c))
    scored.sort(reverse=True)
    pick = scored[: max(1, 8 - stars // 20)]
    _, r, c = random.choice(pick) if stars < 40 else scored[0]
    return [r, c]


# ---------------- Junqi (two-player land battle) ----------------
# 12x5. Black(2) top rows 0-5, Red(1) bottom rows 6-11.
# Camps cannot be attacked. Railroads: rows 1/5/6/10 and cols 0/4.

JQ_CAMPS = {(2, 1), (2, 3), (4, 1), (4, 3), (7, 1), (7, 3), (9, 1), (9, 3)}
JQ_RAIL_ROWS = {1, 5, 6, 10}
JQ_RAIL_COLS = {0, 4}
JQ_RANK = {
    "flag": 0, "mine": 0, "eng": 1, "plt": 2, "co": 3, "bat": 4, "reg": 5,
    "brig": 6, "div": 7, "army": 8, "cmd": 9, "bomb": 10,
}
JQ_KINDS = ("cmd", "army", "div", "brig", "reg", "bat", "co", "plt", "eng", "bomb", "mine", "flag")


def _jq_layout(prefix):
    """25 pieces + 5 camp holes on a 6x5 half-board, camps at (2,1)(2,3)(4,1)(4,3)."""
    rows = [
        ["cmd", "flag", "army", "div", "div"],
        ["brig", "brig", "reg", "reg", "bat"],
        ["bat", "", "co", "", "co"],
        ["co", "plt", "plt", "plt", "eng"],
        ["eng", "", "eng", "", "bomb"],
        ["mine", "mine", "mine", "bomb", ""],
    ]
    return [[(prefix + k if k else "") for k in row] for row in rows]


def new_junqi():
    top = _jq_layout("b_")
    bot = _jq_layout("r_")
    bot.reverse()
    board = top + bot
    return {"board": board, "last": None, "moves": 0, "revealed": []}


def _jq_side(p):
    if not p or p == "?":
        return 0
    return 1 if p.startswith("r_") else 2


def _jq_kind(p):
    return p.split("_", 1)[1] if p and "_" in p else ""


def _jq_on_rail(r, c):
    return r in JQ_RAIL_ROWS or c in JQ_RAIL_COLS


def _jq_inb(r, c):
    return 0 <= r < 12 and 0 <= c < 5


def _jq_combat(atk, dfn):
    if not atk or not dfn:
        return "atk"
    ak, dk = _jq_kind(atk), _jq_kind(dfn)
    if ak in ("mine", "flag"):
        return None
    if ak == "bomb" or dk == "bomb":
        return "both"
    if dk == "mine":
        return "atk" if ak == "eng" else "dfn"
    if dk == "flag":
        return "atk"
    ra, rd = JQ_RANK.get(ak, 0), JQ_RANK.get(dk, 0)
    if ra > rd:
        return "atk"
    if ra < rd:
        return "dfn"
    return "both"


def _jq_can_step(board, r, c, rr, cc, side):
    if not _jq_inb(rr, cc):
        return False
    t = board[rr][cc]
    if t and _jq_side(t) == side:
        return False
    if t and (rr, cc) in JQ_CAMPS:
        return False
    return True


def _jq_moves_from(board, r, c):
    p = board[r][c]
    if not p:
        return []
    kind = _jq_kind(p)
    if kind in ("mine", "flag"):
        return []
    side = _jq_side(p)
    out = []
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        rr, cc = r + dr, c + dc
        if _jq_can_step(board, r, c, rr, cc, side):
            out.append((r, c, rr, cc))
    if _jq_on_rail(r, c):
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            while _jq_inb(rr, cc) and _jq_on_rail(rr, cc):
                t = board[rr][cc]
                if t:
                    if _jq_side(t) != side and (rr, cc) not in JQ_CAMPS:
                        out.append((r, c, rr, cc))
                    break
                out.append((r, c, rr, cc))
                rr += dr
                cc += dc
    # unique
    seen, uniq = set(), []
    for mv in out:
        if mv not in seen:
            seen.add(mv)
            uniq.append(mv)
    return uniq


def _jq_gen(board, side):
    moves = []
    for r in range(12):
        for c in range(5):
            p = board[r][c]
            if p and _jq_side(p) == side:
                moves.extend(_jq_moves_from(board, r, c))
    return moves


def _jq_apply(board, mv, revealed):
    r, c, rr, cc = mv
    atk = board[r][c]
    dfn = board[rr][cc]
    board[r][c] = ""
    if dfn:
        key_a, key_b = f"{r},{c}", f"{rr},{cc}"
        if key_a not in revealed:
            revealed.append(key_a)
        if key_b not in revealed:
            revealed.append(key_b)
        res = _jq_combat(atk, dfn)
        if res == "atk":
            board[rr][cc] = atk
        elif res == "dfn":
            board[rr][cc] = dfn
        else:
            board[rr][cc] = ""
        return dfn, res
    board[rr][cc] = atk
    return None, "atk"


def junqi_move(state, move, side):
    try:
        mv = tuple(int(x) for x in move)
    except Exception:
        return False, state, None
    if len(mv) != 4:
        return False, state, None
    board = [row[:] for row in state["board"]]
    if mv not in _jq_gen(board, side):
        return False, state, None
    revealed = list(state.get("revealed") or [])
    dfn, _res = _jq_apply(board, mv, revealed)
    state["board"] = board
    state["last"] = list(mv)
    state["moves"] = state.get("moves", 0) + 1
    state["revealed"] = revealed
    if dfn and _jq_kind(dfn) == "flag":
        return True, state, f"win:{side}"
    opp = 3 - side
    if not any(board[r][c] and _jq_side(board[r][c]) == opp and _jq_kind(board[r][c]) == "flag"
               for r in range(12) for c in range(5)):
        return True, state, f"win:{side}"
    if not _jq_gen(board, opp):
        return True, state, f"win:{side}"
    return True, state, None


def junqi_legal(state, side):
    return [list(mv) for mv in _jq_gen(state["board"], side)]


def junqi_ai(state, side, stars=30):
    moves = _jq_gen(state["board"], side)
    if not moves:
        return None
    board = state["board"]
    scored = []
    for mv in moves:
        t = board[mv[2]][mv[3]]
        gain = 0
        if t:
            k = _jq_kind(t)
            gain = 200 if k == "flag" else (80 if k == "cmd" else JQ_RANK.get(k, 1) * 4)
        scored.append((gain + random.random() * (1 + (100 - stars) / 20), mv))
    scored.sort(reverse=True)
    return list(scored[0][1])


def junqi_mask(state, viewer_side, reveal_all=False):
    board = [row[:] for row in state["board"]]
    if reveal_all:
        return {**state, "board": board}
    revealed = set(state.get("revealed") or [])
    for r in range(12):
        for c in range(5):
            p = board[r][c]
            if not p:
                continue
            if _jq_side(p) == viewer_side:
                continue
            if f"{r},{c}" in revealed:
                continue
            board[r][c] = "?"
    return {**state, "board": board}


# ---------------- Feixing (Aeroplane / Ludo, 4 players) ----------------
# Plane steps: -1 hangar, 0-49 ring, 50-55 home, 56 finished.
# Takeoff on 6. Land on opponent (same ring cell) sends them to hangar.
# Own-color ring cells (every 4 steps) jump +4 once. Exact 56 to finish, else bounce.

FX_TO_HOME = 50
FX_FINISH = 56
FX_TAKEOFF = {1: 0, 2: 13, 3: 26, 4: 39}
FX_SIDES = (1, 2, 3, 4)


def _fx_key(planes, side):
    return planes.get(side, planes.get(str(side)))


def _fx_abs_ring(side, steps):
    return (FX_TAKEOFF[int(side)] + steps) % 52


def new_feixing():
    return {
        "planes": {str(s): [-1, -1, -1, -1] for s in FX_SIDES},
        "dice": 0,
        "phase": "roll",
        "last": None,
        "moves": 0,
        "turn": 1,
        "extra": 0,
    }


def _fx_can_use(steps, dice):
    if steps >= FX_FINISH:
        return False
    if steps < 0:
        return dice == 6
    return True


def _fx_dest(steps, dice):
    if steps < 0:
        return 0 if dice == 6 else None
    nxt = steps + dice
    if nxt == FX_FINISH:
        return FX_FINISH
    if nxt > FX_FINISH:
        return FX_FINISH - (nxt - FX_FINISH)
    return nxt


def _fx_apply_jump(steps):
    if 0 < steps < FX_TO_HOME and steps % 4 == 0:
        return min(steps + 4, FX_TO_HOME - 1)
    return steps


def _fx_send_home(planes, side, steps):
    if not (0 <= steps < FX_TO_HOME):
        return
    cell = _fx_abs_ring(side, steps)
    for s in FX_SIDES:
        if s == int(side):
            continue
        arr = _fx_key(planes, s)
        if not arr:
            continue
        for i, st in enumerate(arr):
            if 0 <= st < FX_TO_HOME and _fx_abs_ring(s, st) == cell:
                arr[i] = -1


def _fx_movable(state, side, dice):
    arr = _fx_key(state["planes"], side) or [-1, -1, -1, -1]
    out = []
    for i, st in enumerate(arr):
        if _fx_can_use(st, dice) and _fx_dest(st, dice) is not None:
            out.append(i)
    return out


def _fx_next_side(side):
    return side % 4 + 1


def feixing_move(state, move, side, god=False):
    try:
        if isinstance(move, str):
            mv = [move]
        elif isinstance(move, (int, float)):
            mv = [int(move)]
        else:
            mv = list(move)
    except Exception:
        return False, state, None
    side = int(side)
    planes = state["planes"]
    arr = _fx_key(planes, side)
    if arr is None:
        return False, state, None
    if god:
        if len(mv) < 2:
            return False, state, None
        idx, dest = int(mv[0]), int(mv[1])
        if not (0 <= idx < 4 and -1 <= dest <= FX_FINISH):
            return False, state, None
        arr[idx] = dest
        if 0 <= dest < FX_TO_HOME:
            _fx_send_home(planes, side, dest)
        state["last"] = ["god", idx, dest]
        state["moves"] = state.get("moves", 0) + 1
        state["phase"] = "roll"
        state["dice"] = 0
        if all(p >= FX_FINISH for p in arr):
            state["turn"] = side
            return True, state, f"win:{side}"
        state["turn"] = _fx_next_side(side)
        return True, state, None
    phase = state.get("phase") or "roll"
    if phase == "roll":
        op = mv[0] if mv else "roll"
        if op not in ("roll", -1, "-1"):
            return False, state, None
        dice = random.randint(1, 6)
        state["dice"] = dice
        state["last"] = ["roll", dice]
        state["moves"] = state.get("moves", 0) + 1
        movable = _fx_movable(state, side, dice)
        if not movable:
            if dice == 6 and state.get("extra", 0) < 2:
                state["extra"] = state.get("extra", 0) + 1
                state["phase"] = "roll"
                state["turn"] = side
            else:
                state["extra"] = 0
                state["phase"] = "roll"
                state["turn"] = _fx_next_side(side)
                state["dice"] = 0
            return True, state, None
        state["phase"] = "move"
        state["turn"] = side
        return True, state, None
    if not mv:
        return False, state, None
    try:
        idx = int(mv[0])
    except Exception:
        return False, state, None
    dice = int(state.get("dice") or 0)
    if idx not in _fx_movable(state, side, dice):
        return False, state, None
    dest = _fx_dest(arr[idx], dice)
    dest = _fx_apply_jump(dest)
    arr[idx] = dest
    if 0 <= dest < FX_TO_HOME:
        _fx_send_home(planes, side, dest)
    state["last"] = ["move", idx, dest, dice]
    state["moves"] = state.get("moves", 0) + 1
    state["phase"] = "roll"
    if all(p >= FX_FINISH for p in arr):
        state["turn"] = side
        return True, state, f"win:{side}"
    if dice == 6 and state.get("extra", 0) < 2:
        state["extra"] = state.get("extra", 0) + 1
        state["turn"] = side
    else:
        state["extra"] = 0
        state["turn"] = _fx_next_side(side)
    state["dice"] = 0
    return True, state, None


def feixing_legal(state, side):
    if (state.get("phase") or "roll") == "roll":
        return [["roll"]]
    return [[i] for i in _fx_movable(state, side, int(state.get("dice") or 0))]


def feixing_ai(state, side, stars=30):
    legal = feixing_legal(state, side)
    if not legal:
        return ["roll"]
    if legal == [["roll"]]:
        return ["roll"]
    arr = _fx_key(state["planes"], side) or [-1, -1, -1, -1]
    dice = int(state.get("dice") or 0)

    def score(i):
        cur = arr[i]
        dest = _fx_apply_jump(_fx_dest(cur, dice))
        s = dest
        if dest >= FX_FINISH:
            s += 80
        if cur < 0:
            s += 20
        if 0 <= dest < FX_TO_HOME:
            cell = _fx_abs_ring(side, dest)
            for oside in FX_SIDES:
                if oside == int(side):
                    continue
                oarr = _fx_key(state["planes"], oside) or []
                for st in oarr:
                    if 0 <= st < FX_TO_HOME and _fx_abs_ring(oside, st) == cell:
                        s += 40
        return s + random.random() * (1 + (100 - stars) / 25)

    best = max(legal, key=lambda mv: score(mv[0]))
    return best


# ---------------- Doudizhu (3 players) ----------------
# Cards: rank+suit "3c".."2s", plus joker / JOKER.
# Phases: bid then play. Combos: single, pair, triple, triple+1, straight, bomb, rocket.

DDZ_ORDER = "3456789TJQKA2"
DDZ_RANK = {ch: i for i, ch in enumerate(DDZ_ORDER)}
DDZ_RANK["joker"] = 13
DDZ_RANK["JOKER"] = 14


def _ddz_deck():
    cards = [r + s for r in DDZ_ORDER for s in "cdhs"]
    cards += ["joker", "JOKER"]
    random.shuffle(cards)
    return cards


def _ddz_rank(card):
    if card in ("joker", "JOKER"):
        return DDZ_RANK[card]
    return DDZ_RANK.get(card[0], -1)


def _ddz_sort(cards):
    return sorted(cards, key=lambda c: (_ddz_rank(c), c))


def _ddz_hand(state, side):
    h = state["hands"]
    return h.get(side, h.get(str(side)))


def new_doudizhu():
    deck = _ddz_deck()
    hands = {
        "1": _ddz_sort(deck[0:17]),
        "2": _ddz_sort(deck[17:34]),
        "3": _ddz_sort(deck[34:51]),
    }
    return {
        "hands": hands,
        "bottom": deck[51:54],
        "phase": "bid",
        "bid": 0,
        "bids": {"1": -1, "2": -1, "3": -1},
        "landlord": 0,
        "last_play": None,
        "last_player": 0,
        "pass_count": 0,
        "turn": 1,
        "moves": 0,
        "last": None,
    }


def _ddz_kind(cards):
    cards = list(cards)
    n = len(cards)
    if n == 0:
        return None
    ranks = sorted(_ddz_rank(c) for c in cards)
    if any(x < 0 for x in ranks):
        return None
    cnt = Counter(ranks)
    if n == 2 and set(cards) == {"joker", "JOKER"}:
        return ("rocket", 14, 2)
    if n == 4 and len(cnt) == 1:
        return ("bomb", ranks[0], 4)
    if n == 1:
        return ("single", ranks[0], 1)
    if n == 2 and len(cnt) == 1:
        return ("pair", ranks[0], 2)
    if n == 3 and len(cnt) == 1:
        return ("triple", ranks[0], 3)
    if n == 4 and sorted(cnt.values()) == [1, 3]:
        trip = next(r for r, c in cnt.items() if c == 3)
        return ("triple1", trip, 4)
    if n == 5 and sorted(cnt.values()) == [2, 3]:
        trip = next(r for r, c in cnt.items() if c == 3)
        return ("triple2", trip, 5)
    if n >= 4 and n % 2 == 0 and all(v == 2 for v in cnt.values()):
        distinct = sorted(cnt)
        if distinct[-1] < 12 and distinct[-1] - distinct[0] == len(distinct) - 1:
            return ("pairs_seq", distinct[0], n)
    if n >= 5 and len(cnt) == n and max(cnt.values()) == 1:
        if ranks[-1] >= 12:
            return None
        if ranks[-1] - ranks[0] == n - 1:
            return ("straight", ranks[0], n)
    return None


def _ddz_beats(new, old):
    if old is None:
        return True
    if new[0] == "rocket":
        return True
    if new[0] == "bomb" and old[0] != "rocket" and (old[0] != "bomb" or new[1] > old[1]):
        return True
    return new[0] == old[0] and new[2] == old[2] and new[1] > old[1]


def _ddz_next(side):
    return side % 3 + 1


def _ddz_finish_bid(state):
    bids = {int(k): int(v) for k, v in state["bids"].items()}
    lord, best = 1, -1
    for s in (1, 2, 3):
        if bids.get(s, -1) > best:
            best = bids[s]
            lord = s
    if best <= 0:
        lord, best = 1, 1
    state["landlord"] = lord
    state["bid"] = max(1, best)
    hand = _ddz_hand(state, lord)
    hand.extend(state["bottom"])
    state["hands"][str(lord)] = _ddz_sort(hand)
    state["bottom"] = []
    state["phase"] = "play"
    state["turn"] = lord
    state["last_play"] = None
    state["last_player"] = 0
    state["pass_count"] = 0


def doudizhu_move(state, move, side, god=False):
    try:
        if isinstance(move, str):
            mv = [move]
        else:
            mv = list(move)
    except Exception:
        return False, state, None
    side = int(side)
    if not mv:
        return False, state, None
    op = mv[0]
    state["moves"] = state.get("moves", 0) + 1
    if state.get("phase") == "bid":
        if op == "pass":
            val = 0
        elif op == "bid":
            try:
                val = int(mv[1]) if len(mv) > 1 else 0
            except Exception:
                return False, state, None
        else:
            return False, state, None
        if val < 0 or val > 3:
            return False, state, None
        if val and val <= int(state.get("bid") or 0):
            return False, state, None
        state["bids"][str(side)] = val
        if val:
            state["bid"] = val
        state["last"] = ["bid", side, val]
        if val == 3 or all(int(state["bids"][str(s)]) >= 0 for s in (1, 2, 3)):
            _ddz_finish_bid(state)
        else:
            state["turn"] = _ddz_next(side)
        return True, state, None
    hand = _ddz_hand(state, side)
    if hand is None:
        return False, state, None
    if op == "pass":
        if god:
            state["turn"] = _ddz_next(side)
            return True, state, None
        if not state.get("last_play") or int(state.get("last_player") or 0) == side:
            return False, state, None
        state["pass_count"] = int(state.get("pass_count") or 0) + 1
        state["last"] = ["pass", side]
        if state["pass_count"] >= 2:
            state["last_play"] = None
            state["pass_count"] = 0
            state["turn"] = int(state["last_player"])
        else:
            state["turn"] = _ddz_next(side)
        return True, state, None
    if op != "play":
        return False, state, None
    cards = [str(x) for x in mv[1:]]
    if not cards:
        return False, state, None
    need, have = Counter(cards), Counter(hand)
    if any(need[c] > have[c] for c in need):
        return False, state, None
    kind = _ddz_kind(cards)
    if not kind:
        return False, state, None
    last = state.get("last_play")
    last_kind = tuple(last) if last else None
    if not god and not _ddz_beats(kind, last_kind):
        return False, state, None
    for c in cards:
        hand.remove(c)
    state["hands"][str(side)] = hand
    state["last_play"] = list(kind)
    state["last_cards"] = cards
    state["last_player"] = side
    state["pass_count"] = 0
    state["last"] = ["play", side, cards]
    state["turn"] = _ddz_next(side)
    if not hand:
        lord = int(state.get("landlord") or 1)
        if side == lord:
            return True, state, f"win:{lord}"
        others = [s for s in (1, 2, 3) if s != lord]
        return True, state, "win:" + ",".join(str(s) for s in others)
    return True, state, None


def _ddz_combos(hand, last_kind):
    by = defaultdict(list)
    for c in hand:
        by[_ddz_rank(c)].append(c)
    out = []
    ranks = sorted(by)

    def add(cards):
        k = _ddz_kind(cards)
        if k and _ddz_beats(k, last_kind):
            out.append(["play"] + cards)

    if set(hand) >= {"joker", "JOKER"}:
        add(["joker", "JOKER"])
    for r in ranks:
        cs = by[r]
        if len(cs) >= 4:
            add(cs[:4])
        if len(cs) >= 1:
            add(cs[:1])
        if len(cs) >= 2:
            add(cs[:2])
        if len(cs) >= 3:
            add(cs[:3])
            for r2 in ranks:
                if r2 != r and by[r2]:
                    add(cs[:3] + by[r2][:1])
                if r2 != r and len(by[r2]) >= 2:
                    add(cs[:3] + by[r2][:2])
    # straights
    for ln in range(5, 13):
        for start in range(0, 12 - ln):
            seq = list(range(start, start + ln))
            if all(seq_r in by for seq_r in seq):
                add([by[seq_r][0] for seq_r in seq])
    # consecutive pairs (2..6 pairs)
    for ln in range(2, 7):
        for start in range(0, 12 - ln):
            seq = list(range(start, start + ln))
            if all(seq_r in by and len(by[seq_r]) >= 2 for seq_r in seq):
                add([c for seq_r in seq for c in by[seq_r][:2]])
    return out


def doudizhu_legal(state, side):
    if state.get("phase") == "bid":
        cur = int(state.get("bid") or 0)
        moves = [["pass"]]
        for v in range(cur + 1, 4):
            moves.append(["bid", v])
        return moves
    hand = _ddz_hand(state, side) or []
    last = state.get("last_play")
    last_kind = tuple(last) if last else None
    out = _ddz_combos(hand, last_kind)
    if last_kind and int(state.get("last_player") or 0) != int(side):
        out.append(["pass"])
    return out or [["pass"]]


def doudizhu_ai(state, side, stars=30):
    legal = doudizhu_legal(state, side)
    if not legal:
        return ["pass"]
    if state.get("phase") == "bid":
        hand = _ddz_hand(state, side) or []
        power = sum(1 for c in hand if _ddz_rank(c) >= 11) + (2 if "JOKER" in hand else 0)
        bids = [m for m in legal if m[0] == "bid"]
        if power >= 6 and bids:
            pick = bids[-1] if stars >= 50 else bids[0]
            return pick
        return ["pass"] if ["pass"] in legal else (bids[0] if bids else ["pass"])
    plays = [m for m in legal if m[0] == "play"]
    if not plays:
        return ["pass"]
    plays.sort(key=lambda m: (len(m), _ddz_rank(m[1]) if len(m) > 1 else 0))
    idx = 0 if stars >= 40 else min(len(plays) - 1, random.randint(0, max(0, len(plays) // 3)))
    return plays[idx]


def doudizhu_mask(state, viewer_side, reveal_all=False):
    hands = {}
    for s in ("1", "2", "3"):
        h = list(state["hands"].get(s) or [])
        if reveal_all or int(s) == int(viewer_side):
            hands[s] = h
        else:
            hands[s] = ["?"] * len(h)
    bottom = list(state.get("bottom") or [])
    if state.get("phase") == "bid" and not reveal_all:
        bottom = ["?"] * len(bottom)
    return {**state, "hands": hands, "bottom": bottom}


# ---------------- Plants vs Zombies (realtime client, result via WS) ----------------
PVZ_PLANT_COST = {
    "sunflower": 50, "peashooter": 100, "snowpea": 175,
    "wallnut": 50, "potatomine": 25, "cherrybomb": 150,
}
PVZ_ZOMBIE_COST = {"normal": 50, "cone": 75, "bucket": 150, "flag": 0}
PVZ_ZOMBIE_HP = {"normal": 1, "cone": 2, "bucket": 3, "flag": 1}
PVZ_PLANT_HP = {"sunflower": 1, "peashooter": 1, "snowpea": 1, "wallnut": 3, "potatomine": 1}
PVZ_WAVES = [
    ["normal"] * 4,
    ["normal"] * 4 + ["cone"] * 2,
    ["flag"] + ["normal"] * 6 + ["cone"] * 2 + ["bucket"],
]


def new_pvz():
    return {
        "phase": "play",
        "turn": 1,
        "last": None,
        "moves": 0,
    }


def pvz_legal(state, side):
    return [["win"], ["lose"]]


def pvz_move(state, move, side, god=False):
    try:
        mv = list(move) if not isinstance(move, (str, int, float)) else [move]
    except Exception:
        return False, state, None
    if not mv:
        return False, state, None
    op = str(mv[0]).lower()
    side = int(side)
    state = {**state, "turn": side, "last": [op, side], "moves": int(state.get("moves") or 0) + 1}
    if op in ("win", "clear", "pass"):
        return True, state, f"win:{side}"
    if op in ("lose", "fail", "dead"):
        other = 2 if side == 1 else 1
        return True, state, f"win:{other}"
    return False, state, None


def pvz_ai(state, side, stars=30):
    return None


# ---------------- Five Nights horror ----------------
HORROR_ROOMS = ["stage", "dining", "west", "east", "left_door", "right_door", "office"]
HORROR_ADJ = {
    "stage": ["dining"],
    "dining": ["stage", "west", "east"],
    "west": ["dining", "left_door"],
    "east": ["dining", "right_door"],
    "left_door": ["west", "office"],
    "right_door": ["east", "office"],
    "office": ["left_door", "right_door"],
}
HORROR_DOOR = {"left_door": "left", "right_door": "right"}


def new_horror():
    return {
        "ghost": "stage",
        "doors": {"left": 0, "right": 0},
        "power": 100,
        "camera": "office",
        "hour": 0,
        "turn": 1,
        "last": None,
        "moves": 0,
    }


def horror_mask(state, viewer_side, reveal_all=False):
    st = dict(state)
    st["doors"] = dict(state.get("doors") or {"left": 0, "right": 0})
    if reveal_all:
        return st
    if int(viewer_side) == 1 and st.get("camera") != st.get("ghost"):
        st["ghost"] = "?"
    return st


def horror_legal(state, side):
    side = int(side)
    power = int(state.get("power") or 0)
    if side == 1:
        out = [["wait"]]
        if power >= 1:
            for room in HORROR_ROOMS:
                if room != "office":
                    out.append(["cam", room])
            out.append(["door", "left"])
            out.append(["door", "right"])
        return out
    ghost = state.get("ghost") or "stage"
    return [["move", n] for n in HORROR_ADJ.get(ghost, [])]


def horror_move(state, move, side, god=False):
    try:
        mv = list(move) if not isinstance(move, (str, int, float)) else [move]
    except Exception:
        return False, state, None
    if not mv:
        return False, state, None
    side = int(side)
    state = {
        **state,
        "doors": dict(state.get("doors") or {"left": 0, "right": 0}),
    }
    op = str(mv[0])
    power = int(state.get("power") or 0)
    if side == 1:
        if op == "wait":
            drain = 1 + int(state["doors"].get("left") or 0) + int(state["doors"].get("right") or 0)
            state["power"] = max(0, power - drain)
            state["hour"] = int(state.get("hour") or 0) + 1
            if state["power"] <= 0:
                state["doors"] = {"left": 0, "right": 0}
            state["turn"] = 2
            state["last"] = ["wait"]
            state["moves"] = state.get("moves", 0) + 1
            if int(state["hour"]) >= 6:
                return True, state, "win:1"
            return True, state, None
        if op == "cam":
            room = str(mv[1]) if len(mv) > 1 else ""
            if room not in HORROR_ROOMS:
                return False, state, None
            if power < 1 and not god:
                return False, state, None
            if not god:
                state["power"] = power - 1
            state["camera"] = room
            if state["power"] <= 0:
                state["doors"] = {"left": 0, "right": 0}
            state["turn"] = 2
            state["last"] = ["cam", room]
            state["moves"] = state.get("moves", 0) + 1
            return True, state, None
        if op == "door":
            which = str(mv[1]) if len(mv) > 1 else ""
            if which not in ("left", "right"):
                return False, state, None
            if power < 1 and not god:
                return False, state, None
            if not god:
                state["power"] = power - 1
            state["doors"][which] = 0 if state["doors"].get(which) else 1
            if state["power"] <= 0:
                state["doors"] = {"left": 0, "right": 0}
            state["turn"] = 2
            state["last"] = ["door", which]
            state["moves"] = state.get("moves", 0) + 1
            return True, state, None
        if op == "power" and god:
            try:
                state["power"] = max(0, min(100, int(mv[1])))
            except Exception:
                return False, state, None
            state["turn"] = 2
            state["last"] = ["power", state["power"]]
            return True, state, None
        return False, state, None
    if op != "move":
        return False, state, None
    room = str(mv[1]) if len(mv) > 1 else ""
    if room not in HORROR_ROOMS:
        return False, state, None
    cur = state.get("ghost") or "stage"
    if not god and room not in HORROR_ADJ.get(cur, []):
        return False, state, None
    if room == "office":
        door_key = HORROR_DOOR.get(cur)
        closed = door_key and int(state["doors"].get(door_key) or 0)
        if closed and not god:
            state["last"] = ["move", cur]
            state["turn"] = 1
            state["moves"] = state.get("moves", 0) + 1
            return True, state, None
        state["ghost"] = "office"
        state["turn"] = 1
        state["last"] = ["move", "office"]
        state["moves"] = state.get("moves", 0) + 1
        return True, state, "win:2"
    state["ghost"] = room
    state["turn"] = 1
    state["last"] = ["move", room]
    state["moves"] = state.get("moves", 0) + 1
    return True, state, None


def horror_ai(state, side, stars=30):
    side = int(side)
    if side == 1:
        ghost = state.get("ghost") or "stage"
        doors = state.get("doors") or {}
        power = int(state.get("power") or 0)
        if ghost == "left_door" and not doors.get("left") and power >= 1:
            return ["door", "left"]
        if ghost == "right_door" and not doors.get("right") and power >= 1:
            return ["door", "right"]
        if ghost in ("west", "east", "left_door", "right_door", "dining") and power >= 1:
            return ["cam", ghost]
        return ["wait"]
    ghost = state.get("ghost") or "stage"
    doors = state.get("doors") or {}
    path = {
        "stage": "dining", "dining": "west", "west": "left_door",
        "left_door": "office", "east": "right_door", "right_door": "office",
    }
    if ghost == "dining":
        nxt = "east" if doors.get("left") and not doors.get("right") else "west"
        return ["move", nxt]
    nxt = path.get(ghost)
    if nxt:
        return ["move", nxt]
    legal = horror_legal(state, 2)
    return legal[0] if legal else None


GAMES = {
    "gomoku": {
        "key": "gomoku", "name": "五子棋", "max_players": 2, "available": True,
        "new": new_gomoku, "move": gomoku_move, "ai": gomoku_ai, "legal": gomoku_legal,
        "desc": "15路棋盘，五子连珠获胜",
    },
    "tictactoe": {
        "key": "tictactoe", "name": "井字棋", "max_players": 2, "available": True,
        "new": new_tictactoe, "move": tictactoe_move, "ai": tictactoe_ai, "legal": tictactoe_legal,
        "desc": "3x3经典井字棋",
    },
    "xiangqi": {
        "key": "xiangqi", "name": "中国象棋", "max_players": 2, "available": True,
        "new": new_xiangqi, "move": xiangqi_move, "ai": xiangqi_ai, "legal": xiangqi_legal,
        "desc": "完整中国象棋规则",
    },
    "doubeast": {
        "key": "doubeast", "name": "斗兽棋", "max_players": 2, "available": True,
        "new": new_doubeast, "move": doubeast_move, "ai": doubeast_ai, "legal": doubeast_legal,
        "desc": "经典斗兽棋，鼠可克象",
    },
    "go": {
        "key": "go", "name": "围棋", "max_players": 2, "available": True,
        "new": new_go, "move": go_move, "ai": go_ai, "legal": go_legal,
        "desc": "9路围棋，气与提子，两手停着点目，贴目6.5",
    },
    "chess": {
        "key": "chess", "name": "国际象棋", "max_players": 2, "available": True,
        "new": new_chess, "move": chess_move, "ai": chess_ai, "legal": chess_legal,
        "desc": "完整国际象棋规则",
    },
    "junqi": {
        "key": "junqi", "name": "军棋", "max_players": 2, "available": True,
        "new": new_junqi, "move": junqi_move, "ai": junqi_ai, "legal": junqi_legal,
        "desc": "两人军棋，铁路通行，工兵挖雷，军旗被扛即负",
    },
    "feixing": {
        "key": "feixing", "name": "飞行棋", "max_players": 4, "available": True,
        "new": new_feixing, "move": feixing_move, "ai": feixing_ai, "legal": feixing_legal,
        "desc": "4人飞行棋，掷6起飞，同格撞回机库，四子到家获胜",
    },
    "tiaoqi": {
        "key": "tiaoqi", "name": "国际跳棋", "max_players": 2, "available": True,
        "new": new_checkers, "move": checkers_move, "ai": checkers_ai, "legal": checkers_legal,
        "desc": "经典国际跳棋，吃子跳连跳",
    },
    "doudizhu": {
        "key": "doudizhu", "name": "斗地主", "max_players": 3, "available": True,
        "new": new_doudizhu, "move": doudizhu_move, "ai": doudizhu_ai, "legal": doudizhu_legal,
        "desc": "3人斗地主，叫分抢地主，炸弹与火箭，农民或地主出完即胜",
    },
    "pvz": {
        "key": "pvz", "name": "植物大战僵尸", "max_players": 2, "available": True,
        "new": new_pvz, "move": pvz_move, "ai": pvz_ai, "legal": pvz_legal,
        "desc": "原汁原味实时植物大战僵尸，通关即胜，僵尸进家门即负",
    },
    "horror": {
        "key": "horror", "name": "五夜抓鬼", "max_players": 2, "available": True,
        "new": new_horror, "move": horror_move, "ai": horror_ai, "legal": horror_legal,
        "desc": "守卫撑到6点，鬼从舞台摸进办公室，摄像关门耗电",
    },
}


def game_meta():
    return [
        {k: v[k] for k in ("key", "name", "max_players", "available", "desc")}
        for v in GAMES.values()
    ]


RANK_NAMES = [
    "青铜", "白银", "黄金", "铂金", "钻石", "星耀",
    "大师", "宗师", "王者", "传奇", "荣耀", "巅峰",
]


def rank_label(division, stars):
    d = max(1, min(12, division))
    s = max(0, min(2, stars))
    return f"{RANK_NAMES[d - 1]}{'ⅠⅡⅢ'[s]}"


def apply_ranked_result(points, division, stars, won):
    """Returns (points, division, stars, delta). 100 points -> 1 star, 3 stars -> 1 division, 12 divisions max."""
    if won:
        delta = 22 + (division - 1) * 2
    else:
        delta = -(14 + (division - 1))
    points += delta
    while points >= 100:
        points -= 100
        stars += 1
        if stars >= 3:
            stars = 0
            if division < 12:
                division += 1
    while points < 0:
        if stars > 0:
            stars -= 1
            points += 100
        elif division > 1:
            division -= 1
            stars = 2
            points += 100
        else:
            points = 0
            break
    return points, division, stars, delta
