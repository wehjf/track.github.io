import os
import asyncio
import datetime
import re
import importlib
from typing import Optional

# dotenv is optional on the server — fall back to real environment variables if missing
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    # python-dotenv not installed or not needed; rely on actual env vars set in Render
    pass

import discord
from discord.ext import commands

# Try to import a DB helper module under several common names so the code works
# whether the file is named db.py, dp.py, db_execution_manager.py, or execution_db_helper.py.
db_module_names = ["db", "dp", "db_execution_manager", "execution_db_helper", "execution_tracker"]
dbmod = None
for name in db_module_names:
    try:
        dbmod = importlib.import_module(name)
        print(f"Loaded DB module: {name}")
        break
    except ModuleNotFoundError:
        continue

if dbmod is None:
    raise ModuleNotFoundError(
        "No DB helper module found. Add db.py (or dp.py / db_execution_manager.py / execution_db_helper.py) "
        "to the repo root or edit the import in your entrypoint to match your DB filename."
    )

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
WATCH_CHANNEL_ID = int(os.getenv("WATCH_CHANNEL_ID") or 0)
STATS_CHANNEL_ID = int(os.getenv("STATS_CHANNEL_ID") or 0)
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID") or 0)

if not DISCORD_TOKEN or not WATCH_CHANNEL_ID or not STATS_CHANNEL_ID:
    print("ERROR: DISCORD_TOKEN, WATCH_CHANNEL_ID and STATS_CHANNEL_ID must be set in environment")
    raise SystemExit(1)

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)


def parse_embed_for_execution(embed: discord.Embed):
    if not embed:
        return None, None, None
    title = (embed.title or "").lower()
    username = None
    user_id = None
    exec_count = None
    for field in getattr(embed, "fields", []):
        name = (field.name or "").strip().lower()
        value = (field.value or "").strip()
        if "username" in name or name == "user":
            username = value
        elif "userid" in name or "user id" in name or "user_id" in name:
            m = re.search(r"\d+", value)
            if m:
                user_id = m.group(0)
            else:
                user_id = value
        elif "execution" in name and "count" in name:
            m = re.search(r"\d+", value)
            exec_count = int(m.group(0)) if m else None
    desc = (embed.description or "") if getattr(embed, "description", None) else ""
    if desc and (not user_id or not username):
        m_user = re.search(r"Username\s*[:\-]?\s*([^\n\r]+)", desc, re.IGNORECASE)
        m_uid = re.search(r"UserId\s*[:\-]?\s*(\d+)", desc, re.IGNORECASE)
        if m_user and not username:
            username = m_user.group(1).strip()
        if m_uid and not user_id:
            user_id = m_uid.group(1).strip()
    return username, user_id, exec_count


@bot.event
async def on_ready():
    # initialize DB and start the stats poster
    await dbmod.init_db()
    bot.loop.create_task(stats_poster())
    print(f"Bot ready. Logged in as: {bot.user}")


@bot.event
async def on_message(message: discord.Message):
    # ignore messages from ourselves but still allow command processing
    if message.author and message.author.id == bot.user.id:
        await bot.process_commands(message)
        return

    if message.channel.id != WATCH_CHANNEL_ID:
        await bot.process_commands(message)
        return

    if message.embeds:
        for embed in message.embeds:
            username, user_id, exec_count = parse_embed_for_execution(embed)
            if username or user_id:
                uid_for_db = user_id if user_id else (username or str(message.id))
                ts = int(message.created_at.replace(tzinfo=datetime.timezone.utc).timestamp())
                inserted = await dbmod.add_execution(str(message.id), uid_for_db, username or "unknown", ts, exec_count)
                if inserted:
                    text = f"Parsed execution from embed — Username: {username}, UserId: {uid_for_db}, ExecCount: {exec_count}"
                    print(text)
                    if LOG_CHANNEL_ID:
                        try:
                            log_chan = bot.get_channel(LOG_CHANNEL_ID)
                            if log_chan:
                                await log_chan.send(text)
                        except Exception as e:
                            print("Log channel send failed", e)
                else:
                    print(f"Embed message {message.id} already recorded; skipping.")
            else:
                print(f"Embed in message {message.id} didn't match expected fields; skipping.")
    await bot.process_commands(message)


