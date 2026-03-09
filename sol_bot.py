"""
╔══════════════════════════════════════════════════════════╗
║              СОЛ — личный коуч Светы                     ║
║              Telegram Bot · Prime Era 2025               ║
╠══════════════════════════════════════════════════════════╣
║  РЕЖИМЫ:                                                 ║
║  🧠 DBT практика       — навыки DBT пошагово             ║
║  🌙 Вечерняя рефлексия — разбирает день                  ║
║  🍽 Дневник питания     — что поела, ритм, наблюдения    ║
║  📅 Итоги недели        — подводим итоги                  ║
║  🌱 Начало месяца       — планирование                    ║
║  ✦  Конец месяца        — глубокий check-in              ║
║  📊 Трекер              — отмечаешь привычки кнопками    ║
║  💬 Просто поговорить   — просто общение                  ║
║                                                          ║
║  НАПОМИНАНИЯ (Тбилиси UTC+4):                            ║
║  08:05 — доброе утро + утренние привычки                 ║
║  09:50 — перед скалодромом (ПН СР ПТ)                   ║
║  13:45 — обед после тренировки (ПН СР ПТ)               ║
║  17:00 — перекус (каждый день)                           ║
║  19:30 — ужин до 20:00 (каждый день)                     ║
║  21:30 — DBT-дневник + рефлексия (каждый день)           ║
║  22:15 — напоминание про сон (каждый день)               ║
║  ВС 19:00 — итоги недели                                 ║
║  1-е число 09:00 — планирование месяца                   ║
║  Последний день 19:00 — итоги месяца                     ║
║                                                          ║
║  ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ:                                   ║
║  TELEGRAM_TOKEN    — от @BotFather                       ║
║  ANTHROPIC_API_KEY — от console.anthropic.com            ║
║  ALLOWED_USER_ID   — твой числовой ID (@userinfobot)     ║
╚══════════════════════════════════════════════════════════╝
"""

import os
import asyncio
import calendar
from datetime import datetime, timezone, timedelta

import anthropic
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes
)

# ─── CONFIG ───────────────────────────────────────────────────
TELEGRAM_TOKEN    = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ALLOWED_USER_ID   = int(os.environ["ALLOWED_USER_ID"])
TZ = timezone(timedelta(hours=4))   # Тбилиси UTC+4

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ─── SYSTEM PROMPTS ───────────────────────────────────────────
BASE = """Ты — личный коуч и помощник Светы Дёмкиной. Твоё имя — Сол (от «soul» — душа).

О Свете:
- 34 года, Тбилиси. Соучредитель wellness-студии UPDATE и Base for Masters.
- Сейчас 80 кг, цель — 50-54 кг через год, рост 158 см.
- Проходит групповую терапию DBT и телесную терапию, принимает антидепрессанты.
- Скалодром 3x/нед (ПН СР ПТ, 10:00–13:30). Хочет дисциплину без насилия над собой.
- Цель года: лёгкое тело, доход $15-20k/мес, счастливые отношения.
- Программа Prime Era — март: 3 привычки (телефон +30 мин, вода утром, DBT-дневник).
- Питание: метод тарелки (½ овощи, ¼ белок, ¼ углеводы). Цель — ритм, не подсчёт калорий.
- История: работала с нутрициологами, это приводило к набору веса. Никаких протоколов и ограничений.

Принципы:
- Никакой самокритики — только наблюдение и принятие
- Тепло, как близкая подруга которая верит в неё
- Вопросы строго по одному, реагируй на ответ прежде чем двигаться дальше
- До 200 слов за раз, если не просят развёрнутого
- Всегда на русском"""

