import os
import logging
import asyncio
import random
import threading
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, JobQueue
)
from database import (
    init_db, add_user, add_filter, remove_filter, clear_filters,
    get_filters, get_all_active_users, get_unsent_jobs, mark_job_sent,
    get_job_count, increment_user_counter
)
from scraper import run_scraper

# Load env
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_IDS = [499776645]  # Leila

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================
# IMREVOR CONFIG — change these when website goes live
# ============================================================
IMREVOR_LINK = "https://docs.google.com/forms/d/1BUMpyG1UB_Rm9vLe9ZqTPIwy-FXej3oUBmZpWbh5Gwk/viewform"
IMREVOR_CTA = "Get early access"

IMREVOR_NOTIFY_EVERY = 10
IMREVOR_SEARCH_EVERY = 3

IMREVOR_SEARCH_MESSAGES = [
    "💡 Finding the job is step one. Getting shortlisted is step two. "
    "IMREVOR is a community where international dev professionals share real strategies, "
    f"connections, and unlisted roles. Launching soon — [{IMREVOR_CTA}]({IMREVOR_LINK})",

    "💡 Most UN roles get 150+ applications. The ones who get shortlisted? "
    "They had someone review their P11, prep their interview, or flag the role before it went public. "
    f"That's what we're building at IMREVOR — [{IMREVOR_CTA}]({IMREVOR_LINK})",

    "💡 Job boards show you what's open. Networks show you what's coming. "
    f"IMREVOR is a community for international development professionals who want both — [{IMREVOR_CTA}]({IMREVOR_LINK})",
]

IMREVOR_EMPTY_MESSAGES = [
    "No matches yet. Here's the thing — the best roles in this space travel through networks "
    f"before they hit job boards. We're building IMREVOR for exactly that. Be first in → [{IMREVOR_CTA}]({IMREVOR_LINK})",

    "Nothing new right now. But here's what we know: 70% of UN consultancies are filled through "
    f"referrals. IMREVOR is a community where those connections happen — [{IMREVOR_CTA}]({IMREVOR_LINK})",
]

IMREVOR_NOTIFY_MESSAGES = [
    "🔑 Most UN consultancies get 150+ applications. The shortlisted ones? "
    f"They had someone vouch for them. That's what IMREVOR is building — [{IMREVOR_CTA}]({IMREVOR_LINK})",

    "🔑 The biggest career moves in international development happen through conversations, not applications. "
    f"IMREVOR is where those conversations start — [{IMREVOR_CTA}]({IMREVOR_LINK})",
]

REGIONS = {
    "🌍 Africa": ["nairobi", "addis ababa", "dakar", "accra", "abuja", "kampala", "dar es salaam", "harare"],
    "🌏 Asia & Pacific": ["bangkok", "beijing", "delhi", "islamabad", "kabul", "manila", "jakarta", "tokyo"],
    "🌎 Americas": ["new york", "washington", "bogota", "lima", "panama city", "santiago", "brasilia"],
    "🇪🇺 Europe": ["rome", "geneva", "vienna", "paris", "budapest", "copenhagen", "brussels", "the hague"],
    "🌍 Middle East": ["cairo", "amman", "beirut", "riyadh", "baghdad", "jerusalem"],
    "🌐 Remote": ["remote", "home based"],
}

LOCATIONS = []
for cities in REGIONS.values():
    LOCATIONS.extend(cities)

ORGANIZATIONS = [
    "fao", "wfp", "ifad", "who", "undp", "unicef", "unhcr",
    "unops", "iom", "unfpa", "unep", "unesco"
]

GRADES = [
    "p-1", "p-2", "p-3", "p-4", "p-5", "d-1", "d-2",
    "no-a", "no-b", "no-c",
    "consultant", "intern", "unv",
    "temporary", "fixed-term", "sc", "g-5", "g-6", "g-7"
]

SECTORS = [
    "risk", "governance", "finance", "food security", "nutrition",
    "climate", "health", "education", "humanitarian", "procurement",
    "human resources", "communications", "monitoring", "evaluation",
    "programme", "project management", "legal", "audit", "data",
    "technology", "innovation"
]