@bot.command(name="import_history")
@commands.has_permissions(manage_messages=True)
async def import_history(ctx, limit: int = 500):
    if ctx.channel.id != WATCH_CHANNEL_ID:
        await ctx.send("This command must be run in the configured watch channel.")
        return
    await ctx.send(f"Starting history import of last {limit} messages...")
    processed = 0
    inserted = 0
    async for msg in ctx.channel.history(limit=limit, oldest_first=False):
        processed += 1
        if msg.embeds:
            for embed in msg.embeds:
                username, user_id, exec_count = parse_embed_for_execution(embed)
                if username or user_id:
                    uid_for_db = user_id if user_id else (username or str(msg.id))
                    ts = int(msg.created_at.replace(tzinfo=datetime.timezone.utc).timestamp())
                    ok = await dbmod.add_execution(str(msg.id), uid_for_db, username or "unknown", ts, exec_count)
                    if ok:
                        inserted += 1
    await ctx.send(f"Import complete. Processed {processed} messages, inserted {inserted} new executions.")


@bot.command(name="stats")
async def stats_command(ctx):
    minute_count = await dbmod.count_since(60)
    hour_count = await dbmod.count_since(3600)
    day_count = await dbmod.count_since(86400)
    minute_unique = await dbmod.unique_users_since(60)
    hour_unique = await dbmod.unique_users_since(3600)
    day_unique = await dbmod.unique_users_since(86400)
    now = datetime.datetime.utcnow()
    embed = discord.Embed(title="Execution Stats", color=0x3498db, timestamp=now)
    embed.add_field(name="Last minute — Executions", value=str(minute_count), inline=True)
    embed.add_field(name="Last minute — Unique users", value=str(minute_unique), inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(name="Last hour — Executions", value=str(hour_count), inline=True)
    embed.add_field(name="Last hour — Unique users", value=str(hour_unique), inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(name="Last day — Executions", value=str(day_count), inline=True)
    embed.add_field(name="Last day — Unique users", value=str(day_unique), inline=True)
    embed.set_footer(text="Execution Tracker")
    await ctx.send(embed=embed)


async def stats_poster():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.datetime.utcnow()
        secs_to_next_minute = 60 - now.second
        await asyncio.sleep(secs_to_next_minute)
        now = datetime.datetime.utcnow()
        minute = now.minute
        hour = now.hour
        minute_count = await dbmod.count_since(60)
        minute_unique = await dbmod.unique_users_since(60)
        channel = bot.get_channel(STATS_CHANNEL_ID)
        if channel:
            embed = discord.Embed(title="Execution Summary (Last minute)", color=0x2ecc71, timestamp=now)
            embed.add_field(name="Executions", value=str(minute_count), inline=True)
            embed.add_field(name="Unique users", value=str(minute_unique), inline=True)
            await channel.send(embed=embed)
        if minute == 0:
            hour_count = await dbmod.count_since(3600)
            hour_unique = await dbmod.unique_users_since(3600)
            if channel:
                embed = discord.Embed(title="Execution Summary (Last hour)", color=0xf1c40f, timestamp=now)
                embed.add_field(name="Executions", value=str(hour_count), inline=True)
                embed.add_field(name="Unique users", value=str(hour_unique), inline=True)
                await channel.send(embed=embed)
            if hour == 0:
                day_count = await dbmod.count_since(86400)
                day_unique = await dbmod.unique_users_since(86400)
                if channel:
                    embed = discord.Embed(title="Execution Summary (Last day)", color=0xe74c3c, timestamp=now)
                    embed.add_field(name="Executions", value=str(day_count), inline=True)
                    embed.add_field(name="Unique users", value=str(day_unique), inline=True)
                    await channel.send(embed=embed)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