PROMPTS = {
"dbt": BASE + """

РЕЖИМ: DBT-практика
Спроси что сейчас происходит или какой модуль нужен:
1. Осознанность — назвать 5 вещей вокруг, наблюдать без оценок
2. Дистресс-толерантность — TIPP: холодная вода на лицо, 10 приседаний, дыхание 4-7-8
3. Регуляция эмоций — Opposite Action, ABC PLEASE
4. Межличностная эффективность — DEAR MAN
Проведи через практику шаг за шагом. Спроси как было после.""",

"evening": BASE + """

РЕЖИМ: Вечерняя рефлексия. Вопросы по одному:
1. Как сейчас — в теле и эмоциях?
2. Что было самым сложным сегодня?
3. Был ли момент гордости или заботы о себе?
4. Как поела? Был ли ритм?
5. Движение / шаги?
6. DBT навык — использовала?
7. Одна вещь за которую благодарна.
В конце — тёплое резюме дня в 2-3 предложения.""",

"food": BASE + """

РЕЖИМ: Дневник питания

Цель дневника — не считать калории и не осуждать, а замечать паттерны.
Никаких оценок «хорошо/плохо». Только наблюдение.

Что делать:
Спроси Свету что она сегодня ела — или попроси рассказать про конкретный приём пищи.
После каждого ответа мягко уточни:
- Примерно когда это было?
- Как себя чувствовала до еды (голодная? устала? стресс?)?
- Как себя чувствовала после?

Принципы которых придерживаться:
- НИКОГДА не говори что что-то «нельзя» или «плохо»
- НИКОГДА не упоминай калории, граммы, КБЖУ
- Если она поела ночью или «сорвалась» — не осуждать, спросить что предшествовало
- Отмечай позитивное: поела вовремя? хорошо! был белок? отлично!
- В конце предложи один маленький шаг на завтра — не список, одно действие

Метод тарелки (напоминай мягко если уместно):
½ тарелки — овощи / зелень
¼ тарелки — белок (мясо, рыба, яйца, творог)
¼ тарелки — углеводы (гречка, рис, картошка)

Важные паттерны которые стоит замечать (не вслух — просто в уме):
- Ела ли она сегодня до 13:00?
- Был ли ужин до 20:00?
- Был ли перекус в 17:00 чтобы не срываться вечером?
- Пила ли воду?
Если паттерн нарушен — не указывать на ошибку, а мягко спросить что помешало.""",

"weekly": BASE + """

РЕЖИМ: Итоги недели. Вопросы по одному:
1. Неделя на 1-10 — почему?
2. Какие привычки шли хорошо?
3. Что давалось сложнее?
4. Был ли момент лёгкости / уверенности?
5. Питание и движение на неделе?
6. Что берёшь из этой недели в следующую?
7. Одна вещь для себя на следующей неделе.
В конце — краткий тёплый итог, отметь прогресс который она сама не заметила.""",

"month_start": BASE + """

РЕЖИМ: Планирование месяца. Вопросы по одному:
1. Тема / слово месяца?
2. Какую новую привычку добавляет?
3. Цель по весу (ориентир -2 кг)?
4. Финансовая цель — что делает для роста дохода?
5. Поездки или события?
6. Что делает для себя — красота, радость?
7. Намерение — одно предложение.
В конце красиво повтори её план и скажи что-то вдохновляющее.""",

"month_end": BASE + """

РЕЖИМ: Итоги месяца. Вопросы по одному:
1. Месяц на 1-10 — почему?
2. Как изменилось ощущение в теле?
3. Вес в начале и в конце?
4. Сколько дней выполняла привычки из 7?
5. Фактический доход vs план?
6. Был ли момент когда почувствовала себя настоящей собой?
7. Главный урок месяца.
8. Что берёшь в следующий?
Замечай прогресс который она сама не видит. В конце — напомни как далеко она уже прошла.""",

"chat": BASE + """

РЕЖИМ: Свободный разговор.
Просто будь рядом. Слушай, поддерживай, отвечай.
Если касается сложных эмоций — мягко предложи навык DBT.
Если спрашивает про тело / питание — опирайся на программу Prime Era.""",
}

# ─── HABITS ───────────────────────────────────────────────────
HABITS = [
    ("phone",     "🌅 Телефон через 30 мин"),
    ("water_m",   "💧 Вода утром"),
    ("breakfast", "🍳 Завтрак до 9:30"),
    ("dinner",    "🌙 Ужин до 20:00"),
    ("steps",     "👟 Шаги 8,000+"),
    ("movement",  "🏃 Движение / скалодром"),
    ("water",     "💦 Вода 2л"),
    ("body_oil",  "🧴 Масло для тела"),
    ("scrub",     "🧹 Скраб / щётка"),
    ("dbt_m",     "🧠 DBT утром"),
    ("dbt_j",     "📓 DBT дневник"),
    ("skin",      "✨ Уход за лицом"),
    ("sleep",     "😴 Сон до 23:30"),
    ("joy",       "💛 Момент радости"),
]

# ─── KEYBOARDS ────────────────────────────────────────────────
MAIN_KB = ReplyKeyboardMarkup([
    ["🧠 DBT практика",       "🌙 Вечерняя рефлексия"],
    ["🍽 Дневник питания",     "📅 Итоги недели"],
    ["🌱 Начало месяца",       "✦ Конец месяца"],
    ["📊 Трекер привычек",     "💬 Просто поговорить"],
], resize_keyboard=True)

