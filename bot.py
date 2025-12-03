print(">>> bot.py loaded")

# Word Assassin Bot – Full Pro Version with Environment BOT_TOKEN

import os
import json
import random
import re
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

DATA_FILE = "game.json"
BOT_USERNAME = "WordAssassinGameBot"   # Without @

# Load token from ENV
BOT_TOKEN = os.getenv("BOT_TOKEN")     # <<< DO NOT CHANGE THIS

# Word Difficulty Pools
COMMON_WORDS_EASY = ["hello","yes","bro","ok","sorry","good","thanks","hi"]
COMMON_WORDS_MEDIUM = ["tomorrow","night","wait","where","come","why","later"]
COMMON_WORDS_HARD = ["probably","actually","honestly","between","seriously"]

DIFFICULTY_WORDS = {
    "easy": COMMON_WORDS_EASY,
    "medium": COMMON_WORDS_MEDIUM,
    "hard": COMMON_WORDS_HARD
}

DEFAULT_DIFFICULTY = "medium"

# ---------------------- STORAGE ----------------------
def initial_state():
    return {
        "lobby": {"players": [], "status": "waiting"},
        "players": {},
        "difficulty": DEFAULT_DIFFICULTY,
        "teams": {}
    }

def load():
    if not os.path.exists(DATA_FILE):
        return initial_state()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        return initial_state()
    data.setdefault("lobby", {"players": [], "status": "waiting"})
    data.setdefault("players", {})
    data.setdefault("difficulty", DEFAULT_DIFFICULTY)
    data.setdefault("teams", {})
    return data

def save(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def html_escape(t: str):
    return (
        t.replace("&","&amp;")
         .replace("<","&lt;")
         .replace(">","&gt;")
    )

def get_words(level):
    return DIFFICULTY_WORDS.get(level, COMMON_WORDS_MEDIUM)

# ---------------------- START / HELP ----------------------
async def start_or_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    # PM Menu
    if chat.type == "private":
        text = (
            "<b>Word Assassin Pro</b>\n\n"
            "A deception game for Telegram groups.\n"
            "Choose an option:"
        )
        keyboard = [
            [
                InlineKeyboardButton("How to Play 🎮", callback_data="how_play"),
                InlineKeyboardButton("Tutorial 🎬", callback_data="tutorial")
            ],
            [InlineKeyboardButton("PM Leaderboard 🏆", callback_data="lb_pm")],
            [
                InlineKeyboardButton(
                    "➕ Add me to a Group",
                    url=f"https://t.me/{BOT_USERNAME}?startgroup=true"
                )
            ]
        ]
        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Group help
    msg = (
        "<b>Word Assassin – Commands</b>\n\n"
        "<b>Game</b>\n"
        "/startgame – Open lobby\n"
        "/forcestart – Start game (admin)\n"
        "/leave – Leave lobby\n"
        "/kick – Kick lobby player (admin)\n\n"
        "<b>Settings</b>\n"
        "/difficulty easy|medium|hard\n"
        "/team TeamName\n\n"
        "<b>Info</b>\n"
        "/leaderboard\n"
        "/clearleaderboard\n"
        "/resetgame\n"
        "/rules\n"
        "/status\n"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

# ---------------------- INLINE CALLBACKS ----------------------
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data

    if data == "how_play":
        txt = (
            "<b>How to Play</b>\n\n"
            "1. Add bot to group\n"
            "2. /startgame → players join\n"
            "3. /forcestart → assignments sent\n"
            "4. Trick target to say the kill word\n"
            "5. Eliminate, chain continues\n"
        )
        await q.message.edit_text(txt, parse_mode=ParseMode.HTML)

    elif data == "tutorial":
        steps = [
            "Step 1: Add bot to group & make admin",
            "Step 2: /startgame → Join button",
            "Step 3: /forcestart → target & kill word in DM",
            "Step 4: Trick target to say the word"
        ]
        await q.message.edit_text("🎬 <b>Tutorial</b>\n\n"+steps[0], parse_mode=ParseMode.HTML)
        for s in steps[1:]:
            await q.message.chat.send_message(s, parse_mode=ParseMode.HTML)

    elif data == "lb_pm":
        db = load()
        pl = db["players"]
        if not pl:
            await q.answer("No data", show_alert=True)
            return

        sorted_pl = sorted(pl.items(), key=lambda x: x[1]["kills"], reverse=True)
        msg = "🏆 <b>Global Leaderboard</b>\n\n"
        r = 1
        for pid, info in sorted_pl:
            msg += f"{r}. @{html_escape(info['username'])} — {info['kills']} kills\n"
            r += 1
        await q.message.edit_text(msg, parse_mode=ParseMode.HTML)

    await q.answer()

# ---------------------- RULES ----------------------
async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "<b>Rules</b>\n\n"
        "• You get a target + kill word in DM\n"
        "• Trick target to say that exact word\n"
        "• You kill them → get new target\n"
        "• Last alive wins\n\n"
        "No spamming, no revealing your word."
    )
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)

