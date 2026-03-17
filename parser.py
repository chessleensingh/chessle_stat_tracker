import re

# Matches: "Chessle 1494 (Expert) X/6" or "Chessle 1494 (Expert) 3/6"
RESULT_RE = re.compile(
    r"Chessle\s+(\d+)\s+\(([^)]+)\)\s+([X1-6])/6",
    re.IGNORECASE,
)


def parse_chessle_result(text: str) -> dict | None:
    """
    Parse a Chessle result paste.
    Returns dict with puzzle_num, difficulty, score (int or None for fail).
    Returns None if the text doesn't look like a Chessle result.
    """
    match = RESULT_RE.search(text)
    if not match:
        return None

    puzzle_num = int(match.group(1))
    difficulty = match.group(2).strip()
    raw_score = match.group(3)
    score = None if raw_score == "X" else int(raw_score)

    return {
        "puzzle_num": puzzle_num,
        "difficulty": difficulty,
        "score": score,
    }
