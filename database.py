import sqlite3
from contextlib import contextmanager

DB_PATH = "chessle_stats.db"


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT NOT NULL,
                username    TEXT NOT NULL,
                puzzle_num  INTEGER NOT NULL,
                difficulty  TEXT NOT NULL,
                score       INTEGER,          -- NULL means failed (X/6)
                posted_at   TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(user_id, puzzle_num)
            )
        """)


def save_result(user_id: str, username: str, puzzle_num: int, difficulty: str, score: int | None):
    """Insert or replace a result. Returns True if new, False if duplicate."""
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM results WHERE user_id = ? AND puzzle_num = ?",
            (user_id, puzzle_num),
        ).fetchone()
        if existing:
            return False
        conn.execute(
            "INSERT INTO results (user_id, username, puzzle_num, difficulty, score) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, puzzle_num, difficulty, score),
        )
        return True


def get_user_stats(user_id: str) -> dict | None:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM results WHERE user_id = ? ORDER BY puzzle_num",
            (user_id,),
        ).fetchall()
    if not rows:
        return None

    total = len(rows)
    wins = [r for r in rows if r["score"] is not None]
    scores = [r["score"] for r in wins]
    avg = sum(scores) / len(scores) if scores else 0
    distribution = {i: scores.count(i) for i in range(1, 7)}
    streak, best_streak = _calc_streaks(rows)

    return {
        "username": rows[-1]["username"],
        "total": total,
        "wins": len(wins),
        "losses": total - len(wins),
        "win_pct": len(wins) / total * 100,
        "avg_score": avg,
        "distribution": distribution,
        "streak": streak,
        "best_streak": best_streak,
    }


def get_leaderboard(limit: int = 10) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                user_id,
                username,
                COUNT(*) AS total,
                SUM(CASE WHEN score IS NOT NULL THEN 1 ELSE 0 END) AS wins,
                AVG(CASE WHEN score IS NOT NULL THEN score END) AS avg_score
            FROM results
            GROUP BY user_id
            ORDER BY wins DESC, avg_score ASC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_today_results(puzzle_num: int) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM results WHERE puzzle_num = ? ORDER BY score ASC NULLS LAST",
            (puzzle_num,),
        ).fetchall()
    return [dict(r) for r in rows]


def _calc_streaks(rows) -> tuple[int, int]:
    """Return (current_streak, best_streak) counting consecutive wins."""
    puzzle_nums = [r["puzzle_num"] for r in rows]
    scores = {r["puzzle_num"]: r["score"] for r in rows}

    best = cur = 0
    for num in sorted(puzzle_nums, reverse=True):
        if scores[num] is not None:
            cur += 1
            best = max(best, cur)
        else:
            if cur > best:
                best = cur
            break  # streak broken

    # recalc current streak from most recent
    cur = 0
    for num in sorted(puzzle_nums, reverse=True):
        if scores[num] is not None:
            cur += 1
        else:
            break

    return cur, best
