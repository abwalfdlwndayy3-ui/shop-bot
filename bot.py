import os
import logging
from datetime import date, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

from database import (
    init_db,
    ensure_user,
    get_user,
    get_wallet,
    create_order,
    update_order_status,
    create_wallet_tx,
    confirm_wallet_tx,
    add_config,
    get_user_configs,
    get_config,
    deduct_wallet,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ADMIN_ID = 5514518727

CARD_NUMBER = "5022-2915-4349-0807"
CARD_HOLDER = "علی اکبر وندایی"

PACKAGES = {
    "vitori": {
        "name": "🟢 سرور ویتوری",
        "price_per_gb": 30_000,
        "plans": [
            {"label": "10 گیگ / 30 روز",  "gb": 10,  "days": 30, "price": 300_000},
            {"label": "30 گیگ / 30 روز",  "gb": 30,  "days": 30, "price": 900_000},
            {"label": "50 گیگ / 30 روز",  "gb": 50,  "days": 30, "price": 1_500_000},
            {"label": "100 گیگ / 30 روز", "gb": 100, "days": 30, "price": 3_000_000},
        ],
    },
    "iran_guard": {
        "name": "🔵 سرور ایران گارد",
        "price_per_gb": 35_000,
        "plans": [
            {"label": "10 گیگ / 30 روز",  "gb": 10,  "days": 30, "price": 350_000},
            {"label": "30 گیگ / 30 روز",  "gb": 30,  "days": 30, "price": 1_050_000},
            {"label": "50 گیگ / 30 روز",  "gb": 50,  "days": 30, "price": 1_750_000},
            {"label": "100 گیگ / 30 روز", "gb": 100, "days": 30, "price": 3_500_000},
        ],
    },
    "international": {
        "name": "🌐 سرور اینترنشنال",
        "plans": [],
    },
}

(
    SUB_TYPE,
    SUB_PACKAGE,
    SUB_PAY,
    SUB_RECEIPT,
    WALLET_AMOUNT,
    WALLET_RECEIPT,
    INTL_CONTACT,
    INTL_RECEIPT,
) = range(8)


def fmt_price(p: int) -> str:
    return f"{p:,} تومان"


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 خرید اشتراک",   callback_data="sub_start")],
        [InlineKeyboardButton("📋 کانفیگ های من",  callback_data="my_configs")],
        [InlineKeyboardButton("💰 شارژ کیف پول",  callback_data="wallet_start")],
        [InlineKeyboardButton("👤 مشخصات اکانت",  callback_data="account_info")],
        [InlineKeyboardButton("📞 پشتیبانی",       callback_data="support")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ensure_user(user.id, user.username, user.first_name)
    await update.message.reply_text(
        f"👋 سلام *{user.first_name}* عزیز!\n\n"
        "به ربات فروش سرور خوش آمدید.\n"
        "از منوی زیر گزینه مورد نظر را انتخاب کنید:",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown",
    )


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text(
        "🏠 *منوی اصلی*\n\nیک گزینه انتخاب کنید:",
        reply_markup=main_menu_keyboard(),
        parse_mode="Markdown",
    )


# ─── Account Info ────────────────────────────────────────────────────────────

async def account_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    ensure_user(user.id, user.username, user.first_name)
    row = get_user(user.id)
    configs = get_user_configs(user.id)
    active = [c for c in configs if c["status"] == "active"]

    next_expiry = "—"
    if active:
        next_expiry = max(c["expiry_date"] for c in active)

    username_str = f"@{user.username}" if user.username else "ندارد"
    text = (
        "👤 *مشخصات اکانت*\n"
        "━━━━━━━━━━━━━━━\n"
        f"🆔 آیدی: `{user.id}`\n"
        f"👤 یوزرنیم: {username_str}\n"
        f"📛 نام: {user.first_name or '—'}\n"
        f"💰 موجودی کیف پول: {fmt_price(row['wallet'])}\n"
        f"📦 اشتراک فعال: {len(active)} عدد\n"
        f"📅 نزدیک‌ترین انقضا: {next_expiry}\n"
        "━━━━━━━━━━━━━━━"
    )
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]),
        parse_mode="Markdown",
    )


# ─── My Configs ──────────────────────────────────────────────────────────────