def get_main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Search Jobs", callback_data="action_search"),
            InlineKeyboardButton("📋 My Filters", callback_data="action_filters"),
        ],
        [
            InlineKeyboardButton("📍 Location", callback_data="action_location"),
            InlineKeyboardButton("🏛 Organization", callback_data="action_organization"),
        ],
        [
            InlineKeyboardButton("📊 Grade", callback_data="action_grade"),
            InlineKeyboardButton("🎯 Sector", callback_data="action_sector"),
        ],
        [
            InlineKeyboardButton("🗑 Clear Filters", callback_data="action_clear"),
            InlineKeyboardButton("📈 Stats", callback_data="action_stats"),
        ]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.username, user.first_name)
    
    await update.message.reply_text(
        f"👋 Welcome to *UN Jobs Alert*!\n\n"
        f"I find UN and international development jobs that match *your* criteria.\n\n"
        f"🔧 *How to use:*\n"
        f"1. Set filters below (location, org, grade, sector)\n"
        f"2. Tap *🔍 Search Jobs* to find matches\n"
        f"3. Need something specific? Type `/search keyword` (e.g. `/search Lawyer`)\n"
        f"4. I also check automatically every 4 hours and send you new matches\n\n"
        f"Set up your filters to get started:",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )
    
    await update.message.reply_text(
        f"_This bot is built by IMREVOR — a community for international development "
        f"professionals who want more than job boards. "
        f"We're launching soon. [{IMREVOR_CTA}]({IMREVOR_LINK})_",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *How it works:*\n\n"
        "1️⃣ Set your filters (location, org, grade, sector)\n"
        "2️⃣ Tap *🔍 Search Jobs* to see matches\n"
        "3️⃣ Type `/search keyword` to find specific roles (e.g. `/search Finance`)\n"
        "4️⃣ I check job boards every 4 hours automatically\n\n"
        "Use the buttons below:",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )

def build_filter_keyboard(filter_type, options, user_filters):
    active = user_filters.get(filter_type, [])
    keyboard = []
    for i in range(0, len(options), 2):
        row = []
        for opt in options[i:i+2]:
            check = "✅ " if opt in active else ""
            label = f"{check}{opt.upper()}" if filter_type == "grade" else f"{check}{opt.title()}"
            row.append(InlineKeyboardButton(label, callback_data=f"toggle_{filter_type}_{opt}"))
        keyboard.append(row)
        keyboard.append([
        InlineKeyboardButton("✅ Done", callback_data="done"),
        InlineKeyboardButton("🏠 Menu", callback_data="action_menu")
    ])
    return InlineKeyboardMarkup(keyboard)

async def show_filter(query_or_message, filter_type, user_id, is_callback=False):
    user_filters = get_filters(user_id)
    options_map = {
        "organization": (ORGANIZATIONS, "🏛 *Select your preferred organizations:*"),
        "grade": (GRADES, "📊 *Select your preferred grades/contract types:*"),
        "sector": (SECTORS, "🎯 *Select your sectors of interest:*"),
    }
    if filter_type == "location":
        await show_region_selector(query_or_message, user_id, is_callback)
        return
    
    options, text = options_map[filter_type]
    keyboard = build_filter_keyboard(filter_type, options, user_filters)
    text += "\nTap to toggle on/off."
    
    if is_callback:
        await query_or_message.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await query_or_message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")

async def show_region_selector(query_or_message, user_id, is_callback=False):
    user_filters = get_filters(user_id)
    active_locations = user_filters.get("location", [])
    
    keyboard = []
    for region_name in REGIONS:
        cities = REGIONS[region_name]
        active_count = sum(1 for c in cities if c in active_locations)
        label = f"{region_name}"
        if active_count > 0:
            label += f" ({active_count} selected)"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"region_{region_name}")])
    
    if active_locations:
        selected = ", ".join(loc.title() for loc in active_locations)
        text = f"📍 *Select a region to add/remove cities:*\n\nCurrently selected: _{selected}_"
    else:
        text = "📍 *Select a region to see available cities:*"
    
    keyboard.append([
        InlineKeyboardButton("✅ Done", callback_data="done"),
        InlineKeyboardButton("🏠 Menu", callback_data="action_menu")
    ])
    
    markup = InlineKeyboardMarkup(keyboard)
    if is_callback:
        try:
            await query_or_message.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            pass
    else:
        await query_or_message.reply_text(text, reply_markup=markup, parse_mode="Markdown")

