"""
AddisGo bot: Amharic + English menu bot for bookings and products.

Customer flow:
  /start -> language -> Booking or Products -> category -> item
  -> fee shown -> Accept -> bot gives your username + sends YOU the lead.

You (admin) edit everything inside Telegram while browsing the bot.

SETUP (only 2 things to fill in below):
  1. Paste your BotFather token into TOKEN
  2. Choose a secret ADMIN_PASSWORD
Then in Telegram, message your bot:  /admin YOUR_PASSWORD
(Your Telegram account must have a @username: Settings -> Username.)

Install:  pip install "python-telegram-bot>=21"
Run:      python addis_bot.py
"""
import os
import sqlite3
import logging
from datetime import datetime, timedelta

from telegram import (
    Update, InlineKeyboardButton as Btn, InlineKeyboardMarkup as Markup,
    ReplyKeyboardMarkup, KeyboardButton,
)
from telegram.error import BadRequest
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters,
)

logging.basicConfig(level=logging.INFO)

# ===================== FILL THESE IN =====================
TOKEN = os.environ.get("BOT_TOKEN") or "8708147345:AAELQ-W5SkoGPWgHfXlztsnOrvyY7uFqfk4"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or "Biruk@2019"
# =========================================================

# ---------- Texts (English / Amharic) ----------
TEXT = {
    "en": {
        "welcome": "👋 Welcome! What do you need?",
        "booking": "🏨 Booking", "product": "🛍 Products",
        "custom": "✍️ Custom request", "contact": "📞 Contact us",
        "language": "🌐 Language",
        "back": "⬅️ Back", "accept": "✅ Accept & continue",
        "fee": "Fee", "tbc": "To be confirmed", "birr": "birr",
        "empty": "Coming soon.",
        "accepted": "✅ Great! To continue, message us here: {c}\n"
                    "Send your payment proof (screenshot) in that chat. "
                    "We'll confirm your date there.",
        "already": "Your request was already sent. Message us here: {c}",
        "share_phone": "Please tap the button below to share your phone "
                       "number so we can reach you.",
        "share_btn": "📱 Share phone number",
        "chat_admin": "💬 Message us",
        "contact_text": "Message us here: {c}",
        "custom_ask": "Type what you need and we'll get back to you:",
        "custom_sent": "✅ Sent! We'll contact you soon.",
        "notready": "Bot is not ready yet. Please try again later.",
    },
    "am": {
        "welcome": "👋 እንኳን በደህና መጡ! ምን ይፈልጋሉ?",
        "booking": "🏨 ቦታ ማስያዝ", "product": "🛍 ምርቶች",
        "custom": "✍️ ልዩ ጥያቄ", "contact": "📞 አግኙን",
        "language": "🌐 ቋንቋ",
        "back": "⬅️ ተመለስ", "accept": "✅ እቀበላለሁ",
        "fee": "ክፍያ", "tbc": "ይረጋገጣል", "birr": "ብር",
        "empty": "በቅርቡ ይመጣል።",
        "accepted": "✅ በጣም ጥሩ! ለመቀጠል እዚህ ያናግሩን፦ {c}\n"
                    "የክፍያ ማስረጃዎን (screenshot) በዚያ ቻት ይላኩ። "
                    "ቀኑን እዚያ እናረጋግጣለን።",
        "already": "ጥያቄዎ ቀድሞ ተልኳል። እዚህ ያናግሩን፦ {c}",
        "share_phone": "እንድናገኝዎ ከታች ያለውን ቁልፍ ተጭነው ስልክ ቁጥርዎን ያጋሩ።",
        "share_btn": "📱 ስልክ ቁጥር አጋራ",
        "chat_admin": "💬 መልእክት ላኩልን",
        "contact_text": "እዚህ ያናግሩን፦ {c}",
        "custom_ask": "የሚፈልጉትን ይጻፉ፤ መልስ እንሰጥዎታለን፦",
        "custom_sent": "✅ ተልኳል! በቅርቡ እናገኝዎታለን።",
        "notready": "ቦቱ ገና አልተዘጋጀም። እባክዎ ቆይተው ይሞክሩ።",
    },
}

