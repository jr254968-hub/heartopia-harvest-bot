import os
import re
import sqlite3
import asyncio
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
DB_PATH = os.getenv("DATABASE_PATH", "harvests.db")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                crop TEXT NOT NULL,
                planted_at TEXT NOT NULL,
                ready_at TEXT NOT NULL,
                notified INTEGER NOT NULL DEFAULT 0
            )
        """)

def parse_duration(value: str):
    """Accepts durations such as 15m, 2h, 1d, 1h30m."""
    value = value.strip().lower().replace(" ", "")
    matches = re.findall(r"(\d+)([mhd])", value)
    if not matches or "".join(n + u for n, u in matches) != value:
        raise ValueError("Use a duration like `15m`, `2h`, `1d`, or `1h30m`.")
    total = 0
    for amount, unit in matches:
        amount = int(amount)
        total += amount * {"m": 60, "h": 3600, "d": 86400}[unit]
    if total < 60 or total > 30 * 86400:
        raise ValueError("Duration must be between 1 minute and 30 days.")
    return timedelta(seconds=total)

def nice_remaining(seconds):
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if minutes or not parts: parts.append(f"{minutes}m")
    return " ".join(parts)

@bot.event
async def on_ready():
    init_db()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as exc:
        print(f"Command sync failed: {exc}")
    if not check_harvests.is_running():
        check_harvests.start()
    print(f"Logged in as {bot.user}.")

CROP_OPTIONS = [
    ("Tomato", 15), ("Potato", 60), ("Paddy", 20), ("Wheat", 240),
    ("Lettuce", 480), ("Pineapple", 30), ("Carrot", 120),
    ("Strawberry", 360), ("Corn", 720), ("Grape", 600),
    ("Eggplant", 420), ("Tea Leaf", 45), ("Cocoa Bean", 300),
    ("Avocado", 840), ("Pumpkin (event)", 15),
    ("Cape Gooseberry (event)", 15), ("Starfruit (event)", 15),
    ("Lemon Verbena (event)", 15), ("Romaine Lettuce (event)", 15),
    ("White Radish (event)", 15), ("Prickly Pear (event)", 15),
]

@bot.tree.command(name="plant", description="Choose a crop and automatically start its harvest timer.")
@app_commands.describe(crop="Choose the crop you just planted")
@app_commands.choices(crop=[
    app_commands.Choice(
        name=(f"{name} — {minutes} min" if minutes < 60 else
              f"{name} — {minutes // 60}h" if minutes % 60 == 0 else
              f"{name} — {minutes // 60}h {minutes % 60}m"),
        value=f"{name}|{minutes}"
    ) for name, minutes in CROP_OPTIONS
])
async def plant(interaction: discord.Interaction, crop: app_commands.Choice[str]):
    crop_name, minutes_text = crop.value.rsplit("|", 1)
    duration = timedelta(minutes=int(minutes_text))
    now = datetime.now(timezone.utc)
    ready = now + duration
    with connect_db() as conn:
        cur = conn.execute(
            "INSERT INTO crops (guild_id, user_id, crop, planted_at, ready_at) VALUES (?, ?, ?, ?, ?)",
            (interaction.guild_id, interaction.user.id, crop_name,
             now.isoformat(), ready.isoformat())
        )
        crop_id = cur.lastrowid

    await interaction.response.send_message(
        f"🌱 **{crop_name}** added to your garden (ID `#{crop_id}`). "
        f"It should be ready {discord.utils.format_dt(ready, style='R')}.\n"
        f"I'll notify you in the server's harvest-alert channel once the timer ends."
    )

@bot.tree.command(name="mycrops", description="See your active crop timers.")
async def mycrops(interaction: discord.Interaction):
    now = datetime.now(timezone.utc)
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT * FROM crops WHERE guild_id=? AND user_id=? ORDER BY ready_at",
            (interaction.guild_id, interaction.user.id)
        ).fetchall()
    if not rows:
        await interaction.response.send_message("Your garden is empty. Use `/plant` to add a crop.", ephemeral=True)
        return
    lines = []
    for row in rows:
        ready = datetime.fromisoformat(row["ready_at"])
        status = "🟢 Ready" if ready <= now else f"⏳ {nice_remaining((ready-now).total_seconds())} left"
        lines.append(f"`#{row['id']}` **{row['crop']}** — {status}")
    await interaction.response.send_message("🌱 **Your crops**\n" + "\n".join(lines), ephemeral=True)

@bot.tree.command(name="garden", description="See everyone's active crop timers in this server.")
async def garden(interaction: discord.Interaction):
    now = datetime.now(timezone.utc)
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT * FROM crops WHERE guild_id=? ORDER BY ready_at",
            (interaction.guild_id,)
        ).fetchall()
    if not rows:
        await interaction.response.send_message("Nobody has added crops yet. Use `/plant` to start!")
        return
    lines = []
    for row in rows[:40]:
        ready = datetime.fromisoformat(row["ready_at"])
        status = "🟢 Ready" if ready <= now else f"⏳ {nice_remaining((ready-now).total_seconds())} left"
        lines.append(f"`#{row['id']}` <@{row['user_id']}> — **{row['crop']}** — {status}")
    extra = f"\n…and {len(rows)-40} more." if len(rows) > 40 else ""
    await interaction.response.send_message("🌿 **Server garden**\n" + "\n".join(lines) + extra)

@bot.tree.command(name="harvest", description="Mark one of your ready crops as harvested.")
@app_commands.describe(crop_id="The crop ID shown by /mycrops")
async def harvest(interaction: discord.Interaction, crop_id: int):
    with connect_db() as conn:
        row = conn.execute(
            "SELECT * FROM crops WHERE id=? AND guild_id=? AND user_id=?",
            (crop_id, interaction.guild_id, interaction.user.id)
        ).fetchone()
        if row:
            conn.execute("DELETE FROM crops WHERE id=?", (crop_id,))
    if not row:
        await interaction.response.send_message("I couldn't find that crop in your garden.", ephemeral=True)
        return
    await interaction.response.send_message(f"🧺 Harvest recorded: **{row['crop']}** (#{crop_id}).")

@bot.tree.command(name="cancel", description="Remove one of your crop timers.")
@app_commands.describe(crop_id="The crop ID shown by /mycrops")
async def cancel(interaction: discord.Interaction, crop_id: int):
    with connect_db() as conn:
        cur = conn.execute(
            "DELETE FROM crops WHERE id=? AND guild_id=? AND user_id=?",
            (crop_id, interaction.guild_id, interaction.user.id)
        )
    if cur.rowcount:
        await interaction.response.send_message(f"❌ Crop timer `#{crop_id}` cancelled.", ephemeral=True)
    else:
        await interaction.response.send_message("I couldn't find that crop in your garden.", ephemeral=True)

@bot.tree.command(name="setchannel", description="Choose where harvest alerts are posted (server admins only).")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(channel="The channel for harvest notifications")
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    with connect_db() as conn:
        conn.execute(
            "INSERT INTO settings (guild_id, channel_id) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id",
            (interaction.guild_id, channel.id)
        )
    await interaction.response.send_message(f"✅ Harvest alerts will be posted in {channel.mention}.")

@setchannel.error
async def setchannel_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        message = "You need the **Manage Server** permission to change the alert channel."
    else:
        message = "Something went wrong setting the alert channel."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)

@bot.tree.command(name="help", description="Show Heartopia harvest bot commands.")
async def help_command(interaction: discord.Interaction):
    text = (
        "**🌱 Heartopia Harvest Bot**\n"
        "`/plant` — choose a crop from the dropdown; its timer is automatic.\n"
        "`/mycrops` — see your crops privately\n"
        "`/garden` — see everyone's crops\n"
        "`/harvest crop_id` — remove a harvested crop\n"
        "`/cancel crop_id` — cancel a timer\n"
        "`/setchannel #channel` — set alert channel (admins)\n\n"
        "Crop times are preset in the dropdown. "
        "Enter the correct growing time for your Heartopia crop."
    )
    await interaction.response.send_message(text, ephemeral=True)

@tasks.loop(seconds=30)
async def check_harvests():
    now = datetime.now(timezone.utc)
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT crops.*, settings.channel_id FROM crops "
            "JOIN settings ON crops.guild_id=settings.guild_id "
            "WHERE crops.notified=0 AND crops.ready_at<=?",
            (now.isoformat(),)
        ).fetchall()

    for row in rows:
        channel = bot.get_channel(row["channel_id"])
        if channel is None:
            try:
                channel = await bot.fetch_channel(row["channel_id"])
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue
        try:
            await channel.send(
                f"🌾 **HARVEST READY!** <@{row['user_id']}> — "
                f"your **{row['crop']}** is ready to harvest! "
                f"(Crop ID `#{row['id']}`)"
            )
            with connect_db() as conn:
                conn.execute("UPDATE crops SET notified=1 WHERE id=?", (row["id"],))
        except discord.Forbidden:
            print(f"Missing permission to send in channel {row['channel_id']}.")
        except discord.HTTPException as exc:
            print(f"Could not send harvest alert: {exc}")

@check_harvests.before_loop
async def before_check_harvests():
    await bot.wait_until_ready()

if not TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN. Copy .env.example to .env and add your bot token.")

bot.run(TOKEN)
