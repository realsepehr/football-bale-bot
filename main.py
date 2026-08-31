# -*- coding: utf-8 -*-
"""
ربات فانتزی فوتبال بله - نسخه ۲ (تک‌فایلی)
فقط همین یک فایل رو اجرا کن.
"""
import sqlite3
import logging
import random
import math
import datetime
import os
from contextlib import contextmanager

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    TypeHandler,
    ApplicationHandlerStop,
    filters,
    ContextTypes,
)

# ================== تنظیمات (اینجا رو خودت عوض کن) ==================

BOT_TOKEN = "323724086:4HV_kcxlSeEqInyyu9nTnfapRh-L3kuIq5Q"          # <-- توکن ربات بله‌ت
BALE_API_BASE_URL = "https://tapi.bale.ai/bot"

# آیدی عددی کاربر بله‌ت که قراره ادمین باشه (بدون این عدد، دستورات ادمین کار نمی‌کنن)
# اگه نمی‌دونی آیدیت چیه: ربات رو /start بزن، بعد موقتاً پایین همین فایل توضیح دادم چطور پیداش کنی
ADMIN_IDS = [1845840976,12627252]   # <-- آیدی عددی خودت رو اینجا بذار (می‌تونی چند نفر هم بذاری)

# آیدی عددی کانالی که نتایج بازی‌ها توش پست بشه (باید ربات ادمین اون کانال باشه)
# اگه نمی‌خوای، همینو خالی (None) بذار؛ نتایج فقط توی خود پنل ادمین نشون داده می‌شه
CHANNEL_ID = "@FootballXchannel"   # <-- کانال نتایج بازی‌ها

INITIAL_BUDGET = 130      # بودجه اولیه هر کاربر
MIN_TEAM_SIZE = 11
MAX_TEAM_SIZE = 22
DATABASE_PATH = "fantasy.db"

# هزینه ارتقای هر بازیکن = قدرت فعلیش ضربدر این عدد (هر بار که ارتقا بگیره قدرتش +۱ می‌شه)
UPGRADE_COST_PER_POINT = 3

# امتیاز بازی بین تیم‌ها
WIN_POINTS = 3
DRAW_POINTS = 1

# مبلغی که اسپانسر به‌ازای هر بازی به حساب باشگاه واریز می‌کنه (به میلیون تومان)
SPONSOR_MATCH_BONUS = 5
# حداکثر نوسان شانسی نسبت به قدرت پایه تیم (۰.۳ یعنی تا ۳۰٪ نوسان تصادفی)
BATTLE_RANDOM_FACTOR = 0.3

# آرایش‌های قابل انتخاب: تعداد مدافع/هافبک/مهاجم (دروازه‌بان همیشه ۱ نفره و جدا حساب می‌شه)
FORMATIONS = {
    "4-4-2": {"DF": 4, "MF": 4, "FW": 2},
    "4-3-3": {"DF": 4, "MF": 3, "FW": 3},
    "4-2-3-1": {"DF": 4, "MF": 5, "FW": 1},
    "4-1-2-1-2": {"DF": 4, "MF": 4, "FW": 2},
    "4-3-2-1": {"DF": 4, "MF": 5, "FW": 1},
    "4-1-4-1": {"DF": 4, "MF": 5, "FW": 1},
    "4-2-2-2": {"DF": 4, "MF": 4, "FW": 2},
    "4-5-1": {"DF": 4, "MF": 5, "FW": 1},
    "3-5-2": {"DF": 3, "MF": 5, "FW": 2},
    "3-4-3": {"DF": 3, "MF": 4, "FW": 3},
    "3-4-1-2": {"DF": 3, "MF": 5, "FW": 2},
    "5-3-2": {"DF": 5, "MF": 3, "FW": 2},
    "5-2-1-2": {"DF": 5, "MF": 3, "FW": 2},
    "5-4-1": {"DF": 5, "MF": 4, "FW": 1},
}

# تاکتیک‌ها: روی قدرت حمله و دفاع تیم تاثیر می‌ذارن
TACTICS = {
    "standard": {"label": "استاندارد", "emoji": "⚖️", "atk": 1.00, "def": 1.00},
    "tiki_taka": {"label": "تیکی‌تاکا", "emoji": "🔄", "atk": 1.15, "def": 1.10},
    "press": {"label": "پرس سنگین", "emoji": "🔥", "atk": 1.30, "def": 0.75},
    "park_bus": {"label": "اتوبوسی", "emoji": "🚌", "atk": 0.65, "def": 1.40},
    "counter": {"label": "ضدحمله", "emoji": "⚡", "atk": 1.00, "def": 1.20},
    "wings": {"label": "بازی از جناحین", "emoji": "↔️", "atk": 1.20, "def": 0.95},
}

# هزینه‌ی ارتقای هر سطح ورزشگاه (به میلیون تومان) و افزایش ظرفیت/تاثیرش
STADIUM_UPGRADE_BASE_COST = 15
STADIUM_MAX_LEVEL = 10

# شانس مصدومیت هر بازیکن ترکیب اصلی بعد از یه بازی رسمی، و طول مدت مصدومیت (تعداد بازی)
INJURY_CHANCE = 0.06
INJURY_MIN_MATCHES = 1
INJURY_MAX_MATCHES = 3

# قیمت بازیکنایی که آکادمی تولید می‌کنه (بین این دو عدد رندوم انتخاب می‌شه)
ACADEMY_MIN_PRICE = 2
ACADEMY_MAX_PRICE = 5

# اسامی نمونه برای بازیکنای آکادمی (رندوم ترکیب می‌شن)
ACADEMY_FIRST_NAMES = [
    "امیر", "علی", "محمد", "حسین", "رضا", "مهدی", "سینا", "آرش", "پارسا", "دانیال",
    "کیان", "نیما", "شایان", "بردیا", "یاسین",
]
ACADEMY_LAST_NAMES = [
    "احمدی", "محمدی", "حسینی", "رضایی", "کریمی", "نوری", "صادقی", "قاسمی", "رحیمی", "جعفری",
]
ACADEMY_POSITIONS = ["GK", "DF", "MF", "FW"]

# لیست بازیکنان اولیه بازی
SAMPLE_PLAYERS = [
    # ---- دروازه‌بان‌ها ----
    ("اِدرسون", "منچسترسیتی", "GK", 10),
    ("آلیسون", "لیورپول", "GK", 10),
    ("تیبو کورتوا", "رئال مادرید", "GK", 11),
    ("یان اوبلاک", "اتلتیکومادرید", "GK", 9),
    ("جیانلوئیجی دوناروما", "پاری‌سن‌ژرمن", "GK", 9),
    ("مانوئل نویر", "بایرن مونیخ", "GK", 8),

    # ---- مدافعان ----
    ("روبن دیاش", "منچسترسیتی", "DF", 10),
    ("ویرجیل ون‌دایک", "لیورپول", "DF", 11),
    ("آنتونیو رودیگر", "رئال مادرید", "DF", 9),
    ("داوینسون سانچس", "توتنهام", "DF", 6),
    ("تئو هرناندز", "میلان", "DF", 9),
    ("آشرف حکیمی", "پاری‌سن‌ژرمن", "DF", 9),
    ("کیران تریپیه", "نیوکاسل", "DF", 7),
    ("آلفونسو دیویس", "بایرن مونیخ", "DF", 8),
    ("ویلیام سالیبا", "آرسنال", "DF", 8),
    ("جان استونز", "منچسترسیتی", "DF", 7),
    ("رابن گوسنز", "اینتر", "DF", 6),
    ("بن وایت", "آرسنال", "DF", 6),

    # ---- هافبک‌ها ----
    ("کوین دی‌بروین", "منچسترسیتی", "MF", 13),
    ("رودری", "منچسترسیتی", "MF", 12),
    ("جود بلینگهام", "رئال مادرید", "MF", 15),
    ("فردریکو والورده", "رئال مادرید", "MF", 11),
    ("مارتین اودگارد", "آرسنال", "MF", 11),
    ("بروتو فرناندز", "منچستریونایتد", "MF", 10),
    ("دکلان رایس", "آرسنال", "MF", 9),
    ("جمال موسیالا", "بایرن مونیخ", "MF", 11),
    ("فدریکو کیه‌سا", "لیورپول", "MF", 8),
    ("پدری", "بارسلونا", "MF", 10),
    ("گاوی", "بارسلونا", "MF", 9),
    ("آدرین رابیو", "میلان", "MF", 7),
    ("نیکولو باره‌لا", "اینتر", "MF", 9),

    # ---- مهاجمان ----
    ("ارلینگ هالند", "منچسترسیتی", "FW", 18),
    ("کیلیان امباپه", "رئال مادرید", "FW", 17),
    ("محمد صلاح", "لیورپول", "FW", 15),
    ("هری کین", "بایرن مونیخ", "FW", 14),
    ("وینیسیوس جونیور", "رئال مادرید", "FW", 15),
    ("رحیم استرلینگ", "چلسی", "FW", 9),
    ("رافائل لئائو", "میلان", "FW", 11),
    ("اوسمانه دمبله", "پاری‌سن‌ژرمن", "FW", 12),
    ("ویکتور اوسیمن", "ناپولی", "FW", 12),
    ("لائوتارو مارتینز", "اینتر", "FW", 12),
    ("بوکایو ساکا", "آرسنال", "FW", 12),
    ("دارویین نونیز", "لیورپول", "FW", 9),
]

# ================== دیتابیس ==================

@contextmanager
def get_conn():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            budget REAL DEFAULT %f,
            total_points REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """ % INITIAL_BUDGET)

        c.execute("""
        CREATE TABLE IF NOT EXISTS players (
            player_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            team TEXT,
            position TEXT CHECK(position IN ('GK','DF','MF','FW')),
            price REAL NOT NULL,
            power REAL DEFAULT 5,
            week_points REAL DEFAULT 0,
            total_points REAL DEFAULT 0
        )
        """)

        c.execute("""
        CREATE TABLE IF NOT EXISTS user_players (
            user_id INTEGER,
            player_id INTEGER,
            PRIMARY KEY (user_id, player_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(player_id) REFERENCES players(player_id)
        )
        """)

        # جدول اخبار: فقط یک ردیف نگه می‌داریم (آخرین خبر)
        c.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            content TEXT NOT NULL DEFAULT ''
        )
        """)
        c.execute("INSERT OR IGNORE INTO news (id, content) VALUES (1, 'فعلاً خبری ثبت نشده.')")

        # جدول تنظیمات کلی ربات (مثل روشن/خاموش بودن)
        c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('bot_enabled', '1')")

    # اگه دیتابیس از قبل ساخته شده بود (نسخه قبلی ربات)، ستون‌های جدید رو اضافه کن
    with get_conn() as conn:
        def _has_column(table, column):
            cur = conn.execute(f"PRAGMA table_info({table})")
            return any(row["name"] == column for row in cur.fetchall())

        if not _has_column("players", "power"):
            conn.execute("ALTER TABLE players ADD COLUMN power REAL DEFAULT 5")
            conn.execute("UPDATE players SET power = price WHERE power IS NULL")
        if not _has_column("users", "wins"):
            conn.execute("ALTER TABLE users ADD COLUMN wins INTEGER DEFAULT 0")
        if not _has_column("users", "draws"):
            conn.execute("ALTER TABLE users ADD COLUMN draws INTEGER DEFAULT 0")
        if not _has_column("users", "losses"):
            conn.execute("ALTER TABLE users ADD COLUMN losses INTEGER DEFAULT 0")
        if not _has_column("users", "last_battle_date"):
            conn.execute("ALTER TABLE users ADD COLUMN last_battle_date TEXT")
        if not _has_column("users", "last_academy_date"):
            conn.execute("ALTER TABLE users ADD COLUMN last_academy_date TEXT")
        if not _has_column("users", "last_statement_date"):
            conn.execute("ALTER TABLE users ADD COLUMN last_statement_date TEXT")
        if not _has_column("users", "team_name"):
            conn.execute("ALTER TABLE users ADD COLUMN team_name TEXT")
        if not _has_column("users", "kit_color1"):
            conn.execute("ALTER TABLE users ADD COLUMN kit_color1 TEXT")
        if not _has_column("users", "kit_color2"):
            conn.execute("ALTER TABLE users ADD COLUMN kit_color2 TEXT")
        if not _has_column("users", "sponsor"):
            conn.execute("ALTER TABLE users ADD COLUMN sponsor TEXT")
        if not _has_column("users", "formation"):
            conn.execute("ALTER TABLE users ADD COLUMN formation TEXT")
        if not _has_column("users", "tactic"):
            conn.execute("ALTER TABLE users ADD COLUMN tactic TEXT DEFAULT 'standard'")
        if not _has_column("users", "stadium_level"):
            conn.execute("ALTER TABLE users ADD COLUMN stadium_level INTEGER DEFAULT 1")
        if not _has_column("users", "fans"):
            conn.execute("ALTER TABLE users ADD COLUMN fans INTEGER DEFAULT 1000")
        if not _has_column("users", "foot_tokens"):
            conn.execute("ALTER TABLE users ADD COLUMN foot_tokens INTEGER DEFAULT 0")
        if not _has_column("user_players", "injury_matches_left"):
            conn.execute("ALTER TABLE user_players ADD COLUMN injury_matches_left INTEGER DEFAULT 0")
        if not _has_column("user_players", "season_points"):
            conn.execute("ALTER TABLE user_players ADD COLUMN season_points REAL DEFAULT 0")
        if not _has_column("user_players", "owned_power"):
            conn.execute("ALTER TABLE user_players ADD COLUMN owned_power REAL")
            # هر بازیکنی که قبلاً به یه تیم اضافه شده، قدرتش رو از کاتالوگ فعلی اسنپ‌شات می‌گیریم
            conn.execute("""
                UPDATE user_players
                SET owned_power = (SELECT power FROM players WHERE players.player_id = user_players.player_id)
                WHERE owned_power IS NULL
            """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS user_lineup (
            user_id INTEGER,
            player_id INTEGER,
            PRIMARY KEY (user_id, player_id)
        )
        """)

        # کدوم تیم‌ها این فصل قبلاً با هم بازی کردن (برای اینکه لیگ خودکار دوباره تکرارشون نکنه
        # و تیم تازه‌وارد فقط با کسایی که هنوز باهاشون بازی نکرده جفت بشه)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS fixtures (
            user_a INTEGER,
            user_b INTEGER,
            PRIMARY KEY (user_a, user_b)
        )
        """)
        if not _has_column("fixtures", "legs_played"):
            # هرچی از قبل توی جدول بود یعنی یه بار (رفت) بازی شده
            conn.execute("ALTER TABLE fixtures ADD COLUMN legs_played INTEGER DEFAULT 1")


def seed_players_if_empty():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as cnt FROM players")
        count = c.fetchone()["cnt"]
        if count > 0:
            return
        for name, team, pos, price in SAMPLE_PLAYERS:
            c.execute(
                "INSERT INTO players (name, team, position, price, power) VALUES (?, ?, ?, ?, ?)",
                (name, team, pos, price, price),
            )


def get_or_create_user(user_id: int, username: str):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row is None:
            c.execute(
                "INSERT INTO users (user_id, username, budget) VALUES (?, ?, ?)",
                (user_id, username, INITIAL_BUDGET),
            )
            c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = c.fetchone()
        return row


def get_user_budget(user_id: int) -> float:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT budget FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        return row["budget"] if row else 0.0


def update_user_budget(user_id: int, new_budget: float):
    with get_conn() as conn:
        conn.execute("UPDATE users SET budget = ? WHERE user_id = ?", (new_budget, user_id))


def set_user_team_name(user_id: int, team_name: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET team_name = ? WHERE user_id = ?", (team_name, user_id))


def set_user_kit_colors(user_id: int, color1: str = None, color2: str = None):
    with get_conn() as conn:
        if color1 is not None:
            conn.execute("UPDATE users SET kit_color1 = ? WHERE user_id = ?", (color1, user_id))
        if color2 is not None:
            conn.execute("UPDATE users SET kit_color2 = ? WHERE user_id = ?", (color2, user_id))


def get_user_row(user_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return c.fetchone()


def team_display_name(user_row) -> str:
    """اسم قابل‌نمایش تیم: اسم انتخابی کاربر (با رنگ‌هاش) یا در نبودش یوزرنیمش"""
    name = user_row["team_name"] if "team_name" in user_row.keys() else None
    name = name or user_row["username"] or "بدون‌نام"
    c1 = user_row["kit_color1"] if "kit_color1" in user_row.keys() else None
    c2 = user_row["kit_color2"] if "kit_color2" in user_row.keys() else None
    emojis = ""
    if c1 and c1 in KIT_COLOR_MAP:
        emojis += KIT_COLOR_MAP[c1][1]
    if c2 and c2 in KIT_COLOR_MAP:
        emojis += KIT_COLOR_MAP[c2][1]
    return f"{emojis} {name}".strip()


def kit_color_keyboard(callback_prefix: str, exclude_key: str = None) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for key, label, emoji in KIT_COLORS:
        if key == exclude_key:
            continue
        row.append(InlineKeyboardButton(f"{emoji} {label}", callback_data=f"{callback_prefix}_{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def sponsor_keyboard() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for key, label, emoji in SPONSORS:
        row.append(InlineKeyboardButton(f"{emoji} {label}", callback_data=f"setsponsor_{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def set_user_sponsor(user_id: int, sponsor_key: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET sponsor = ? WHERE user_id = ?", (sponsor_key, user_id))


def lineup_tactics_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 چیدن ترکیب (فرمیشن)", callback_data="lineup_formations")],
        [InlineKeyboardButton("🎯 انتخاب تاکتیک", callback_data="tactic_pick")],
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="admin_back")],
    ])


def formation_keyboard() -> InlineKeyboardMarkup:
    rows = []
    row = []
    for key in FORMATIONS:
        row.append(InlineKeyboardButton(key, callback_data=f"setformation_{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_lineup_tactics")])
    return InlineKeyboardMarkup(rows)