# ---------- Database ----------
db = sqlite3.connect("addis_bot.db", check_same_thread=False)
db.row_factory = sqlite3.Row
db.executescript("""
CREATE TABLE IF NOT EXISTS nodes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent INTEGER, kind TEXT, en TEXT, am TEXT, fee REAL);
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, lang TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS leads(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, node_id INTEGER, ts TEXT);
""")
db.commit()


def seed():
    """Starter menu. You can change/add/delete all of it inside Telegram."""
    if db.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]:
        return
    db.execute("INSERT INTO nodes(id,parent,kind,en,am) VALUES(1,0,'root','Booking','ቦታ ማስያዝ')")
    db.execute("INSERT INTO nodes(id,parent,kind,en,am) VALUES(2,0,'root','Products','ምርቶች')")

    def add(parent, kind, en, am, fee=None):
        cur = db.execute(
            "INSERT INTO nodes(parent,kind,en,am,fee) VALUES(?,?,?,?,?)",
            (parent, kind, en, am, fee))
        return cur.lastrowid

    for en, am in [
        ("Hotels", "ሆቴሎች"),
        ("Restaurants & tables", "ሬስቶራንት እና ጠረጴዛ"),
        ("Car rental & drivers", "የመኪና ኪራይ እና ሾፌር"),
        ("Flights & travel", "በረራ እና ጉዞ"),
        ("Events & venues", "ዝግጅቶች እና አዳራሾች"),
        ("Salon & spa", "ሳሎን እና ስፓ"),
        ("Clinics & appointments", "ክሊኒክ እና ቀጠሮ"),
        ("Apartments & guesthouses", "አፓርትመንት እና የእንግዳ ማረፊያ"),
    ]:
        cid = add(1, "cat", en, am)
        if en == "Hotels":  # sample items - EDIT fees/names in Telegram
            add(cid, "item", "Skylight Hotel", "ስካይላይት ሆቴል", 500)
            add(cid, "item", "Hilton Addis Ababa", "ሂልተን አዲስ አበባ", 500)
            add(cid, "item", "Sheraton Addis", "ሸራተን አዲስ", 500)
        if en == "Car rental & drivers":
            add(cid, "item", "Airport pickup", "ከአየር ማረፊያ መውሰድ", 300)

    for en, am in [
        ("Electronics", "ኤሌክትሮኒክስ"),
        ("Clothing & shoes", "ልብስ እና ጫማ"),
        ("Groceries & household", "ሸቀጣ ሸቀጥ እና የቤት እቃዎች"),
        ("Gifts & flowers", "ስጦታ እና አበባ"),
        ("Pharmacy", "ፋርማሲ"),
        ("Delivery & errands", "ማድረስ እና ተላላኪ"),
        ("Food & cakes", "ምግብ እና ኬክ"),
    ]:
        cid = add(2, "cat", en, am)
        if en == "Delivery & errands":
            add(cid, "item", "Pick up & deliver a package", "እቃ መውሰድና ማድረስ", 200)
    db.commit()


seed()


# ---------- Helpers ----------
def get_setting(key):
    r = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else None


def set_setting(key, value):
    db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))
    db.commit()


def lang(uid):
    r = db.execute("SELECT lang FROM users WHERE id=?", (uid,)).fetchone()
    return r["lang"] if r else "en"


def T(key, l):
    return TEXT[l][key]


def is_admin(uid):
    a = get_setting("admin_id")
    return bool(a) and int(a) == uid


def get_node(nid):
    return db.execute("SELECT * FROM nodes WHERE id=?", (nid,)).fetchone()


def children(nid):
    return db.execute("SELECT * FROM nodes WHERE parent=? ORDER BY id", (nid,)).fetchall()


def nname(node, l):
    return node["am"] if l == "am" and node["am"] else node["en"]


def path_en(node):
    parts = []
    while node:
        parts.append(node["en"])
        node = get_node(node["parent"]) if node["parent"] else None
    return " → ".join(reversed(parts))


