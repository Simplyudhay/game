print(">>> bot.py loaded")

# Word Assassin Game Bot – Pro Version (Single Group State)

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.request import HTTPXRequest
from telegram.constants import ParseMode

import random
import json
import re
import os

DATA_FILE = "game.json"
BOT_USERNAME = "WordAssassinGameBot"  # without @

# ---------------------------------------------------------
# WORD LISTS + DIFFICULTY
# ---------------------------------------------------------
COMMON_WORDS_EASY = [
    "hello", "yes", "bro", "ok", "sorry", "good", "thanks", "hi"
]

COMMON_WORDS_MEDIUM = [
    "tomorrow", "night", "wait", "where", "come", "why", "later"
]

COMMON_WORDS_HARD = [
    "probably", "actually", "honestly", "between", "seriously"
]

DIFFICULTY_WORDS = {
    "easy": COMMON_WORDS_EASY,
    "medium": COMMON_WORDS_MEDIUM,
    "hard": COMMON_WORDS_HARD,
}

DEFAULT_DIFFICULTY = "medium"

# ---------------------------------------------------------
# BASIC LOAD / SAVE SYSTEM
# ---------------------------------------------------------
def initial_state():
    return {
        "lobby": {"players": [], "status": "waiting"},
        "players": {},
        "difficulty": DEFAULT_DIFFICULTY,
        "teams": {},
    }


def load():
    if not os.path.exists(DATA_FILE):
        return initial_state()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return initial_state()

    # Ensure keys
    data.setdefault("lobby", {"players": [], "status": "waiting"})
    data.setdefault("players", {})
    data.setdefault("difficulty", DEFAULT_DIFFICULTY)
    data.setdefault("teams", {})

    return data