def tactic_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for key, t in TACTICS.items():
        rows.append([InlineKeyboardButton(f"{t['emoji']} {t['label']}", callback_data=f"settactic_{key}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_lineup_tactics")])
    return InlineKeyboardMarkup(rows)


def lineup_pick_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """چک‌لیست بازیکن‌های تیم (غیرمصدوم) برای انتخاب ترکیب اصلی، به تفکیک پست"""
    required = get_lineup_required_counts(user_id) or {}
    counts = get_lineup_position_counts(user_id)
    lineup_ids = {p["player_id"] for p in get_user_lineup(user_id)}
    squad = get_available_squad(user_id)

    rows = []
    for p in squad:
        checked = "✅" if p["player_id"] in lineup_ids else "▫️"
        pos = p["position"]
        need = required.get(pos, 0)
        have = counts.get(pos, 0)
        label = f"{checked} {POSITION_FA.get(pos, pos)} | {p['name']} ({have}/{need})"
        rows.append([InlineKeyboardButton(label, callback_data=f"togglelineup_{p['player_id']}")])
    rows.append([InlineKeyboardButton("✅ ثبت ترکیب", callback_data="lineup_confirm")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu_lineup_tactics")])
    return InlineKeyboardMarkup(rows)


def edit_team_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 مشاهده تیم فعلی", callback_data="editteam_view")],
        [InlineKeyboardButton("➕ افزودن بازیکن به تیم", callback_data="editteam_add")],
        [InlineKeyboardButton("➖ حذف بازیکن از تیم", callback_data="editteam_remove")],
        [InlineKeyboardButton("🔙 بازگشت به پنل ادمین", callback_data="admin_back_to_panel")],
    ])


def team_remove_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """دکمه‌ی حذف برای تک‌تک بازیکنای یه تیم خاص"""
    team = get_user_team(user_id)
    rows = []
    for p in team:
        label = f"❌ #{p['player_id']} {p['name']} ({POSITION_FA.get(p['position'], p['position'])})"
        rows.append([InlineKeyboardButton(label, callback_data=f"editteam_rm_{p['player_id']}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_edit_team_menu")])
    return InlineKeyboardMarkup(rows)


def get_today_str() -> str:
    """امروز رو به شکل رشته YYYY-MM-DD برمی‌گردونه (برای مقایسه محدودیت روزانه)"""
    return datetime.date.today().isoformat()


def get_last_action_date(user_id: int, column: str):
    """column باید 'last_battle_date' یا 'last_academy_date' باشه"""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(f"SELECT {column} FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        return row[column] if row else None


def set_last_action_date(user_id: int, column: str, date_str: str):
    """column باید 'last_battle_date' یا 'last_academy_date' باشه"""
    with get_conn() as conn:
        conn.execute(f"UPDATE users SET {column} = ? WHERE user_id = ?", (date_str, user_id))


def parse_id(text: str):
    """آیدی عددی رو از متن استخراج می‌کنه؛ اگه کاربر با '#' یا فاصله فرستاده باشه هم درست کار می‌کنه"""
    cleaned = text.strip().lstrip("#").strip()
    if not cleaned.lstrip("-").isdigit():
        return None
    return int(cleaned)


def get_setting(key: str, default: str = None):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = c.fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def is_bot_enabled() -> bool:
    return get_setting("bot_enabled", "1") == "1"


def set_bot_enabled(enabled: bool):
    set_setting("bot_enabled", "1" if enabled else "0")


def get_all_players():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM players ORDER BY position, price DESC")
        return c.fetchall()


def get_player(player_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM players WHERE player_id = ?", (player_id,))
        return c.fetchone()


def add_player(name: str, team: str, position: str, price: float, power: float = None) -> int:
    if power is None:
        power = price
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO players (name, team, position, price, power) VALUES (?, ?, ?, ?, ?)",
            (name, team, position, price, power),
        )
        return c.lastrowid


def delete_player(player_id: int):
    """بازیکن رو کامل حذف می‌کنه؛ اگه توی تیم کسی بود، از تیمش هم برداشته می‌شه"""
    with get_conn() as conn:
        conn.execute("DELETE FROM user_players WHERE player_id = ?", (player_id,))
        conn.execute("DELETE FROM players WHERE player_id = ?", (player_id,))


def get_user_team(user_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT p.player_id, p.name, p.team, p.position, p.price,
                   COALESCE(up.owned_power, p.power) as power,
                   p.week_points, p.total_points,
                   up.season_points as season_points, up.injury_matches_left as injury_matches_left
            FROM players p
            JOIN user_players up ON up.player_id = p.player_id
            WHERE up.user_id = ?
            ORDER BY p.position
        """, (user_id,))
        return c.fetchall()


def get_user_team_size(user_id: int) -> int:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as cnt FROM user_players WHERE user_id = ?", (user_id,))
        return c.fetchone()["cnt"]


def is_player_in_team(user_id: int, player_id: int) -> bool:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT 1 FROM user_players WHERE user_id = ? AND player_id = ?",
            (user_id, player_id),
        )
        return c.fetchone() is not None


def add_player_to_team(user_id: int, player_id: int):
    """بازیکن رو به تیم کاربر اضافه می‌کنه و قدرت فعلی کاتالوگ رو به‌عنوان قدرت مخصوص این تیم
    اسنپ‌شات می‌گیره — اینجوری اگه بعداً همین بازیکن رو یه تیم دیگه هم داشته باشه، ارتقای هرکدوم
    کاملاً جدا از اون یکی حساب می‌شه"""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT power FROM players WHERE player_id = ?", (player_id,))
        row = c.fetchone()
        base_power = row["power"] if row else 0
        conn.execute(
            "INSERT INTO user_players (user_id, player_id, owned_power) VALUES (?, ?, ?)",
            (user_id, player_id, base_power),
        )


def remove_player_from_team(user_id: int, player_id: int):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM user_players WHERE user_id = ? AND player_id = ?",
            (user_id, player_id),
        )
        conn.execute(
            "DELETE FROM user_lineup WHERE user_id = ? AND player_id = ?",
            (user_id, player_id),
        )


def get_user_team_power(user_id: int) -> float:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT COALESCE(SUM(COALESCE(up.owned_power, p.power)), 0) as total
            FROM players p
            JOIN user_players up ON up.player_id = p.player_id
            WHERE up.user_id = ?
        """, (user_id,))
        return c.fetchone()["total"]


def get_team_position_counts(user_id: int) -> dict:
    """تعداد بازیکنای تیم رو به تفکیک پست برمی‌گردونه، مثل {'GK': 1, 'DF': 4, ...}"""
    counts = {"GK": 0, "DF": 0, "MF": 0, "FW": 0}
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT p.position, COUNT(*) as cnt
            FROM players p
            JOIN user_players up ON up.player_id = p.player_id
            WHERE up.user_id = ?
            GROUP BY p.position
        """, (user_id,))
        for row in c.fetchall():
            if row["position"] in counts:
                counts[row["position"]] = row["cnt"]
    return counts


# ================== ترکیب اصلی (Lineup) و تاکتیک ==================

def get_injured_squad_ids(user_id: int) -> set:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT player_id FROM user_players WHERE user_id = ? AND injury_matches_left > 0",
            (user_id,),
        )
        return {row["player_id"] for row in c.fetchall()}


def get_available_squad(user_id: int):
    """بازیکن‌های تیم که الان مصدوم نیستن"""
    injured = get_injured_squad_ids(user_id)
    return [p for p in get_user_team(user_id) if p["player_id"] not in injured]


def get_injured_players(user_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT p.*, up.injury_matches_left FROM players p
            JOIN user_players up ON up.player_id = p.player_id
            WHERE up.user_id = ? AND up.injury_matches_left > 0
        """, (user_id,))
        return c.fetchall()


def set_formation(user_id: int, formation_key: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET formation = ? WHERE user_id = ?", (formation_key, user_id))
        conn.execute("DELETE FROM user_lineup WHERE user_id = ?", (user_id,))  # با عوض شدن آرایش، ترکیب قبلی پاک می‌شه


def clear_lineup(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM user_lineup WHERE user_id = ?", (user_id,))


def toggle_lineup_player(user_id: int, player_id: int) -> bool:
    """اگه توی ترکیب بود درش میاره، وگرنه اضافه می‌کنه. True برمی‌گردونه یعنی الان اضافه شده."""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM user_lineup WHERE user_id = ? AND player_id = ?", (user_id, player_id))
        if c.fetchone():
            conn.execute("DELETE FROM user_lineup WHERE user_id = ? AND player_id = ?", (user_id, player_id))
            return False
        conn.execute("INSERT INTO user_lineup (user_id, player_id) VALUES (?, ?)", (user_id, player_id))
        return True


def get_user_lineup(user_id: int):
    """بازیکن‌های ترکیب اصلی فعلی (فقط اونایی که مصدوم نشدن)"""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT p.player_id, p.name, p.team, p.position, p.price,
                   COALESCE(up.owned_power, p.power) as power,
                   p.week_points, p.total_points
            FROM players p
            JOIN user_lineup ul ON ul.player_id = p.player_id
            JOIN user_players up ON up.player_id = p.player_id AND up.user_id = ul.user_id
            WHERE ul.user_id = ? AND up.injury_matches_left = 0
        """, (user_id,))
        return c.fetchall()


def get_lineup_position_counts(user_id: int) -> dict:
    counts = {"GK": 0, "DF": 0, "MF": 0, "FW": 0}
    for p in get_user_lineup(user_id):
        if p["position"] in counts:
            counts[p["position"]] += 1
    return counts


def get_lineup_required_counts(user_id: int):
    """بر اساس آرایش انتخابی، تعداد لازم هر پست رو برمی‌گردونه (دروازه‌بان همیشه ۱)"""
    row = get_user_row(user_id)
    formation_key = row["formation"] if row and row["formation"] in FORMATIONS else None
    if not formation_key:
        return None
    req = dict(FORMATIONS[formation_key])
    req["GK"] = 1
    return req


def is_lineup_complete(user_id: int) -> bool:
    required = get_lineup_required_counts(user_id)
    if not required:
        return False
    counts = get_lineup_position_counts(user_id)
    return all(counts.get(pos, 0) == need for pos, need in required.items())


def get_match_power(user_id: int) -> float:
    """قدرت موثر تیم برای بازی: اگه ترکیب اصلی کامل چیده شده باشه از همون استفاده می‌کنه
    (که فقط ۱۱ نفره)، وگرنه (برای سازگاری با تیم‌هایی که هنوز ترکیب نچیدن) از کل بازیکن‌های
    غیرمصدوم تیم استفاده می‌کنه."""
    if is_lineup_complete(user_id):
        return sum(p["power"] for p in get_user_lineup(user_id))
    return sum(p["power"] for p in get_available_squad(user_id))


def set_user_tactic(user_id: int, tactic_key: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET tactic = ? WHERE user_id = ?", (tactic_key, user_id))


def get_user_tactic(user_id: int) -> str:
    row = get_user_row(user_id)
    t = row["tactic"] if row and row["tactic"] in TACTICS else "standard"
    return t


# ================== ورزشگاه و هواداران ==================

def get_stadium_upgrade_cost(current_level: int) -> int:
    return STADIUM_UPGRADE_BASE_COST * current_level


def upgrade_stadium(user_id: int) -> str:
    row = get_user_row(user_id)
    level = row["stadium_level"] or 1
    if level >= STADIUM_MAX_LEVEL:
        return f"ورزشگاهت همین الانشم توی حداکثر سطح ({STADIUM_MAX_LEVEL}) هست."
    cost = get_stadium_upgrade_cost(level)
    budget = get_user_budget(user_id)
    if budget < cost:
        return f"برای ارتقا به سطح {level+1} به {cost} م.ت نیاز داری؛ بودجه‌ت {budget:.1f} م.ت هست."
    update_user_budget(user_id, budget - cost)
    with get_conn() as conn:
        conn.execute("UPDATE users SET stadium_level = stadium_level + 1 WHERE user_id = ?", (user_id,))
    return f"🏟 ورزشگاهت به سطح {level+1} ارتقا پیدا کرد! ({cost} م.ت کم شد)"


def update_fans(user_id: int, delta: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET fans = MAX(0, fans + ?) WHERE user_id = ?",
            (delta, user_id),
        )


def apply_match_gate_income(user_id: int):
    """درآمد فروش بلیت بر اساس تعداد هواداران و سطح ورزشگاه، بعد از هر بازی رسمی"""
    row = get_user_row(user_id)
    fans = row["fans"] or 0
    level = row["stadium_level"] or 1
    income = (fans // 1000) * level
    if income > 0:
        update_user_budget(user_id, get_user_budget(user_id) + income)
    return income


# ================== مصدومیت ==================

def process_injuries_after_match(user_id: int, played_player_ids: list):
    """بعد از هر بازی رسمی: هر بازیکنی که بازی کرده یه شانس کوچیک مصدومیتِ چند بازی داره،
    و شمارش‌معکوس مصدومیت‌های قبلیِ کل بازیکنای تیم هم یکی کم می‌شه"""
    with get_conn() as conn:
        conn.execute(
            "UPDATE user_players SET injury_matches_left = MAX(0, injury_matches_left - 1) WHERE user_id = ?",
            (user_id,),
        )
    new_injuries = []
    for pid in played_player_ids:
        if random.random() < INJURY_CHANCE:
            duration = random.randint(INJURY_MIN_MATCHES, INJURY_MAX_MATCHES)
            with get_conn() as conn:
                conn.execute(
                    "UPDATE user_players SET injury_matches_left = ? WHERE user_id = ? AND player_id = ?",
                    (duration, user_id, pid),
                )
            player = get_player(pid)
            if player:
                new_injuries.append((player["name"], duration))
    return new_injuries


def get_missing_positions_text(user_id: int):
    """اگه تیم ترکیب لازم (پست‌ها) رو نداشته باشه، متن توضیح کمبودها رو برمی‌گردونه؛ وگرنه None"""
    counts = get_team_position_counts(user_id)
    missing = []
    for pos, need in REQUIRED_POSITION_COUNTS.items():
        have = counts.get(pos, 0)
        if have < need:
            missing.append(f"{POSITION_FA.get(pos, pos)}: {have} از {need} لازم")
    if not missing:
        return None
    lines = ["ترکیب تیمت کامل نیست! برای بازی حداقل باید داشته باشی:"]
    lines.append(
        f"{REQUIRED_POSITION_COUNTS['GK']} دروازه‌بان، "
        f"{REQUIRED_POSITION_COUNTS['DF']} مدافع، "
        f"{REQUIRED_POSITION_COUNTS['MF']} هافبک، "
        f"{REQUIRED_POSITION_COUNTS['FW']} مهاجم"
    )
    lines.append("\nکمبودهای تیمت:")
    lines.extend(f"- {m}" for m in missing)
    return "\n".join(lines)


def get_random_opponent(exclude_user_id: int, min_team_size: int):
    """یه کاربر دیگه که حداقل min_team_size بازیکن داره و ترکیب پست‌هاش کامله رو تصادفی برمی‌گردونه"""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT u.user_id, u.username, COUNT(up.player_id) as team_size
            FROM users u
            JOIN user_players up ON up.user_id = u.user_id
            WHERE u.user_id != ?
            GROUP BY u.user_id
            HAVING team_size >= ?
        """, (exclude_user_id, min_team_size))
        rows = c.fetchall()
        if not rows:
            return None
        valid_rows = [row for row in rows if get_missing_positions_text(row["user_id"]) is None]
        if not valid_rows:
            return None
        return random.choice(valid_rows)


def get_all_matchday_eligible_users():
    """همه کاربرایی که تیمشون کامله (اندازه و ترکیب پست) و آماده‌ی بازی هستن، بدون هیچ سقفی
    (ادمین‌ها هیچ‌وقت جزو تیم‌های لیگ حساب نمی‌شن)"""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT u.user_id, u.total_points, COUNT(up.player_id) as team_size
            FROM users u
            JOIN user_players up ON up.user_id = u.user_id
            GROUP BY u.user_id
            HAVING team_size >= ?
            ORDER BY u.total_points DESC
        """, (MIN_TEAM_SIZE,))
        rows = c.fetchall()
    return [
        row["user_id"] for row in rows
        if row["user_id"] not in ADMIN_IDS and get_missing_positions_text(row["user_id"]) is None
    ]


def get_matchday_eligible_users():
    """همه‌ی تیم‌های آماده رو برمی‌گردونه، بدون هیچ سقفی"""
    return get_all_matchday_eligible_users()


def get_all_teams_for_manual():
    """همه‌ی کاربرایی که حداقل یه بازیکن دارن رو برمی‌گردونه (مهم نیست تیمشون کامل باشه یا نه)،
    برای اینکه ادمین بتونه خودش دستی جفتشون کنه. ادمین‌ها جزو این لیست نیستن."""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT u.user_id, COUNT(up.player_id) as team_size
            FROM users u
            JOIN user_players up ON up.user_id = u.user_id
            GROUP BY u.user_id
            HAVING team_size >= 1
            ORDER BY u.user_id
        """)
        rows = c.fetchall()
    return [row["user_id"] for row in rows if row["user_id"] not in ADMIN_IDS]


