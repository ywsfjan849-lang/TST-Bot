import os
import sqlite3
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

MIN_WITHDRAWAL = 25.00
TON_FEE = 0.35
TST_TO_USDT = 0.0001

TON_WALLET = "UQDN7a9bxBBar5mF97NGPoodZUPlsTjED8-3uJvODK3ogvxm"

DB = "tst_bot.db"


def db():
    return sqlite3.connect(DB)


def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            usdt REAL DEFAULT 0,
            tst_coins INTEGER DEFAULT 0,
            invited_by INTEGER,
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_claims (
            user_id INTEGER PRIMARY KEY,
            claim_date TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            fee_ton REAL,
            net_amount REAL,
            fee_txid TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)

    con.commit()
    con.close()


def get_user(user_id):
    con = db()
    cur = con.cursor()
    cur.execute(
        "SELECT user_id, username, usdt, tst_coins, invited_by FROM users WHERE user_id=?",
        (user_id,),
    )
    user = cur.fetchone()
    con.close()
    return user


def create_user(user_id, username, invited_by=None):
    if get_user(user_id):
        return

    con = db()
    cur = con.cursor()

    cur.execute("""
        INSERT INTO users
        (user_id, username, usdt, tst_coins, invited_by, created_at)
        VALUES (?, ?, 0, 0, ?, ?)
    """, (
        user_id,
        username or "",
        invited_by,
        datetime.now(timezone.utc).isoformat()
    ))

    con.commit()
    con.close()