def fee_text(fee, l):
    if fee is None:
        return T("tbc", l)
    return f"{fee:,.0f} {T('birr', l)}"


def delete_tree(nid):
    for k in children(nid):
        delete_tree(k["id"])
    db.execute("DELETE FROM nodes WHERE id=?", (nid,))


def admin_contact():
    u = get_setting("admin_username")
    return f"@{u}" if u else ""


def contact_markup(l):
    u = get_setting("admin_username")
    if not u:
        return None
    return Markup([[Btn(T("chat_admin", l), url=f"https://t.me/{u}")]])


async def show(update: Update, text, kb=None):
    """Edit the message if it came from a button, else send a new one."""
    q = update.callback_query
    if q:
        await q.answer()
        try:
            await q.edit_message_text(text, reply_markup=kb)
        except BadRequest:
            pass
    else:
        await update.effective_message.reply_text(text, reply_markup=kb)


# ---------- Customer screens ----------
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    kb = Markup([[Btn("English 🇬🇧", callback_data="lang:en"),
                  Btn("አማርኛ 🇪🇹", callback_data="lang:am")]])
    await show(update, "Choose your language / ቋንቋ ይምረጡ", kb)


async def main_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    l = lang(update.effective_user.id)
    ctx.user_data.pop("await", None)
    kb = Markup([
        [Btn(T("booking", l), callback_data="n:1")],
        [Btn(T("product", l), callback_data="n:2")],
        [Btn(T("custom", l), callback_data="custom"),
         Btn(T("contact", l), callback_data="contact")],
        [Btn(T("language", l), callback_data="chooselang")],
    ])
    text = T("welcome", l)
    if is_admin(update.effective_user.id):
        text += "\n\n🛠 Admin mode: open any menu to add, edit or delete items."
    await show(update, text, kb)


async def view_node(update: Update, ctx: ContextTypes.DEFAULT_TYPE, node_id):
    node = get_node(node_id)
    if not node:
        return await main_menu(update, ctx)
    uid = update.effective_user.id
    l, admin = lang(uid), is_admin(uid)
    back = Btn(T("back", l),
               callback_data=f"n:{node['parent']}" if node["parent"] else "menu")
    rows = []

    if node["kind"] == "item":
        text = f"{nname(node, l)}\n\n{T('fee', l)}: {fee_text(node['fee'], l)}"
        rows.append([Btn(T("accept", l), callback_data=f"acc:{node_id}")])
        if admin:
            rows.append([Btn("💰 Set fee", callback_data=f"fee:{node_id}"),
                         Btn("🗑 Delete", callback_data=f"del:{node_id}")])
    else:
        kids = children(node_id)
        text = nname(node, l)
        if not kids:
            text += "\n\n" + T("empty", l)
        for k in kids:
            label = nname(k, l)
            if k["kind"] == "cat":
                label = "📂 " + label
            rows.append([Btn(label, callback_data=f"n:{k['id']}")])
        if admin:
            rows.append([Btn("➕ Add category", callback_data=f"addc:{node_id}"),
                         Btn("➕ Add item", callback_data=f"addi:{node_id}")])
            if node["kind"] != "root":
                rows.append([Btn("🗑 Delete this category", callback_data=f"del:{node_id}")])
    rows.append([back])
    await show(update, text, Markup(rows))