def manual_teams_keyboard(exclude_id: int = None) -> InlineKeyboardMarkup:
    team_ids = get_all_teams_for_manual()
    rows = []
    for uid in team_ids:
        if uid == exclude_id:
            continue
        row = get_user_row(uid)
        size = get_user_team_size(uid)
        label = f"{team_display_name(row)} ({size} نفر)"
        rows.append([InlineKeyboardButton(label, callback_data=f"manualpick_{uid}")])
    rows.append([InlineKeyboardButton("🏁 پایان و اعلام نتایج در کانال", callback_data="manual_finish")])
    rows.append([InlineKeyboardButton("❌ لغو و بازگشت به پنل", callback_data="manual_cancel")])
    return InlineKeyboardMarkup(rows)


async def play_one_match(bot, user_a: int, user_b: int) -> str:
    """یه بازی رسمی (لیگ/دستی) بین دو تیم مشخص برگزار می‌کنه: تاکتیک و ترکیب اصلی رو حساب می‌کنه،
    نتیجه، گل‌زن‌ها، پاس‌گل‌ها، بهترین بازیکن زمین، هواداران، درآمد ورزشگاه، مصدومیت و پاداش اسپانسر
    رو مدیریت می‌کنه، به هر دو طرف خصوصی پیام می‌ده و خط نتیجه (برای نمایش/کانال) رو برمی‌گردونه."""
    base_power_a = get_match_power(user_a)
    base_power_b = get_match_power(user_b)

    tactic_a = TACTICS[get_user_tactic(user_a)]
    tactic_b = TACTICS[get_user_tactic(user_b)]
    adj_power_a = (base_power_a + 1) * tactic_a["atk"] / tactic_b["def"]
    adj_power_b = (base_power_b + 1) * tactic_b["atk"] / tactic_a["def"]

    goals_a, goals_b = simulate_goals(adj_power_a, adj_power_b)

    if goals_a == goals_b:
        record_battle_result(user_a, user_b, is_draw=True)
        result_a = f"🤝 مساوی! {DRAW_POINTS} امتیاز گرفتی."
        result_b = f"🤝 مساوی! {DRAW_POINTS} امتیاز گرفتی."
    elif goals_a > goals_b:
        record_battle_result(user_a, user_b)
        result_a = f"🏆 بردی! {WIN_POINTS} امتیاز گرفتی."
        result_b = "😔 باختی."
    else:
        record_battle_result(user_b, user_a)
        result_a = "😔 باختی."
        result_b = f"🏆 بردی! {WIN_POINTS} امتیاز گرفتی."

    record_fixture(user_a, user_b)

    row_a = get_user_row(user_a)
    row_b = get_user_row(user_b)
    name_a = team_display_name(row_a)
    name_b = team_display_name(row_b)

    bonus_note_a = ""
    bonus_note_b = ""
    if row_a["sponsor"] in SPONSOR_MAP:
        update_user_budget(user_a, get_user_budget(user_a) + SPONSOR_MATCH_BONUS)
        label, emoji = SPONSOR_MAP[row_a["sponsor"]]
        bonus_note_a = f"\n{emoji} اسپانسر {label}: +{SPONSOR_MATCH_BONUS} میلیون تومان"
    if row_b["sponsor"] in SPONSOR_MAP:
        update_user_budget(user_b, get_user_budget(user_b) + SPONSOR_MATCH_BONUS)
        label, emoji = SPONSOR_MAP[row_b["sponsor"]]
        bonus_note_b = f"\n{emoji} اسپانسر {label}: +{SPONSOR_MATCH_BONUS} میلیون تومان"

    set_last_action_date(user_a, "last_battle_date", get_today_str())
    set_last_action_date(user_b, "last_battle_date", get_today_str())

    # ---- ترکیب واقعی بازی‌کننده‌ها، گل‌زن‌ها و پاس‌گل‌ها ----
    players_a = get_match_participants(user_a)
    players_b = get_match_participants(user_b)
    events = build_match_events(players_a, players_b, goals_a, goals_b)
    timeline = format_match_events(events)
    timeline_block = f"\n\n⚽ گل‌ها:\n{timeline}" if timeline else ""

    # ---- امتیاز بازیکنان و بهترین بازیکن زمین ----
    scores_a = compute_match_scores(players_a, events, "a", goals_b)
    scores_b = compute_match_scores(players_b, events, "b", goals_a)
    apply_match_scores(user_a, scores_a)
    apply_match_scores(user_b, scores_b)

    mvp_text = ""
    best_pid_a = max(scores_a, key=scores_a.get) if scores_a else None
    best_pid_b = max(scores_b, key=scores_b.get) if scores_b else None
    candidates = []
    if best_pid_a:
        candidates.append((scores_a[best_pid_a], best_pid_a, players_a, name_a))
    if best_pid_b:
        candidates.append((scores_b[best_pid_b], best_pid_b, players_b, name_b))
    if candidates:
        best_score, best_pid, best_players, best_team_name = max(candidates, key=lambda x: x[0])
        best_player = next((p for p in best_players if p["player_id"] == best_pid), None)
        if best_player:
            mvp_text = f"\n\n⭐ بهترین بازیکن زمین: {best_player['name']} ({best_team_name})"

    # ---- هواداران ----
    if goals_a > goals_b:
        update_fans(user_a, random.randint(50, 150))
        update_fans(user_b, -random.randint(20, 80))
    elif goals_b > goals_a:
        update_fans(user_b, random.randint(50, 150))
        update_fans(user_a, -random.randint(20, 80))
    else:
        update_fans(user_a, random.randint(5, 25))
        update_fans(user_b, random.randint(5, 25))

    # ---- درآمد فروش بلیت ورزشگاه ----
    income_a = apply_match_gate_income(user_a)
    income_b = apply_match_gate_income(user_b)
    income_note_a = f"\n🏟 درآمد بلیت: +{income_a} م.ت" if income_a > 0 else ""
    income_note_b = f"\n🏟 درآمد بلیت: +{income_b} م.ت" if income_b > 0 else ""

    # ---- مصدومیت ----
    injuries_a = process_injuries_after_match(user_a, [p["player_id"] for p in players_a])
    injuries_b = process_injuries_after_match(user_b, [p["player_id"] for p in players_b])
    injury_note_a = ""
    if injuries_a:
        injury_note_a = "\n\n🚑 مصدومیت:\n" + "\n".join(f"{n} ({d} بازی محروم)" for n, d in injuries_a)
    injury_note_b = ""
    if injuries_b:
        injury_note_b = "\n\n🚑 مصدومیت:\n" + "\n".join(f"{n} ({d} بازی محروم)" for n, d in injuries_b)

    for target_id, text in (
        (user_a, f"⚔️ نتیجه بازی:\n\n{name_a}  {goals_a} - {goals_b}  {name_b}{timeline_block}{mvp_text}\n\n{result_a}{bonus_note_a}{income_note_a}{injury_note_a}"),
        (user_b, f"⚔️ نتیجه بازی:\n\n{name_a}  {goals_a} - {goals_b}  {name_b}{timeline_block}{mvp_text}\n\n{result_b}{bonus_note_b}{income_note_b}{injury_note_b}"),
    ):
        try:
            await bot.send_message(chat_id=target_id, text=text)
        except Exception:
            pass

    return f"{name_a}  {goals_a} - {goals_b}  {name_b}"


async def play_friendly_match(bot, requester_id: int, opponent_id: int) -> str:
    """بازی دوستانه بین دو کاربر: نتیجه واقعیه، تاکتیک و ترکیب اصلی هم حساب می‌شه،
    ولی هیچ تاثیری روی امتیاز/برد/باخت جدول لیگ، درآمد اسپانسر، هواداران یا مصدومیت نداره
    (فقط برای تفریحه). متن نتیجه برای درخواست‌دهنده برگردونده می‌شه؛ به حریف هم خصوصی پیام می‌ره."""
    base_power_a = get_match_power(requester_id)
    base_power_b = get_match_power(opponent_id)
    tactic_a = TACTICS[get_user_tactic(requester_id)]
    tactic_b = TACTICS[get_user_tactic(opponent_id)]
    adj_power_a = (base_power_a + 1) * tactic_a["atk"] / tactic_b["def"]
    adj_power_b = (base_power_b + 1) * tactic_b["atk"] / tactic_a["def"]
    goals_a, goals_b = simulate_goals(adj_power_a, adj_power_b)

    row_a = get_user_row(requester_id)
    row_b = get_user_row(opponent_id)
    name_a = team_display_name(row_a)
    name_b = team_display_name(row_b)

    if goals_a > goals_b:
        result_a, result_b = "🏆 بردی!", "😔 باختی."
    elif goals_b > goals_a:
        result_a, result_b = "😔 باختی.", "🏆 بردی!"
    else:
        result_a = result_b = "🤝 مساوی شد."

    footer = "\n\n(این یه بازی دوستانه بود، روی جدول لیگ و درآمد اسپانسر تاثیری نداره)"
    players_a = get_match_participants(requester_id)
    players_b = get_match_participants(opponent_id)
    events = build_match_events(players_a, players_b, goals_a, goals_b)
    timeline = format_match_events(events)
    timeline_block = f"\n\n⚽ گل‌ها:\n{timeline}" if timeline else ""
    text_a = f"🤝 بازی دوستانه:\n\n{name_a}  {goals_a} - {goals_b}  {name_b}{timeline_block}\n\n{result_a}{footer}"
    text_b = f"🤝 بازی دوستانه:\n\n{name_a}  {goals_a} - {goals_b}  {name_b}{timeline_block}\n\n{result_b}{footer}"

    try:
        await bot.send_message(chat_id=opponent_id, text=text_b)
    except Exception:
        pass

    return text_a