def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎮 TST", callback_data="game"),
            InlineKeyboardButton("💰 Balance", callback_data="balance"),
        ],
        [
            InlineKeyboardButton("✅ Tasks", callback_data="tasks"),
            InlineKeyboardButton("👥 Referral", callback_data="referral"),
        ],
        [
            InlineKeyboardButton("💸 Withdraw", callback_data="withdraw"),
            InlineKeyboardButton("📜 History", callback_data="history"),
        ],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    invited_by = None

    if context.args:
        try:
            invited_by = int(context.args[0])
            if invited_by == user.id:
                invited_by = None
        except ValueError:
            invited_by = None

    create_user(user.id, user.username, invited_by)

    text = (
        "🎮 خوش آمدی به TST!\n\n"
        "🪙 TST Coins جمع کن\n"
        "🎁 تسک‌ها را انجام بده\n"
        "👥 دوستانت را دعوت کن\n"
        "💰 موجودی‌ات را افزایش بده\n\n"
        "از منوی پایین شروع کن:"
    )

    await update.message.reply_text(
        text,
        reply_markup=main_menu()
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data == "balance":
        user = get_user(user_id)

        if not user:
            create_user(user_id, query.from_user.username)
            user = get_user(user_id)

        usdt = user[2]
        tst = user[3]

        text = (
            "💰 موجودی شما\n\n"
            f"🪙 TST Coins: {tst:,}\n"
            f"💵 USDT: {usdt:.4f}\n"
        )

        await query.edit_message_text(
            text,
            reply_markup=main_menu()
        )

    elif query.data == "game":
        text = (
            "🎮 TST\n\n"
            "🪙 TST Coins جمع کن و امتیازت را افزایش بده.\n\n"
            "نسخه Mini App بازی در مرحله بعد به این بخش متصل می‌شود."
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🪙 Collect TST Coins", callback_data="collect")],
            [InlineKeyboardButton("🔙 Back", callback_data="back")]
        ])

        await query.edit_message_text(text, reply_markup=keyboard)

    elif query.data == "collect":
        con = db()
        cur = con.cursor()

        cur.execute(
            "UPDATE users SET tst_coins = tst_coins + 1 WHERE user_id=?",
            (user_id,)
        )

        con.commit()
        con.close()

        user = get_user(user_id)

        await query.edit_message_text(
            f"🪙 +1 TST Coin!\n\n"
            f"موجودی TST Coins: {user[3]:,}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🪙 Collect again", callback_data="collect")],
                [InlineKeyboardButton("🔙 Back", callback_data="back")]
            ])
        )

    elif query.data == "tasks":
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        con = db()
        cur = con.cursor()

        cur.execute(
            "SELECT claim_date FROM daily_claims WHERE user_id=?",
            (user_id,)
        )

        row = cur.fetchone()

        claimed = row and row[0] == today

        con.close()

        if claimed:
            text = (
                "Available tasks\n\n"
                "Daily check-in — Earn 0.25 USDT\n\n"
                "✅ Already claimed today."
            )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back")]
            ])

        else:
            text = (
                "Available tasks\n\n"
                "Daily check-in — Earn 0.25 USDT"
            )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎁 Claim 0.25 USDT", callback_data="claim_daily")],
                [InlineKeyboardButton("🔙 Back", callback_data="back")]
            ])

        await query.edit_message_text(text, reply_markup=keyboard)

    elif query.data == "claim_daily":
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        con = db()
        cur = con.cursor()

        cur.execute(
            "SELECT claim_date FROM daily_claims WHERE user_id=?",
            (user_id,)
        )

        row = cur.fetchone()

        if row and row[0] == today:
            con.close()

            await query.edit_message_text(
                "❌ این پاداش را امروز قبلاً گرفته‌ای.",
                reply_markup=main_menu()
            )
            return

        cur.execute(
            "UPDATE users SET usdt = usdt + 0.25 WHERE user_id=?",
            (user_id,)
        )

        cur.execute(
            """
            INSERT OR REPLACE INTO daily_claims
            (user_id, claim_date)
            VALUES (?, ?)
            """,
            (user_id, today)
        )

        con.commit()
        con.close()

        await query.edit_message_text(
            "🎉 موفق شد!\n\n"
            "💰 +0.25 USDT به موجودی اضافه شد.",
            reply_markup=main_menu()
        )

    elif query.data == "referral":
        bot = await context.bot.get_me()

        link = f"https://t.me/{bot.username}?start={user_id}"

        await query.edit_message_text(
            "👥 Referral\n\n"
            "لینک دعوت شما:\n\n"
            f"{link}\n\n"
            "لینک را برای دوستانت ارسال کن.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back")]
            ])
        )

    elif query.data == "withdraw":
        user = get_user(user_id)

        await query.edit_message_text(
            f"💸 Withdraw\n\n"
            f"Minimum: {MIN_WITHDRAWAL:.2f} USDT\n"
            f"Fee: {TON_FEE:.2f} TON\n\n"
            f"موجودی فعلی: {user[2]:.4f} USDT\n\n"
            "برای شروع، مقدار برداشت را به صورت عدد ارسال کن.\n"
            "برای لغو /cancel را بزن.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back")]
            ])
        )

        context.user_data["withdraw_step"] = "amount"

    elif query.data == "history":
        con = db()
        cur = con.cursor()

        cur.execute(
            """
            SELECT amount, fee_ton, net_amount, status, created_at
            FROM withdrawals
            WHERE user_id=?
            ORDER BY id DESC
            LIMIT 10
            """,
            (user_id,)
        )

        rows = cur.fetchall()
        con.close()

        if not rows:
            text = "📜 هنوز هیچ درخواست برداشتی ثبت نشده است."
        else:
            text = "📜 تاریخچه برداشت‌ها\n\n"

            for amount, fee, net, status, created in rows:
                text += (
                    f"💵 {amount:.2f} USDT\n"
                    f"💎 Fee: {fee:.2f} TON\n"
                    f"📤 Net: {net:.2f} USDT\n"
                    f"📌 {status}\n\n"
                )

        await query.edit_message_text(
            text,
            reply_markup=main_menu()
        )

    elif query.data == "back":
        await query.edit_message_text(
            "🏠 منوی اصلی",
            reply_markup=main_menu()
        )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if text == "/cancel":
        context.user_data.clear()

        await update.message.reply_text(
            "❌ عملیات لغو شد.",
            reply_markup=main_menu()
        )
        return
if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()
    app.run_polling()
