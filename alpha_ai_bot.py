"""
╔══════════════════════════════════════════════════════════════╗
║           ALPHA AI SIGNALS — Pocket Option Signal Bot        ║
║           with Quotex OTC Candle Result Verification         ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import random
import logging
import time
from datetime import datetime, timedelta

import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ── Quotex API ───────────────────────────────────────────────────────────────
QUOTEX_AVAILABLE = False
try:
    from quotexapi.stable_api import Quotex
    QUOTEX_AVAILABLE = True
    print("✅ quotexapi loaded successfully")
except ImportError:
    print("⚠️  quotexapi not available — results will show UNAVAILABLE")

# ════════════════════════════════════════════════════════════════
#  YOUR CONFIGURATION  ← update these
# ════════════════════════════════════════════════════════════════

BOT_TOKEN       = "YOUR_NEW_BOT_TOKEN_HERE"   # ← paste your new token
QUOTEX_EMAIL    = "tloontop01@gmail.com"
QUOTEX_PASSWORD = "Zxcvbnm0@"
QUOTEX_IS_DEMO  = True
ADMIN_ID        = "7571089858"
CHANNEL_ID      = -1003734299929
USERS_FILE      = "users.txt"
PAIRS_FILE      = "pairs.txt"

# Signal timing
SIGNAL_GAP_MIN  = 110
SIGNAL_GAP_MAX  = 140
CANDLE_WAIT     = 65
MTG_WAIT        = 62

# ════════════════════════════════════════════════════════════════
#  CONSTANTS
# ════════════════════════════════════════════════════════════════

IST = pytz.timezone("Asia/Kolkata")
logging.basicConfig(level=logging.WARNING)

DEFAULT_PAIRS = [
    ("EUR/USD (OTC)", "EURUSD-OTC"),
    ("GBP/USD (OTC)", "GBPUSD-OTC"),
    ("USD/JPY (OTC)", "USDJPY-OTC"),
    ("AUD/USD (OTC)", "AUDUSD-OTC"),
    ("USD/CAD (OTC)", "USDCAD-OTC"),
    ("EUR/GBP (OTC)", "EURGBP-OTC"),
]

PAIR_MAP = {
    "EURUSD":  ("EUR/USD (OTC)", "EURUSD-OTC"),
    "GBPUSD":  ("GBP/USD (OTC)", "GBPUSD-OTC"),
    "USDJPY":  ("USD/JPY (OTC)", "USDJPY-OTC"),
    "AUDUSD":  ("AUD/USD (OTC)", "AUDUSD-OTC"),
    "USDCAD":  ("USD/CAD (OTC)", "USDCAD-OTC"),
    "EURGBP":  ("EUR/GBP (OTC)", "EURGBP-OTC"),
    "GBPJPY":  ("GBP/JPY (OTC)", "GBPJPY-OTC"),
    "EURJPY":  ("EUR/JPY (OTC)", "EURJPY-OTC"),
    "AUDJPY":  ("AUD/JPY (OTC)", "AUDJPY-OTC"),
    "NZDUSD":  ("NZD/USD (OTC)", "NZDUSD-OTC"),
    "USDCHF":  ("USD/CHF (OTC)", "USDCHF-OTC"),
    "EURCAD":  ("EUR/CAD (OTC)", "EURCAD-OTC"),
}

DIRECTIONS = [("UP 🔝", "call"), ("DOWN 🔻", "put")]

quotex_client = None

# ════════════════════════════════════════════════════════════════
#  USER MANAGEMENT
# ════════════════════════════════════════════════════════════════

def load_users() -> set:
    try:
        with open(USERS_FILE) as f:
            return set(l.strip() for l in f if l.strip())
    except:
        return set()

def save_user(uid: str):
    if uid not in load_users():
        with open(USERS_FILE, "a") as f:
            f.write(uid + "\n")

def remove_user(uid: str):
    users = load_users()
    users.discard(uid)
    with open(USERS_FILE, "w") as f:
        f.write("\n".join(users) + "\n")

# ════════════════════════════════════════════════════════════════
#  PAIRS MANAGEMENT
# ════════════════════════════════════════════════════════════════

def load_pairs() -> list:
    try:
        with open(PAIRS_FILE) as f:
            keys = [l.strip().upper() for l in f if l.strip()]
            pairs = [PAIR_MAP[k] for k in keys if k in PAIR_MAP]
            return pairs if pairs else DEFAULT_PAIRS
    except:
        return DEFAULT_PAIRS

def save_pairs(keys: list):
    with open(PAIRS_FILE, "w") as f:
        f.write("\n".join(keys) + "\n")

# ════════════════════════════════════════════════════════════════
#  BROADCAST
# ════════════════════════════════════════════════════════════════

async def broadcast(bot, text: str):
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="Markdown")
    except Exception as e:
        print(f"  [CHANNEL WARN] {e}")

    for uid in list(load_users()):
        try:
            await bot.send_message(chat_id=uid, text=text, parse_mode="Markdown")
        except Exception as e:
            print(f"  [WARN] {uid}: {e}")

# ════════════════════════════════════════════════════════════════
#  TIME HELPER
# ════════════════════════════════════════════════════════════════

def get_next_entry() -> datetime:
    now   = datetime.now(IST)
    entry = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    if (entry - now).total_seconds() < 30:
        entry += timedelta(minutes=1)
    return entry

# ════════════════════════════════════════════════════════════════
#  QUOTEX CONNECTION
# ════════════════════════════════════════════════════════════════

async def ensure_quotex_connected() -> bool:
    global quotex_client

    if not QUOTEX_AVAILABLE:
        return False

    try:
        if quotex_client is not None:
            try:
                if quotex_client.check_connect():
                    return True
            except:
                pass

        print("  [Quotex] Logging in...")
        quotex_client = Quotex(
            email=QUOTEX_EMAIL,
            password=QUOTEX_PASSWORD,
            lang="en",
        )

        check, reason = await quotex_client.connect()

        if check:
            print("  [Quotex] ✅ Login successful!")
            await asyncio.sleep(2)
            return True
        else:
            print(f"  [Quotex] ❌ Login failed: {reason}")
            quotex_client = None
            return False

    except Exception as e:
        print(f"  [Quotex] ❌ Error: {e}")
        quotex_client = None
        return False

# ════════════════════════════════════════════════════════════════
#  GET CANDLE RESULT
# ════════════════════════════════════════════════════════════════

async def get_result_quotex(symbol: str, direction: str) -> str:
    global quotex_client

    if not await ensure_quotex_connected():
        return "UNAVAILABLE"

    try:
        print(f"  [Quotex] Checking candle: {symbol}...")

        candles = await quotex_client.get_candles(
            asset=symbol,
            end_from_time=time.time(),
            offset=300,
            period=60,
        )

        if not candles or len(candles) < 2:
            return "UNAVAILABLE"

        candle = candles[-2]
        o = float(candle["open"])
        c = float(candle["close"])

        print(f"  [Quotex] {symbol} | Open:{o:.5f} Close:{c:.5f}")

        if c > o and direction == "call":   return "WIN"
        if c < o and direction == "put":    return "WIN"
        if c == o:                           return "TIE"
        return "LOSS"

    except Exception as e:
        print(f"  [Quotex ERROR] {e}")
        quotex_client = None
        return "UNAVAILABLE"

# ════════════════════════════════════════════════════════════════
#  MESSAGE BUILDERS
# ════════════════════════════════════════════════════════════════

def build_signal(pair: str, direction: str, entry: datetime, n: int) -> str:
    trend = "Buy 📈" if "UP" in direction else "Sell 📉"
    return (
        f"👑 *ALPHA AI SIGNALS* 👑\n"
        f"🅿️ *POCKET OPTION SIGNAL* 🔵\n"
        f"━━━━━━━━━━━━\n"
        f"📌 *Pair:* `{pair}`\n"
        f"🕐 *Timeframe:* 1 Minute\n"
        f"🕰 *Entry Time:* `{entry.strftime('%H:%M:%S')}`\n"
        f"📍 *Direction:* `{direction}`\n"
        f"🚦 *Trend:* {trend}\n"
        f"━━━━━━━━━━━━\n"
        f"🇮🇳 All times in UTC+5:30 (IST)\n"
        f"💲 Follow Proper Money Management\n"
        f"⏳ Always Select *1 Minute* timeframe\n"
        f"━━━━━━━━━━━━\n"
        f"🤖 *Powered by ALPHA AI*"
    )

def build_result(result: str, mtg: bool = False) -> str:
    if result == "WIN":
        return (
            f"👑 *ALPHA AI SIGNALS* 👑\n"
            f"━━━━━━━━━━━━\n"
            f"✅ *{'1 MTG WIN' if mtg else 'WIN'}* 🏆\n"
            f"━━━━━━━━━━━━\n"
            f"💰 Follow money management!\n"
            f"🤖 *Powered by ALPHA AI*"
        )
    elif result == "TIE":
        return (
            f"👑 *ALPHA AI SIGNALS* 👑\n"
            f"━━━━━━━━━━━━\n"
            f"🔄 *TIE* — No profit / No loss\n"
            f"━━━━━━━━━━━━\n"
            f"🤖 *Powered by ALPHA AI*"
        )
    elif result == "UNAVAILABLE":
        return (
            f"👑 *ALPHA AI SIGNALS* 👑\n"
            f"━━━━━━━━━━━━\n"
            f"⚠️ *Result unavailable*\n"
            f"Please check your platform\n"
            f"━━━━━━━━━━━━\n"
            f"🤖 *Powered by ALPHA AI*"
        )
    else:
        return (
            f"👑 *ALPHA AI SIGNALS* 👑\n"
            f"━━━━━━━━━━━━\n"
            f"❌ *LOSS*\n"
            f"━━━━━━━━━━━━\n"
            f"💡 Stay calm, next signal soon!\n"
            f"🤖 *Powered by ALPHA AI*"
        )

# ════════════════════════════════════════════════════════════════
#  SIGNAL LOOP
# ════════════════════════════════════════════════════════════════

async def signal_loop(bot):
    print("✅ Signal loop started\n")
    n = 1

    while True:
        try:
            pairs              = load_pairs()
            pd_label, pa_sym   = random.choice(pairs)
            dd_label, da_act   = random.choice(DIRECTIONS)
            entry              = get_next_entry()
            wait               = max((entry - datetime.now(IST)).total_seconds(), 5)

            print(f"[#{n}] {pd_label} | {dd_label} | Entry:{entry.strftime('%H:%M:%S')} IST | Wait:{int(wait)}s")

            await broadcast(bot, build_signal(pd_label, dd_label, entry, n))
            await asyncio.sleep(wait)

            print(f"  Waiting {CANDLE_WAIT}s for candle to close...")
            await asyncio.sleep(CANDLE_WAIT)

            result = await get_result_quotex(pa_sym, da_act)
            print(f"  Result: {result}")

            if result == "LOSS":
                print(f"  LOSS — MTG: waiting {MTG_WAIT}s...")
                await asyncio.sleep(MTG_WAIT)
                mtg_result = await get_result_quotex(pa_sym, da_act)
                print(f"  MTG Result: {mtg_result}\n")
                if mtg_result == "WIN":
                    await broadcast(bot, build_result("WIN", mtg=True))
                else:
                    await broadcast(bot, build_result("LOSS"))
            else:
                await broadcast(bot, build_result(result))

            n  += 1
            gap = random.randint(SIGNAL_GAP_MIN, SIGNAL_GAP_MAX)
            print(f"  Next signal in {gap}s\n")
            await asyncio.sleep(gap)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[SIGNAL LOOP ERROR] {e}")
            await asyncio.sleep(30)

# ════════════════════════════════════════════════════════════════
#  ERROR HANDLER
# ════════════════════════════════════════════════════════════════

async def error_handler(update, context):
    print(f"[BOT ERROR] {context.error}")

# ════════════════════════════════════════════════════════════════
#  TELEGRAM COMMANDS
# ════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(str(update.effective_user.id))
    name = update.effective_user.first_name or "Trader"
    qx_status = "🟢 Quotex OTC Live" if quotex_client else "🟡 Connecting..."

    await update.message.reply_text(
        f"👑 *ALPHA AI SIGNALS* 👑\n\n"
        f"🅿️ *POCKET OPTION SIGNAL* 🔵\n"
        f"━━━━━━━━━━━━\n"
        f"👋 Welcome *{name}*!\n\n"
        f"✅ You are now subscribed to live signals!\n\n"
        f"⚡ Signals every ~6 minutes 24/7\n"
        f"📊 Data: {qx_status}\n\n"
        f"📌 /stop — Unsubscribe\n"
        f"📊 /status — Bot status\n"
        f"💱 /pairs — Active pairs\n"
        f"━━━━━━━━━━━━\n"
        f"⚠️ *RISK WARNING*\n"
        f"Binary options involve high risk.\n"
        f"Only trade what you can afford to lose.\n"
        f"━━━━━━━━━━━━\n"
        f"🇮🇳 UTC+5:30 IST | 1 Min | Pocket Option OTC\n"
        f"🤖 *Powered by ALPHA AI*",
        parse_mode="Markdown"
    )

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if uid in load_users():
        remove_user(uid)
        await update.message.reply_text(
            f"👑 *ALPHA AI SIGNALS* 👑\n\n"
            f"❌ *Unsubscribed successfully.*\n\n"
            f"Use /start to re-subscribe anytime.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"ℹ️ You are not subscribed.\n\nUse /start to subscribe.",
            parse_mode="Markdown"
        )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pairs  = load_pairs()
    users  = load_users()
    qx_ok  = quotex_client is not None
    qx_txt = "🟢 Connected — OTC data live" if qx_ok else "🔴 Reconnecting..."

    await update.message.reply_text(
        f"👑 *ALPHA AI — Status* 👑\n\n"
        f"🟢 Bot: *Running 24/7*\n"
        f"📡 Quotex: {qx_txt}\n"
        f"👥 Subscribers: `{len(users)}`\n"
        f"🕐 IST Time: `{datetime.now(IST).strftime('%H:%M:%S')}`\n"
        f"💱 Active Pairs: `{len(pairs)}`\n"
        f"📊 Account: `{'Demo' if QUOTEX_IS_DEMO else 'Live'}`\n"
        f"━━━━━━━━━━━━\n"
        f"🤖 *Powered by ALPHA AI*",
        parse_mode="Markdown"
    )

async def pairs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pairs     = load_pairs()
    pair_list = "\n".join([f"• {p[0]}" for p in pairs])
    await update.message.reply_text(
        f"👑 *ALPHA AI — Active Pairs* 👑\n\n"
        f"{pair_list}\n\n"
        f"🔧 Admin: /setpairs to change\n"
        f"━━━━━━━━━━━━\n"
        f"🤖 *Powered by ALPHA AI*",
        parse_mode="Markdown"
    )

async def setpairs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only.", parse_mode="Markdown")
        return

    if not context.args:
        available = " ".join(PAIR_MAP.keys())
        await update.message.reply_text(
            f"👑 *Set Active Pairs*\n\n"
            f"Usage: `/setpairs EURUSD GBPUSD USDJPY`\n\n"
            f"*Available:*\n`{available}`",
            parse_mode="Markdown"
        )
        return

    keys    = [a.upper() for a in context.args]
    valid   = [k for k in keys if k in PAIR_MAP]
    invalid = [k for k in keys if k not in PAIR_MAP]

    if not valid:
        await update.message.reply_text("❌ No valid pairs.", parse_mode="Markdown")
        return

    save_pairs(valid)
    pair_list = "\n".join([f"✅ *{PAIR_MAP[k][0]}*" for k in valid])
    msg = f"👑 *Pairs Updated!*\n\n{pair_list}"
    if invalid:
        msg += f"\n\n⚠️ Ignored: `{', '.join(invalid)}`"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def reconnect_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only.", parse_mode="Markdown")
        return

    global quotex_client
    quotex_client = None
    await update.message.reply_text("🔄 Reconnecting to Quotex...", parse_mode="Markdown")
    success = await ensure_quotex_connected()

    if success:
        await update.message.reply_text("✅ Quotex reconnected!", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Reconnection failed.", parse_mode="Markdown")

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only.", parse_mode="Markdown")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: `/broadcast Your message here`",
            parse_mode="Markdown"
        )
        return

    msg = " ".join(context.args)
    await broadcast(update.message.bot, f"📢 *ALPHA AI ANNOUNCEMENT*\n\n{msg}")
    await update.message.reply_text("✅ Broadcast sent!", parse_mode="Markdown")

# ════════════════════════════════════════════════════════════════
#  STARTUP
# ════════════════════════════════════════════════════════════════

async def post_init(app):
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  Connecting to Quotex...")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    connected = await ensure_quotex_connected()

    if connected:
        print("  ✅ Quotex ready — OTC results active")
    else:
        print("  ⚠️  Quotex not connected — will retry each signal")

    asyncio.create_task(signal_loop(app.bot))

# ════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════

def main():
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  ALPHA AI SIGNALS — Starting")
    print(f"  Account : {'Demo' if QUOTEX_IS_DEMO else 'Live'}")
    print(f"  Channel : {CHANNEL_ID}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("stop",       stop_cmd))
    app.add_handler(CommandHandler("status",     status_cmd))
    app.add_handler(CommandHandler("pairs",      pairs_cmd))
    app.add_handler(CommandHandler("setpairs",   setpairs_cmd))
    app.add_handler(CommandHandler("reconnect",  reconnect_cmd))
    app.add_handler(CommandHandler("broadcast",  broadcast_cmd))
    app.add_error_handler(error_handler)

    print("  Bot is running... Press Ctrl+C to stop\n")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