async def my_configs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    ensure_user(user.id, user.username, user.first_name)
    configs = get_user_configs(user.id)
    back = [[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]

    if not configs:
        await query.edit_message_text(
            "📋 *کانفیگ های من*\n\nشما هیچ کانفیگ فعالی ندارید.\n"
            "برای خرید اشتراک از منوی اصلی اقدام کنید.",
            reply_markup=InlineKeyboardMarkup(back),
            parse_mode="Markdown",
        )
        return

    buttons = []
    for c in configs:
        icon = {"active": "✅", "pending": "⏳", "expired": "❌"}.get(c["status"], "❓")
        buttons.append([InlineKeyboardButton(
            f"{icon} {c['server_type']} — {c['package_label']}",
            callback_data=f"config_detail_{c['id']}",
        )])
    buttons.extend(back)
    await query.edit_message_text(
        f"📋 *کانفیگ های من* ({len(configs)} عدد)\n\nبرای مشاهده جزئیات روی هر کانفیگ کلیک کنید:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


async def config_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    config_id = int(query.data.split("_")[-1])
    c = get_config(config_id)

    if not c or c["user_id"] != update.effective_user.id:
        await query.answer("کانفیگ یافت نشد.", show_alert=True)
        return

    status_map = {"active": "✅ فعال", "pending": "⏳ در انتظار تأیید", "expired": "❌ منقضی"}
    remaining = max(0, c["traffic_total"] - c["traffic_used"])
    config_block = (
        f"\n\n📎 *کانفیگ:*\n`{c['config_text']}`"
        if c["config_text"]
        else "\n\n⏳ کانفیگ پس از تأیید ادمین ارسال می‌شود."
    )
    text = (
        "📋 *جزئیات کانفیگ*\n"
        "━━━━━━━━━━━━━━━\n"
        f"🖥 سرور: {c['server_type']}\n"
        f"📦 پکیج: {c['package_label']}\n"
        f"📊 وضعیت: {status_map.get(c['status'], c['status'])}\n"
        f"📅 انقضا: {c['expiry_date']}\n"
        f"📶 ترافیک کل: {c['traffic_total']} گیگ\n"
        f"📉 مصرف شده: {c['traffic_used']} گیگ\n"
        f"📈 باقی‌مانده: {remaining} گیگ\n"
        "━━━━━━━━━━━━━━━"
        f"{config_block}"
    )
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="my_configs")]]),
        parse_mode="Markdown",
    )


# ─── Subscription ─────────────────────────────────────────────────────────────

async def sub_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("🟢 خرید سرور ویتوری",    callback_data="sub_type_vitori")],
        [InlineKeyboardButton("🔵 خرید سرور ایران گارد", callback_data="sub_type_iran_guard")],
        [InlineKeyboardButton("🌐 سرور اینترنشنال",      callback_data="sub_type_international")],
        [InlineKeyboardButton("🔙 بازگشت",               callback_data="main_menu")],
    ]
    await query.edit_message_text(
        "🛒 *خرید اشتراک*\n\nنوع سرور مورد نظر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return SUB_TYPE


def _packages_keyboard(server_key: str) -> InlineKeyboardMarkup:
    plans = PACKAGES[server_key]["plans"]
    buttons = [
        [InlineKeyboardButton(
            f"{p['label']} — {fmt_price(p['price'])}",
            callback_data=f"sub_pkg_{server_key}_{i}",
        )]
        for i, p in enumerate(plans)
    ]
    buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="sub_start_back")])
    return InlineKeyboardMarkup(buttons)


async def sub_type_vitori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["server_key"] = "vitori"
    pkg = PACKAGES["vitori"]
    await query.edit_message_text(
        f"{pkg['name']}\n💰 قیمت: {fmt_price(pkg['price_per_gb'])} به ازای هر گیگ\n\nپکیج مورد نظر را انتخاب کنید:",
        reply_markup=_packages_keyboard("vitori"),
        parse_mode="Markdown",
    )
    return SUB_PACKAGE


async def sub_type_iran_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["server_key"] = "iran_guard"
    pkg = PACKAGES["iran_guard"]
    await query.edit_message_text(
        f"{pkg['name']}\n💰 قیمت: {fmt_price(pkg['price_per_gb'])} به ازای هر گیگ\n\nپکیج مورد نظر را انتخاب کنید:",
        reply_markup=_packages_keyboard("iran_guard"),
        parse_mode="Markdown",
    )
    return SUB_PACKAGE