def get_friendly_opponents(exclude_id: int):
    """همه‌ی کاربرایی که حداقل یه بازیکن دارن (مهم نیست ترکیبشون کامل باشه یا نه)،
    به‌جز خود کاربر و ادمین‌ها، برای بازی دوستانه"""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT u.user_id, COUNT(up.player_id) as team_size
            FROM users u
            JOIN user_players up ON up.user_id = u.user_id
            GROUP BY u.user_id
            HAVING team_size >= 1
            ORDER BY u.user_id
        """)
        rows = c.fetchall()
    return [row for row in rows if row["user_id"] != exclude_id and row["user_id"] not in ADMIN_IDS]


def friendly_opponents_keyboard(exclude_id: int) -> InlineKeyboardMarkup:
    rows = []
    for row in get_friendly_opponents(exclude_id):
        uid = row["user_id"]
        urow = get_user_row(uid)
        label = f"{team_display_name(urow)} ({row['team_size']} نفر)"
        rows.append([InlineKeyboardButton(label, callback_data=f"friendlypick_{uid}")])
    rows.append([InlineKeyboardButton("❌ انصراف", callback_data="friendly_cancel")])
    return InlineKeyboardMarkup(rows)


async def run_matchday(bot) -> str:
    """همه‌ی تیم‌های آماده رو به‌صورت دوره‌ای (لیگی) با هم بازی می‌ده — هر جفت تیم رفت و برگشت
    (دقیقاً ۲ بار) با هم بازی می‌کنن؛ جفت‌هایی که هر دو بازیشون تموم شده دیگه تکرار نمی‌شن.
    این یعنی اگه یه تیم وسط فصل بیاد، خودکار فقط با بقیه‌ی تیم‌ها (که هنوز رفت‌وبرگشتشون تموم نشده) جفت می‌شه.
    به هر بازیکن نتیجه‌ی بازی‌هاش خصوصی می‌رسه و خلاصه‌ی کامل هم به کانال (اگه تنظیم شده باشه) پست می‌شه."""
    eligible = get_matchday_eligible_users()
    match_lines = []
    skipped_already_played = 0

    if len(eligible) < 2:
        return "⚠️ برای برگزاری بازی حداقل به ۲ تیم آماده نیاز داریم."

    # هر جفت تیم رفت و برگشت (۲ بار) با هم بازی می‌کنن؛ جفت‌هایی که کامل شدن رد می‌شن
    for idx_a in range(len(eligible)):
        for idx_b in range(idx_a + 1, len(eligible)):
            user_a, user_b = eligible[idx_a], eligible[idx_b]
            if has_played_fixture(user_a, user_b):
                skipped_already_played += 1
                continue
            line = await play_one_match(bot, user_a, user_b)
            match_lines.append(line)

    if match_lines:
        channel_text = "⚽️ نتایج بازی‌های امروز:\n\n" + "\n".join(match_lines)
        if CHANNEL_ID:
            try:
                await bot.send_message(chat_id=CHANNEL_ID, text=channel_text)
            except Exception as e:
                logger.warning(f"ارسال نتایج به کانال ناموفق بود: {e}")

    summary = f"✅ روز بازی تموم شد. {len(eligible)} تیم شرکت کردن و {len(match_lines)} بازی جدید برگزار شد."
    if skipped_already_played:
        summary += f"\n({skipped_already_played} جفت رفت‌وبرگشتشون قبلاً کامل شده بود، دوباره بازی نکردن.)"
    if not match_lines:
        summary += "\n\nهمه‌ی تیم‌های آماده رفت‌وبرگشتشون کامل شده؛ چیز جدیدی برای بازی نبود."
    if not CHANNEL_ID:
        summary += "\n\n⚠️ آیدی کانال تنظیم نشده، برای همین نتایج فقط به خود بازیکنا پیام خصوصی شد."
    return summary


def render_final_season_table() -> str:
    rows = get_leaderboard(50)
    if not rows:
        return "🏁 فصل تموم شد، ولی هیچ تیمی امتیازی نداشت."
    lines = ["🏁 فصل به پایان رسید! همه‌ی تیم‌ها رفت و برگشت با هم بازی کردن.\n", "🏅 جدول نهایی لیگ:\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows):
        games = (r["wins"] or 0) + (r["draws"] or 0) + (r["losses"] or 0)
        avg = (r["total_points"] / games) if games > 0 else 0.0
        prefix = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{prefix} {team_display_name(r)} - میانگین {avg:.2f} ({games} بازی، {r['total_points']:.1f} امتیاز کل)")
    champion = team_display_name(rows[0])
    lines.append(f"\n🏆 قهرمان فصل: {champion} 🏆")
    return "\n".join(lines)


async def auto_matchday_job(context: ContextTypes.DEFAULT_TYPE):
    """این تابع هر ۵ ساعت خودکار اجرا می‌شه: یه دور بازی برگزار می‌کنه، و اگه همه‌ی تیم‌ها
    رفت‌وبرگشتشون تموم شده باشه، جدول نهایی و قهرمان رو اعلام می‌کنه و خودش متوقف می‌شه."""
    bot = context.bot
    try:
        summary = await run_matchday(bot)
        logger.info(f"اجرای خودکار فصل: {summary}")
    except Exception as e:
        logger.warning(f"خطا توی اجرای خودکار فصل: {e}")
        return

    if is_season_complete():
        final_text = render_final_season_table()
        if CHANNEL_ID:
            try:
                await bot.send_message(chat_id=CHANNEL_ID, text=final_text)
            except Exception as e:
                logger.warning(f"ارسال جدول نهایی به کانال ناموفق بود: {e}")
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(chat_id=admin_id, text="✅ فصل خودکار تموم شد و متوقف شد.\n\n" + final_text)
            except Exception:
                pass
        if context.job:
            context.job.schedule_removal()


def _poisson_random(lam: float) -> int:
    """یه عدد تصادفی به سبک توزیع پواسون تولید می‌کنه (بدون نیاز به numpy)"""
    lam = max(lam, 0.05)
    limit = math.exp(-lam)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= random.random()
        if p <= limit:
            return k - 1


def simulate_goals(power_a: float, power_b: float):
    """بر اساس قدرت دو تیم، یه نتیجه گل‌به‌گل واقعی (مثل ۳-۱) شبیه‌سازی می‌کنه.
    فرمول طوری تنظیم شده که تفاوت قدرت واقعاً روی نتیجه تاثیر بذاره، نه اینکه حس تصادفی بده:
    تیم‌های هم‌قدرت تقریباً ۵۰-۵۰ هستن، ولی هرچی فاصله‌ی قدرت بیشتر بشه، تیم قوی‌تر خیلی بیشتر می‌بره."""
    pa = max(power_a, 0) + 1
    pb = max(power_b, 0) + 1
    power_exponent = 2.2   # هرچی بزرگ‌تر باشه، تاثیر قدرت روی نتیجه تعیین‌کننده‌تره
    base_goals = 0.35      # حداقل میانگین گل هر تیم (حتی تیم خیلی ضعیف)
    goal_spread = 3.2       # سقف اضافه‌ی گل بر اساس برتری قدرت

    ratio_a = (pa ** power_exponent) / (pa ** power_exponent + pb ** power_exponent)
    avg_a = base_goals + goal_spread * ratio_a
    avg_b = base_goals + goal_spread * (1 - ratio_a)
    return _poisson_random(avg_a), _poisson_random(avg_b)


def get_match_participants(user_id: int):
    """بازیکن‌هایی که واقعاً توی این بازی حساب می‌شن: اگه ترکیب اصلی کامل چیده شده، همون ۱۱ نفر،
    وگرنه کل بازیکن‌های غیرمصدوم تیم (برای سازگاری با تیم‌هایی که هنوز ترکیب نچیدن)"""
    if is_lineup_complete(user_id):
        return get_user_lineup(user_id)
    return get_available_squad(user_id)


# شانس نسبی هر پست برای پاس گل دادن (پلی‌میکر و هافبک‌ها بیشتر از همه)
ASSIST_SCORE_WEIGHT = {"GK": 0, "DF": 1, "MF": 3, "FW": 2}
ASSIST_CHANCE = 0.55  # احتمال اینکه یه گل روی پاس گل کسی زده بشه (نه گل تنهایی)


def _weighted_pick(weighted_pairs):
    if not weighted_pairs:
        return None
    total = sum(w for _, w in weighted_pairs)
    r = random.uniform(0, total)
    upto = 0
    for p, w in weighted_pairs:
        upto += w
        if upto >= r:
            return p
    return weighted_pairs[-1][0]


def pick_scorer(players):
    """یه گلزن از بین بازیکن‌های بازی‌کننده انتخاب می‌کنه: دروازه‌بان هیچ‌وقت انتخاب نمی‌شه،
    مهاجم بیشترین شانس رو داره، بعد هافبک، بعد مدافع. بازیکن‌های قوی‌تر هم شانس بیشتری دارن."""
    weighted = [
        (p, POSITION_SCORE_WEIGHT.get(p["position"], 0) * (p["power"] + 1))
        for p in players
    ]
    weighted = [(p, w) for p, w in weighted if w > 0]
    return _weighted_pick(weighted)


def pick_assister(players, exclude_player_id):
    weighted = [
        (p, ASSIST_SCORE_WEIGHT.get(p["position"], 0) * (p["power"] + 1))
        for p in players if p["player_id"] != exclude_player_id
    ]
    weighted = [(p, w) for p, w in weighted if w > 0]
    return _weighted_pick(weighted)


def build_match_events(team_a_players, team_b_players, goals_a, goals_b):
    """برای هر گل یه گلزن (و شاید یه پاس‌گل‌دهنده) و یه دقیقه‌ی تصادفی می‌سازه"""
    events = []
    for _ in range(goals_a):
        scorer = pick_scorer(team_a_players)
        assister = pick_assister(team_a_players, scorer["player_id"]) if scorer and random.random() < ASSIST_CHANCE else None
        events.append({"minute": random.randint(1, 90), "side": "a", "scorer": scorer, "assister": assister})
    for _ in range(goals_b):
        scorer = pick_scorer(team_b_players)
        assister = pick_assister(team_b_players, scorer["player_id"]) if scorer and random.random() < ASSIST_CHANCE else None
        events.append({"minute": random.randint(1, 90), "side": "b", "scorer": scorer, "assister": assister})
    events.sort(key=lambda e: e["minute"])
    return events


def format_match_events(events) -> str:
    if not events:
        return ""
    lines = []
    for e in events:
        arrow = "⬅️" if e["side"] == "a" else "➡️"
        scorer_name = e["scorer"]["name"] if e["scorer"] else "نامشخص"
        line = f"{e['minute']}' {arrow} {scorer_name}"
        if e["assister"]:
            line += f" (پاس گل: {e['assister']['name']})"
        lines.append(line)
    return "\n".join(lines)


def compute_match_scores(players, events, side, conceded_goals):
    """امتیاز هر بازیکن توی این بازی رو حساب می‌کنه: گل=۴، پاس‌گل=۲، حضور=۱، کلین‌شیت برای مدافع/دروازه‌بان=۲"""
    scores = {p["player_id"]: 1.0 for p in players}  # امتیاز حضور
    for e in events:
        if e["side"] != side:
            continue
        if e["scorer"]:
            scores[e["scorer"]["player_id"]] = scores.get(e["scorer"]["player_id"], 0) + 4
        if e["assister"]:
            scores[e["assister"]["player_id"]] = scores.get(e["assister"]["player_id"], 0) + 2
    if conceded_goals == 0:
        for p in players:
            if p["position"] in ("GK", "DF"):
                scores[p["player_id"]] = scores.get(p["player_id"], 0) + 2
    return scores


def apply_match_scores(user_id: int, scores: dict):
    with get_conn() as conn:
        for player_id, pts in scores.items():
            conn.execute(
                "UPDATE user_players SET season_points = season_points + ? WHERE user_id = ? AND player_id = ?",
                (pts, user_id, player_id),
            )


def record_battle_result(winner_id: int, loser_id: int, is_draw: bool = False):
    with get_conn() as conn:
        if is_draw:
            conn.execute(
                "UPDATE users SET draws = draws + 1, total_points = total_points + ? WHERE user_id IN (?, ?)",
                (DRAW_POINTS, winner_id, loser_id),
            )
        else:
            conn.execute(
                "UPDATE users SET wins = wins + 1, total_points = total_points + ? WHERE user_id = ?",
                (WIN_POINTS, winner_id),
            )
            conn.execute("UPDATE users SET losses = losses + 1 WHERE user_id = ?", (loser_id,))


def get_leaderboard(limit: int = 10):
    """جدول لیگ رو برمی‌گردونه — فقط شامل کاربرایی که الان واقعاً تیم معتبر و کامل دارن،
    و رتبه‌بندی بر اساس میانگین امتیاز هر بازی (Points Per Game) نه مجموع امتیاز؛ اینجوری تیمی
    که وسط فصل اومده و بازی کمتری داشته، به‌خاطر تعداد بازی کم ناعادلانه ته جدول نمی‌مونه."""
    eligible_ids = get_all_matchday_eligible_users()
    if not eligible_ids:
        return []
    with get_conn() as conn:
        c = conn.cursor()
        placeholders = ",".join("?" * len(eligible_ids))
        c.execute(
            f"SELECT user_id, username, team_name, kit_color1, kit_color2, "
            f"total_points, wins, draws, losses FROM users "
            f"WHERE user_id IN ({placeholders})",
            eligible_ids,
        )
        rows = c.fetchall()

    def games_played(row):
        return (row["wins"] or 0) + (row["draws"] or 0) + (row["losses"] or 0)

    def ppg(row):
        games = games_played(row)
        return (row["total_points"] / games) if games > 0 else 0.0

    rows_sorted = sorted(rows, key=lambda r: (ppg(r), r["total_points"]), reverse=True)
    return rows_sorted[:limit]


def _normalize_pair(user_a: int, user_b: int):
    return (user_a, user_b) if user_a < user_b else (user_b, user_a)


MAX_LEGS_PER_PAIR = 2  # هر جفت تیم رفت و برگشت (۲ بار) با هم بازی می‌کنن


def get_fixture_legs(user_a: int, user_b: int) -> int:
    a, b = _normalize_pair(user_a, user_b)
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT legs_played FROM fixtures WHERE user_a = ? AND user_b = ?", (a, b))
        row = c.fetchone()
        return row["legs_played"] if row else 0


def has_played_fixture(user_a: int, user_b: int) -> bool:
    """آیا این جفت تیم رفت و برگشت (هر دو بازی) رو کامل انجام دادن؟"""
    return get_fixture_legs(user_a, user_b) >= MAX_LEGS_PER_PAIR


def record_fixture(user_a: int, user_b: int):
    a, b = _normalize_pair(user_a, user_b)
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO fixtures (user_a, user_b, legs_played) VALUES (?, ?, 1)
            ON CONFLICT(user_a, user_b) DO UPDATE SET legs_played = legs_played + 1
        """, (a, b))


def reset_fixtures():
    with get_conn() as conn:
        conn.execute("DELETE FROM fixtures")


def is_season_complete() -> bool:
    """آیا همه‌ی تیم‌های آماده، رفت و برگشت (هر دو بازی) رو با هم انجام دادن؟"""
    eligible = get_matchday_eligible_users()
    if len(eligible) < 2:
        return False
    for i in range(len(eligible)):
        for j in range(i + 1, len(eligible)):
            if get_fixture_legs(eligible[i], eligible[j]) < MAX_LEGS_PER_PAIR:
                return False
    return True


def reset_league():
    """امتیاز کل، برد/باخت/مساوی همه کاربرا رو صفر می‌کنه و تاریخچه‌ی بازی‌های قبلی (fixtures) هم
    پاک می‌شه، یعنی انگار یه فصل تازه شروع شده و همه دوباره باید با همه بازی کنن"""
    with get_conn() as conn:
        conn.execute("UPDATE users SET total_points = 0, wins = 0, draws = 0, losses = 0")
    reset_fixtures()


def remove_all_players():
    """همه‌ی بازیکن‌ها رو کاملاً از بازی حذف می‌کنه (هم از فروشگاه، هم از تیم همه کاربرا)"""
    with get_conn() as conn:
        conn.execute("DELETE FROM user_players")
        conn.execute("DELETE FROM players")
        try:
            conn.execute("DELETE FROM sqlite_sequence WHERE name = 'players'")
        except sqlite3.OperationalError:
            pass


def clear_user_team(user_id: int):
    """تیم یه کاربر خاص رو کاملاً خالی می‌کنه و بودجه‌ش رو به مقدار اولیه برمی‌گردونه
    تا بتونه از صفر یه تیم جدید بسازه (بازیکن‌ها توی فروشگاه دست‌نخورده می‌مونن)"""
    with get_conn() as conn:
        conn.execute("DELETE FROM user_players WHERE user_id = ?", (user_id,))
        conn.execute("UPDATE users SET budget = ? WHERE user_id = ?", (INITIAL_BUDGET, user_id))


def clear_all_teams():
    """تیم همه‌ی کاربرا رو کاملاً خالی می‌کنه و بودجه‌ی همه رو به مقدار اولیه برمی‌گردونه
    (بازیکن‌ها توی فروشگاه می‌مونن، هرکس می‌تونه از نو تیم بسازه)"""
    with get_conn() as conn:
        conn.execute("DELETE FROM user_players")
        conn.execute("UPDATE users SET budget = ?", (INITIAL_BUDGET,))


def find_user_by_username(username: str):
    """جستجوی کاربر با یوزرنیم (بدون @) برای دستورات ادمین"""
    username = username.lstrip("@")
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        return c.fetchone()


def get_news() -> str:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT content FROM news WHERE id = 1")
        row = c.fetchone()
        return row["content"] if row else ""


def set_news(content: str):
    with get_conn() as conn:
        conn.execute("UPDATE news SET content = ? WHERE id = 1", (content,))


# ================== ربات ==================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

POSITION_FA = {"GK": "دروازه‌بان", "DF": "مدافع", "MF": "هافبک", "FW": "مهاجم"}

# شانس نسبی هر پست برای گلزنی: دروازه‌بان اصلاً گل نمی‌زنه، مهاجم از همه بیشتر
POSITION_SCORE_WEIGHT = {"GK": 0, "DF": 1, "MF": 2, "FW": 4}

# پالت رنگ‌های قابل انتخاب برای پیراهن تیم (کلید، اسم فارسی، ایموجی)
KIT_COLORS = [
    ("red", "قرمز", "🔴"),
    ("blue", "آبی", "🔵"),
    ("green", "سبز", "🟢"),
    ("yellow", "زرد", "🟡"),
    ("black", "مشکی", "⚫"),
    ("white", "سفید", "⚪"),
    ("orange", "نارنجی", "🟠"),
    ("purple", "بنفش", "🟣"),
]
KIT_COLOR_MAP = {key: (label, emoji) for key, label, emoji in KIT_COLORS}

# لیست اسپانسرهای قابل انتخاب برای باشگاه (کلید، اسم، ایموجی)
SPONSORS = [
    ("digikala", "دیجی‌کالا", "🛒"),
    ("snapp", "اسنپ", "🚕"),
    ("irancell", "ایرانسل", "📱"),
    ("tapsi", "تپسی", "🚖"),
    ("bank_melli", "بانک ملی", "🏦"),
    ("golrang", "گلرنگ", "🧴"),
    ("mihan", "میهن", "🥛"),
    ("zarrin", "زرین", "🍫"),
]
SPONSOR_MAP = {key: (label, emoji) for key, label, emoji in SPONSORS}

# پک‌های قابل خرید با فوت توکن. هر بازیکن با (نام, تیم, پست, قیمت, قدرت) مشخص شده —
# دقیقاً همون مشخصاتی که قبلاً برای این بازیکن‌ها تعیین شده بود.
PACKS = {
    "standard": {
        "label": "🥉 پک معمولی",
        "cost": 50,
        "players": [
            ("مالدینی", "میلان", "DF", 2000, 20),
            ("بوفون", "یوونتوس", "GK", 2000, 20),
        ],
        "bonus_budget": 0,
    },
    "advanced": {
        "label": "🥈 پک پیشرفته",
        "cost": 70,
        "players": [
            ("مودریچ", "رئال مادرید", "MF", 2000, 20),
            ("نیمار", "بارسلونا", "FW", 2000, 25),
        ],
        "bonus_budget": 0,
    },
    "semi_special": {
        "label": "🥇 پک نیمه ویژه",
        "cost": 100,
        "players": [
            ("مسی", "بارسلونا", "FW", 2000, 30),
            ("رونالدو", "رئال مادرید", "FW", 2000, 30),
            ("نیمار", "بارسلونا", "FW", 2000, 25),
        ],
        "bonus_budget": 50,
    },
    "special": {
        "label": "💎 پک ویژه",
        "cost": 150,  # ⚠️ قیمتش رو نگفته بودی؛ فرض کردم ۱۵۰، بگو اگه چیز دیگه‌ای مدنظرت بود
        "players": [
            ("مسی", "بارسلونا", "FW", 2000, 30),
            ("رونالدو", "رئال مادرید", "FW", 2000, 30),
            ("نیمار", "بارسلونا", "FW", 2000, 25),
            ("مودریچ", "رئال مادرید", "MF", 2000, 20),
            ("بوفون", "یوونتوس", "GK", 2000, 20),
            ("مالدینی", "میلان", "DF", 2000, 20),
        ],
        "bonus_budget": 100,
    },
}

# حداقل تعداد لازم از هر پست برای اینکه تیم اجازه بازی داشته باشه
REQUIRED_POSITION_COUNTS = {"GK": 1, "DF": 4, "MF": 4, "FW": 3}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ---------- دستورات عمومی ----------