# ---------- Leads ----------
async def send_lead(ctx, user, node_id, phone):
    l = lang(user.id)
    node = get_node(node_id)
    if not node:
        return
    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    dup = db.execute(
        "SELECT 1 FROM leads WHERE user_id=? AND node_id=? AND ts>?",
        (user.id, node_id, cutoff)).fetchone()
    if dup:
        await ctx.bot.send_message(
            user.id, T("already", l).format(c=admin_contact()),
            reply_markup=contact_markup(l))
        return
    db.execute("INSERT INTO leads(user_id,node_id,ts) VALUES(?,?,?)",
               (user.id, node_id, datetime.utcnow().isoformat()))
    db.commit()

    link = (f"https://t.me/{user.username}" if user.username
            else f"tg://user?id={user.id}")
    text = (
        "🔔 NEW REQUEST\n\n"
        f"📌 {path_en(node)}\n"
        f"💰 Fee: {fee_text(node['fee'], 'en')}\n\n"
        f"👤 {user.full_name}\n"
        f"🔗 {'@' + user.username if user.username else 'no username'}\n"
        f"📱 {phone or 'not shared'}\n"
        f"🆔 {user.id}"
    )
    await ctx.bot.send_message(
        int(get_setting("admin_id")), text,
        reply_markup=Markup([[Btn("💬 Open chat", url=link)]]))
    await ctx.bot.send_message(
        user.id, T("accepted", l).format(c=admin_contact()),
        reply_markup=contact_markup(l))


async def accept(update: Update, ctx: ContextTypes.DEFAULT_TYPE, node_id):
    q = update.callback_query
    u = update.effective_user
    l = lang(u.id)
    if not get_setting("admin_id"):
        await q.answer(T("notready", l), show_alert=True)
        return
    await q.answer()
    if not u.username:
        ctx.user_data["pending"] = node_id
        await q.message.reply_text(
            T("share_phone", l),
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton(T("share_btn", l), request_contact=True)]],
                resize_keyboard=True, one_time_keyboard=True))
        return
    await send_lead(ctx, u, node_id, None)


async def on_contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    node_id = ctx.user_data.pop("pending", None)
    if node_id:
        await send_lead(ctx, update.effective_user, node_id,
                        update.message.contact.phone_number)


# ---------- Buttons ----------
ADMIN_ACTIONS = {"addc", "addi", "fee", "del", "delok"}


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = update.effective_user.id
    act, _, arg = q.data.partition(":")
    l = lang(uid)

    if act in ADMIN_ACTIONS and not is_admin(uid):
        await q.answer("Not allowed", show_alert=True)
        return

    if act == "menu":
        return await main_menu(update, ctx)
    if act == "chooselang":
        return await start(update, ctx)
    if act == "lang":
        db.execute("INSERT OR REPLACE INTO users(id,lang) VALUES(?,?)", (uid, arg))
        db.commit()
        return await main_menu(update, ctx)
    if act == "n":
        ctx.user_data.pop("await", None)
        return await view_node(update, ctx, int(arg))
    if act == "acc":
        return await accept(update, ctx, int(arg))
    if act == "contact":
        text = T("contact_text", l).format(c=admin_contact()) if admin_contact() \
            else T("notready", l)
        kb = contact_markup(l)
        rows = (kb.inline_keyboard if kb else [])
        rows = list(rows) + [[Btn(T("back", l), callback_data="menu")]]
        return await show(update, text, Markup(rows))
    if act == "custom":
        if not get_setting("admin_id"):
            await q.answer(T("notready", l), show_alert=True)
            return
        ctx.user_data["await"] = {"type": "custom"}
        return await show(update, T("custom_ask", l),
                          Markup([[Btn(T("back", l), callback_data="menu")]]))

    # ----- admin actions -----
    cancel = Markup([[Btn("❌ Cancel", callback_data=f"n:{arg}")]])
    if act in ("addc", "addi"):
        ctx.user_data["await"] = {
            "type": "add", "kind": "cat" if act == "addc" else "item",
            "parent": int(arg), "step": "en", "data": {}}
        return await show(update, "Send the ENGLISH name:", cancel)
    if act == "fee":
        ctx.user_data["await"] = {"type": "fee", "id": int(arg)}
        node = get_node(int(arg))
        back = Markup([[Btn("❌ Cancel", callback_data=f"n:{arg}")]])
        return await show(
            update, f"Send the new fee in birr for {node['en']} "
                    "(numbers only), or - for 'to be confirmed':", back)
    if act == "del":
        node = get_node(int(arg))
        if not node or node["kind"] == "root":
            return await q.answer("Can't delete this", show_alert=True)
        kb = Markup([[Btn("✅ Yes, delete", callback_data=f"delok:{arg}"),
                      Btn("❌ No", callback_data=f"n:{arg}")]])
        return await show(update, f"Delete '{node['en']}' and everything inside it?", kb)
    if act == "delok":
        node = get_node(int(arg))
        if node and node["kind"] != "root":
            parent = node["parent"]
            delete_tree(node["id"])
            db.commit()
            return await view_node(update, ctx, parent)
        return await main_menu(update, ctx)


