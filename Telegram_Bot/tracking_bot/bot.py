import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)
from config import BOT_TOKEN, PROXY_URL
from api_client import OneCClient

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

onec = OneCClient()

STATUS_EMOJI = {
    "создан": "📝", "принят": "✅", "на складе": "🏭",
    "передан курьеру": "🚚", "в пути": "🛣️",
    "в городе назначения": "🏙️", "на пункте выдачи": "📦",
    "доставлен": "🎉", "отменён": "❌", "возврат": "↩️",
}

def status_emoji(s: str) -> str:
    sl = str(s).lower()
    for k, v in STATUS_EMOJI.items():
        if k in sl:
            return v
    return "📌"

def fmt_date(d: str) -> str:
    if not d:
        return ""
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%d.%m.%Y")
    except Exception:
        return d

def fmt_dt(d: str) -> str:
    if not d:
        return ""
    try:
        return datetime.strptime(d, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y в %H:%M")
    except Exception:
        return d

def build_message(d: dict) -> str:
    """Форматирование карточки заказа под стиль обработки из 1С"""
    tn = d.get("trackNumber", "")
    st = d.get("status", "Неизвестно")
    emoji = status_emoji(st)

    lines = [
        "══════════════════════════",
        f"📦 <b>ЗАКАЗ {tn}</b>",
        "══════════════════════════",
        "",
        f"📅 <b>Дата создания:</b> {fmt_date(d.get('orderDate'))}",
        f"{emoji} <b>Текущий статус:</b> {st}",
        f"💳 <b>Оплата:</b> {d.get('statusPayment', '-')}",
        "",
        f"🗺 <b>Маршрут:</b> {d.get('from', '')} ➔ {d.get('to', '')}",
        f"🚚 <b>Тип доставки:</b> {d.get('deliveryType', '-')}",
    ]

    if d.get("address"):
        lines.append(f"🏠 <b>Адрес доставки:</b> {d['address']}")
    if d.get("pvz"):
        lines.append(f"📍 <b>Текущий ПВЗ:</b> {d['pvz']}")
    if d.get("sc"):
        lines.append(f"🏭 <b>Текущий СЦ:</b> {d['sc']}")

    lines.extend([
        "",
        f"👤 <b>Отправитель:</b> {d.get('sender', '-')}",
        f"👤 <b>Получатель:</b> {d.get('recipient', '-')}",
        "",
        f"📊 <b>Детали:</b> {d.get('places', 0)} мест(а) | {d.get('weight', 0)} кг | {d.get('cost', 0)} руб.",
    ])

    if d.get("planDate"):
        lines.append(f"⏱ <b>План. дата:</b> {fmt_date(d['planDate'])}")
    if d.get("factDate"):
        lines.append(f"✅ <b>Факт. дата:</b> {fmt_date(d['factDate'])}")

    # История статусов
    sts = d.get("statuses", [])
    if sts:
        lines.extend([
            "",
            "──────────────────────────",
            "📜 <b>ИСТОРИЯ СТАТУСОВ</b>",
            "──────────────────────────",
            ""
        ])
        for i, s in enumerate(sts):
            is_last = (i == len(sts) - 1)
            name = f"<b>{s['status']}</b>" if is_last else s['status']
            lines.append(f"  {status_emoji(s['status'])} {name}")
            lines.append(f"     🕐 {fmt_dt(s['datetime'])}")
            if s.get("comment"):
                lines.append(f"     💬 <i>{s['comment']}</i>")
            if not is_last:
                lines.append("  │")

    lines.extend(["", "══════════════════════════"])
    return "\n".join(lines)


# ── Обработчики ──

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📦 Отследить заказ", callback_data="track")],
    ])
    await update.message.reply_text(
        "🚚 <b>Служба отслеживания доставок</b>\n\n"
        "Здесь вы можете узнать точный статус вашей посылки.",
        reply_markup=kb, parse_mode="HTML",
    )

async def cmd_track(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("⚠️ Укажите трек-номер: /track <code>ТРЕК_НОМЕР</code>", parse_mode="HTML")
        return
    await do_track(update.message, ctx.args[0].strip())

async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if 1 <= len(txt) <= 50:
        await do_track(update.message, txt)

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "track":
        await q.message.reply_text("📦 Отправьте трек-номер заказа:", parse_mode="HTML")
    elif q.data.startswith("refresh_"):
        await do_track(q.message, q.data.replace("refresh_", ""), edit=True)

async def do_track(msg, track: str, edit=False):
    send = msg.edit_text if edit else msg.reply_text
    loading = await send(f"🔍 Ищу заказ <code>{track}</code>...", parse_mode="HTML")

    res = await onec.get_order_tracking(track)

    if res["success"]:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Обновить", callback_data=f"refresh_{track}")
        ]])
        text = build_message(res["data"])
        if edit:
            text += f"\n\n🕐 <i>Обновлено {datetime.now():%H:%M:%S}</i>"
        await loading.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        errs = {
            "not_found": f"❌ Заказ с трек-номером <code>{track}</code> не найден.",
            "connection_error": "⚠️ Не удалось подключиться к серверу 1С.",
            "timeout": "⏳ 1С не ответила вовремя.",
            "auth_error": "🔐 Ошибка авторизации в 1С.",
        }
        await loading.edit_text(errs.get(res.get("error"), f"⚠️ {res.get('message')}"), parse_mode="HTML")


def main():
    from telegram.request import HTTPXRequest

    if PROXY_URL:
        request = HTTPXRequest(
            proxy=PROXY_URL,
            connect_timeout=30.0,
            read_timeout=30.0,
            write_timeout=30.0,
            pool_timeout=30.0,
        )
        app = Application.builder().token(BOT_TOKEN).request(request).get_updates_request(request).build()
        logger.info(f"🌐 Прокси: {PROXY_URL}")
    else:
        app = Application.builder().token(BOT_TOKEN).build()
        logger.info("🌐 Прямое подключение")

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("track", cmd_track))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    logger.info("🚀 Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()