def main_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("📋 لیست بازیکنان", callback_data="menu_players"),
            InlineKeyboardButton("👥 تیم من", callback_data="menu_myteam"),
        ],
        [
            InlineKeyboardButton("🏷 تیم و رنگ من", callback_data="menu_team_setup"),
            InlineKeyboardButton("🌱 آکادمی", callback_data="menu_academy"),
        ],
        [
            InlineKeyboardButton("🎁 پک‌ها", callback_data="menu_packs"),
            InlineKeyboardButton("🧩 ترکیب و تاکتیک", callback_data="menu_lineup_tactics"),
        ],
        [
            InlineKeyboardButton("🏟 ورزشگاه من", callback_data="menu_stadium"),
        ],
        [
            InlineKeyboardButton("🤝 اسپانسر تیم", callback_data="menu_sponsor"),
            InlineKeyboardButton("⚽ بازی دوستانه", callback_data="menu_friendly"),
        ],
        [InlineKeyboardButton("⚔️ وضعیت بازی‌ها", callback_data="menu_battle")],
        [
            InlineKeyboardButton("💰 بودجه من", callback_data="menu_budget"),
            InlineKeyboardButton("📊 آمار من", callback_data="menu_mystats"),
        ],
        [InlineKeyboardButton("🏅 جدول لیگ", callback_data="menu_league")],
        [
            InlineKeyboardButton("📰 اخبار", callback_data="menu_news"),
            InlineKeyboardButton("📢 بیانیه", callback_data="menu_statement"),
        ],
    ]
    if is_admin(user_id):
        rows.append([InlineKeyboardButton("🛠 پنل ادمین", callback_data="menu_admin")])
    return InlineKeyboardMarkup(rows)


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    bot_on = is_bot_enabled()
    toggle_label = "🔴 خاموش کردن ربات" if bot_on else "🟢 روشن کردن ربات"
    rows = [
        [InlineKeyboardButton(toggle_label, callback_data="admin_toggle_bot")],
        [InlineKeyboardButton("🎮 شروع بازی‌های امروز", callback_data="admin_matchday")],
        [
            InlineKeyboardButton("🚀 شروع فصل خودکار (هر ۵ ساعت)", callback_data="admin_start_auto_season"),
        ],
        [
            InlineKeyboardButton("⏹ توقف فصل خودکار", callback_data="admin_stop_auto_season"),
        ],
        [
            InlineKeyboardButton("💵 افزودن بودجه", callback_data="admin_give_budget"),
            InlineKeyboardButton("🎟 افزودن فوت توکن", callback_data="admin_give_tokens"),
        ],
        [InlineKeyboardButton("📰 تنظیم خبر", callback_data="admin_set_news")],
        [
            InlineKeyboardButton("⚽ افزودن بازیکن", callback_data="admin_add_player"),
            InlineKeyboardButton("🗑 حذف بازیکن", callback_data="admin_remove_player"),
        ],
        [
            InlineKeyboardButton("✅ ثبت امتیاز بازیکن", callback_data="admin_set_points"),
            InlineKeyboardButton("⚡ تنظیم قدرت بازیکن", callback_data="admin_set_power"),
        ],
        [InlineKeyboardButton("♻️ ریست جدول لیگ", callback_data="admin_reset_league")],
        [InlineKeyboardButton("✏️ ویرایش تیم یک کاربر", callback_data="admin_edit_team")],
        [
            InlineKeyboardButton("🗑 خالی کردن تیم یک کاربر", callback_data="admin_clear_team"),
            InlineKeyboardButton("💥 خالی کردن همه‌ی تیم‌ها", callback_data="admin_clear_all_teams"),
        ],
        [InlineKeyboardButton("🗑 حذف همه‌ی بازیکنان از فروشگاه", callback_data="admin_remove_all_players")],
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="admin_back")],
    ]
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id, user.username or user.first_name)
    text = (
        f"سلام {user.first_name}! 👋\n\n"
        "به بازی فانتزی فوتبال خوش اومدی ⚽️\n\n"
        f"با بودجه اولیه‌ات یک تیم بین {MIN_TEAM_SIZE} تا {MAX_TEAM_SIZE} نفره بساز.\n\n"
        "از دکمه‌های زیر استفاده کن 👇"
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard(user.id))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """برای اینکه بفهمی آیدی عددیت چیه و بذاریش توی ADMIN_IDS"""
    user = update.effective_user
    await update.message.reply_text(f"آیدی عددی تو: {user.id}")


def render_budget(user_id: int) -> str:
    b = get_user_budget(user_id)
    tokens = get_user_foot_tokens(user_id)
    return f"💰 بودجه باقی‌مانده تو: {b:.1f} میلیون تومان\n🎟 فوت توکن: {tokens}"


async def budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(render_budget(user_id))


def render_players_messages(user_id: int):
    players = get_all_players()
    if not players:
        return [("هنوز بازیکنی در سیستم ثبت نشده.", None)]

    grouped = {}
    for p in players:
        grouped.setdefault(p["position"], []).append(p)

    messages = []
    for pos, plist in grouped.items():
        lines = [f"⚽️ {POSITION_FA.get(pos, pos)}:"]
        buttons = []
        for p in plist:
            owned = "✅" if is_player_in_team(user_id, p["player_id"]) else ""
            lines.append(f"#{p['player_id']} | {p['name']} ({p['team']}) - قیمت: {p['price']} م.ت | قدرت: {p['power']:.0f} {owned}")
            if not owned:
                buttons.append([
                    InlineKeyboardButton(
                        f"خرید {p['name']} ({p['price']}م)",
                        callback_data=f"buy_{p['player_id']}",
                    )
                ])
        keyboard = InlineKeyboardMarkup(buttons) if buttons else None
        messages.append(("\n".join(lines), keyboard))
    return messages


async def players_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    for text, keyboard in render_players_messages(user_id):
        await update.message.reply_text(text, reply_markup=keyboard)


async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    player_id = int(query.data.split("_")[1])

    player = get_player(player_id)
    if not player:
        await query.message.reply_text("این بازیکن پیدا نشد.")
        return

    if is_player_in_team(user_id, player_id):
        await query.message.reply_text("این بازیکن از قبل توی تیم توئه.")
        return

    team_size = get_user_team_size(user_id)
    if team_size >= MAX_TEAM_SIZE:
        await query.message.reply_text(f"تیم تو پره! حداکثر {MAX_TEAM_SIZE} بازیکن.")
        return

    b = get_user_budget(user_id)
    if b < player["price"]:
        await query.message.reply_text(
            f"بودجه کافی نداری! قیمت بازیکن: {player['price']} م.ت، بودجه تو: {b:.1f} م.ت"
        )
        return

    add_player_to_team(user_id, player_id)
    update_user_budget(user_id, b - player["price"])
    await query.message.reply_text(
        f"✅ {player['name']} به تیمت اضافه شد!\nبودجه باقی‌مانده: {b - player['price']:.1f} م.ت"
    )


def render_myteam(user_id: int):
    team = get_user_team(user_id)
    if not team:
        return None

    row = get_user_row(user_id)
    tactic = TACTICS[get_user_tactic(user_id)]
    formation = row["formation"] if row["formation"] in FORMATIONS else "انتخاب نشده"
    lineup_ids = {p["player_id"] for p in get_user_lineup(user_id)}
    lineup_status = "کامل ✅" if is_lineup_complete(user_id) else "چیده‌نشده/ناقص ⚠️"

    lines = [
        f"🏆 تیم من: {team_display_name(row)}",
        f"🧩 آرایش: {formation} ({lineup_status})",
        f"🎯 تاکتیک: {tactic['emoji']} {tactic['label']}",
        f"🏟 ورزشگاه: سطح {row['stadium_level'] or 1} | 👥 هواداران: {row['fans'] or 0}\n",
    ]
    total_points = 0
    total_power = 0
    buttons = []
    for p in team:
        injured = p["injury_matches_left"] and p["injury_matches_left"] > 0
        status_icon = "🚑" if injured else ("🟢" if p["player_id"] in lineup_ids else "")
        injury_note = f" (مصدوم، {p['injury_matches_left']} بازی مونده)" if injured else ""
        lines.append(
            f"{status_icon} #{p['player_id']} | {POSITION_FA.get(p['position'], p['position'])} | {p['name']} ({p['team']}) "
            f"- قدرت: {p['power']:.0f} | امتیاز فصل: {p['season_points']:.1f}{injury_note}"
        )
        total_points += p["season_points"]
        total_power += p["power"]
        buttons.append([
            InlineKeyboardButton(f"⬆️ ارتقا {p['name']}", callback_data=f"upgrade_{p['player_id']}"),
            InlineKeyboardButton(f"❌ فروش {p['name']}", callback_data=f"sell_{p['player_id']}"),
        ])

    lines.append(f"\n⚡️ مجموع قدرت تیم: {total_power:.0f}")
    lines.append(f"🏅 مجموع امتیاز فصل بازیکنان: {total_points:.1f}")
    lines.append("\n(🟢 = توی ترکیب اصلی، 🚑 = مصدوم)")
    return "\n".join(lines), InlineKeyboardMarkup(buttons)


async def my_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    result = render_myteam(user_id)
    if result is None:
        await update.message.reply_text("هنوز تیمی نساختی! با /players یا دکمه «لیست بازیکنان» انتخاب کن.")
        return
    text, keyboard = result
    await update.message.reply_text(text, reply_markup=keyboard)


async def sell_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    player_id = int(query.data.split("_")[1])

    player = get_player(player_id)
    if not player or not is_player_in_team(user_id, player_id):
        await query.message.reply_text("این بازیکن توی تیم تو نیست.")
        return

    remove_player_from_team(user_id, player_id)
    b = get_user_budget(user_id)
    update_user_budget(user_id, b + player["price"])
    await query.message.reply_text(
        f"🔻 {player['name']} از تیمت فروخته شد.\nبودجه باقی‌مانده: {b + player['price']:.1f} م.ت"
    )


def get_user_foot_tokens(user_id: int) -> int:
    row = get_user_row(user_id)
    return row["foot_tokens"] if row and row["foot_tokens"] is not None else 0