async def show_city_selector(query, region_name, user_id):
    cities = REGIONS.get(region_name, [])
    user_filters = get_filters(user_id)
    active = user_filters.get("location", [])
    
    keyboard = []
    for i in range(0, len(cities), 2):
        row = []
        for city in cities[i:i+2]:
            check = "✅ " if city in active else ""
            row.append(InlineKeyboardButton(
                f"{check}{city.title()}", callback_data=f"toggle_location_{city}"
            ))
        keyboard.append(row)
    
    keyboard.append([
        InlineKeyboardButton("⬅️ Back to Regions", callback_data="action_location"),
        InlineKeyboardButton("✅ Done", callback_data="done")
    ])
    
    await query.edit_message_text(
        f"📍 *{region_name}*\nTap cities to toggle on/off:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def location_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_filter(update.message, "location", update.effective_user.id)

async def organization_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_filter(update.message, "organization", update.effective_user.id)

async def grade_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_filter(update.message, "grade", update.effective_user.id)

async def sector_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_filter(update.message, "sector", update.effective_user.id)
    async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data == "action_search":
        await do_search(query, user_id, context)
        return
    if data == "action_next_10":
        await callback_next_10(update, context)
        return
    if data == "action_filters":
        await do_filters(query, user_id)
        return
    if data == "action_location":
        await show_filter(query, "location", user_id, is_callback=True)
        return
    if data.startswith("region_"):
        region_name = data[7:] 
        await show_city_selector(query, region_name, user_id)
        return
    if data == "action_organization":
        await show_filter(query, "organization", user_id, is_callback=True)
        return
    if data == "action_grade":
        await show_filter(query, "grade", user_id, is_callback=True)
        return
    if data == "action_sector":
        await show_filter(query, "sector", user_id, is_callback=True)
        return
    if data == "action_clear":
        clear_filters(user_id)
        await query.edit_message_text(
            "🗑 All filters cleared.\n\nSet new ones below:",
            reply_markup=get_main_menu()
        )
        return
    if data == "action_stats":
        import datetime
        count = get_job_count()
        users = get_all_active_users()
        now = datetime.datetime.utcnow().strftime("%H:%M UTC")
        try:
            await query.edit_message_text(
                f"📊 *Bot Statistics:*\n\n"
                f"👥 Users: {len(users)}\n"
                f"💼 Jobs in database: {count}\n"
                f"Sources: unjobs.org, impactpool.org, linkedin.com\nAuto-check: every 4 hours\n"
                f"_Updated: {now}_",
                parse_mode="Markdown",
                reply_markup=get_main_menu()
            )
        except Exception:
            pass
        return
    if data == "action_menu":
        try:
            await query.edit_message_text(
                "🏠 *Main Menu*\n\nWhat would you like to do?",
                parse_mode="Markdown",
                reply_markup=get_main_menu()
            )
        except Exception:
            pass
        return
    if data == "done":
        await query.edit_message_text(
            "✅ Filters saved!\n\n🔔 I'll notify you when matching jobs appear.\nOr search now:",
            reply_markup=get_main_menu()
        )
        return
    
    if data.startswith("toggle_"):
        parts = data.split("_", 2)
        if len(parts) != 3:
            return
        _, filter_type, filter_value = parts
        
        current = get_filters(user_id)
        active = current.get(filter_type, [])
        
        if filter_value in active:
            remove_filter(user_id, filter_type, filter_value)
        else:
            add_filter(user_id, filter_type, filter_value)
        
        if filter_type == "location":
            for region_name, cities in REGIONS.items():
                if filter_value in cities:
                    await show_city_selector(query, region_name, user_id)
                    return
            return
        
        options_map = {
            "organization": ORGANIZATIONS,
            "grade": GRADES, "sector": SECTORS
        }
        updated_filters = get_filters(user_id)
        keyboard = build_filter_keyboard(filter_type, options_map.get(filter_type, []), updated_filters)
        try:
            await query.edit_message_reply_markup(reply_markup=keyboard)
        except Exception:
            pass

# ============================================================
# SEARCH & PAGINATION
# ============================================================

async def send_paginated_results(message_or_query, context, user_id):
    matching = context.user_data.get('search_results', [])
    index = context.user_data.get('search_index', 0)
    
    chunk = matching[index:index+10]
    if not chunk:
        await context.bot.send_message(user_id, "No more results.")
        return
        
    await context.bot.send_message(
        user_id,
        f"📋 Showing jobs {index+1} to {index+len(chunk)} of *{len(matching)}* matches:",
        parse_mode="Markdown"
    )
    
    for job in chunk:
        text = format_job(job)
        await context.bot.send_message(user_id, text, parse_mode="Markdown", disable_web_page_preview=True)
        mark_job_sent(user_id, job["job_id"])
        
    context.user_data['search_index'] = index + 10
    
    keyboard = []
    if context.user_data['search_index'] < len(matching):
        keyboard.append([InlineKeyboardButton("⏭ Show Next 10", callback_data="action_next_10")])
    keyboard.append([InlineKeyboardButton("🏠 Menu", callback_data="action_menu")])
    
    await context.bot.send_message(
        user_id,
        "👆 Latest matches.\n\nWhat's next?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def callback_next_10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await send_paginated_results(query, context, query.from_user.id)

async def do_search(query, user_id, context):
    await query.edit_message_text("🔍 Searching for matching jobs...")
    
    user_filters = get_filters(user_id)
    run_scraper()
    jobs = get_unsent_jobs(user_id)
    
    if not jobs:
        await context.bot.send_message(
            user_id,
            random.choice(IMREVOR_EMPTY_MESSAGES),
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=get_main_menu()
        )
        return
    
    matching = [job for job in jobs if matches_filters(job, user_filters)]
    
    if not matching:
        msg = (f"Found {len(jobs)} jobs but none match your filters.\n"
               f"Try broadening your criteria.\n\n"
               + random.choice(IMREVOR_EMPTY_MESSAGES))
        await context.bot.send_message(
            user_id, msg,
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=get_main_menu()
        )
        return
        
    context.user_data['search_results'] = matching
    context.user_data['search_index'] = 0
    
    search_count = increment_user_counter(user_id, "search_count")
    if search_count % IMREVOR_SEARCH_EVERY == 0:
        await context.bot.send_message(
            user_id,
            random.choice(IMREVOR_SEARCH_MESSAGES),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        
    await send_paginated_results(query, context, user_id)

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_filters = get_filters(user.id)
    
    keyword = " ".join(context.args).lower() if context.args else None
    
    await update.message.reply_text("🔍 Searching for matching jobs...")
    
    run_scraper()
    jobs = get_unsent_jobs(user.id)
    
    if not jobs:
        await update.message.reply_text(
            random.choice(IMREVOR_EMPTY_MESSAGES),
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=get_main_menu()
        )
        return
    
    matching = [job for job in jobs if matches_filters(job, user_filters)]
    
    if keyword:
        matching = [job for job in matching if keyword in job["title"].lower() or keyword in (job["organization"] or "").lower()]
    
    if not matching:
        msg = (f"Found {len(jobs)} jobs but none match your filters/keywords.\n"
               f"Try broadening your criteria.\n\n"
               + random.choice(IMREVOR_EMPTY_MESSAGES))
        await update.message.reply_text(
            msg, parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=get_main_menu()
        )
        return
    
    context.user_data['search_results'] = matching
    context.user_data['search_index'] = 0
    
    search_count = increment_user_counter(user.id, "search_count")
    if search_count % IMREVOR_SEARCH_EVERY == 0:
        await update.message.reply_text(
            random.choice(IMREVOR_SEARCH_MESSAGES),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        
    await send_paginated_results(update.message, context, user.id)

async def do_filters(query, user_id):
    user_filters = get_filters(user_id)
    if not user_filters:
        await query.edit_message_text(
            "No filters set yet.\n\nTap below to set your preferences:",
            reply_markup=get_main_menu()
        )
        return
    
    text = "🔍 *Your current filters:*\n\n"
    labels = {"location": "📍 Locations", "organization": "🏛 Organizations",
              "grade": "📊 Grades", "sector": "🎯 Sectors"}
    for ft, values in user_filters.items():
        label = labels.get(ft, ft.title())
        formatted = ", ".join(v.upper() if ft == "grade" else v.title() for v in values)
        text += f"{label}: {formatted}\n"
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_menu())

async def filters_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_filters = get_filters(user.id)
    if not user_filters:
        await update.message.reply_text(
            "No filters set yet.\n\nTap below to set your preferences:",
            reply_markup=get_main_menu()
        )
        return
    
    text = "🔍 *Your current filters:*\n\n"
    labels = {"location": "📍 Locations", "organization": "🏛 Organizations",
              "grade": "📊 Grades", "sector": "🎯 Sectors"}
    for ft, values in user_filters.items():
        label = labels.get(ft, ft.title())
        formatted = ", ".join(v.upper() if ft == "grade" else v.title() for v in values)
        text += f"{label}: {formatted}\n"
    
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_main_menu())

async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_filters(update.effective_user.id)
    await update.message.reply_text(
        "🗑 All filters cleared.\n\nSet new ones below:",
        reply_markup=get_main_menu()
    )

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = get_job_count()
    users = get_all_active_users()
    user_count = len(users)
    await update.message.reply_text(
        f"📊 *Bot Statistics:*\n\nActive Users: {user_count}\nJobs in database: {count}\n"
        f"Sources: unjobs.org, impactpool.org, linkedin.com\nAuto-check: every 4 hours",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )

def matches_filters(job, user_filters):
    if not user_filters:
        return False
    
    title_lower = job["title"].lower()
    org_lower = (job["organization"] or "").lower()
    location_lower = (job["location"] or "").lower()
    grade_lower = (job["grade"] or "").lower()
    
    score = 0
    checked = 0
    
    if "location" in user_filters:
        checked += 1
        for loc in user_filters["location"]:
            if loc in title_lower or loc in location_lower:
                score += 1
                break
    
    if "organization" in user_filters:
        checked += 1
        for org in user_filters["organization"]:
            if org in org_lower or org in title_lower:
                score += 1
                break
    
    if "grade" in user_filters:
        checked += 1
        grade_keywords = {
            "consultant": ["consultant", "consultancy", "consulting"],
            "intern": ["intern", "internship"],
            "unv": ["unv", "un volunteer", "united nations volunteer"],
            "temporary": ["temporary", "temporary appointment"],
            "fixed-term": ["fixed-term", "fixed term"],
            "sc": ["sc-", "service contract"],
        }
        for g in user_filters["grade"]:
            g_safe = re.escape(g.lower())
            g_no_hyphen = re.escape(g.lower().replace("-", ""))
            pattern = rf"(?<![a-zA-Z0-9])(?:{g_safe}|{g_no_hyphen})(?![a-zA-Z0-9])"
            
            if re.search(pattern, grade_lower) or re.search(pattern, title_lower):
                score += 1
                break
            if g in grade_keywords:
                matched_kw = False
                for kw in grade_keywords[g]:
                    if kw in title_lower:
                        score += 1
                        matched_kw = True
                        break
                if matched_kw:
                    break
        
        if score < checked:
            return False
    
    if "sector" in user_filters:
        checked += 1
        for sector in user_filters["sector"]:
            if sector in title_lower:
                score += 1
                break
    
    return score > 0 if checked > 0 else True

def format_job(job):
    title = job["title"]
    org = job["organization"] or "—"
    url = job["url"]
    grade = job["grade"] or "—"
    source = job["source"] or "unjobs"
    
    return (
        f"💼 *{title}*\n"
        f"🏛 {org}\n"
        f"📊 Grade: {grade}\n"
        f"🔗 [Apply here]({url})\n"
        f"📌 Source: {source}"
    )

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin only.")
        return
    
    from database import get_conn
    conn = get_conn()
    
    total = conn.execute("SELECT COUNT(*) as c FROM users WHERE active = 1").fetchone()["c"]
    users = conn.execute(
        "SELECT user_id, username, first_name, created_at FROM users WHERE active = 1 ORDER BY created_at DESC"
    ).fetchall()
    today_count = conn.execute(
        "SELECT COUNT(*) as c FROM users WHERE DATE(created_at) = DATE('now')"
    ).fetchone()["c"]
    pop_filters = conn.execute(
        "SELECT filter_type, filter_value, COUNT(*) as c FROM user_filters GROUP BY filter_type, filter_value ORDER BY c DESC LIMIT 10"
    ).fetchall()
    job_count = conn.execute("SELECT COUNT(*) as c FROM jobs").fetchone()["c"]
    
    total_searches = 0
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_counters (
                user_id INTEGER,
                counter_name TEXT,
                counter_value INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, counter_name)
            )
        """)
        search_rows = conn.execute(
            "SELECT SUM(counter_value) as s FROM user_counters WHERE counter_name = 'search_count'"
        ).fetchone()
        total_searches = search_rows["s"] or 0
    except Exception:
        pass
    
    conn.close()
    
    text = f"🔐 *Admin Dashboard*\n\n"
    text += f"👥 *Users:* {total} total ({today_count} today)\n"
    text += f"💼 *Jobs in DB:* {job_count}\n"
    text += f"🔍 *Total searches:* {total_searches}\n\n"
    
    text += "*Recent users:*\n"
    for u in users[:15]:
        name = u["first_name"] or "—"
        uname = f"@{u['username']}" if u["username"] else "no username"
        text += f"  • {name} ({uname}) — {u['created_at'][:16]}\n"
    
    if pop_filters:
        text += f"\n*Top filters:*\n"
        for f in pop_filters:
            text += f"  • {f['filter_type']}: {f['filter_value']} ({f['c']} users)\n"
    
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_main_menu())

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin only.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /broadcast Your message to all users")
        return
    
    message = " ".join(context.args)
        users = get_all_active_users()
sent = 0
    failed = 0
    for uid in users:
        try:
            await context.bot.send_message(uid, message, parse_mode="Markdown", disable_web_page_preview=True)
            sent += 1
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Broadcast failed for {uid}: {e}")
            failed += 1
    
    await update.message.reply_text(f"📢 Broadcast sent: {sent} delivered, {failed} failed.")

async def auto_notify(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Running auto-notification check...")
    try:
        run_scraper()
    except Exception as e:
        logger.error(f"Scraper failed: {e}")
        return
    
    users = get_all_active_users()
    
    for user_id in users:
        try:
            user_filters = get_filters(user_id)
            jobs = get_unsent_jobs(user_id)
            matching = [job for job in jobs if matches_filters(job, user_filters)]
            
            if not matching:
                continue
            
            count = min(5, len(matching))
            
            await context.bot.send_message(
                user_id,
                f"🔔 *{len(matching)} new matching jobs found!*\n\nHere are the latest:",
                parse_mode="Markdown"
            )
            
            for job in matching[:count]:
                text = format_job(job)
                await context.bot.send_message(user_id, text, parse_mode="Markdown", disable_web_page_preview=True)
                mark_job_sent(user_id, job["job_id"])
            
            notify_count = increment_user_counter(user_id, "notify_count")
            if notify_count % IMREVOR_NOTIFY_EVERY == 0:
                await context.bot.send_message(
                    user_id,
                    random.choice(IMREVOR_NOTIFY_MESSAGES),
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
            
            if len(matching) > count:
                await context.bot.send_message(
                    user_id,
                    f"... and {len(matching) - count} more. Tap Search to see all.",
                    reply_markup=get_main_menu()
                )
            else:
                await context.bot.send_message(
                    user_id,
                    "That's everything new! I'll check again in 4 hours.",
                    reply_markup=get_main_menu()
                )
            
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {e}")

async def clear_conflict():
    import httpx
    url = f"https://api.telegram.org/bot{TOKEN}"
    async with httpx.AsyncClient() as client:
        await client.post(f"{url}/deleteWebhook", params={"drop_pending_updates": True})
        for _ in range(3):
            try:
                await client.post(f"{url}/getUpdates", json={"offset": -1, "timeout": 1}, timeout=5)
            except Exception:
                pass
            await asyncio.sleep(2)
    await asyncio.sleep(5)
    logger.info("Conflict cleared, starting bot...")

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def start_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health server on port {port}")

def main():
    init_db()
    
    import httpx
    url = f"https://api.telegram.org/bot{TOKEN}"
    with httpx.Client() as client:
        client.post(f"{url}/deleteWebhook", params={"drop_pending_updates": True})
        for _ in range(2):
            try:
                                client.post(f"{url}/getUpdates", json={"offset": -1, "timeout": 1}, timeout=5)
                except Exception:
                pass
    logger.info("Conflict cleared, starting bot...")
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("location", location_cmd))
    app.add_handler(CommandHandler("organization", organization_cmd))
    app.add_handler(CommandHandler("grade", grade_cmd))
    app.add_handler(CommandHandler("sector", sector_cmd))
    app.add_handler(CommandHandler("filters", filters_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    
    app.add_handler(CallbackQueryHandler(callback_handler))
    
    job_queue = app.job_queue
    job_queue.run_repeating(auto_notify, interval=14400, first=60)
    
    print("🤖 UN Jobs Alert Bot is running...")
    print(f"📡 Auto-notifications: every 4 hours")
    print(f"🌱 IMREVOR hook: search every {IMREVOR_SEARCH_EVERY}th, notify every {IMREVOR_NOTIFY_EVERY}th")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