# ---------------------- START GAME ----------------------
async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group","supergroup"):
        await update.message.reply_text("Use /startgame in group")
        return

    save(initial_state())
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎮 Join Game", callback_data="join")]])
    await update.message.reply_text("Lobby open!", reply_markup=kb)

# ---------------------- JOIN ----------------------
async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    u = q.from_user
    chat = q.message.chat

    if chat.type not in ("group","supergroup"):
        await q.answer("Join from group", show_alert=True)
        return

    db = load()
    if db["lobby"]["status"] != "waiting":
        await q.answer("Game already started", show_alert=True)
        return

    # DM permission check
    try:
        await context.bot.send_message(u.id, "Joined. Missions will come here.")
    except:
        await q.answer("Open bot in DM & press START, then join again.", show_alert=True)
        return

    if u.id not in db["lobby"]["players"]:
        db["lobby"]["players"].append(u.id)
        save(db)
        await chat.send_message(f"🟢 @{u.username} joined!")
    await q.answer()

# ---------------------- LEAVE ----------------------
async def leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db = load()
    if uid in db["lobby"]["players"]:
        db["lobby"]["players"].remove(uid)
        save(db)
        await update.message.reply_text("You left.")
    else:
        await update.message.reply_text("Not in lobby.")

# ---------------------- TEAM ----------------------
async def team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Use: /team Name")
        return
    name = " ".join(context.args)
    db = load()
    db["teams"][str(update.effective_user.id)] = name
    save(db)
    await update.message.reply_text(f"Team set: {name}")

# ---------------------- DIFFICULTY ----------------------
async def difficulty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    db = load()

    if chat.type not in ("group","supergroup"):
        await update.message.reply_text("Use in group.")
        return

    admins = [a.user.id for a in await context.bot.get_chat_administrators(chat.id)]
    if update.effective_user.id not in admins:
        await update.message.reply_text("Admins only.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /difficulty easy|medium|hard")
        return

    level = context.args[0].lower()
    if level not in DIFFICULTY_WORDS:
        await update.message.reply_text("Invalid level.")
        return

    db["difficulty"] = level
    save(db)
    await update.message.reply_text(f"Difficulty set: {level}")

# ---------------------- FORCE START ----------------------
async def forcestart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group","supergroup"):
        await update.message.reply_text("Use in group.")
        return

    admins = [a.user.id for a in await context.bot.get_chat_administrators(chat.id)]
    if update.effective_user.id not in admins:
        await update.message.reply_text("Admins only.")
        return

    db = load()
    players = db["lobby"]["players"]

    if len(players) < 2:
        await update.message.reply_text("Need 2+ players.")
        return

    random.shuffle(players)
    db["players"] = {}
    level = db["difficulty"]
    pool = get_words(level)

    for i,p in enumerate(players):
        target = players[(i+1) % len(players)]
        kill = random.choice(pool)

        cm = await context.bot.get_chat_member(chat.id, p)
        tm = await context.bot.get_chat_member(chat.id, target)

        pu = cm.user.username or str(p)
        tu = tm.user.username or str(target)

        db["players"][str(p)] = {
            "username": pu,
            "target": target,
            "kill_word": kill,
            "alive": True,
            "kills": 0
        }

        try:
            await context.bot.send_message(
                p,
                f"<b>Your Target</b>\n@{tu}\n<b>Word:</b> {kill}",
                parse_mode=ParseMode.HTML
            )
        except:
            await chat.send_message(f"⚠️ Cannot DM @{pu}. They must press START.")

    db["lobby"]["status"] = "locked"
    save(db)
    await update.message.reply_text(f"🔥 Game started! Difficulty: {level}")