# ---------- Text input ----------
def parse_fee(t):
    t = t.strip()
    if t == "-":
        return None
    return float(t.replace(",", ""))


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    st = ctx.user_data.get("await")
    if not st:
        return
    u = update.effective_user
    text = update.message.text.strip()
    l = lang(u.id)

    if st["type"] == "custom":
        ctx.user_data.pop("await")
        link = (f"https://t.me/{u.username}" if u.username
                else f"tg://user?id={u.id}")
        await ctx.bot.send_message(
            int(get_setting("admin_id")),
            f"✍️ CUSTOM REQUEST\n\n👤 {u.full_name}\n"
            f"🔗 {'@' + u.username if u.username else 'no username'}\n"
            f"🆔 {u.id}\n\n{text}",
            reply_markup=Markup([[Btn("💬 Open chat", url=link)]]))
        await update.message.reply_text(
            T("custom_sent", l),
            reply_markup=Markup([[Btn(T("back", l), callback_data="menu")]]))
        return

    if not is_admin(u.id):
        return

    if st["type"] == "fee":
        try:
            fee = parse_fee(text)
        except ValueError:
            await update.message.reply_text("Please send numbers only, e.g. 500 (or - to clear).")
            return
        db.execute("UPDATE nodes SET fee=? WHERE id=?", (fee, st["id"]))
        db.commit()
        ctx.user_data.pop("await")
        await update.message.reply_text("✅ Fee updated.")
        return await view_node(update, ctx, st["id"])

    if st["type"] == "add":
        step, data = st["step"], st["data"]
        if step == "en":
            data["en"] = text
            st["step"] = "am"
            await update.message.reply_text("Now the AMHARIC name (or send - to reuse English):")
            return
        if step == "am":
            data["am"] = None if text == "-" else text
            if st["kind"] == "item":
                st["step"] = "fee"
                await update.message.reply_text("Fee in birr (numbers only), or - for 'to be confirmed':")
                return
            data["fee"] = None
        elif step == "fee":
            try:
                data["fee"] = parse_fee(text)
            except ValueError:
                await update.message.reply_text("Please send numbers only, e.g. 500 (or -).")
                return
        db.execute(
            "INSERT INTO nodes(parent,kind,en,am,fee) VALUES(?,?,?,?,?)",
            (st["parent"], st["kind"], data["en"], data.get("am"), data.get("fee")))
        db.commit()
        ctx.user_data.pop("await")
        await update.message.reply_text("✅ Added.")
        return await view_node(update, ctx, st["parent"])


# ---------- Commands ----------
async def myid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Your Telegram ID: {update.effective_user.id}")


async def admin_claim(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if ADMIN_PASSWORD == "CHANGE_ME":
        await update.message.reply_text("Set ADMIN_PASSWORD in the bot file first.")
        return
    if not ctx.args or ctx.args[0] != ADMIN_PASSWORD:
        await update.message.reply_text("Wrong password.")
        return
    set_setting("admin_id", str(u.id))
    set_setting("admin_username", u.username or "")
    try:
        await update.message.delete()  # hide the password
    except BadRequest:
        pass
    msg = "✅ You are now the admin. Send /start and open any menu to edit it."
    if not u.username:
        msg += ("\n\n⚠️ You have no @username. Set one in Telegram Settings, "
                "then send /admin PASSWORD again, so customers can message you.")
    await ctx.bot.send_message(u.id, msg)


def main():
    if TOKEN == "PASTE_YOUR_TOKEN_HERE":
        raise SystemExit("Put your BotFather token in TOKEN at the top of the file.")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("admin", admin_claim))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.CONTACT, on_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
