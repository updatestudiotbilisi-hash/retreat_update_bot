"""
╔══════════════════════════════════════════════════════════════╗
║          UPDATE CAMP BOT — сбор заявок на кэмп              ║
║          Wellness Camp · Family Camp · 2026                  ║
╠══════════════════════════════════════════════════════════════╣
║  ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ:                                       ║
║  TELEGRAM_TOKEN     — токен бота из BotFather                ║
║  MANAGER_GROUP_ID   — chat_id группы менеджеров              ║
║  PORT               — порт healthcheck для web-деплоя        ║
║
║                                                              ║
║  Бот умеет:                                                  ║
║  ✅ Рассказывать о двух кэмпах с полным описанием            ║
║  📸 Показывать номера с фотографиями                         ║
║  💰 Озвучивать цены и опции                                  ║
║  📝 Принимать заявки пошагово                                ║
║  📨 Слать красивые карточки лидов в группу менеджеров        ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import threading
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes
)

# ─── CONFIG ───────────────────────────────────────────────────
def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def start_healthcheck_server() -> None:
    """Поднимает простой HTTP healthcheck для web-деплоя."""
    port = os.getenv("PORT")
    if not port:
        return

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    server = ThreadingHTTPServer(("0.0.0.0", int(port)), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Healthcheck server is listening on port {port}")


TELEGRAM_TOKEN = require_env("TELEGRAM_TOKEN")

try:
    MANAGER_GROUP_ID = int(require_env("MANAGER_GROUP_ID"))
except ValueError as exc:
    raise RuntimeError("MANAGER_GROUP_ID must be an integer chat_id") from exc

# ─── STATES ───────────────────────────────────────────────────
S_MAIN      = "main"
S_WELLNESS  = "wellness"
S_FAMILY    = "family"
S_ROOMS_W   = "rooms_w"
S_ROOMS_F   = "rooms_f"

# Шаги формы заявки
S_A_NAME    = "a_name"
S_A_CONTACT = "a_contact"
S_A_PEOPLE  = "a_people"
S_A_ROOM    = "a_room"
S_A_DATES   = "a_dates"      # только Family Camp
S_A_OPTIONS = "a_options"
S_A_COMMENT = "a_comment"

# ─── КОНТЕНТ ──────────────────────────────────────────────────
WELLNESS_INTRO = (
    "🏕 *WELLNESS CAMP*\n"
    "📅 5–10 июня 2026 · 5 ночей\n"
    "📍 Edis Dacha, горы Грузии — 2 часа от Тбилиси\n\n"
    "Выезд в горы небольшой группой: массажи, баня, хайкинг, "
    "бассейн на краю каньона, off-road и вечера у костра. "
    "Весь отель только для нас — без посторонних.\n\n"
    "_Максимум 20 человек — места ограничены._"
)

FAMILY_INTRO = (
    "👨‍👩‍👧 *UPDATE FAMILY CAMP*\n"
    "📅 22–26 мая · 5–9 июня · Июль · Август\n"
    "📍 Edis Dacha, горы Грузии — 2 часа от Тбилиси\n\n"
    "5 дней движения и восстановления для семей с детьми. "
    "Мануальный терапевт, 3 массажа каждому взрослому, "
    "телесный терапевт, вожатый для детей каждый день, "
    "сауна, бассейн и горный воздух.\n\n"
    "_Максимум 20 человек (включая детей) — камерно и своё._"
)

WELLNESS_PROGRAM = (
    "📋 *Программа Wellness Camp*\n\n"
    "*День 1 · 5 июня — Тбилиси*\n"
    "Встреча в аэропорту, заселение в Hilton. "
    "Ужин и вечерняя прогулка по городу.\n\n"
    "*День 2 · 6 июня — В горы*\n"
    "Утро: массажи или чекап в A-clinic (по желанию). "
    "Переезд на базу по живописной горной дороге. "
    "Вечер: сауна, бассейн, барбекю у костра.\n\n"
    "*День 3 · 7 июня — Off-road*\n"
    "Зарядка у каньона. Off-road — каждый за рулём. "
    "Пикник с видом на горы. "
    "Вечер: массажи, сауна, костёр и гитара.\n\n"
    "*День 4 · 8 июня — Окрестности*\n"
    "Каньон, древние храмы и сильные места рядом с базой. "
    "Массажи на базе. Вечер: покер-турнир или кино-клуб под небом.\n\n"
    "*День 5 · 9 июня — Хайк и дегустация*\n"
    "Хайкинг с обедом на маршруте. "
    "Возвращение, сауна, винная дегустация. "
    "Финальный вечер у костра в высокогорье.\n\n"
    "*День 6 · 10 июня — Домой*\n"
    "Завтрак, сборы, трансфер в Тбилиси. "
    "Если время позволяет — обед по дороге."
)

FAMILY_PROGRAM = (
    "📋 *Программа Family Camp*\n\n"
    "*День 1 — Тбилиси*\n"
    "Встреча всех семей в аэропорту, Hilton Tbilisi. "
    "Ужин, прогулка, дети знакомятся друг с другом.\n\n"
    "*День 2 — В горы*\n"
    "Взрослые: чекап в A-clinic или массажи в UPDATE. "
    "Дети: парк Ваке с вожатым — прогулка, игры, зарядка. "
    "Общий переезд на базу. Вечер: заселение, бассейн, сауна, барбекю.\n\n"
    "*День 3 — Тело и движение*\n"
    "Зарядка у каньона — взрослые и дети вместе. "
    "Индивидуальные сессии с мануальным терапевтом (и для детей). "
    "Массажи по расписанию. Вечер: off-road или хайкинг, костёр.\n\n"
    "*День 4 — Восстановление*\n"
    "Зарядка, бассейн, завтрак в своём темпе. "
    "Практики с телесным терапевтом — для взрослых и детей. "
    "Пикник у реки. Последний костёр и сауна.\n\n"
    "*День 5 — Возвращение*\n"
    "Зарядка, неторопливый завтрак, прогулка над каньоном. "
    "Трансфер в Тбилиси. Для вечерних рейсов — время в городе."
)

WELLNESS_INCLUDED = (
    "🎯 *Что входит в стоимость Wellness Camp*\n\n"
    "✅ Трансферы: Тбилиси ↔ база + все выезды по Грузии\n"
    "✅ Питание на всю поездку: завтраки, обеды, ужины, барбекю\n"
    "✅ Массажи на локации\n"
    "✅ Сауна в скале и бассейн на краю каньона\n"
    "✅ Программа: хайкинг, пикники, костёр, покер, кино-клуб\n"
    "✅ Организация и сопровождение\n\n"
    "❌ *Не входит:*\n"
    "— Перелёт до Тбилиси и личные расходы\n"
    "— Страховка на время поездки\n"
    "— Off-road тур (+130 $ / чел)\n"
    "— Чекап в A-clinic (+180 $ / чел)\n\n"
    "_До 4 мая действует ранняя цена на все номера._"
)

FAMILY_INCLUDED = (
    "🎯 *Что входит в стоимость Family Camp*\n\n"
    "✅ Трансферы: Тбилиси ↔ Edis Dacha + все выезды\n"
    "✅ Питание: завтраки, обеды, ужины, барбекю\n"
    "✅ 3 массажа для каждого взрослого\n"
    "✅ Сессии с мануальным и телесным терапевтом\n"
    "✅ Сауна, бассейн и все общие пространства\n"
    "✅ Вожатый для детей каждый день\n"
    "✅ Программа: зарядки, хайкинг, пикники, костры\n"
    "✅ Организация и логистика под ключ\n\n"
    "❌ *Не входит:*\n"
    "— Чекап в A-clinic (+180 $ / чел, есть педиатры)\n"
    "— Off-road тур (+130 $ / чел, по желанию)\n"
    "— Трансфер аэропорт ↔ Тбилиси\n"
    "— Перелёт до Тбилиси и личные расходы\n"
    "— Страховка"
)

WELLNESS_FAQ = (
    "❓ *Частые вопросы — Wellness Camp*\n\n"
    "*Кто может поехать?*\n"
    "Все, кто хочет перезагрузиться. Можно одному, вдвоём, с друзьями.\n\n"
    "*Можно ехать без пары?*\n"
    "Да, это нормальный сценарий. Берёте номер целиком или "
    "договариваемся о совместном размещении.\n\n"
    "*Как добраться?*\n"
    "Прилетаете в Тбилиси — дальше всю логистику берём на себя. "
    "Есть прямые рейсы из многих городов.\n\n"
    "*Обязательна ли вся программа?*\n"
    "Есть активности, которые хочется прожить вместе — "
    "но это не армейский тайминг, внутри есть воздух.\n\n"
    "*Когда лучше вписываться?*\n"
    "До 4 мая — действует ранняя цена. После — дороже. "
    "Мест всего 14 — не тянем."
)

FAMILY_FAQ = (
    "❓ *Частые вопросы — Family Camp*\n\n"
    "*Кто может поехать?*\n"
    "Семьи с детьми, пары, друзья семьями. Без детей тоже ок.\n\n"
    "*С какого возраста берёте детей?*\n"
    "С любого. Для детей до 12 лет уточняем детали при заявке.\n\n"
    "*Что с детьми во время массажей?*\n"
    "С ними вожатый — программа, игры, активности. Безопасно и весело.\n\n"
    "*Есть детский массаж?*\n"
    "Да, наши специалисты работают с детьми.\n\n"
    "*Как добраться?*\n"
    "Летите в Тбилиси, встречаем в аэропорту — "
    "дальше всё организуем сами.\n\n"
    "*Можно ехать в июле или августе?*\n"
    "Открыта предзапись. Оставьте заявку — узнаете о датах первыми."
)

FAMILY_DATES_TEXT = (
    "📅 *Даты заездов Family Camp*\n\n"
    "🗓 *22–26 мая* — Основной майский заезд\n"
    "Полная программа со всеми активностями.\n\n"
    "🗓 *5–9 июня* — Июньский заезд\n"
    "Для семей, которым удобнее в начале лета.\n\n"
    "🗓 *Июль* — Открыта предзапись\n"
    "Оставьте заявку — сообщим о датах первыми.\n\n"
    "🗓 *Август* — Открыта предзапись\n"
    "Для тех, кто планирует отпуск заранее.\n\n"
    "_Максимум 20 человек на заезд — чем раньше, тем лучше._"
)

# ─── ДАННЫЕ ПО НОМЕРАМ ────────────────────────────────────────
WELLNESS_ROOMS = [
    {
        "label": "🌄 Panorama",
        "photo": "https://update-club.com/phystech/assets/panorama_1.webp",
        "caption": (
            "🌄 *Panorama* — 2 номера · отдельное здание\n\n"
            "Лучший вид на горы, своя ванная комната. "
            "Максимальная приватность — отдельное здание вдали от основного.\n\n"
            "💰 *1 765 $* / чел при заселении вдвоём\n"
            "💰 *2 240 $* — номер целиком на 1 человека\n\n"
            "_⏰ До 4 мая — ранняя цена. После дороже._"
        ),
    },
    {
        "label": "🏠 House 1936 Double King",
        "photo": "https://update-club.com/phystech/assets/old_money_double_king_1.webp",
        "caption": (
            "🏠 *House 1936 Double King* — 2 номера · дом 1936 года\n\n"
            "Двухъярусный номер в старинном доме. "
            "Полноценный санузел и свой балкон. "
            "Идеально для двух друзей или коллег.\n\n"
            "💰 *1 610 $* / чел\n\n"
            "_⏰ До 4 мая — ранняя цена._"
        ),
    },
    {
        "label": "🛏 House 1936 Twin",
        "photo": "https://update-club.com/phystech/assets/old_money_twin.webp",
        "caption": (
            "🛏 *House 1936 Twin* — 1 номер · дом 1936 года\n\n"
            "Две отдельные кровати — по запросу объединяем в double. "
            "Санузел и балкон с видом.\n\n"
            "💰 *1 530 $* / чел при заселении вдвоём\n"
            "💰 *1 770 $* — номер целиком на 1\n\n"
            "_⏰ До 4 мая — ранняя цена._"
        ),
    },
    {
        "label": "👑 House 1936 King",
        "photo": "https://update-club.com/phystech/assets/old_money_king_1.webp",
        "caption": (
            "👑 *House 1936 King* — 1 номер · дом 1936 года\n\n"
            "King-кровать (или twin по запросу). "
            "Санузел и балкон.\n\n"
            "💰 *1 530 $* / чел при заселении вдвоём\n"
            "💰 *1 770 $* — номер целиком на 1\n\n"
            "_⏰ До 4 мая — ранняя цена._"
        ),
    },
    {
        "label": "🏡 Standard Twin",
        "photo": "https://update-club.com/phystech/assets/standart.webp",
        "caption": (
            "🏡 *Standard Twin* — 1 номер · новый дом\n\n"
            "Две кровати, по запросу объединяем. "
            "Санузел. Самый доступный вариант в поездке.\n\n"
            "💰 *1 480 $* / чел при заселении вдвоём\n"
            "💰 *1 670 $* — номер целиком на 1\n\n"
            "_⏰ До 4 мая — ранняя цена._"
        ),
    },
]

FAMILY_ROOMS = [
    {
        "label": "🌄 Panorama",
        "photo": "https://update-club.com/phystech/assets/panorama_1.webp",
        "caption": (
            "🌄 *Panorama* — 2 номера · отдельное здание\n\n"
            "Лучший вид на горы, своя ванная. "
            "Удобно для двух семей — оба номера рядом в отдельном здании.\n\n"
            "💰 *1 650 $* / чел\n"
            "💰 *3 300 $* — весь номер (2 гостя)\n\n"
            "_Включено: проживание, питание, 3 массажа, специалисты, программа._"
        ),
    },
    {
        "label": "🏠 House 1936 Double King",
        "photo": "https://update-club.com/phystech/assets/old_money_double_king_1.webp",
        "caption": (
            "🏠 *House 1936 Double King* — семейный · до 4 гостей\n\n"
            "Двухъярусная планировка: большая кровать для родителей "
            "и отдельные места для детей. Санузел и балкон.\n\n"
            "💰 *1 360 $* / чел (при 3 гостях)\n"
            "💰 *4 080 $* — весь номер (3 гостя)\n"
            "💬 _4-й гость: доплата 1 023 $ (только программа)_\n\n"
            "_Включено: проживание, питание, 3 массажа, специалисты, программа._"
        ),
    },
    {
        "label": "🛏 House 1936 Twin",
        "photo": "https://update-club.com/phystech/assets/old_money_twin.webp",
        "caption": (
            "🛏 *House 1936 Twin* — до 2 гостей\n\n"
            "Две кровати. Отлично для взрослого с ребёнком "
            "или для двоих взрослых. Санузел и балкон.\n\n"
            "💰 *1 420 $* / чел\n"
            "💰 *2 840 $* — весь номер (2 гостя)\n\n"
            "_Включено: проживание, питание, 3 массажа, специалисты, программа._"
        ),
    },
    {
        "label": "👑 House 1936 King",
        "photo": "https://update-club.com/phystech/assets/old_money_king_1.webp",
        "caption": (
            "👑 *House 1936 King* — до 2 гостей\n\n"
            "Большая двуспальная кровать для пары. "
            "Рядом на том же этаже — Twin для детей. "
            "Санузел и балкон.\n\n"
            "💰 *1 420 $* / чел\n"
            "💰 *2 840 $* — весь номер (2 гостя)\n\n"
            "_Включено: проживание, питание, 3 массажа, специалисты, программа._"
        ),
    },
    {
        "label": "🏡 Standard Twin",
        "photo": "https://update-club.com/phystech/assets/standart.webp",
        "caption": (
            "🏡 *Standard Twin* — новый дом · до 2 гостей\n\n"
            "Две отдельные кровати. "
            "Можно взять 2 номера рядом — вся семья под одной крышей. "
            "Санузел.\n\n"
            "💰 *1 380 $* / чел\n"
            "💰 *2 760 $* — весь номер (2 гостя)\n\n"
            "_Включено: проживание, питание, 3 массажа, специалисты, программа._"
        ),
    },
]

# ─── КЛАВИАТУРЫ ───────────────────────────────────────────────
def mk(rows):
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

MAIN_KB = mk([
    ["🏕 WELLNESS CAMP", "👨‍👩‍👧 FAMILY CAMP"],
])

WELLNESS_MENU_KB = mk([
    ["📋 Программа", "🛏 Номера и цены"],
    ["🎯 Что входит", "❓ Частые вопросы"],
    ["✅ Оставить заявку"],
    ["🔙 К выбору кэмпа"],
])

FAMILY_MENU_KB = mk([
    ["📋 Программа", "🛏 Номера и цены"],
    ["📅 Даты заездов", "🎯 Что входит"],
    ["❓ Частые вопросы", "✅ Оставить заявку"],
    ["🔙 К выбору кэмпа"],
])

BACK_KB = mk([["🔙 Назад"]])

SKIP_BACK_KB = mk([["Пропустить"], ["🔙 Назад"]])

OPTIONS_KB = mk([
    ["Off-road (+130 $/чел)"],
    ["Чекап A-clinic (+180 $/чел)"],
    ["Off-road + Чекап"],
    ["Без доп. опций"],
])

DATES_KB = mk([
    ["22–26 мая"],
    ["5–9 июня"],
    ["Предзапись на июль"],
    ["Предзапись на август"],
    ["🔙 Назад"],
])

def rooms_nav_kb(idx: int, total: int) -> ReplyKeyboardMarkup:
    nav = []
    if idx > 0:
        nav.append("◀ Предыдущий")
    if idx < total - 1:
        nav.append("Следующий ▶")
    rows = []
    if nav:
        rows.append(nav)
    rows.append(["✅ Оставить заявку"])
    rows.append(["🔙 Назад"])
    return mk(rows)

def room_choose_kb(rooms: list) -> ReplyKeyboardMarkup:
    rows = [[r["label"]] for r in rooms]
    rows.append(["Ещё не определился(лась)"])
    rows.append(["🔙 Назад"])
    return mk(rows)

# ─── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ──────────────────────────────────
def get_state(ctx: ContextTypes.DEFAULT_TYPE) -> str:
    return ctx.user_data.get("state", S_MAIN)

def set_state(ctx: ContextTypes.DEFAULT_TYPE, s: str):
    ctx.user_data["state"] = s

def get_camp(ctx: ContextTypes.DEFAULT_TYPE) -> str:
    return ctx.user_data.get("camp", "wellness")

async def show_room_photo(update: Update, rooms: list, idx: int):
    """Отправляет фото номера с описанием и навигацией."""
    room = rooms[idx]
    total = len(rooms)
    caption = room["caption"] + f"\n\n_Номер {idx + 1} из {total}_"
    try:
        await update.message.reply_photo(
            photo=room["photo"],
            caption=caption,
            parse_mode="Markdown",
            reply_markup=rooms_nav_kb(idx, total),
        )
    except Exception:
        # Если фото не загрузилось — отправляем текст
        await update.message.reply_text(
            caption,
            parse_mode="Markdown",
            reply_markup=rooms_nav_kb(idx, total),
        )

async def send_lead(ctx: ContextTypes.DEFAULT_TYPE, form: dict, user):
    """Формирует и отправляет карточку заявки менеджерам."""
    camp_emoji = "🏕" if form.get("camp") == "wellness" else "👨‍👩‍👧"
    camp_name  = "WELLNESS CAMP" if form.get("camp") == "wellness" else "FAMILY CAMP"

    def safe(value: object) -> str:
        return escape(str(value or "—"))

    lines = [
        f"<b>🔔 Новая заявка — {camp_emoji} {camp_name}</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"<b>👤 Имя:</b> {safe(form.get('name'))}",
        f"<b>📱 Контакт:</b> {safe(form.get('contact'))}",
        f"<b>👥 Состав/количество:</b> {safe(form.get('people'))}",
        f"<b>🛏 Номер:</b> {safe(form.get('room'))}",
    ]

    if form.get("camp") == "family" and form.get("dates"):
        lines.append(f"<b>📅 Даты:</b> {safe(form.get('dates'))}")

    lines.append(f"<b>➕ Опции:</b> {safe(form.get('options'))}")

    if form.get("comment"):
        lines.append(f"<b>💬 Комментарий:</b> {safe(form.get('comment'))}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    tg_link = (
        f"@{escape(user.username)}"
        if user.username
        else f'<a href="tg://user?id={user.id}">написать</a>'
    )
    lines.append(f"<b>🔗 Telegram:</b> {tg_link}")
    lines.append(f"<b>🆔 User ID:</b> <code>{user.id}</code>")
    lines.append(escape(datetime.now().strftime('%d.%m.%Y  %H:%M')))

    message_text = "\n".join(lines)
    candidate_chat_ids = [MANAGER_GROUP_ID]

    # В Telegram у supergroup/chat id для Bot API часто имеют формат -100...
    manager_group_id_str = str(MANAGER_GROUP_ID)
    if MANAGER_GROUP_ID < 0 and not manager_group_id_str.startswith("-100"):
        candidate_chat_ids.append(int(f"-100{abs(MANAGER_GROUP_ID)}"))

    last_error = None
    for chat_id in candidate_chat_ids:
        try:
            await ctx.bot.send_message(
                chat_id,
                message_text,
                parse_mode="HTML",
            )
            return
        except Exception as exc:
            print(f"Ошибка отправки лида в chat_id={chat_id}: {exc}")
            last_error = exc

    if last_error:
        raise last_error

# ─── ОБРАБОТЧИКИ ──────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    set_state(ctx, S_MAIN)
    await update.message.reply_text(
        "Привет! 👋\n\n"
        "Это бот для записи на кэмпы *UPDATE* в горах Грузии.\n\n"
        "Здесь вы можете:\n"
        "• Узнать о программе и ценах\n"
        "• Посмотреть варианты номеров с фото\n"
        "• Оставить заявку за 2 минуты\n\n"
        "Выберите кэмп 👇",
        parse_mode="Markdown",
        reply_markup=MAIN_KB,
    )

async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    s    = get_state(ctx)

    # ── Глобальные команды ────────────────────────────────────
    if text in ("🔙 К выбору кэмпа", "/menu"):
        ctx.user_data.clear()
        set_state(ctx, S_MAIN)
        await update.message.reply_text("Выберите кэмп 👇", reply_markup=MAIN_KB)
        return

    # ── ГЛАВНЫЙ ЭКРАН: выбор кэмпа ────────────────────────────
    if s == S_MAIN:
        if text == "🏕 WELLNESS CAMP":
            ctx.user_data["camp"] = "wellness"
            set_state(ctx, S_WELLNESS)
            await update.message.reply_text(
                WELLNESS_INTRO, parse_mode="Markdown", reply_markup=WELLNESS_MENU_KB
            )
        elif text == "👨‍👩‍👧 FAMILY CAMP":
            ctx.user_data["camp"] = "family"
            set_state(ctx, S_FAMILY)
            await update.message.reply_text(
                FAMILY_INTRO, parse_mode="Markdown", reply_markup=FAMILY_MENU_KB
            )
        else:
            await update.message.reply_text("Выберите кэмп 👇", reply_markup=MAIN_KB)
        return

    # ── WELLNESS МЕНЮ ─────────────────────────────────────────
    if s == S_WELLNESS:
        if text == "📋 Программа":
            await update.message.reply_text(
                WELLNESS_PROGRAM, parse_mode="Markdown", reply_markup=WELLNESS_MENU_KB
            )
        elif text == "🛏 Номера и цены":
            ctx.user_data["room_idx"] = 0
            set_state(ctx, S_ROOMS_W)
            await show_room_photo(update, WELLNESS_ROOMS, 0)
        elif text == "🎯 Что входит":
            await update.message.reply_text(
                WELLNESS_INCLUDED, parse_mode="Markdown", reply_markup=WELLNESS_MENU_KB
            )
        elif text == "❓ Частые вопросы":
            await update.message.reply_text(
                WELLNESS_FAQ, parse_mode="Markdown", reply_markup=WELLNESS_MENU_KB
            )
        elif text == "✅ Оставить заявку":
            ctx.user_data["form"] = {"camp": "wellness"}
            set_state(ctx, S_A_NAME)
            await update.message.reply_text(
                "Оформляем заявку на *Wellness Camp* 🏕\n\n"
                "Как вас зовут?",
                parse_mode="Markdown",
                reply_markup=BACK_KB,
            )
        else:
            await update.message.reply_text("Выберите раздел 👇", reply_markup=WELLNESS_MENU_KB)
        return

    # ── FAMILY МЕНЮ ───────────────────────────────────────────
    if s == S_FAMILY:
        if text == "📋 Программа":
            await update.message.reply_text(
                FAMILY_PROGRAM, parse_mode="Markdown", reply_markup=FAMILY_MENU_KB
            )
        elif text == "🛏 Номера и цены":
            ctx.user_data["room_idx"] = 0
            set_state(ctx, S_ROOMS_F)
            await show_room_photo(update, FAMILY_ROOMS, 0)
        elif text == "📅 Даты заездов":
            await update.message.reply_text(
                FAMILY_DATES_TEXT, parse_mode="Markdown", reply_markup=FAMILY_MENU_KB
            )
        elif text == "🎯 Что входит":
            await update.message.reply_text(
                FAMILY_INCLUDED, parse_mode="Markdown", reply_markup=FAMILY_MENU_KB
            )
        elif text == "❓ Частые вопросы":
            await update.message.reply_text(
                FAMILY_FAQ, parse_mode="Markdown", reply_markup=FAMILY_MENU_KB
            )
        elif text == "✅ Оставить заявку":
            ctx.user_data["form"] = {"camp": "family"}
            set_state(ctx, S_A_NAME)
            await update.message.reply_text(
                "Оформляем заявку на *Family Camp* 👨‍👩‍👧\n\n"
                "Как вас зовут?",
                parse_mode="Markdown",
                reply_markup=BACK_KB,
            )
        else:
            await update.message.reply_text("Выберите раздел 👇", reply_markup=FAMILY_MENU_KB)
        return

    # ── ПРОСМОТР НОМЕРОВ: WELLNESS ────────────────────────────
    if s == S_ROOMS_W:
        idx   = ctx.user_data.get("room_idx", 0)
        total = len(WELLNESS_ROOMS)

        if text == "◀ Предыдущий":
            idx = max(0, idx - 1)
            ctx.user_data["room_idx"] = idx
            await show_room_photo(update, WELLNESS_ROOMS, idx)
        elif text == "Следующий ▶":
            idx = min(total - 1, idx + 1)
            ctx.user_data["room_idx"] = idx
            await show_room_photo(update, WELLNESS_ROOMS, idx)
        elif text == "✅ Оставить заявку":
            # Предзаполняем выбранный номер
            ctx.user_data["form"] = {
                "camp": "wellness",
                "room": WELLNESS_ROOMS[idx]["label"],
            }
            set_state(ctx, S_A_NAME)
            await update.message.reply_text(
                f"Выбран номер: *{WELLNESS_ROOMS[idx]['label']}* ✓\n\n"
                "Как вас зовут?",
                parse_mode="Markdown",
                reply_markup=BACK_KB,
            )
        elif text == "🔙 Назад":
            set_state(ctx, S_WELLNESS)
            await update.message.reply_text(
                WELLNESS_INTRO, parse_mode="Markdown", reply_markup=WELLNESS_MENU_KB
            )
        else:
            await show_room_photo(update, WELLNESS_ROOMS, idx)
        return

    # ── ПРОСМОТР НОМЕРОВ: FAMILY ──────────────────────────────
    if s == S_ROOMS_F:
        idx   = ctx.user_data.get("room_idx", 0)
        total = len(FAMILY_ROOMS)

        if text == "◀ Предыдущий":
            idx = max(0, idx - 1)
            ctx.user_data["room_idx"] = idx
            await show_room_photo(update, FAMILY_ROOMS, idx)
        elif text == "Следующий ▶":
            idx = min(total - 1, idx + 1)
            ctx.user_data["room_idx"] = idx
            await show_room_photo(update, FAMILY_ROOMS, idx)
        elif text == "✅ Оставить заявку":
            ctx.user_data["form"] = {
                "camp": "family",
                "room": FAMILY_ROOMS[idx]["label"],
            }
            set_state(ctx, S_A_NAME)
            await update.message.reply_text(
                f"Выбран номер: *{FAMILY_ROOMS[idx]['label']}* ✓\n\n"
                "Как вас зовут?",
                parse_mode="Markdown",
                reply_markup=BACK_KB,
            )
        elif text == "🔙 Назад":
            set_state(ctx, S_FAMILY)
            await update.message.reply_text(
                FAMILY_INTRO, parse_mode="Markdown", reply_markup=FAMILY_MENU_KB
            )
        else:
            await show_room_photo(update, FAMILY_ROOMS, idx)
        return

    # ─────────────────────────────────────────────────────────
    # ФОРМА ЗАЯВКИ
    # ─────────────────────────────────────────────────────────
    c = get_camp(ctx)

    # ── Кнопка «Назад» внутри формы ──────────────────────────
    if text == "🔙 Назад":
        if s == S_A_NAME:
            set_state(ctx, S_WELLNESS if c == "wellness" else S_FAMILY)
            kb_menu = WELLNESS_MENU_KB if c == "wellness" else FAMILY_MENU_KB
            await update.message.reply_text("Выберите раздел 👇", reply_markup=kb_menu)

        elif s == S_A_CONTACT:
            set_state(ctx, S_A_NAME)
            await update.message.reply_text("Как вас зовут?", reply_markup=BACK_KB)

        elif s == S_A_PEOPLE:
            set_state(ctx, S_A_CONTACT)
            await update.message.reply_text(
                "Укажите ваш Telegram или телефон:", reply_markup=BACK_KB
            )

        elif s == S_A_ROOM:
            set_state(ctx, S_A_PEOPLE)
            rooms = WELLNESS_ROOMS if c == "wellness" else FAMILY_ROOMS
            prompt = (
                "Сколько человек едет?" if c == "wellness"
                else "Расскажите про состав группы:"
            )
            await update.message.reply_text(prompt, reply_markup=BACK_KB)

        elif s == S_A_DATES:
            set_state(ctx, S_A_ROOM)
            rooms = FAMILY_ROOMS
            await update.message.reply_text(
                "Какой номер вас интересует?",
                reply_markup=room_choose_kb(rooms),
            )

        elif s == S_A_OPTIONS:
            if c == "family":
                set_state(ctx, S_A_DATES)
                await update.message.reply_text("Выберите даты:", reply_markup=DATES_KB)
            else:
                set_state(ctx, S_A_ROOM)
                await update.message.reply_text(
                    "Какой номер вас интересует?",
                    reply_markup=room_choose_kb(WELLNESS_ROOMS),
                )

        elif s == S_A_COMMENT:
            set_state(ctx, S_A_OPTIONS)
            await update.message.reply_text(
                "Хотите добавить опции?", reply_markup=OPTIONS_KB
            )
        return

    # ── Шаг 1: Имя ───────────────────────────────────────────
    if s == S_A_NAME:
        ctx.user_data["form"]["name"] = text
        set_state(ctx, S_A_CONTACT)
        first_name = text.split()[0]
        await update.message.reply_text(
            f"Приятно познакомиться, {first_name}! 👋\n\n"
            "Укажите ваш Telegram (@username) или номер телефона — "
            "менеджер свяжется именно туда:",
            reply_markup=BACK_KB,
        )
        return

    # ── Шаг 2: Контакт ───────────────────────────────────────
    if s == S_A_CONTACT:
        ctx.user_data["form"]["contact"] = text
        set_state(ctx, S_A_PEOPLE)
        if c == "family":
            await update.message.reply_text(
                "Расскажите про состав вашей группы:\n\n"
                "_Например: «2 взрослых + 1 ребёнок 7 лет» "
                "или «Пара, без детей»_",
                parse_mode="Markdown",
                reply_markup=BACK_KB,
            )
        else:
            await update.message.reply_text(
                "Сколько человек едет?\n\n"
                "_Например: «1 человек» или «Двое — я и подруга»_",
                parse_mode="Markdown",
                reply_markup=BACK_KB,
            )
        return

    # ── Шаг 3: Состав ────────────────────────────────────────
    if s == S_A_PEOPLE:
        ctx.user_data["form"]["people"] = text

        # Если номер уже выбран через браузер номеров — пропускаем этот шаг
        pre_room = ctx.user_data["form"].get("room")
        if pre_room:
            if c == "family":
                set_state(ctx, S_A_DATES)
                await update.message.reply_text(
                    f"Номер: *{pre_room}* ✓\n\nВыберите даты заезда:",
                    parse_mode="Markdown",
                    reply_markup=DATES_KB,
                )
            else:
                set_state(ctx, S_A_OPTIONS)
                await update.message.reply_text(
                    f"Номер: *{pre_room}* ✓\n\nХотите добавить опции?",
                    parse_mode="Markdown",
                    reply_markup=OPTIONS_KB,
                )
        else:
            set_state(ctx, S_A_ROOM)
            rooms = WELLNESS_ROOMS if c == "wellness" else FAMILY_ROOMS
            await update.message.reply_text(
                "Какой номер вас интересует?\n"
                "_Если хотите посмотреть фото — вернитесь в «🛏 Номера и цены»_",
                parse_mode="Markdown",
                reply_markup=room_choose_kb(rooms),
            )
        return

    # ── Шаг 4: Номер ─────────────────────────────────────────
    if s == S_A_ROOM:
        rooms = WELLNESS_ROOMS if c == "wellness" else FAMILY_ROOMS
        valid  = [r["label"] for r in rooms] + ["Ещё не определился(лась)"]
        if text in valid:
            ctx.user_data["form"]["room"] = text
            if c == "family":
                set_state(ctx, S_A_DATES)
                await update.message.reply_text(
                    "Выберите даты заезда:", reply_markup=DATES_KB
                )
            else:
                set_state(ctx, S_A_OPTIONS)
                await update.message.reply_text(
                    "Хотите добавить опции к поездке?", reply_markup=OPTIONS_KB
                )
        else:
            await update.message.reply_text(
                "Пожалуйста, выберите из списка 👇",
                reply_markup=room_choose_kb(rooms),
            )
        return

    # ── Шаг 5: Даты (только Family) ──────────────────────────
    if s == S_A_DATES:
        valid = ["22–26 мая", "5–9 июня", "Предзапись на июль", "Предзапись на август"]
        if text in valid:
            ctx.user_data["form"]["dates"] = text
            set_state(ctx, S_A_OPTIONS)
            await update.message.reply_text(
                "Хотите добавить опции?", reply_markup=OPTIONS_KB
            )
        else:
            await update.message.reply_text("Выберите даты 👇", reply_markup=DATES_KB)
        return

    # ── Шаг 6: Опции ─────────────────────────────────────────
    if s == S_A_OPTIONS:
        valid = [
            "Off-road (+130 $/чел)",
            "Чекап A-clinic (+180 $/чел)",
            "Off-road + Чекап",
            "Без доп. опций",
        ]
        if text in valid:
            ctx.user_data["form"]["options"] = text
            set_state(ctx, S_A_COMMENT)
            await update.message.reply_text(
                "Последний шаг! 🙌\n\n"
                "Есть вопросы или пожелания? Напишите здесь.\n"
                "Или нажмите «Пропустить»:",
                reply_markup=SKIP_BACK_KB,
            )
        else:
            await update.message.reply_text(
                "Выберите опцию 👇", reply_markup=OPTIONS_KB
            )
        return

    # ── Шаг 7: Комментарий → финал ───────────────────────────
    if s == S_A_COMMENT:
        form = ctx.user_data.get("form", {})
        form["comment"] = "" if text == "Пропустить" else text

        # Отправляем лид менеджерам
        try:
            await send_lead(ctx, form, update.effective_user)
            lead_sent = True
        except Exception as e:
            print(f"Ошибка отправки лида: {e}")
            lead_sent = False

        # Контакт менеджера для ответа
        contact = "@Kopperfild" if c == "wellness" else "@updatestudio"
        camp_name = "Wellness Camp 🏕" if c == "wellness" else "Family Camp 👨‍👩‍👧"

        # Возвращаем в меню кэмпа
        menu_kb = WELLNESS_MENU_KB if c == "wellness" else FAMILY_MENU_KB
        set_state(ctx, S_WELLNESS if c == "wellness" else S_FAMILY)
        ctx.user_data.pop("form", None)

        if lead_sent:
            confirm_text = (
                "✅ *Заявка принята!*\n\n"
                f"Спасибо! Ваша заявка на *{camp_name}* передана менеджеру.\n\n"
                f"Мы свяжемся с вами в ближайшее время и пришлём все детали.\n\n"
                f"Можно также написать напрямую: {contact}\n\n"
                "_До встречи в горах Грузии! 🏔_"
            )
        else:
            confirm_text = (
                "⚠️ *Заявка сохранена, но не отправлена менеджеру автоматически.*\n\n"
                f"Пожалуйста, напишите напрямую: {contact}\n\n"
                "Мы уже проверяем техническую ошибку."
            )

        await update.message.reply_text(
            confirm_text, parse_mode="Markdown", reply_markup=menu_kb
        )
        return

    # ── Fallback ──────────────────────────────────────────────
    if s in (S_WELLNESS, S_ROOMS_W):
        await update.message.reply_text("Выберите раздел 👇", reply_markup=WELLNESS_MENU_KB)
    elif s in (S_FAMILY, S_ROOMS_F):
        await update.message.reply_text("Выберите раздел 👇", reply_markup=FAMILY_MENU_KB)
    else:
        await update.message.reply_text("Выберите кэмп 👇", reply_markup=MAIN_KB)


# ─── ЗАПУСК ───────────────────────────────────────────────────
def main():
    start_healthcheck_server()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu",  cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("UPDATE CAMP BOT запущен ✦  Tbilisi")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
