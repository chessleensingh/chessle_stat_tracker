import os
import sqlite3

import discord
from discord import app_commands
from dotenv import load_dotenv

import database as db
from parser import parse_chessle_result

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CHESSLE_CHANNEL_ID = os.getenv("CHESSLE_CHANNEL_ID")

# MESSAGE_CONTENT is a privileged intent — must be enabled in the Discord
# Developer Portal under Bot > Privileged Gateway Intents.
# Without it the bot cannot read message text and won't detect Chessle pastes.
intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@client.event
async def on_ready():
    db.init_db()
    await tree.sync()
    print(f"Logged in as {client.user} (ID: {client.user.id})")


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if CHESSLE_CHANNEL_ID and str(message.channel.id) != CHESSLE_CHANNEL_ID:
        return

    result = parse_chessle_result(message.content)
    if not result:
        return

    is_new = db.save_result(
        user_id=str(message.author.id),
        username=message.author.display_name,
        puzzle_num=result["puzzle_num"],
        difficulty=result["difficulty"],
        score=result["score"],
    )
    if is_new:
        await message.add_reaction("✅")
    else:
        await message.add_reaction("⚠️")


@tree.command(name="stats", description="Show your Chessle stats (or another member's)")
@app_commands.describe(member="The member to look up (defaults to you)")
async def stats(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    data = db.get_user_stats(str(target.id))

    if not data:
        await interaction.response.send_message(
            f"No Chessle results recorded for {target.display_name}.", ephemeral=True
        )
        return

    dist = data["distribution"]
    dist_bar = "\n".join(
        f"`{i}/6` {'🟩' * dist[i]:<6} {dist[i]}"
        for i in range(1, 7)
        if dist[i] > 0
    )

    embed = discord.Embed(title=f"Chessle Stats — {data['username']}", color=0x5865F2)
    embed.add_field(name="Played", value=str(data["total"]), inline=True)
    embed.add_field(name="Win %", value=f"{data['win_pct']:.0f}%", inline=True)
    embed.add_field(name="Avg Score", value=f"{data['avg_score']:.2f}/6" if data["wins"] else "—", inline=True)
    embed.add_field(name="Current Streak", value=f"🔥 {data['streak']}", inline=True)
    embed.add_field(name="Best Streak", value=f"⭐ {data['best_streak']}", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    if dist_bar:
        embed.add_field(name="Score Distribution", value=dist_bar, inline=False)

    await interaction.response.send_message(embed=embed)


@tree.command(name="leaderboard", description="Show the all-time Chessle leaderboard")
async def leaderboard(interaction: discord.Interaction):
    rows = db.get_leaderboard(10)
    if not rows:
        await interaction.response.send_message("No results yet!", ephemeral=True)
        return

    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(rows):
        prefix = medals[i] if i < 3 else f"`{i+1}.`"
        avg = f"{row['avg_score']:.2f}" if row["avg_score"] else "—"
        lines.append(f"{prefix} **{row['username']}** — {row['wins']}/{row['total']} wins, avg {avg}/6")

    embed = discord.Embed(title="Chessle Leaderboard", description="\n".join(lines), color=0xF1C40F)
    await interaction.response.send_message(embed=embed)


@tree.command(name="today", description="Show everyone's results for a puzzle number")
@app_commands.describe(puzzle_num="Puzzle number (defaults to most recent)")
async def today(interaction: discord.Interaction, puzzle_num: int = None):
    if puzzle_num is None:
        with sqlite3.connect(db.DB_PATH) as conn:
            row = conn.execute("SELECT MAX(puzzle_num) FROM results").fetchone()
            puzzle_num = row[0] if row and row[0] else None

    if puzzle_num is None:
        await interaction.response.send_message("No results logged yet.", ephemeral=True)
        return

    rows = db.get_today_results(puzzle_num)
    if not rows:
        await interaction.response.send_message(
            f"No results logged for Chessle #{puzzle_num}.", ephemeral=True
        )
        return

    lines = [
        f"**{row['username']}** — {row['score']}/6" if row["score"] else f"**{row['username']}** — X/6"
        for row in rows
    ]

    embed = discord.Embed(
        title=f"Chessle #{puzzle_num} Results",
        description="\n".join(lines),
        color=0x2ECC71,
    )
    embed.set_footer(text=f"{len(rows)} player(s) logged")
    await interaction.response.send_message(embed=embed)


@tree.command(name="results", description="Show all logged Chessle results")
async def results(interaction: discord.Interaction):
    with sqlite3.connect(db.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT puzzle_num, username, score, difficulty, posted_at FROM results ORDER BY puzzle_num DESC, score ASC NULLS LAST"
        ).fetchall()

    if not rows:
        await interaction.response.send_message("No results logged yet.", ephemeral=True)
        return

    # Try to fit in an embed table
    lines = ["```", f"{'#':<6} {'Player':<20} {'Score':<7} {'Difficulty'}", "-" * 46]
    for row in rows:
        score_str = f"{row['score']}/6" if row["score"] else "X/6"
        lines.append(f"{row['puzzle_num']:<6} {row['username'][:20]:<20} {score_str:<7} {row['difficulty']}")
    lines.append("```")

    content = "\n".join(lines)
    if len(content) <= 2000:
        await interaction.response.send_message(content)
    else:
        # Too long — send as CSV file
        import io
        csv_lines = ["puzzle_num,username,score,difficulty,posted_at"]
        for row in rows:
            score_str = str(row["score"]) if row["score"] else "X"
            csv_lines.append(f"{row['puzzle_num']},{row['username']},{score_str},{row['difficulty']},{row['posted_at']}")
        csv_bytes = "\n".join(csv_lines).encode("utf-8")
        await interaction.response.send_message(
            f"Too many results to display — here's the full list ({len(rows)} entries):",
            file=discord.File(io.BytesIO(csv_bytes), filename="chessle_results.csv"),
        )


@tree.command(name="backfill", description="Scan a channel's history and log all Chessle results (admin only)")
@app_commands.describe(channel="Channel to scan (defaults to current channel)")
@app_commands.default_permissions(manage_guild=True)
async def backfill(interaction: discord.Interaction, channel: discord.TextChannel = None):
    target_channel = channel or interaction.channel
    await interaction.response.send_message(
        f"Scanning {target_channel.mention} history... this may take a moment.", ephemeral=True
    )

    added = 0
    skipped = 0
    async for message in target_channel.history(limit=None, oldest_first=True):
        if message.author.bot:
            continue
        result = parse_chessle_result(message.content)
        if not result:
            continue
        is_new = db.save_result(
            user_id=str(message.author.id),
            username=message.author.display_name,
            puzzle_num=result["puzzle_num"],
            difficulty=result["difficulty"],
            score=result["score"],
        )
        if is_new:
            added += 1
        else:
            skipped += 1

    await interaction.followup.send(
        f"Done! Found **{added + skipped}** Chessle results — added **{added}** new, skipped **{skipped}** duplicates.",
        ephemeral=True,
    )


client.run(TOKEN)