# ---------------------- KICK ----------------------
async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group","supergroup"):
        await update.message.reply_text("Use in group.")
        return

    admins = [a.user.id for a in await context.bot.get_chat_administrators(chat.id)]
    if update.effective_user.id not in admins:
        await update.message.reply_text("Admins only.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /kick @user")
        return

    username = context.args[0].replace("@","")
    db = load()
    remove_id = None

    for pid in db["lobby"]["players"]:
        m = await context.bot.get_chat_member(chat.id, pid)
        if (m.user.username or "").lower() == username.lower():
            remove_id = pid
            break

    if remove_id:
        db["lobby"]["players"].remove(remove_id)
        save(db)
        await update.message.reply_text(f"Removed @{username}")
    else:
        await update.message.reply_text("Not found.")

# ---------------------- LEADERBOARD ----------------------
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load()
    pl = db["players"]
    if not pl:
        await update.message.reply_text("No game yet.")
        return

    sorted_pl = sorted(pl.items(), key=lambda x: x[1]["kills"], reverse=True)
    msg = "🏆 <b>Leaderboard</b>\n\n"
    i = 1
    for pid, info in sorted_pl:
        msg += f"{i}. @{html_escape(info['username'])} — {info['kills']} kills\n"
        i += 1

    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

# ---------------------- CLEAR LEADERBOARD ----------------------
async def clear_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group","supergroup"):
        await update.message.reply_text("Use in group.")
        return

    admins = [a.user.id for a in await context.bot.get_chat_administrators(chat.id)]
    if update.effective_user.id not in admins:
        await update.message.reply_text("Admins only.")
        return

    db = load()
    db["players"] = {}
    save(db)

    await update.message.reply_text("Leaderboard cleared.")

# ---------------------- RESET GAME ----------------------
async def resetgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group","supergroup"):
        await update.message.reply_text("Use in group.")
        return

    admins = [a.user.id for a in await context.bot.get_chat_administrators(chat.id)]
    if update.effective_user.id not in admins:
        await update.message.reply_text("Admins only.")
        return

    save(initial_state())
    await update.message.reply_text("Game reset.")

# ---------------------- STATUS ----------------------
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load()
    lobby = db["lobby"]
    players = db["players"]

    t = (
        "<b>Status</b>\n\n"
        f"Lobby players: {len(lobby['players'])}\n"
        f"Active players: {len(players)}\n"
    )

    await update.message.reply_text(t, parse_mode=ParseMode.HTML)

# ---------------------- KILL ENGINE ----------------------
async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group","supergroup"):
        return

    msg = update.message
    if not msg or not msg.text:
        return

    text = msg.text.lower()
    victim_id = str(msg.from_user.id)

    db = load()
    players = db["players"]

    if victim_id not in players:
        return

    for killer_id, info in players.items():
        if not info["alive"]:
            continue

        if str(info["target"]) != victim_id:
            continue

        word = info["kill_word"].lower()

        if re.search(rf"\b{re.escape(word)}\b", text):
            killer = info["username"]
            victim = players[victim_id]["username"]

            info["kills"] += 1
            players[victim_id]["alive"] = False

            new_target = players[victim_id]["target"]
            new_word = random.choice(get_words(db["difficulty"]))

            info["target"] = new_target
            info["kill_word"] = new_word

            save(db)

            # announce
            await chat.send_message(
                f"💥 @{killer} eliminated @{victim} using '{word}'!"
            )

            # DM
            try:
                tu = players[str(new_target)]["username"]
                await context.bot.send_message(
                    killer_id,
                    f"🎯 New target: @{tu}\n🔪 Word: {new_word}"
                )
            except:
                pass

            return

# ---------------------- MAIN ----------------------
def main():
    print(">>> main() started")

    request = HTTPXRequest(
        connect_timeout=10,
        read_timeout=10,
        write_timeout=10,
        pool_timeout=10
    )

    app = ApplicationBuilder().token(BOT_TOKEN).request(request).build()

    print(">>> polling starting...")

    # Start/help
    app.add_handler(CommandHandler("start", start_or_help))
    app.add_handler(CommandHandler("help", start_or_help))

    # Game
    app.add_handler(CommandHandler("startgame", startgame))
    app.add_handler(CommandHandler("forcestart", forcestart))
    app.add_handler(CommandHandler("leave", leave))
    app.add_handler(CommandHandler("kick", kick))
    app.add_handler(CommandHandler("difficulty", difficulty))
    app.add_handler(CommandHandler("team", team))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("clearleaderboard", clear_leaderboard))
    app.add_handler(CommandHandler("resetgame", resetgame))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("status", status))

    # Join + menu
    app.add_handler(CallbackQueryHandler(join_game, pattern="^join$"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^(how_play|tutorial|lb_pm)$"))

    # Kill detection
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_message))

    app.run_polling()

if __name__ == "__main__":
    main()
