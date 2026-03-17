# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Discord bot that auto-tracks Chessle (chess Wordle) daily puzzle results. When a user pastes their Chessle result into Discord, the bot parses it, stores it in SQLite, and reacts with a confirmation. Commands show personal stats and a group leaderboard.

## Setup & Running

```bash
pip install -r requirements.txt
cp .env.example .env        # fill in DISCORD_TOKEN
python bot.py
```

## Commands (slash commands)

| Command | Description |
|---|---|
| `/stats [member]` | Personal stats (win %, avg score, streaks, distribution) |
| `/leaderboard` | All-time leaderboard |
| `/today [puzzle_num]` | Results for the latest (or given) puzzle number |

## Architecture

- **`bot.py`** — Discord bot entry point. `on_message` auto-detects Chessle pastes; slash-style `!commands` for stats.
- **`parser.py`** — Regex parser for the Chessle result format: `Chessle {N} ({Difficulty}) {score}/6`.
- **`database.py`** — SQLite wrapper (`chessle_stats.db`). Single `results` table; unique constraint on `(user_id, puzzle_num)` prevents duplicates.

## Chessle result format

```
Chessle 1494 (Expert) X/6

🟨🟨⬛⬛⬛⬛⬛🟨🟨⬛
🟩🟩🟩🟨⬛🟨⬛⬛🟨⬛
...
```

The header line is what the parser extracts — the emoji grid is ignored. Score `X` is stored as `NULL` (failed puzzle).

## Developer Portal setup

1. **Message Content Intent** — Bot > Privileged Gateway Intents > enable "Message Content Intent". Without this the bot cannot read message text and will never detect Chessle pastes.
2. **Slash command sync** — `tree.sync()` is called on `on_ready`, so commands register automatically on first boot. They can take up to an hour to propagate globally.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | Yes | Bot token from Discord Developer Portal |
| `CHESSLE_CHANNEL_ID` | No | If set, only parses results in that channel |