def set_user_foot_tokens(user_id: int, amount: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET foot_tokens = ? WHERE user_id = ?", (amount, user_id))


def ensure_pack_player(name: str, team: str, position: str, price: float, power: float) -> int:
    """اگه این بازیکن (با همین اسم و تیم) از قبل توی فروشگاه باشه همون آیدی رو برمی‌گردونه،
    وگرنه تازه می‌سازتش — اینجوری چند تا پک می‌تونن یه بازیکن مشترک (مثلاً نیمار) داشته باشن"""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT player_id FROM players WHERE name = ? AND team = ?", (name, team))
        row = c.fetchone()
        if row:
            return row["player_id"]
    return add_player(name, team, position, price, power)


def packs_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for key, pack in PACKS.items():
        rows.append([InlineKeyboardButton(f"{pack['label']} — {pack['cost']} 🎟", callback_data=f"buypack_{key}")])
    return InlineKeyboardMarkup(rows)


def render_packs_text(user_id: int) -> str:
    tokens = get_user_foot_tokens(user_id)
    lines = [f"🎟 فوت توکن تو: {tokens}\n"]
    for pack in PACKS.values():
        if pack["players"] == "ALL":
            content = "تمام بازیکنان فروشگاه"
        else:
            content = "، ".join(p[0] for p in pack["players"])
        bonus = pack.get("bonus_budget", 0)
        bonus_text = f" + {bonus} میلیون تومان" if bonus else ""
        lines.append(f"{pack['label']} ({pack['cost']} 🎟): {content}{bonus_text}")
    return "\n".join(lines)


def redeem_pack(user_id: int, pack_key: str) -> str:
    pack = PACKS.get(pack_key)
    if not pack:
        return "این پک پیدا نشد."

    tokens = get_user_foot_tokens(user_id)
    if tokens < pack["cost"]:
        return f"🎟 فوت توکن کافی نداری! هزینه‌ی این پک: {pack['cost']}، موجودی تو: {tokens}"

    if pack["players"] == "ALL":
        player_ids = [p["player_id"] for p in get_all_players()]
    else:
        player_ids = [
            ensure_pack_player(name, team, pos, price, power)
            for name, team, pos, price, power in pack["players"]
        ]

    added_names = []
    already_owned = 0
    team_full_count = 0
    for pid in player_ids:
        if is_player_in_team(user_id, pid):
            already_owned += 1
            continue
        if get_user_team_size(user_id) >= MAX_TEAM_SIZE:
            team_full_count += 1
            continue
        add_player_to_team(user_id, pid)
        p = get_player(pid)
        if p:
            added_names.append(p["name"])

    set_user_foot_tokens(user_id, tokens - pack["cost"])
    bonus = pack.get("bonus_budget", 0)
    if bonus:
        update_user_budget(user_id, get_user_budget(user_id) + bonus)

    lines = [f"🎁 {pack['label']} فعال شد!"]
    if added_names:
        lines.append("بازیکن‌های جدید: " + "، ".join(added_names))
    if already_owned:
        lines.append(f"({already_owned} نفرشون از قبل توی تیمت بودن)")
    if team_full_count:
        lines.append(f"⚠️ تیمت پر بود، {team_full_count} بازیکن اضافه نشد.")
    if bonus:
        lines.append(f"💰 {bonus} میلیون تومان هم به بودجه‌ت اضافه شد.")
    lines.append(f"🎟 فوت توکن باقی‌مانده: {tokens - pack['cost']}")
    return "\n".join(lines)


def get_owned_power(user_id: int, player_id: int):
    """قدرت این بازیکن مخصوص همین تیم (نه قدرت مشترک کاتالوگ)"""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT COALESCE(up.owned_power, p.power) as power
            FROM players p
            JOIN user_players up ON up.player_id = p.player_id
            WHERE up.user_id = ? AND up.player_id = ?
        """, (user_id, player_id))
        row = c.fetchone()
        return row["power"] if row else None


async def upgrade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    player_id = int(query.data.split("_")[1])

    player = get_player(player_id)
    if not player or not is_player_in_team(user_id, player_id):
        await query.message.reply_text("این بازیکن توی تیم تو نیست.")
        return

    current_power = get_owned_power(user_id, player_id)
    cost = max(1, round(current_power)) * UPGRADE_COST_PER_POINT
    budget = get_user_budget(user_id)
    if budget < cost:
        await query.message.reply_text(
            f"بودجه کافی نداری! هزینه ارتقا: {cost} م.ت، بودجه تو: {budget:.1f} م.ت"
        )
        return

    new_power = current_power + 1
    with get_conn() as conn:
        conn.execute(
            "UPDATE user_players SET owned_power = ? WHERE user_id = ? AND player_id = ?",
            (new_power, user_id, player_id),
        )
    update_user_budget(user_id, budget - cost)

    await query.message.reply_text(
        f"⬆️ {player['name']} ارتقا پیدا کرد!\n"
        f"قدرت جدید (فقط توی تیم خودت): {new_power:.0f}\n"
        f"هزینه پرداخت‌شده: {cost} م.ت\n"
        f"بودجه باقی‌مانده: {budget - cost:.1f} م.ت"
    )


async def perform_battle(user_id: int, bot):
    """بازی رو شبیه‌سازی می‌کنه؛ برمی‌گردونه: (متن نتیجه برای خودم، آیدی حریف یا None، متن نتیجه برای حریف)"""
    today = get_today_str()
    if get_last_action_date(user_id, "last_battle_date") == today:
        return (
            "⏳ امروز قبلاً بازی کردی! فردا دوباره بیا.",
            None,
            None,
        )

    my_size = get_user_team_size(user_id)
    if my_size < MIN_TEAM_SIZE:
        return (
            f"اول باید حداقل {MIN_TEAM_SIZE} بازیکن توی تیمت داشته باشی.",
            None,
            None,
        )

    missing_text = get_missing_positions_text(user_id)
    if missing_text:
        return (missing_text, None, None)

    opponent = get_random_opponent(user_id, MIN_TEAM_SIZE)
    if not opponent:
        return (
            "فعلاً هیچ حریف آماده‌ای پیدا نشد (کسی که تیمش کامل باشه). بعداً دوباره امتحان کن.",
            None,
            None,
        )

    set_last_action_date(user_id, "last_battle_date", today)

    my_power = get_user_team_power(user_id)
    opp_power = get_user_team_power(opponent["user_id"])
    goals_me, goals_opp = simulate_goals(my_power, opp_power)

    if goals_me == goals_opp:
        record_battle_result(user_id, opponent["user_id"], is_draw=True)
        my_result_line = f"🤝 مساوی شدید! هر دو {DRAW_POINTS} امتیاز گرفتین."
        opp_result_line = f"🤝 مساوی شد! {DRAW_POINTS} امتیاز گرفتی."
    elif goals_me > goals_opp:
        record_battle_result(user_id, opponent["user_id"])
        my_result_line = f"🏆 بردی! {WIN_POINTS} امتیاز به جدولت اضافه شد."
        opp_result_line = "😔 باختی."
    else:
        record_battle_result(opponent["user_id"], user_id)
        my_result_line = "😔 باختی."
        opp_result_line = f"🏆 بردی! {WIN_POINTS} امتیاز به جدولت اضافه شد."

    my_text = (
        "⚔️ نتیجه بازی:\n\n"
        f"تیم تو  {goals_me} - {goals_opp}  تیم {opponent['username']}\n\n"
        f"{my_result_line}"
    )
    opp_text = (
        "⚔️ یکی از حریفا باهات بازی کرد!\n\n"
        f"تیم {opponent['username']}  {goals_opp} - {goals_me}  تیم حریف\n\n"
        f"{opp_result_line}"
    )
    return my_text, opponent["user_id"], opp_text


def render_battle_status(user_id: int) -> str:
    my_size = get_user_team_size(user_id)
    lines = ["⚔️ بازی‌ها دیگه خودسرو نیستن!", "فقط مدیر می‌تونه «روز بازی» رو شروع کنه؛ وقتی این کارو کنه، همه تیم‌های کامل با هم بازی می‌کنن و نتیجه توی کانال اعلام می‌شه.\n"]
    if my_size < MIN_TEAM_SIZE:
        lines.append(f"وضعیت تیم تو: هنوز کامل نیست (حداقل {MIN_TEAM_SIZE} بازیکن لازمه).")
    else:
        missing_text = get_missing_positions_text(user_id)
        if missing_text:
            lines.append("وضعیت تیم تو:\n" + missing_text)
        else:
            lines.append("✅ تیم تو کامله و آماده‌ی بازیه!")
    return "\n".join(lines)


async def battle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دیگه بازی‌ها خودسرو نیستن؛ فقط مدیر می‌تونه روز بازی رو شروع کنه (همه تیم‌ها با هم بازی می‌کنن)"""
    await update.message.reply_text(render_battle_status(update.effective_user.id))


def render_mystats(user) -> str:
    row = get_or_create_user(user.id, user.username or user.first_name)
    power = get_user_team_power(user.id)
    return (
        "📊 آمار تو:\n\n"
        f"💰 بودجه: {row['budget']:.1f} م.ت\n"
        f"⚡️ قدرت تیم: {power:.0f}\n"
        f"🏆 برد: {row['wins']} | 🤝 مساوی: {row['draws']} | 😔 باخت: {row['losses']}\n"
        f"🏅 امتیاز کل: {row['total_points']:.1f}"
    )


async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(render_mystats(update.effective_user))


def render_league() -> str:
    rows = get_leaderboard(10)
    if not rows:
        return "هنوز کسی امتیازی نداره."
    lines = ["🏅 جدول لیگ (بر اساس میانگین امتیاز هر بازی):\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows):
        games = (r["wins"] or 0) + (r["draws"] or 0) + (r["losses"] or 0)
        avg = (r["total_points"] / games) if games > 0 else 0.0
        prefix = medals[i] if i < 3 else f"{i+1}."
        lines.append(
            f"{prefix} {team_display_name(r)} - میانگین {avg:.2f} "
            f"({games} بازی، {r['total_points']:.1f} امتیاز کل)"
        )
    return "\n".join(lines)


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """جدول لیگ / رده‌بندی"""
    await update.message.reply_text(render_league())


def perform_academy(user_id: int) -> str:
    today = get_today_str()
    if get_last_action_date(user_id, "last_academy_date") == today:
        return "⏳ امروز قبلاً از آکادمی بازیکن گرفتی! فردا دوباره بیا."

    team_size = get_user_team_size(user_id)
    if team_size >= MAX_TEAM_SIZE:
        return f"تیم تو پره! حداکثر {MAX_TEAM_SIZE} بازیکن، اول یکیو بفروش."

    set_last_action_date(user_id, "last_academy_date", today)

    first = random.choice(ACADEMY_FIRST_NAMES)
    last = random.choice(ACADEMY_LAST_NAMES)
    name = f"{first} {last}"
    position = random.choice(ACADEMY_POSITIONS)
    price = random.randint(ACADEMY_MIN_PRICE, ACADEMY_MAX_PRICE)

    player_id = add_player(name, "آکادمی", position, price)
    add_player_to_team(user_id, player_id)

    return (
        f"🌱 آکادمی یک بازیکن جدید برات تربیت کرد!\n\n"
        f"نام: {name}\n"
        f"پست: {POSITION_FA.get(position, position)}\n"
        f"ارزش: {price} م.ت\n\n"
        f"این بازیکن رایگان مستقیم به تیمت اضافه شد. با گذشت زمان و بازی کردن می‌تونه امتیازش بالا بره."
    )


async def academy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """گرفتن یک بازیکن جوان و رایگان از آکادمی مستقیم به تیم کاربر"""
    user_id = update.effective_user.id
    await update.message.reply_text(perform_academy(user_id))


def render_news() -> str:
    return f"📰 آخرین خبر:\n\n{get_news()}"


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(render_news())


# ---------- منوی شیشه‌ای (اینلاین) ----------

async def team_setup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتخاب رنگ اول و دوم پیراهن تیم از دکمه‌های شیشه‌ای"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("setcolor1_"):
        color_key = data[len("setcolor1_"):]
        if color_key not in KIT_COLOR_MAP:
            return
        set_user_kit_colors(user_id, color1=color_key)
        await query.message.reply_text(
            f"رنگ اول: {KIT_COLOR_MAP[color_key][1]} {KIT_COLOR_MAP[color_key][0]}\n\n"
            "حالا رنگ دوم پیراهن رو انتخاب کن:",
            reply_markup=kit_color_keyboard("setcolor2", exclude_key=color_key),
        )

    elif data.startswith("setcolor2_"):
        color_key = data[len("setcolor2_"):]
        if color_key not in KIT_COLOR_MAP:
            return
        set_user_kit_colors(user_id, color2=color_key)
        row = get_user_row(user_id)
        await query.message.reply_text(
            f"✅ تیمت آماده شد: {team_display_name(row)}\n\n"
            "این اسم و رنگ‌ها توی نتایج بازی‌ها نشون داده می‌شه."
        )

    elif data.startswith("setsponsor_"):
        sponsor_key = data[len("setsponsor_"):]
        if sponsor_key not in SPONSOR_MAP:
            return
        set_user_sponsor(user_id, sponsor_key)
        label, emoji = SPONSOR_MAP[sponsor_key]
        await query.message.reply_text(
            f"✅ اسپانسر تیمت شد: {emoji} {label}\n\n"
            f"از این به بعد هر بازی که تیمت انجام بده، {SPONSOR_MATCH_BONUS} میلیون تومان بهت واریز می‌شه."
        )


async def edit_team_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه‌های زیرمنوی «ویرایش تیم یک کاربر» توی پنل ادمین (مشاهده/افزودن/حذف بازیکن)"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    target_id = context.user_data.get("edit_team_target")
    if not target_id:
        await query.message.reply_text("اول باید یه کاربر انتخاب کنی. از پنل ادمین «✏️ ویرایش تیم یک کاربر» رو بزن.")
        return

    data = query.data
    target_row = get_user_row(target_id)
    if not target_row:
        await query.message.reply_text("این کاربر دیگه پیدا نشد.")
        return

    if data == "editteam_view":
        team = get_user_team(target_id)
        if not team:
            await query.message.reply_text(f"تیم «{team_display_name(target_row)}» فعلاً خالیه.")
            return
        lines = [f"👥 تیم «{team_display_name(target_row)}»:\n"]
        for p in team:
            lines.append(
                f"#{p['player_id']} | {POSITION_FA.get(p['position'], p['position'])} | "
                f"{p['name']} ({p['team']}) - قدرت: {p['power']:.0f}"
            )
        await query.message.reply_text("\n".join(lines))

    elif data == "editteam_add":
        context.user_data["awaiting"] = "admin_edit_team_add_player"
        await query.message.reply_text(
            f"آیدی بازیکنی که می‌خوای به تیم «{team_display_name(target_row)}» اضافه کنی رو بفرست:"
        )

    elif data == "editteam_remove":
        team = get_user_team(target_id)
        if not team:
            await query.message.reply_text(f"تیم «{team_display_name(target_row)}» خالیه، بازیکنی برای حذف نیست.")
            return
        await query.message.reply_text(
            f"کدوم بازیکن از تیم «{team_display_name(target_row)}» حذف بشه؟",
            reply_markup=team_remove_keyboard(target_id),
        )

    elif data.startswith("editteam_rm_"):
        player_id = int(data[len("editteam_rm_"):])
        player = get_player(player_id)
        remove_player_from_team(target_id, player_id)
        name = player["name"] if player else f"#{player_id}"
        await query.message.reply_text(f"➖ «{name}» از تیم «{team_display_name(target_row)}» حذف شد.")
        team = get_user_team(target_id)
        if team:
            await query.message.reply_text("بازیکن دیگه‌ای هم می‌خوای حذف کنی؟", reply_markup=team_remove_keyboard(target_id))


async def manual_pairing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """جفت کردن دستی بازی‌ها توسط ادمین: خودش دو به دو تیم‌ها رو انتخاب می‌کنه و بازی برگزار می‌شه"""
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    data = query.data

    if data == "manual_cancel":
        context.user_data["manual_pair_a"] = None
        context.user_data["manual_matches"] = []
        await query.message.reply_text("لغو شد.", reply_markup=admin_menu_keyboard())
        return

    if data == "manual_finish":
        matches = context.user_data.get("manual_matches") or []
        context.user_data["manual_pair_a"] = None
        context.user_data["manual_matches"] = []
        if not matches:
            await query.message.reply_text("هنوز هیچ بازی‌ای ثبت نشده بود.", reply_markup=admin_menu_keyboard())
            return
        channel_text = "⚽️ نتایج بازی‌های امروز:\n\n" + "\n".join(matches)
        if CHANNEL_ID:
            try:
                await context.bot.send_message(chat_id=CHANNEL_ID, text=channel_text)
            except Exception as e:
                logger.warning(f"ارسال نتایج به کانال ناموفق بود: {e}")
        summary = f"✅ {len(matches)} بازی برگزار شد."
        if not CHANNEL_ID:
            summary += "\n\n⚠️ آیدی کانال تنظیم نشده، برای همین نتایج فقط به خود بازیکنا پیام خصوصی شد."
        await query.message.reply_text(summary, reply_markup=admin_menu_keyboard())
        return

    if data.startswith("manualpick_"):
        picked_id = int(data[len("manualpick_"):])
        team_a = context.user_data.get("manual_pair_a")

        if team_a is None:
            context.user_data["manual_pair_a"] = picked_id
            row = get_user_row(picked_id)
            await query.message.reply_text(
                f"تیم اول: {team_display_name(row)}\nحالا حریفشو انتخاب کن:",
                reply_markup=manual_teams_keyboard(exclude_id=picked_id),
            )
            return

        if picked_id == team_a:
            await query.message.reply_text("باید دو تیم متفاوت انتخاب کنی.")
            return

        line = await play_one_match(context.bot, team_a, picked_id)
        context.user_data.setdefault("manual_matches", []).append(line)
        context.user_data["manual_pair_a"] = None

        await query.message.reply_text(
            f"✅ بازی ثبت شد:\n{line}\n\nتیم بعدی رو انتخاب کن یا پایان بده:",
            reply_markup=manual_teams_keyboard(),
        )


async def friendly_match_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتخاب حریف برای بازی دوستانه از طرف یه کاربر عادی"""
    query = update.callback_query
    await query.answer()
    data = query.data
    requester_id = query.from_user.id

    if data == "friendly_cancel":
        await query.message.reply_text("باشه، بی‌خیال بازی دوستانه شدیم.")
        return

    if data.startswith("friendlypick_"):
        opponent_id = int(data[len("friendlypick_"):])
        if opponent_id == requester_id:
            await query.message.reply_text("نمی‌تونی با خودت بازی کنی 😄")
            return
        if get_user_team_size(requester_id) < 1:
            await query.message.reply_text("اول باید حداقل یه بازیکن توی تیمت داشته باشی.")
            return
        text_a = await play_friendly_match(context.bot, requester_id, opponent_id)
        await query.message.reply_text(text_a)


async def buypack_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """خرید یکی از پک‌های بازیکن با فوت توکن"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    pack_key = query.data[len("buypack_"):]
    result = redeem_pack(user_id, pack_key)
    await query.message.reply_text(result)


async def lineup_tactic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """چیدن آرایش/ترکیب اصلی، انتخاب تاکتیک، و ارتقای ورزشگاه"""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "lineup_formations":
        row = get_user_row(user_id)
        current = row["formation"] if row and row["formation"] in FORMATIONS else None
        text = f"آرایش فعلی: {current or 'انتخاب نشده'}\n\nیکی از این آرایش‌ها رو انتخاب کن:"
        await query.message.reply_text(text, reply_markup=formation_keyboard())
        return

    if data.startswith("setformation_"):
        key = data[len("setformation_"):]
        if key not in FORMATIONS:
            return
        set_formation(user_id, key)
        req = dict(FORMATIONS[key])
        req["GK"] = 1
        need_text = "، ".join(f"{POSITION_FA[pos]}: {n}" for pos, n in req.items())
        await query.message.reply_text(
            f"✅ آرایش «{key}» انتخاب شد.\nترکیب لازم: {need_text}\n\n"
            "حالا بازیکن‌های ترکیب اصلی رو انتخاب کن:",
            reply_markup=lineup_pick_keyboard(user_id),
        )
        return

    if data == "lineup_pick":
        row = get_user_row(user_id)
        if not row or row["formation"] not in FORMATIONS:
            await query.message.reply_text("اول باید یه آرایش انتخاب کنی.", reply_markup=formation_keyboard())
            return
        await query.message.reply_text("بازیکن‌های ترکیب اصلی رو انتخاب کن:", reply_markup=lineup_pick_keyboard(user_id))
        return

    if data.startswith("togglelineup_"):
        player_id = int(data[len("togglelineup_"):])
        required = get_lineup_required_counts(user_id)
        if not required:
            await query.message.reply_text("اول باید یه آرایش انتخاب کنی.", reply_markup=formation_keyboard())
            return
        player = get_player(player_id)
        counts = get_lineup_position_counts(user_id)
        lineup_ids = {p["player_id"] for p in get_user_lineup(user_id)}
        if player_id not in lineup_ids and player and counts.get(player["position"], 0) >= required.get(player["position"], 0):
            await query.answer(f"جای {POSITION_FA.get(player['position'], player['position'])} توی این آرایش پره!", show_alert=True)
            return
        toggle_lineup_player(user_id, player_id)
        await query.message.reply_text("ترکیب به‌روزرسانی شد:", reply_markup=lineup_pick_keyboard(user_id))
        return

    if data == "lineup_confirm":
        if is_lineup_complete(user_id):
            await query.message.reply_text("✅ ترکیب اصلی‌ت کامل و ثبت شد! از این به بعد توی بازی‌ها همین ۱۱ نفر حساب می‌شن.")
        else:
            required = get_lineup_required_counts(user_id) or {}
            counts = get_lineup_position_counts(user_id)
            missing = [f"{POSITION_FA[pos]}: {counts.get(pos,0)}/{need}" for pos, need in required.items() if counts.get(pos, 0) != need]
            await query.message.reply_text(
                "⚠️ ترکیبت هنوز کامل نیست:\n" + "\n".join(missing),
                reply_markup=lineup_pick_keyboard(user_id),
            )
        return

    if data == "tactic_pick":
        current = TACTICS[get_user_tactic(user_id)]
        await query.message.reply_text(
            f"تاکتیک فعلی: {current['emoji']} {current['label']}\n\n"
            "⚖️ استاندارد: نه ضعف نه قوت خاصی، متعادل\n"
            "🔄 تیکی‌تاکا: هم حمله هم دفاع بهتر می‌شه (نیاز به تیم قوی)\n"
            "🔥 پرس سنگین: حمله خیلی قوی، ولی دفاع ضعیف می‌شه\n"
            "🚌 اتوبوسی: دفاع خیلی قوی، ولی حمله خیلی ضعیف می‌شه\n"
            "⚡ ضدحمله: دفاع خوب، حمله معمولی ولی کارآمد\n"
            "↔️ بازی از جناحین: حمله قوی، دفاع کمی ضعیف‌تر\n\n"
            "کدومو می‌خوای؟",
            reply_markup=tactic_keyboard(),
        )
        return

    if data.startswith("settactic_"):
        key = data[len("settactic_"):]
        if key not in TACTICS:
            return
        set_user_tactic(user_id, key)
        t = TACTICS[key]
        await query.message.reply_text(f"✅ تاکتیک تیمت شد: {t['emoji']} {t['label']}")
        return

    if data == "stadium_upgrade":
        result = upgrade_stadium(user_id)
        await query.message.reply_text(result)
        return


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_id = user.id
    action = query.data

    if action == "menu_players":
        for text, keyboard in render_players_messages(user_id):
            await query.message.reply_text(text, reply_markup=keyboard)

    elif action == "menu_myteam":
        result = render_myteam(user_id)
        if result is None:
            await query.message.reply_text("هنوز تیمی نساختی! از «📋 لیست بازیکنان» انتخاب کن.")
        else:
            text, keyboard = result
            await query.message.reply_text(text, reply_markup=keyboard)

    elif action == "menu_battle":
        await query.message.reply_text(render_battle_status(user_id))

    elif action == "menu_team_setup":
        context.user_data["team_setup_stage"] = "name"
        await query.message.reply_text(
            "اسم تیمت رو بفرست (مثلاً «شاهین‌های سرخ»). این اسم توی نتایج بازی‌ها نشون داده می‌شه:"
        )

    elif action == "menu_statement":
        today = get_today_str()
        if get_last_action_date(user_id, "last_statement_date") == today:
            await query.message.reply_text("⏳ امروز قبلاً یه بیانیه دادی! فردا دوباره بیا.")
        elif not CHANNEL_ID:
            await query.message.reply_text("⚠️ آیدی کانال هنوز تنظیم نشده، برای همین بیانیه‌ها جایی پست نمی‌شن.")
        else:
            context.user_data["awaiting_statement"] = True
            await query.message.reply_text(
                "متن بیانیه‌ت رو بفرست؛ با اسم تیمت توی کانال پست می‌شه (هر تیم روزی فقط یه بیانیه):"
            )

    elif action == "menu_sponsor":
        row = get_user_row(user_id)
        current = row["sponsor"] if row and "sponsor" in row.keys() else None
        current_text = ""
        if current and current in SPONSOR_MAP:
            label, emoji = SPONSOR_MAP[current]
            current_text = f"اسپانسر فعلیت: {emoji} {label}\n\n"
        await query.message.reply_text(
            f"{current_text}یه اسپانسر برای باشگاهت انتخاب کن. اسپانسر هر بار که تیمت توی لیگ بازی کنه، "
            f"{SPONSOR_MATCH_BONUS} میلیون تومان به حسابت واریز می‌کنه (بازی‌های دوستانه شامل این پاداش نمی‌شن):",
            reply_markup=sponsor_keyboard(),
        )

    elif action == "menu_packs":
        await query.message.reply_text(render_packs_text(user_id), reply_markup=packs_keyboard())

    elif action == "menu_lineup_tactics":
        row = get_user_row(user_id)
        formation = row["formation"] if row and row["formation"] in FORMATIONS else None
        tactic_key = get_user_tactic(user_id)
        tactic = TACTICS[tactic_key]
        lineup_status = "کامل ✅" if is_lineup_complete(user_id) else "ناقص یا چیده‌نشده ⚠️"
        text = (
            f"آرایش فعلی: {formation or 'انتخاب نشده'}\n"
            f"ترکیب اصلی: {lineup_status}\n"
            f"تاکتیک فعلی: {tactic['emoji']} {tactic['label']}\n\n"
            "چیکار می‌خوای بکنی؟"
        )
        await query.message.reply_text(text, reply_markup=lineup_tactics_menu_keyboard())

    elif action == "menu_stadium":
        row = get_user_row(user_id)
        level = row["stadium_level"] or 1
        fans = row["fans"] or 0
        cost = get_stadium_upgrade_cost(level)
        upgrade_text = (
            f"هزینه‌ی ارتقا به سطح {level+1}: {cost} م.ت" if level < STADIUM_MAX_LEVEL
            else "ورزشگاهت به حداکثر سطح رسیده! 🏆"
        )
        kb_rows = []
        if level < STADIUM_MAX_LEVEL:
            kb_rows.append([InlineKeyboardButton("⬆️ ارتقای ورزشگاه", callback_data="stadium_upgrade")])
        await query.message.reply_text(
            f"🏟 ورزشگاه «{team_display_name(row)}»\n\n"
            f"سطح فعلی: {level} از {STADIUM_MAX_LEVEL}\n"
            f"👥 هواداران: {fans}\n"
            f"{upgrade_text}\n\n"
            "هرچی سطح ورزشگاه و تعداد هوادارات بیشتر باشه، بعد از هر بازی رسمی درآمد بلیت بیشتری می‌گیری.",
            reply_markup=InlineKeyboardMarkup(kb_rows) if kb_rows else None,
        )

    elif action == "menu_friendly":
        if get_user_team_size(user_id) < 1:
            await query.message.reply_text("اول باید حداقل یه بازیکن توی تیمت داشته باشی.")
        else:
            opponents = get_friendly_opponents(user_id)
            if not opponents:
                await query.message.reply_text("فعلاً هیچ تیم دیگه‌ای برای بازی دوستانه نیست.")
            else:
                await query.message.reply_text(
                    "حریفت رو برای یه بازی دوستانه انتخاب کن (این بازی روی جدول لیگ تاثیری نداره):",
                    reply_markup=friendly_opponents_keyboard(user_id),
                )

    elif action == "menu_academy":
        await query.message.reply_text(perform_academy(user_id))

    elif action == "menu_budget":
        await query.message.reply_text(render_budget(user_id))

    elif action == "menu_mystats":
        await query.message.reply_text(render_mystats(user))

    elif action == "menu_league":
        await query.message.reply_text(render_league())

    elif action == "menu_news":
        await query.message.reply_text(render_news())

    elif action == "menu_admin":
        if not is_admin(user_id):
            await query.message.reply_text("این بخش فقط برای ادمین‌هاست.")
            return
        await query.message.reply_text("🛠 پنل ادمین:", reply_markup=admin_menu_keyboard())


async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.message.reply_text("این دستور فقط برای ادمین‌هاست.")
        return

    action = query.data

    if action == "admin_back":
        await query.message.reply_text("منوی اصلی:", reply_markup=main_menu_keyboard(user_id))
        return

    if action == "admin_toggle_bot":
        new_state = not is_bot_enabled()
        set_bot_enabled(new_state)
        status_text = "🟢 ربات روشن شد و کاربرا می‌تونن ازش استفاده کنن." if new_state else "🔴 ربات خاموش شد؛ فقط ادمین‌ها می‌تونن باهاش کار کنن."
        await query.message.reply_text(status_text, reply_markup=admin_menu_keyboard())
        return

    if action == "admin_matchday":
        choice_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ خودکار (لیگ کامل، همه با همه)", callback_data="admin_matchday_auto")],
            [InlineKeyboardButton("🎯 دستی (خودم جفت می‌کنم)", callback_data="admin_matchday_manual")],
            [InlineKeyboardButton("❌ انصراف", callback_data="admin_back")],
        ])
        await query.message.reply_text("چطور می‌خوای بازی‌های امروز رو شروع کنی؟", reply_markup=choice_kb)
        return

    if action == "admin_matchday_auto":
        eligible = get_all_matchday_eligible_users()
        n = len(eligible)
        max_possible = n * (n - 1) // 2 if n >= 2 else 0
        new_matches = 0
        for i in range(n):
            for j in range(i + 1, n):
                if not has_played_fixture(eligible[i], eligible[j]):
                    new_matches += 1
        confirm_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ بله، بازی‌ها رو شروع کن", callback_data="admin_matchday_confirm")],
            [InlineKeyboardButton("❌ انصراف", callback_data="admin_back")],
        ])
        already_played_note = ""
        if max_possible - new_matches > 0:
            already_played_note = f"\n({max_possible - new_matches} جفت رفت‌وبرگشتشون قبلاً کامل شده و دوباره تکرار نمی‌شن.)"
        team_list_text = ""
        if eligible:
            names = [team_display_name(get_user_row(uid)) for uid in eligible]
            team_list_text = "\n\nتیم‌های شرکت‌کننده:\n" + "\n".join(f"• {nm}" for nm in names)
        await query.message.reply_text(
            f"⚠️ الان {n} تیم آماده‌ی بازی هستن (ترکیبشون کامله).\n"
            f"با تایید، {new_matches} بازی جدید (رفت یا برگشت، هرکدوم هنوز کامل نشده) برگزار می‌شه؛ "
            "نتیجه‌ها هم توی کانال اعلام می‌شه."
            f"{already_played_note}"
            f"{team_list_text}\n\n"
            "مطمئنی؟",
            reply_markup=confirm_kb,
        )
        return

    if action == "admin_matchday_confirm":
        summary = await run_matchday(context.bot)
        await query.message.reply_text(summary)
        return

    if action == "admin_start_auto_season":
        existing = context.job_queue.get_jobs_by_name("auto_matchday_job") if context.job_queue else []
        if existing:
            await query.message.reply_text("🚀 فصل خودکار از قبل در حال اجراست (هر ۵ ساعت یه دور بازی می‌شه).")
        elif not context.job_queue:
            await query.message.reply_text(
                "⚠️ زمان‌بند (JobQueue) روی این سرور فعال نیست. باید کتابخونه‌ی "
                "python-telegram-bot[job-queue] نصب باشه."
            )
        else:
            context.job_queue.run_repeating(
                auto_matchday_job, interval=5 * 3600, first=10, name="auto_matchday_job"
            )
            await query.message.reply_text(
                "🚀 فصل خودکار شروع شد!\n"
                "هر ۵ ساعت یه دور بازی خودش برگزار می‌شه (هر جفت تیم رفت و برگشت بازی می‌کنه)، "
                "و وقتی همه‌ی تیم‌های آماده رفت‌وبرگشتشون تموم بشه، خودش متوقف می‌شه و "
                "جدول نهایی و قهرمان فصل رو توی کانال اعلام می‌کنه."
            )
        return

    if action == "admin_stop_auto_season":
        existing = context.job_queue.get_jobs_by_name("auto_matchday_job") if context.job_queue else []
        for job in existing:
            job.schedule_removal()
        await query.message.reply_text("⏹ فصل خودکار متوقف شد." if existing else "فصل خودکاری در حال اجرا نبود.")
        return

    if action == "admin_matchday_manual":
        context.user_data["manual_pair_a"] = None
        context.user_data["manual_matches"] = []
        teams = get_all_teams_for_manual()
        if not teams:
            await query.message.reply_text("هیچ کاربری هنوز حتی یه بازیکن هم نداره.")
            return
        await query.message.reply_text(
            f"🎯 {len(teams)} تیم هست (مهم نیست کامل باشن یا نه). اول تیم شماره‌ی یک رو انتخاب کن:",
            reply_markup=manual_teams_keyboard(),
        )
        return

    if action == "admin_reset_league":
        confirm_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ بله، ریست کن", callback_data="admin_reset_confirm")],
            [InlineKeyboardButton("❌ انصراف", callback_data="admin_back")],
        ])
        await query.message.reply_text(
            "⚠️ مطمئنی؟ این کار امتیاز و رکورد همه کاربرا رو صفر می‌کنه.",
            reply_markup=confirm_kb,
        )
        return

    if action == "admin_reset_confirm":
        reset_league()
        await query.message.reply_text("♻️ جدول لیگ ریست شد. امتیاز و رکورد همه کاربرا صفر شد.")
        return

    if action == "admin_remove_all_players":
        confirm_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ بله، همه رو حذف کن", callback_data="admin_remove_all_players_confirm")],
            [InlineKeyboardButton("❌ انصراف", callback_data="admin_back")],
        ])
        await query.message.reply_text(
            "⚠️ این کار همه‌ی بازیکن‌ها رو کاملاً از بازی حذف می‌کنه — هم از فروشگاه، هم از تیم همه‌ی کاربرا. "
            "غیرقابل بازگشته!\n\nمطمئنی؟",
            reply_markup=confirm_kb,
        )
        return

    if action == "admin_remove_all_players_confirm":
        remove_all_players()
        await query.message.reply_text("💥 همه‌ی بازیکن‌ها حذف شدن. حالا می‌تونی بازیکن‌های جدید اضافه کنی.")
        return

    if action == "admin_clear_all_teams":
        confirm_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ بله، همه‌ی تیم‌ها رو خالی کن", callback_data="admin_clear_all_teams_confirm")],
            [InlineKeyboardButton("❌ انصراف", callback_data="admin_back")],
        ])
        await query.message.reply_text(
            "⚠️ این کار تیم همه‌ی کاربرا رو کاملاً پاک می‌کنه و بودجه‌ی همه به مقدار اولیه برمی‌گرده "
            "(بازیکن‌ها توی فروشگاه می‌مونن، امتیاز و اسم تیم هرکس دست نمی‌خوره).\n\nمطمئنی؟",
            reply_markup=confirm_kb,
        )
        return

    if action == "admin_clear_all_teams_confirm":
        clear_all_teams()
        await query.message.reply_text(
            f"💥 تیم همه‌ی کاربرا کاملاً پاک شد و بودجه‌ی همه به {INITIAL_BUDGET} م.ت برگشت. "
            "هرکس می‌تونه از نو تیم بسازه."
        )
        return

    if action == "admin_edit_team":
        context.user_data["awaiting"] = "admin_edit_team_user_id"
        await query.message.reply_text("آیدی عددی کاربری که می‌خوای تیمش رو ویرایش کنی رو بفرست:")
        return

    if action == "admin_edit_team_menu":
        target_id = context.user_data.get("edit_team_target")
        if not target_id:
            await query.message.reply_text("اول باید یه کاربر انتخاب کنی. از پنل ادمین «✏️ ویرایش تیم یک کاربر» رو بزن.")
            return
        row = get_user_row(target_id)
        await query.message.reply_text(
            f"در حال ویرایش تیم: {team_display_name(row)}\nچیکار می‌خوای بکنی؟",
            reply_markup=edit_team_menu_keyboard(),
        )
        return

    if action == "admin_back_to_panel":
        await query.message.reply_text("🛠 پنل ادمین:", reply_markup=admin_menu_keyboard())
        return

    prompts = {
        "admin_give_budget": "آیدی عددی کاربر و مقدار رو با یه فاصله بفرست.\nمثال: 123456789 50",
        "admin_give_tokens": "آیدی عددی کاربر و مقدار فوت توکن رو با یه فاصله بفرست.\nمثال: 123456789 50",
        "admin_set_news": "متن خبر جدید رو بفرست:",
        "admin_add_player": (
            "اطلاعات بازیکن رو به این شکل بفرست:\n"
            "نام|تیم|پست(GK/DF/MF/FW)|قیمت|قدرت(اختیاری)\n\n"
            "مثال:\nرونالدو|النصر|FW|14\nیا با قدرت دلخواه:\nرونالدو|النصر|FW|14|16"
        ),
        "admin_remove_player": "آیدی بازیکنی که می‌خوای حذف بشه رو بفرست:",
        "admin_set_points": "آیدی بازیکن و امتیاز رو با یه فاصله بفرست.\nمثال: 12 5",
        "admin_set_power": "آیدی بازیکن و قدرت جدید رو با یه فاصله بفرست.\nمثال: 12 15",
        "admin_clear_team": "آیدی عددی کاربری که می‌خوای تیمش خالی بشه رو بفرست:",
    }

    if action in prompts:
        context.user_data["awaiting"] = action
        await query.message.reply_text(prompts[action])