async def sub_type_international(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["server_key"] = "international"
    await query.edit_message_text(
        "🌐 *سرور اینترنشنال*\n\n"
        "قیمت این سرور توافقی است.\n"
        "لطفاً نام و شماره تماس خود را ارسال کنید تا ادمین با شما تماس بگیرد:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="sub_start_back")]]),
        parse_mode="Markdown",
    )
    return INTL_CONTACT


async def sub_start_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("🟢 خرید سرور ویتوری",    callback_data="sub_type_vitori")],
        [InlineKeyboardButton("🔵 خرید سرور ایران گارد", callback_data="sub_type_iran_guard")],
        [InlineKeyboardButton("🌐 سرور اینترنشنال",      callback_data="sub_type_international")],
        [InlineKeyboardButton("🔙 بازگشت",               callback_data="main_menu")],
    ]
    await query.edit_message_text(
        "🛒 *خرید اشتراک*\n\nنوع سرور مورد نظر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return SUB_TYPE


async def sub_package(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # callback: sub_pkg_<server_key>_<index>
    parts = query.data.split("_")
    # parts: ["sub", "pkg", server_key_part1, (server_key_part2?), index]
    # server_key may contain underscore (iran_guard) so reconstruct:
    pkg_index = int(parts[-1])
    server_key = "_".join(parts[2:-1])

    context.user_data["server_key"] = server_key
    plan = PACKAGES[server_key]["plans"][pkg_index]
    context.user_data["plan"] = plan

    user_id = update.effective_user.id
    wallet = get_wallet(user_id)
    server_name = PACKAGES[server_key]["name"]

    pay_buttons = []
    if wallet >= plan["price"]:
        pay_buttons.append([InlineKeyboardButton(
            f"💰 پرداخت از کیف پول (موجودی: {fmt_price(wallet)})",
            callback_data="sub_pay_wallet",
        )])
    pay_buttons.append([InlineKeyboardButton("💳 کارت به کارت", callback_data="sub_pay_card")])
    pay_buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"sub_back_pkgs_{server_key}")])

    text = (
        "🧾 *خلاصه سفارش*\n"
        "━━━━━━━━━━━━━━━\n"
        f"🖥 سرور: {server_name}\n"
        f"📊 پکیج: {plan['label']}\n"
        f"💰 مبلغ: {fmt_price(plan['price'])}\n"
        f"💼 موجودی کیف پول: {fmt_price(wallet)}\n"
        "━━━━━━━━━━━━━━━\n"
        "روش پرداخت را انتخاب کنید:"
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(pay_buttons), parse_mode="Markdown")
    return SUB_PAY


async def sub_back_to_packages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # callback: sub_back_pkgs_<server_key>
    server_key = "_".join(query.data.split("_")[3:])
    pkg = PACKAGES[server_key]
    await query.edit_message_text(
        f"{pkg['name']}\n\nپکیج مورد نظر را انتخاب کنید:",
        reply_markup=_packages_keyboard(server_key),
        parse_mode="Markdown",
    )
    return SUB_PACKAGE


async def sub_pay_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    plan = context.user_data.get("plan")
    server_key = context.user_data.get("server_key", "vitori")
    if not plan:
        await query.answer("خطا. لطفاً دوباره امتحان کنید.", show_alert=True)
        return ConversationHandler.END

    success = deduct_wallet(user.id, plan["price"])
    if not success:
        await query.answer("موجودی کیف پول کافی نیست.", show_alert=True)
        return SUB_PAY

    server_name = PACKAGES[server_key]["name"]
    order_id = create_order(user.id, server_name, plan["label"], plan["price"])

    await query.edit_message_text(
        "✅ *پرداخت موفق از کیف پول!*\n\n"
        f"🖥 سرور: {server_name}\n"
        f"📦 پکیج: {plan['label']}\n"
        f"💰 مبلغ کسر شده: {fmt_price(plan['price'])}\n"
        f"🆔 شماره سفارش: `{order_id}`\n\n"
        "سفارش شما ثبت شد. پس از تأیید ادمین، کانفیگ ارسال می‌شود. 🙏",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]]),
        parse_mode="Markdown",
    )
    await _notify_admin_order(context, user, order_id, server_name, plan, paid_by="wallet")
    context.user_data.clear()
    return ConversationHandler.END


async def sub_pay_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = context.user_data.get("plan")
    await query.edit_message_text(
        "💳 *پرداخت کارت به کارت*\n"
        "━━━━━━━━━━━━━━━\n"
        f"💰 مبلغ: *{fmt_price(plan['price'])}*\n\n"
        f"شماره کارت:\n`{CARD_NUMBER}`\n"
        f"به نام: *{CARD_HOLDER}*\n"
        "━━━━━━━━━━━━━━━\n"
        "پس از واریز، تصویر رسید را ارسال کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف", callback_data="main_menu")]]),
        parse_mode="Markdown",
    )
    return SUB_RECEIPT