def save(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def get_words_for_difficulty(level: str):
    return DIFFICULTY_WORDS.get(level, COMMON_WORDS_MEDIUM)


def html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ---------------------------------------------------------
# /start and /help – PM vs GROUP
# ---------------------------------------------------------
async def start_or_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    # PRIVATE CHAT: show inline menu + add-to-group button
    if chat.type == "private":
        text = (
            "<b>Word Assassin Bot</b>\n\n"
            "I’m a social deception game for groups.\n\n"
            "1️⃣ Add me to a group\n"
            "2️⃣ In that group use <code>/startgame</code>\n"
            "3️⃣ Players tap <b>Join Game</b>\n"
            "4️⃣ Admin uses <code>/forcestart</code>\n\n"
            "Choose an option below:"
        )

        keyboard = [
            [
                InlineKeyboardButton("How to Play 🎮", callback_data="how_play"),
                InlineKeyboardButton("Tutorial 🎬", callback_data="tutorial"),
            ],
            [InlineKeyboardButton("PM Leaderboard 🏆", callback_data="lb_pm")],
            [
                InlineKeyboardButton(
                    "➕ Add me to a Group",
                    url=f"https://t.me/{BOT_USERNAME}?startgroup=true",
                )
            ],
        ]

        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # GROUP CHAT: show commands list
    commands_text = (
        "<b>Word Assassin – Commands</b>\n\n"
        "<b>Core Game</b>\n"
        "/startgame – Open lobby\n"
        "/forcestart – Start game (admin)\n"
        "/leave – Leave lobby\n"
        "/kick @user – Kick from lobby (admin)\n\n"
        "<b>Gameplay Settings</b>\n"
        "/difficulty easy|medium|hard – Set kill word difficulty (admin)\n"
        "/team TeamName – Join a team\n\n"
        "<b>Info & Control</b>\n"
        "/leaderboard – Show current leaderboard\n"
        "/clearleaderboard – Wipe leaderboard (admin)\n"
        "/resetgame – Full reset of game state (admin)\n"
        "/rules – Show game rules\n"
        "/status – Show current game status\n"
    )

    await update.message.reply_text(commands_text, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------
# INLINE MENU CALLBACK HANDLER (PM)
# ---------------------------------------------------------
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data_id = query.data

    if data_id == "how_play":
        text = (
            "<b>How to Play – Word Assassin</b>\n\n"
            "1️⃣ Add bot to a group & make it admin.\n"
            "2️⃣ Use <code>/startgame</code> to open lobby.\n"
            "3️⃣ Players tap <b>Join Game</b>.\n"
            "4️⃣ Admin uses <code>/forcestart</code>.\n"
            "5️⃣ You get a target + kill word in DM.\n"
            "6️⃣ Trick your target into typing that word in the group.\n"
            "7️⃣ Bot announces kills & reassigns targets.\n\n"
            "Last assassin standing or with most kills wins. 🔥"
        )
        await query.message.edit_text(text, parse_mode=ParseMode.HTML)

    elif data_id == "tutorial":
        steps = [
            "🎬 <b>Tutorial – Step 1/4</b>\nAdd me to a group and make me admin.",
            "🎬 <b>Tutorial – Step 2/4</b>\nIn that group, type <code>/startgame</code>. Players tap <b>Join Game</b>.",
            "🎬 <b>Tutorial – Step 3/4</b>\nAdmin types <code>/forcestart</code>. You’ll get your target & kill word here in DM.",
            "🎬 <b>Tutorial – Step 4/4</b>\nChat naturally, trick your target into typing that word. 💥",
        ]
        await query.message.edit_text(steps[0], parse_mode=ParseMode.HTML)
        for s in steps[1:]:
            await query.message.chat.send_message(s, parse_mode=ParseMode.HTML)

    elif data_id == "lb_pm":
        data = load()
        players = data.get("players", {})
        if not players:
            await query.answer("No games played yet.", show_alert=True)
            return

        sorted_players = sorted(
            players.items(),
            key=lambda kv: kv[1].get("kills", 0),
            reverse=True,
        )

        msg = "🏆 <b>Global Leaderboard</b>\n\n"
        rank = 1
        for pid, info in sorted_players:
            uname = html_escape(info.get("username") or str(pid))
            kills = info.get("kills", 0)
            msg += f"{rank}. @{uname} — {kills} kills\n"
            rank += 1

        await query.message.edit_text(msg, parse_mode=ParseMode.HTML)

    await query.answer()


# ---------------------------------------------------------
# /rules
# ---------------------------------------------------------
async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "<b>Word Assassin – Rules</b>\n\n"
        "• You will receive a secret <b>target</b> and a <b>kill word</b> in DM.\n"
        "• Your goal is to make your target type that word in the group chat.\n"
        "• You cannot force them (no “type this word”), you must trick them.\n"
        "• Once they type the exact word, you eliminate them.\n"
        "• You then get a new target and a new kill word.\n"
        "• Last player alive or with the most kills wins.\n\n"
        "<b>Fair play:</b>\n"
        "• No spamming long word lists.\n"
        "• No telling others their kill words.\n"
        "• Admin can reset or clear leaderboard if needed.\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------
# /startgame → OPEN LOBBY
# ---------------------------------------------------------
async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Use /startgame in a group.")
        return

    data = initial_state()
    save(data)

    keyboard = [[InlineKeyboardButton("🎮 Join Game", callback_data="join")]]

    await update.message.reply_text(
        "🎮 WORD ASSASSIN LOBBY OPEN!\nPress the button to join.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---------------------------------------------------------
# JOIN GAME (GROUP BUTTON)
# ---------------------------------------------------------
async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    chat = query.message.chat

    if chat.type not in ("group", "supergroup"):
        await query.answer("Join from the game group.", show_alert=True)
        return

    data = load()
    lobby = data["lobby"]

    if lobby["status"] != "waiting":
        await query.answer("Game already started.", show_alert=True)
        return

    if user.id in lobby["players"]:
        await query.answer("You already joined.", show_alert=True)
        return

    # Try DM first (Telegram rule: user must start bot)
    try:
        await context.bot.send_message(
            chat_id=user.id,
            text="You joined Word Assassin.\nI will send your missions here in DM."
        )
    except Exception:
        await query.answer(
            "Open me in private & press START, then join again.",
            show_alert=True,
        )
        return

    lobby["players"].append(user.id)
    save(data)

    await chat.send_message(f"🟢 @{user.username} joined the game!")
    await query.answer()


# ---------------------------------------------------------
# LEAVE LOBBY
# ---------------------------------------------------------
async def leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    data = load()

    if uid in data["lobby"]["players"]:
        data["lobby"]["players"].remove(uid)
        save(data)
        await update.message.reply_text("🚪 You left the game.")
    else:
        await update.message.reply_text("You are not in the lobby.")


# ---------------------------------------------------------
# /team – REGISTER TEAM
# ---------------------------------------------------------
async def team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /team TeamName")
        return

    team_name = " ".join(context.args).strip()
    data = load()
    data["teams"][str(update.effective_user.id)] = team_name
    save(data)

    await update.message.reply_text(
        f"✅ @{update.effective_user.username} joined team: {team_name}"
    )


# ---------------------------------------------------------
# /difficulty – SET DIFFICULTY (ADMIN)
# ---------------------------------------------------------
async def difficulty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Use /difficulty in a group.")
        return

    user = update.effective_user
    admins = await context.bot.get_chat_administrators(chat.id)
    admin_ids = [a.user.id for a in admins]
    if user.id not in admin_ids:
        await update.message.reply_text("Admins only.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /difficulty easy|medium|hard")
        return

    level = context.args[0].lower()
    if level not in DIFFICULTY_WORDS:
        await update.message.reply_text("Invalid difficulty.")
        return

    data = load()
    data["difficulty"] = level
    save(data)

    await update.message.reply_text(f"✅ Difficulty set to: {level}")


# ---------------------------------------------------------
# /forcestart – ASSIGN TARGETS (ADMIN)
# ---------------------------------------------------------
async def forcestart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Use /forcestart in a group.")
        return

    user = update.effective_user
    admins = await context.bot.get_chat_administrators(chat.id)
    admin_ids = [a.user.id for a in admins]
    if user.id not in admin_ids:
        await update.message.reply_text("Admins only.")
        return

    data = load()
    players = data["lobby"]["players"]

    if len(players) < 2:
        await update.message.reply_text("Need at least 2 players.")
        return

    random.shuffle(players)
    data["players"] = {}
    words_pool = get_words_for_difficulty(data["difficulty"])

    # Assign circular targets
    for i, p in enumerate(players):
        target = players[(i + 1) % len(players)]
        kill_word = random.choice(words_pool)

        member = await context.bot.get_chat_member(chat.id, p)
        target_member = await context.bot.get_chat_member(chat.id, target)

        username = member.user.username or str(member.user.id)
        target_username = target_member.user.username or str(target_member.user.id)

        data["players"][str(p)] = {
            "username": username,
            "target": target,
            "kill_word": kill_word,
            "alive": True,
            "kills": 0,
        }

        try:
            await context.bot.send_message(
                chat_id=p,
                text=(
                    "<b>Your Assignment</b>\n\n"
                    f"Target: @{html_escape(target_username)}\n"
                    f"Kill word: <b>{html_escape(kill_word)}</b>\n\n"
                    "Talk normally in the group and make them say it."
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            await chat.send_message(
                f"⚠️ @{username} could not be DM'ed. "
                "Ask them to press START in DM before next game."
            )

    data["lobby"]["status"] = "locked"
    save(data)

    await update.message.reply_text(
        f"🔥 Game started! Difficulty: {data['difficulty']}"
    )


# ---------------------------------------------------------
# /kick – REMOVE FROM LOBBY (ADMIN)
# ---------------------------------------------------------
async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Use /kick in a group.")
        return

    user = update.effective_user
    admins = await context.bot.get_chat_administrators(chat.id)
    admin_ids = [a.user.id for a in admins]
    if user.id not in admin_ids:
        await update.message.reply_text("Admins only.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /kick @username")
        return

    to_kick = context.args[0].replace("@", "")
    data = load()

    remove_id = None
    for pid in data["lobby"]["players"]:
        m = await context.bot.get_chat_member(chat.id, pid)
        if (m.user.username or "").lower() == to_kick.lower():
            remove_id = pid
            break

    if remove_id:
        data["lobby"]["players"].remove(remove_id)
        save(data)
        await update.message.reply_text(f"❌ @{to_kick} removed from lobby.")
    else:
        await update.message.reply_text("User not found in lobby.")


# ---------------------------------------------------------
# /leaderboard – GROUP LEADERBOARD
# ---------------------------------------------------------
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    players = data.get("players", {})
    teams = data.get("teams", {})

    if not players:
        await update.message.reply_text("No game data yet.")
        return

    sorted_players = sorted(
        players.items(),
        key=lambda kv: kv[1].get("kills", 0),
        reverse=True,
    )

    msg = "🏆 <b>Leaderboard</b>\n\n"
    r = 1
    for pid, info in sorted_players:
        name = html_escape(info["username"])
        kills = info["kills"]
        teamname = teams.get(str(pid))
        if teamname:
            msg += f"{r}. @{name} [{teamname}] — {kills} kills\n"
        else:
            msg += f"{r}. @{name} — {kills} kills\n"
        r += 1

    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------
# /clearleaderboard – ADMIN
# ---------------------------------------------------------
async def clear_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Use /clearleaderboard in the game group.")
        return

    user = update.effective_user
    admins = await context.bot.get_chat_administrators(chat.id)
    admin_ids = [a.user.id for a in admins]
    if user.id not in admin_ids:
        await update.message.reply_text("Admins only.")
        return

    data = load()
    data["players"] = {}
    save(data)

    await update.message.reply_text("🧹 Leaderboard cleared.")


# ---------------------------------------------------------
# /resetgame – FULL RESET (ADMIN)
# ---------------------------------------------------------
async def resetgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Use /resetgame in the game group.")
        return

    user = update.effective_user
    admins = await context.bot.get_chat_administrators(chat.id)
    admin_ids = [a.user.id for a in admins]
    if user.id not in admin_ids:
        await update.message.reply_text("Admins only.")
        return

    data = initial_state()
    save(data)

    await update.message.reply_text("♻️ Game state fully reset.")


# ---------------------------------------------------------
# /status – SHOW CURRENT GAME STATUS
# ---------------------------------------------------------
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load()
    players = data.get("players", {})
    lobby = data.get("lobby", {})

    lobby_count = len(lobby.get("players", []))
    if not players:
        text = (
            "<b>Game Status</b>\n\n"
            f"Lobby players: {lobby_count}\n"
            "No active game yet.\n"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    alive = [p for p in players.values() if p.get("alive")]
    dead = [p for p in players.values() if not p.get("alive")]

    text = (
        "<b>Game Status</b>\n\n"
        f"Lobby players (before start): {lobby_count}\n"
        f"Alive: {len(alive)}\n"
        f"Eliminated: {len(dead)}\n\n"
    )

    if alive:
        text += "Alive players:\n"
        for p in alive:
            text += f"• @{html_escape(p['username'])}\n"

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------
# MESSAGE CHECKER – KILL SYSTEM
# ---------------------------------------------------------
async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        return

    message = update.message
    if not message or not message.text:
        return

    text = message.text.lower()
    victim_id = str(message.from_user.id)

    data = load()
    players = data.get("players", {})

    if victim_id not in players:
        return

    for killer_id, info in players.items():
        if not info.get("alive", True):
            continue

        if str(info.get("target")) != victim_id:
            continue

        kill_word = info.get("kill_word", "").lower()
        if not kill_word:
            continue

        # basic anti-cheat: ignore very long messages
        if len(text) > 300:
            return

        if not re.search(rf"\b{re.escape(kill_word)}\b", text):
            continue

        killer_name = info["username"]
        victim_name = players[victim_id]["username"]

        info["kills"] += 1
        players[victim_id]["alive"] = False

        # chain target + new word
        new_target = players[victim_id]["target"]
        new_word = random.choice(get_words_for_difficulty(data["difficulty"]))
        info["target"] = new_target
        info["kill_word"] = new_word

        save(data)

        await chat.send_message(
            f"💥 @{killer_name} eliminated @{victim_name} using the word '{kill_word}'!"
        )

        try:
            target_username = players[str(new_target)]["username"]
            await context.bot.send_message(
                killer_id,
                f"🎯 New target: @{target_username}\n🔪 New word: '{new_word}'"
            )
        except Exception:
            pass

        return


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
def main():
    print(">>> main() started")

    request = HTTPXRequest(
        connect_timeout=10,
        read_timeout=10,
        write_timeout=10,
        pool_timeout=10,
    )

    BOT_TOKEN = "8069533921:AAExzWpIhvoVwobAr_76fXoTmaB7ihXk-EY"  # <<< put your real token here

    app = ApplicationBuilder().token(BOT_TOKEN).request(request).build()

    print(">>> polling starting...")

    # PM + Group help
    app.add_handler(CommandHandler("start", start_or_help))
    app.add_handler(CommandHandler("help", start_or_help))

    # Group commands
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

    # Inline menu + join
    app.add_handler(CallbackQueryHandler(join_game, pattern="^join$"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^(how_play|tutorial|lb_pm)$"))

    # Kill detection
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), check_message))

    app.run_polling()


if __name__ == "__main__":
    main()