async def admin_text_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وقتی کاربر (عادی یا ادمین) از پنل شیشه‌ای یه گزینه رو زده و منتظر ورودی متنیشیم"""
    user_id = update.effective_user.id

    # ---- تنظیم اسم تیم (برای همه کاربرا، نه فقط ادمین) ----
    if context.user_data.get("team_setup_stage") == "name":
        context.user_data["team_setup_stage"] = None
        team_name = update.message.text.strip()[:40]
        if not team_name:
            await update.message.reply_text("اسم تیم نمی‌تونه خالی باشه. دوباره امتحان کن.")
            return
        set_user_team_name(user_id, team_name)
        await update.message.reply_text(
            f"✅ اسم تیمت شد: «{team_name}»\n\nحالا رنگ اول پیراهن تیمت رو انتخاب کن:",
            reply_markup=kit_color_keyboard("setcolor1"),
        )
        return

    # ---- بیانیه (برای همه کاربرا، نه فقط ادمین) ----
    if context.user_data.get("awaiting_statement"):
        context.user_data["awaiting_statement"] = False
        statement_text = update.message.text.strip()[:1000]
        if not statement_text:
            await update.message.reply_text("متن بیانیه نمی‌تونه خالی باشه.")
            return
        today = get_today_str()
        if get_last_action_date(user_id, "last_statement_date") == today:
            await update.message.reply_text("⏳ امروز قبلاً یه بیانیه دادی! فردا دوباره بیا.")
            return
        row = get_user_row(user_id)
        channel_text = f"📢 بیانیه رسمی از طرف {team_display_name(row)}:\n\n{statement_text}"
        if CHANNEL_ID:
            try:
                await context.bot.send_message(chat_id=CHANNEL_ID, text=channel_text)
                set_last_action_date(user_id, "last_statement_date", today)
                await update.message.reply_text("✅ بیانیه‌ت توی کانال پست شد.")
            except Exception as e:
                logger.warning(f"ارسال بیانیه به کانال ناموفق بود: {e}")
                await update.message.reply_text("⚠️ ارسال بیانیه به کانال ناموفق بود؛ مطمئن شو ربات ادمین کانال باشه.")
        else:
            await update.message.reply_text("⚠️ آیدی کانال تنظیم نشده، برای همین بیانیه‌ای پست نشد.")
        return

    awaiting = context.user_data.get("awaiting")
    if not awaiting:
        return
    if not is_admin(update.effective_user.id):
        return

    context.user_data["awaiting"] = None
    text = update.message.text.strip()

    if awaiting == "admin_give_budget":
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("فرمت درست نبود. آیدی و مقدار رو با فاصله بفرست: مثلاً 123456789 50")
            return
        try:
            target_id = int(parts[0])
            amount = float(parts[1])
        except ValueError:
            await update.message.reply_text("آیدی و مقدار باید عدد باشن.")
            return
        with get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM users WHERE user_id = ?", (target_id,))
            if c.fetchone() is None:
                await update.message.reply_text("این آیدی هنوز ربات رو استارت نکرده.")
                return
        current = get_user_budget(target_id)
        update_user_budget(target_id, current + amount)
        await update.message.reply_text(
            f"✅ به کاربر {target_id} مقدار {amount} م.ت اضافه شد.\nبودجه جدید: {current + amount:.1f} م.ت"
        )

    elif awaiting == "admin_give_tokens":
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("فرمت درست نبود. آیدی و مقدار رو با فاصله بفرست: مثلاً 123456789 50")
            return
        try:
            target_id = int(parts[0])
            amount = int(parts[1])
        except ValueError:
            await update.message.reply_text("آیدی و مقدار باید عدد باشن.")
            return
        with get_conn() as conn:
            c = conn.cursor()
            c.execute("SELECT 1 FROM users WHERE user_id = ?", (target_id,))
            if c.fetchone() is None:
                await update.message.reply_text("این آیدی هنوز ربات رو استارت نکرده.")
                return
        current_tokens = get_user_foot_tokens(target_id)
        set_user_foot_tokens(target_id, current_tokens + amount)
        await update.message.reply_text(
            f"✅ به کاربر {target_id} مقدار {amount} 🎟 فوت توکن اضافه شد.\nموجودی جدید: {current_tokens + amount}"
        )

    elif awaiting == "admin_set_news":
        set_news(text)
        await update.message.reply_text("✅ خبر جدید ثبت شد.")
        if CHANNEL_ID:
            try:
                await context.bot.send_message(chat_id=CHANNEL_ID, text=f"📰 خبر جدید:\n\n{text}")
            except Exception as e:
                logger.warning(f"ارسال خبر به کانال ناموفق بود: {e}")
                await update.message.reply_text("⚠️ خبر ثبت شد ولی ارسالش به کانال ناموفق بود؛ مطمئن شو ربات ادمین کانال باشه.")

    elif awaiting == "admin_add_player":
        parts = [p.strip() for p in text.split("|")]
        if len(parts) not in (4, 5):
            await update.message.reply_text(
                "فرمت درست نبود.\nنام|تیم|پست(GK/DF/MF/FW)|قیمت|قدرت(اختیاری)"
            )
            return
        if len(parts) == 5:
            name, team, position, price_str, power_str = parts
        else:
            name, team, position, price_str = parts
            power_str = None
        if position not in ("GK", "DF", "MF", "FW"):
            await update.message.reply_text("پست باید یکی از این‌ها باشه: GK, DF, MF, FW")
            return
        try:
            price = float(price_str)
            power = float(power_str) if power_str is not None else None
        except ValueError:
            await update.message.reply_text("قیمت و قدرت باید عدد باشن.")
            return
        player_id = add_player(name, team, position, price, power)
        await update.message.reply_text(f"✅ بازیکن «{name}» با آیدی {player_id} اضافه شد.")

    elif awaiting == "admin_remove_player":
        player_id = parse_id(text)
        if player_id is None:
            await update.message.reply_text("آیدی بازیکن باید عدد باشه.")
            return
        player = get_player(player_id)
        if not player:
            await update.message.reply_text(
                f"بازیکنی با آیدی {player_id} پیدا نشد. از «📋 لیست بازیکنان» آیدی درست رو چک کن."
            )
            return
        delete_player(player_id)
        await update.message.reply_text(f"🗑 بازیکن «{player['name']}» حذف شد.")

    elif awaiting == "admin_clear_team":
        target_user_id = parse_id(text)
        if target_user_id is None:
            await update.message.reply_text("آیدی کاربر باید عدد باشه.")
            return
        target_row = get_user_row(target_user_id)
        if not target_row:
            await update.message.reply_text("کاربری با این آیدی پیدا نشد.")
            return
        clear_user_team(target_user_id)
        await update.message.reply_text(
            f"🗑 تیم «{team_display_name(target_row)}» کاملاً پاک شد و بودجه‌ش به {INITIAL_BUDGET} م.ت برگشت. "
            "الان می‌تونه از فروشگاه یه تیم جدید بسازه."
        )

    elif awaiting == "admin_edit_team_user_id":
        target_user_id = parse_id(text)
        if target_user_id is None:
            await update.message.reply_text("آیدی کاربر باید عدد باشه.")
            return
        target_row = get_user_row(target_user_id)
        if not target_row:
            await update.message.reply_text("کاربری با این آیدی پیدا نشد.")
            return
        context.user_data["edit_team_target"] = target_user_id
        await update.message.reply_text(
            f"در حال ویرایش تیم: {team_display_name(target_row)}\nچیکار می‌خوای بکنی؟",
            reply_markup=edit_team_menu_keyboard(),
        )

    elif awaiting == "admin_edit_team_add_player":
        target_user_id = context.user_data.get("edit_team_target")
        if not target_user_id:
            await update.message.reply_text("اول باید یه کاربر انتخاب کنی.")
            return
        player_id = parse_id(text)
        if player_id is None:
            await update.message.reply_text("آیدی بازیکن باید عدد باشه.")
            return
        player = get_player(player_id)
        if not player:
            await update.message.reply_text(
                f"بازیکنی با آیدی {player_id} پیدا نشد. از «📋 لیست بازیکنان» آیدی درست رو چک کن "
                "(اگه قبلاً بازیکن‌ها رو حذف کرده باشی، آیدی‌ها ممکنه عوض شده باشن)."
            )
            context.user_data["awaiting"] = "admin_edit_team_add_player"
            return
        if is_player_in_team(target_user_id, player_id):
            await update.message.reply_text("این بازیکن از قبل توی تیم این کاربر هست.")
            context.user_data["awaiting"] = "admin_edit_team_add_player"
            return
        if get_user_team_size(target_user_id) >= MAX_TEAM_SIZE:
            await update.message.reply_text(f"تیم این کاربر پره (حداکثر {MAX_TEAM_SIZE} نفر).")
            return
        add_player_to_team(target_user_id, player_id)
        target_row = get_user_row(target_user_id)
        await update.message.reply_text(
            f"✅ «{player['name']}» به تیم «{team_display_name(target_row)}» اضافه شد.\n\n"
            "می‌خوای بازیکن دیگه‌ای هم اضافه کنی؟ آیدیشو بفرست، یا برگرد به منوی ویرایش."
        )
        context.user_data["awaiting"] = "admin_edit_team_add_player"

    elif awaiting == "admin_set_points":
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("فرمت درست نبود. آیدی بازیکن و امتیاز رو با فاصله بفرست: مثلاً 12 5")
            return
        try:
            player_id = int(parts[0])
            points = float(parts[1])
        except ValueError:
            await update.message.reply_text("آیدی بازیکن و امتیاز باید عدد باشن.")
            return
        player = get_player(player_id)
        if not player:
            await update.message.reply_text("بازیکنی با این آیدی پیدا نشد.")
            return
        with get_conn() as conn:
            conn.execute(
                "UPDATE players SET week_points = ?, total_points = total_points + ? WHERE player_id = ?",
                (points, points, player_id),
            )
            c = conn.cursor()
            c.execute("SELECT DISTINCT user_id FROM user_players WHERE player_id = ?", (player_id,))
            owners = c.fetchall()
            for o in owners:
                conn.execute(
                    "UPDATE users SET total_points = total_points + ? WHERE user_id = ?",
                    (points, o["user_id"]),
                )
        await update.message.reply_text(
            f"✅ امتیاز {points} برای «{player['name']}» ثبت شد و به مجموع امتیاز صاحبانش اضافه شد."
        )

    elif awaiting == "admin_set_power":
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("فرمت درست نبود. آیدی بازیکن و قدرت رو با فاصله بفرست: مثلاً 12 15")
            return
        try:
            player_id = int(parts[0])
            power = float(parts[1])
        except ValueError:
            await update.message.reply_text("آیدی بازیکن و قدرت باید عدد باشن.")
            return
        player = get_player(player_id)
        if not player:
            await update.message.reply_text("بازیکنی با این آیدی پیدا نشد.")
            return
        with get_conn() as conn:
            conn.execute("UPDATE players SET power = ? WHERE player_id = ?", (power, player_id))
        await update.message.reply_text(f"✅ قدرت «{player['name']}» روی {power:.0f} تنظیم شد.")


# ---------- دستورات ادمین (متنی، برای کسی که ترجیح میده تایپ کنه) ----------

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای ادمین‌هاست.")
        return
    text = (
        "🛠 پنل ادمین:\n\n"
        "/give_budget <آیدی عددی کاربر> <مقدار> - افزودن بودجه به یک کاربر\n"
        "/set_news <متن> - تنظیم خبر جدید\n"
        "/add_player <نام>|<تیم>|<پست GK/DF/MF/FW>|<قیمت>|<قدرت اختیاری> - افزودن بازیکن جدید\n"
        "/set_points <آیدی بازیکن> <امتیاز> - ثبت امتیاز هفتگی یک بازیکن\n"
        "/set_power <آیدی بازیکن> <قدرت> - تنظیم دستی قدرت یک بازیکن\n"
        "/remove_player <آیدی بازیکن> - حذف کامل یک بازیکن\n"
        "/reset_league - ریست کامل جدول لیگ (صفر کردن امتیاز و رکورد همه)\n"
        "/admin_help - همین راهنما"
    )
    await update.message.reply_text(text)


async def give_budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای ادمین‌هاست.")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("استفاده درست:\n/give_budget <آیدی عددی کاربر> <مقدار>")
        return

    try:
        target_id = int(args[0])
        amount = float(args[1])
    except ValueError:
        await update.message.reply_text("آیدی و مقدار باید عدد باشن.")
        return

    current = get_user_budget(target_id)
    # اگه کاربر قبلاً /start نزده باشه، ردیفش وجود نداره
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM users WHERE user_id = ?", (target_id,))
        if c.fetchone() is None:
            await update.message.reply_text("این آیدی هنوز ربات رو استارت نکرده.")
            return

    update_user_budget(target_id, current + amount)
    await update.message.reply_text(
        f"✅ به کاربر {target_id} مقدار {amount} م.ت اضافه شد.\nبودجه جدید: {current + amount:.1f} م.ت"
    )


async def set_news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای ادمین‌هاست.")
        return

    if not context.args:
        await update.message.reply_text("استفاده درست:\n/set_news متن خبر اینجا")
        return

    text = " ".join(context.args)
    set_news(text)
    await update.message.reply_text("✅ خبر جدید ثبت شد.")
    if CHANNEL_ID:
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=f"📰 خبر جدید:\n\n{text}")
        except Exception as e:
            logger.warning(f"ارسال خبر به کانال ناموفق بود: {e}")
            await update.message.reply_text("⚠️ خبر ثبت شد ولی ارسالش به کانال ناموفق بود؛ مطمئن شو ربات ادمین کانال باشه.")


async def add_player_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای ادمین‌هاست.")
        return

    raw = " ".join(context.args)
    parts = [p.strip() for p in raw.split("|")]
    if len(parts) not in (4, 5):
        await update.message.reply_text(
            "استفاده درست:\n/add_player نام|تیم|پست(GK/DF/MF/FW)|قیمت|قدرت(اختیاری)\n\n"
            "مثال:\n/add_player رونالدو|النصر|FW|14\n"
            "یا با قدرت دلخواه:\n/add_player رونالدو|النصر|FW|14|16"
        )
        return

    if len(parts) == 5:
        name, team, position, price_str, power_str = parts
    else:
        name, team, position, price_str = parts
        power_str = None

    if position not in ("GK", "DF", "MF", "FW"):
        await update.message.reply_text("پست باید یکی از این‌ها باشه: GK, DF, MF, FW")
        return
    try:
        price = float(price_str)
        power = float(power_str) if power_str is not None else None
    except ValueError:
        await update.message.reply_text("قیمت و قدرت باید عدد باشن.")
        return

    player_id = add_player(name, team, position, price, power)
    await update.message.reply_text(f"✅ بازیکن «{name}» با آیدی {player_id} اضافه شد.")


async def set_points_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای ادمین‌هاست.")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("استفاده درست:\n/set_points <آیدی بازیکن> <امتیاز>")
        return

    try:
        player_id = int(args[0])
        points = float(args[1])
    except ValueError:
        await update.message.reply_text("آیدی بازیکن و امتیاز باید عدد باشن.")
        return

    player = get_player(player_id)
    if not player:
        await update.message.reply_text("بازیکنی با این آیدی پیدا نشد.")
        return

    with get_conn() as conn:
        conn.execute(
            "UPDATE players SET week_points = ?, total_points = total_points + ? WHERE player_id = ?",
            (points, points, player_id),
        )
        c = conn.cursor()
        c.execute("SELECT DISTINCT user_id FROM user_players WHERE player_id = ?", (player_id,))
        owners = c.fetchall()
        for o in owners:
            conn.execute(
                "UPDATE users SET total_points = total_points + ? WHERE user_id = ?",
                (points, o["user_id"]),
            )

    await update.message.reply_text(
        f"✅ امتیاز {points} برای «{player['name']}» ثبت شد و به مجموع امتیاز صاحبانش اضافه شد."
    )


async def set_power_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای ادمین‌هاست.")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("استفاده درست:\n/set_power <آیدی بازیکن> <قدرت>")
        return

    try:
        player_id = int(args[0])
        power = float(args[1])
    except ValueError:
        await update.message.reply_text("آیدی بازیکن و قدرت باید عدد باشن.")
        return

    player = get_player(player_id)
    if not player:
        await update.message.reply_text("بازیکنی با این آیدی پیدا نشد.")
        return

    with get_conn() as conn:
        conn.execute("UPDATE players SET power = ? WHERE player_id = ?", (power, player_id))

    await update.message.reply_text(f"✅ قدرت «{player['name']}» روی {power:.0f} تنظیم شد.")


async def remove_player_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای ادمین‌هاست.")
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text("استفاده درست:\n/remove_player <آیدی بازیکن>")
        return

    try:
        player_id = int(args[0])
    except ValueError:
        await update.message.reply_text("آیدی بازیکن باید عدد باشه.")
        return

    player = get_player(player_id)
    if not player:
        await update.message.reply_text("بازیکنی با این آیدی پیدا نشد.")
        return

    delete_player(player_id)
    await update.message.reply_text(f"🗑 بازیکن «{player['name']}» حذف شد (از تیم هرکسی هم بود، برداشته شد).")


async def reset_league_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("این دستور فقط برای ادمین‌هاست.")
        return

    reset_league()
    await update.message.reply_text("♻️ جدول لیگ ریست شد. امتیاز و رکورد همه کاربرا صفر شد.")


# ================== راه‌اندازی ==================

async def bot_enabled_gate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اگه ادمین ربات رو خاموش کرده باشه، جز خود ادمین‌ها هیچکس نمی‌تونه ازش استفاده کنه"""
    user = update.effective_user
    if user and is_admin(user.id):
        return
    if is_bot_enabled():
        return
    if update.callback_query:
        try:
            await update.callback_query.answer("⛔️ ربات موقتاً خاموش است.", show_alert=True)
        except Exception:
            pass
        raise ApplicationHandlerStop
    if update.effective_message:
        await update.effective_message.reply_text("⛔️ ربات موقتاً خاموش است. بعداً امتحان کن.")
    raise ApplicationHandlerStop