MODE_MAP = {
    "🧠 DBT практика":       "dbt",
    "🌙 Вечерняя рефлексия": "evening",
    "🍽 Дневник питания":     "food",
    "📅 Итоги недели":        "weekly",
    "🌱 Начало месяца":       "month_start",
    "✦ Конец месяца":         "month_end",
    "💬 Просто поговорить":   "chat",
}

def tracker_kb(tracker: dict) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(
        ("✅ " if tracker.get(hid) else "⬜ ") + label
    )] for hid, label in HABITS]
    rows.append([KeyboardButton("🔙 Главное меню")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

# ─── CLAUDE ───────────────────────────────────────────────────
async def ask_claude(history: list, mode: str) -> str:
    try:
        r = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=600,
            system=PROMPTS.get(mode, PROMPTS["chat"]),
            messages=history[-20:],
        )
        return r.content[0].text
    except Exception as e:
        return f"Что-то пошло не так 😔\nПопробуй ещё раз или напиши /start\n\n({e})"

# ─── HANDLERS ─────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    ctx.user_data.clear()
    await update.message.reply_text(
        "Привет, Света ✦\n\nЯ Сол — твой личный коуч.\nЧем займёмся?",
        reply_markup=MAIN_KB,
    )

async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID:
        return
    text = update.message.text.strip()

    # ── Tracker mode ──────────────────────────────────────────
    if ctx.user_data.get("mode") == "tracker":
        if text == "🔙 Главное меню":
            ctx.user_data["mode"] = None
            await update.message.reply_text("Главное меню 👇", reply_markup=MAIN_KB)
            return
        tracker = ctx.user_data.setdefault("tracker", {})
        for hid, label in HABITS:
            if label in text:
                tracker[hid] = not tracker.get(hid, False)
                done = sum(1 for h, _ in HABITS if tracker.get(h))
                icon = "✅" if tracker[hid] else "⬜"
                msg = f"{icon} {label}\n\nВыполнено: {done}/{len(HABITS)}"
                if done == len(HABITS):
                    msg += "\n\n✦ Все привычки! Ты молодец, Света 🌸"
                await update.message.reply_text(msg, reply_markup=tracker_kb(tracker))
                return
        done = sum(1 for h, _ in HABITS if tracker.get(h))
        await update.message.reply_text(
            f"Нажми на привычку чтобы отметить ✓\nВыполнено: {done}/{len(HABITS)}",
            reply_markup=tracker_kb(tracker),
        )
        return

    # ── Open tracker ──────────────────────────────────────────
    if text == "📊 Трекер привычек":
        ctx.user_data["mode"] = "tracker"
        tracker = ctx.user_data.setdefault("tracker", {})
        done = sum(1 for h, _ in HABITS if tracker.get(h))
        await update.message.reply_text(
            f"Привычки на сегодня 📊\nВыполнено: {done}/{len(HABITS)}\n\nНажми на привычку:",
            reply_markup=tracker_kb(tracker),
        )
        return

    # ── Select mode ───────────────────────────────────────────
    if text in MODE_MAP:
        mode = MODE_MAP[text]
        ctx.user_data.update({"mode": mode, "history": []})
        await update.message.reply_text("...", reply_markup=MAIN_KB)
        history = [{"role": "user", "content": "Начни"}]
        reply = await ask_claude(history, mode)
        ctx.user_data["history"] = [
            {"role": "user", "content": "Начни"},
            {"role": "assistant", "content": reply},
        ]
        await update.message.reply_text(reply, reply_markup=MAIN_KB)
        return

    # ── Back / menu ───────────────────────────────────────────
    if text in ("🔙 Главное меню", "/menu"):
        ctx.user_data.update({"mode": None, "history": []})
        await update.message.reply_text("Главное меню 👇", reply_markup=MAIN_KB)
        return

    # ── Free chat ─────────────────────────────────────────────
    mode = ctx.user_data.get("mode", "chat")
    history = ctx.user_data.setdefault("history", [])
    history.append({"role": "user", "content": text})
    reply = await ask_claude(history, mode)
    history.append({"role": "assistant", "content": reply})
    await update.message.reply_text(reply, reply_markup=MAIN_KB)

# ─── REMINDERS ────────────────────────────────────────────────
REMINDERS = [
    (8,  5,  None,
     "Доброе утро, Света ✦\n\n"
     "• Стакан воды прямо сейчас 💧\n"
     "• Телефон отложи — первые 30 минут только для себя 🌅\n\n"
     "Хорошего дня!"),

    (9,  50, 0,  "Скалодром через 10 минут 🧗‍♀️\nВозьми воду!"),
    (9,  50, 2,  "Скалодром через 10 минут 🧗‍♀️\nВозьми воду!"),
    (9,  50, 4,  "Скалодром через 10 минут 🧗‍♀️\nВозьми воду!"),

    (13, 45, 0,
     "Тренировка позади 💪\n"
     "Время обеда — метод тарелки:\n"
     "½ овощи · ¼ белок · ¼ углеводы 🍽\n\n"
     "Можешь записать в «🍽 Дневник питания»"),
    (13, 45, 2,
     "Тренировка позади 💪\n"
     "Время обеда — метод тарелки:\n"
     "½ овощи · ¼ белок · ¼ углеводы 🍽\n\n"
     "Можешь записать в «🍽 Дневник питания»"),
    (13, 45, 4,
     "Тренировка позади 💪\n"
     "Время обеда — метод тарелки:\n"
     "½ овощи · ¼ белок · ¼ углеводы 🍽\n\n"
     "Можешь записать в «🍽 Дневник питания»"),

    (17, 0,  None,
     "Время перекуса 🍎\n"
     "Фрукт + орехи, йогурт или кефир.\n"
     "Помогает не сорваться вечером 💛"),

    (19, 30, None,
     "Напоминание: ужин до 20:00 🌙\n"
     "Ещё 30 минут — успеешь!"),

    (21, 30, None,
     "Время DBT-дневника 📓\n\n"
     "Вопрос: какую эмоцию ты чувствовала сильнее всего сегодня?\n\n"
     "Нажми «🌙 Вечерняя рефлексия» чтобы поговорить со мной."),

    (22, 15, None,
     "Сон до 23:30 — уже почти время 😴\n"
     "Магний принят? Телефон в другую комнату 🌙"),

    (19, 0,  6,
     "Воскресенье — время подвести итоги недели 📅\n\n"
     "Нажми «📅 Итоги недели» — 10 минут\n"
     "и следующая неделя будет лучше ✦"),
]

async def reminder_loop(app: Application):
    sent: set[str] = set()
    last_month_start = -1
    last_month_end   = -1

    while True:
        await asyncio.sleep(30)
        now = datetime.now(TZ)
        h, m, wd, day, month = now.hour, now.minute, now.weekday(), now.day, now.month

        for (rh, rm, rwd, msg) in REMINDERS:
            key = f"{rh}:{rm}:{rwd}"
            if h == rh and m == rm and (rwd is None or rwd == wd) and key not in sent:
                sent.add(key)
                try:
                    await app.bot.send_message(ALLOWED_USER_ID, msg, reply_markup=MAIN_KB)
                except Exception:
                    pass

        if day == 1 and h == 9 and m == 0 and last_month_start != month:
            last_month_start = month
            try:
                await app.bot.send_message(
                    ALLOWED_USER_ID,
                    "Первое число — новый месяц 🌱\n\n"
                    "Нажми «🌱 Начало месяца» — потратим 15 минут\n"
                    "чтобы месяц прошёл как надо ✦",
                    reply_markup=MAIN_KB,
                )
            except Exception:
                pass

        last_day = calendar.monthrange(now.year, month)[1]
        if day == last_day and h == 19 and m == 0 and last_month_end != month:
            last_month_end = month
            try:
                await app.bot.send_message(
                    ALLOWED_USER_ID,
                    "Последний день месяца ✦\n\n"
                    "Нажми «✦ Конец месяца» — разберём месяц вместе.\n"
                    "20 минут чтобы увидеть как далеко ты прошла 🌸",
                    reply_markup=MAIN_KB,
                )
            except Exception:
                pass

        if h == 0 and m == 0:
            sent.clear()

# ─── INIT & MAIN ──────────────────────────────────────────────
async def post_init(app: Application):
    asyncio.create_task(reminder_loop(app))

def main():
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu",
        lambda u, c: c.user_data.update({"mode": None, "history": []})
        or u.message.reply_text("Главное меню 👇", reply_markup=MAIN_KB)
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("Сол запущена ✦  Тбилиси UTC+4")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