async def sub_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    plan = context.user_data.get("plan")
    server_key = context.user_data.get("server_key", "vitori")

    # Guard: context may have been lost if bot restarted mid-conversation
    if not plan:
        await update.message.reply_text(
            "❌ اطلاعات سفارش شما یافت نشد.\n"
            "لطفاً دوباره از منوی اصلی اقدام کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]]),
        )
        return ConversationHandler.END

    server_name = PACKAGES[server_key]["name"]

    if not (update.message.photo or update.message.document):
        await update.message.reply_text("⚠️ لطفاً تصویر یا فایل رسید پرداخت را ارسال کنید.")
        return SUB_RECEIPT

    file_id = update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id
    order_id = create_order(user.id, server_name, plan["label"], plan["price"], file_id)

    await update.message.reply_text(
        "✅ *سفارش شما ثبت شد!*\n\n"
        f"🖥 سرور: {server_name}\n"
        f"📦 پکیج: {plan['label']}\n"
        f"🆔 شماره سفارش: `{order_id}`\n\n"
        "رسید دریافت شد. پس از تأیید ادمین، کانفیگ برای شما ارسال می‌شود. 🙏",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]]),
        parse_mode="Markdown",
    )
    await _notify_admin_order(context, user, order_id, server_name, plan, paid_by="card", receipt_msg=update.message)
    context.user_data.clear()
    return ConversationHandler.END


async def intl_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.text.strip()
    context.user_data["intl_contact"] = contact
    await update.message.reply_text(
        "🌐 *سرور اینترنشنال*\n\n"
        "اطلاعات تماس شما ثبت شد.\n"
        "آیا می‌خواهید پیش‌پرداختی ارسال کنید؟\n\n"
        f"💳 شماره کارت:\n`{CARD_NUMBER}`\n"
        f"به نام: *{CARD_HOLDER}*\n\n"
        "تصویر رسید را ارسال کنید یا دکمه زیر را بزنید:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ بدون پیش‌پرداخت", callback_data="intl_no_receipt")],
            [InlineKeyboardButton("❌ انصراف",           callback_data="main_menu")],
        ]),
        parse_mode="Markdown",
    )
    return INTL_RECEIPT


async def intl_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    contact = context.user_data.get("intl_contact", "—")
    file_id = None

    if update.message and (update.message.photo or update.message.document):
        file_id = update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id

    order_id = create_order(user.id, "اینترنشنال", "توافقی", 0, file_id)
    reply_text = (
        "✅ *درخواست شما ثبت شد!*\n\n"
        f"🆔 شماره سفارش: `{order_id}`\n\n"
        "ادمین به زودی با شما تماس می‌گیرد. 🙏"
    )
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منوی اصلی", callback_data="main_menu")]])

    if update.message:
        await update.message.reply_text(reply_text, reply_markup=back_kb, parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(reply_text, reply_markup=back_kb, parse_mode="Markdown")

    admin_msg = (
        f"🔔 *درخواست سرور اینترنشنال*\n\n"
        f"👤 نام: {user.first_name}\n"
        f"🆔 آیدی: `{user.id}`\n"
        f"👤 یوزر: @{user.username or '—'}\n"
        f"📞 تماس: {contact}\n"
        f"📎 رسید: {'✅ ارسال شده' if file_id else '❌ ندارد'}\n"
        f"🆔 سفارش: `{order_id}`"
    )
    await context.bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
    if file_id and update.message:
        if update.message.photo:
            await context.bot.send_photo(ADMIN_ID, file_id, caption=f"رسید سفارش #{order_id}")
        else:
            await context.bot.send_document(ADMIN_ID, file_id, caption=f"رسید سفارش #{order_id}")

    context.user_data.clear()
    return ConversationHandler.END


async def intl_no_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    update._message = None
    return await intl_receipt(update, context)


# ─── Wallet ──────────────────────────────────────────────────────────────────

async def wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    wallet = get_wallet(update.effective_user.id)
    await query.edit_message_text(
        f"💰 *شارژ کیف پول*\n\n"
        f"موجودی فعلی: *{fmt_price(wallet)}*\n\n"
        "مبلغ مورد نظر برای شارژ را به تومان وارد کنید:\n"
        "_(حداقل مبلغ: 10,000 تومان)_",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]),
        parse_mode="Markdown",
    )
    return WALLET_AMOUNT


async def wallet_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip().replace(",", "").replace("،", "").replace(" ", "")
    if not raw.isdigit():
        await update.message.reply_text(
     