def main():
    if not BOT_TOKEN:
        raise RuntimeError("توکن ربات (BOT_TOKEN) تنظیم نشده! خط BOT_TOKEN رو توی فایل پر کن.")

    init_db()
    seed_players_if_empty()

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .base_url(BALE_API_BASE_URL)
        .build()
    )

    # دستورات عمومی
    app.add_handler(TypeHandler(Update, bot_enabled_gate), group=-1)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("myid", myid_command))
    app.add_handler(CommandHandler("players", players_list))
    app.add_handler(CommandHandler("myteam", my_team))
    app.add_handler(CommandHandler("budget", budget_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command))
    app.add_handler(CommandHandler("league", leaderboard_command))
    app.add_handler(CommandHandler("academy", academy_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("battle", battle_command))
    app.add_handler(CommandHandler("mystats", mystats_command))
    app.add_handler(CallbackQueryHandler(buy_callback, pattern=r"^buy_\d+$"))
    app.add_handler(CallbackQueryHandler(sell_callback, pattern=r"^sell_\d+$"))
    app.add_handler(CallbackQueryHandler(upgrade_callback, pattern=r"^upgrade_\d+$"))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu_"))
    app.add_handler(CallbackQueryHandler(team_setup_callback, pattern=r"^(setcolor[12]_|setsponsor_)"))
    app.add_handler(CallbackQueryHandler(edit_team_callback, pattern=r"^editteam_"))
    app.add_handler(CallbackQueryHandler(manual_pairing_callback, pattern=r"^(manualpick_|manual_finish|manual_cancel)"))
    app.add_handler(CallbackQueryHandler(friendly_match_callback, pattern=r"^(friendlypick_|friendly_cancel)"))
    app.add_handler(CallbackQueryHandler(buypack_callback, pattern=r"^buypack_"))
    app.add_handler(CallbackQueryHandler(
        lineup_tactic_callback,
        pattern=r"^(lineup_|setformation_|togglelineup_|tactic_pick|settactic_|stadium_upgrade)"
    ))
    app.add_handler(CallbackQueryHandler(admin_menu_callback, pattern=r"^admin_"))

    # دستورات ادمین (متنی - برای کسی که ترجیح میده تایپ کنه)
    app.add_handler(CommandHandler("admin_help", admin_help))
    app.add_handler(CommandHandler("give_budget", give_budget_command))
    app.add_handler(CommandHandler("set_news", set_news_command))
    app.add_handler(CommandHandler("add_player", add_player_command))
    app.add_handler(CommandHandler("set_points", set_points_command))
    app.add_handler(CommandHandler("set_power", set_power_command))
    app.add_handler(CommandHandler("remove_player", remove_player_command))
    app.add_handler(CommandHandler("reset_league", reset_league_command))

    # ورودی متنی بعد از زدن یکی از دکمه‌های پنل ادمین (باید آخر از همه ثبت بشه)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text_input_handler))

    logger.info("ربات در حال اجراست...")
    app.run_polling()


if __name__ == "__main__":
    main()
