"""
Telegram-бот: звуковые и световые сигналы МППСС-72 (COLREG-72) + тест.

Установка:   pip install "aiogram>=3.7"
Запуск:      BOT_TOKEN=123:ABC python colreg_bot.py
"""
import asyncio
import os
import random
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

QUESTIONS_IN_TEST = 10

# ---------------------------------------------------------------- ДАННЫЕ ---
# kind: sound | light | day
# запись: (сигнал, значение)
SECTIONS = {
    "man": ("sound", "🔊 Манёвры (пр. 34)", [
        ("•", "Изменяю курс вправо"),
        ("• •", "Изменяю курс влево"),
        ("• • •", "Мои машины работают на задний ход"),
        ("• • • • • (пять и более коротких, быстро)",
         "Сомневаюсь в намерениях вашего судна или считаю, что вы не принимаете достаточных мер для предупреждения столкновения"),
        ("— (один продолжительный)",
         "Приближаюсь к изгибу или участку, где другие суда могут быть скрыты препятствием (и ответ на такой сигнал)"),
    ]),
    "ovt": ("sound", "🔊 Обгон в узкости (пр. 9, 34)", [
        ("— — •", "Намерен обогнать вас по вашему правому борту"),
        ("— — • •", "Намерен обогнать вас по вашему левому борту"),
        ("— • — •", "Согласен на обгон"),
    ]),
    "vis": ("sound", "🌫 Ограниченная видимость (пр. 35)", [
        ("— (не реже 1 раза в 2 мин)",
         "Механическое судно на ходу, имеющее ход относительно воды"),
        ("— — (интервал ~2 с, не реже 1 раза в 2 мин)",
         "Механическое судно на ходу, но остановившееся и не имеющее хода"),
        ("— • • (не реже 1 раза в 2 мин)",
         "Судно, не имеющее управления / ограниченное в возможности маневрировать / стеснённое осадкой / парусное / занятое ловом / буксирующее или толкающее"),
        ("— • • • (не реже 1 раза в 2 мин)",
         "Буксируемое судно (если на нём есть экипаж)"),
        ("Быстрый звон в колокол ~5 с каждую минуту",
         "Судно на якоре"),
        ("Колокол в носу + гонг в корме (звон ~5 с каждую минуту)",
         "Судно на якоре длиной 100 м и более"),
        ("• — •", "Судно на якоре (дополнительно): предупреждение о своём месте и возможности столкновения"),
        ("Быстрый звон в колокол, до и после него по 3 отдельных удара",
         "Судно на мели"),
        ("• • • •", "Лоцманское судно при исполнении обязанностей (опознавательный сигнал, дополнительно)"),
    ]),
    "dist": ("sound", "🆘 Бедствие (пр. 37, прил. IV)", [
        ("Выстрелы из пушки или взрывные сигналы с интервалом около 1 мин", "Сигнал бедствия"),
        ("Непрерывный звук любым аппаратом тумана", "Сигнал бедствия"),
        ("Красные ракеты (парашютные) или красный фальшфейер", "Сигнал бедствия"),
        ("Оранжевый дым", "Сигнал бедствия"),
        ("SOS (··· ——— ···) любым способом", "Сигнал бедствия"),
        ("Радиотелефонный сигнал «Мэйдэй» (MAYDAY)", "Сигнал бедствия"),
        ("Флаги N над C (по Международному своду сигналов)", "Сигнал бедствия"),
        ("Квадратный флаг, над или под которым шар или нечто похожее", "Сигнал бедствия"),
        ("Медленное поднимание и опускание рук, вытянутых в стороны", "Сигнал бедствия"),
    ]),
    "nav": ("light", "💡 Ходовые огни (пр. 23–25)", [
        ("⚪ мачтовый\n⚪ второй мачтовый (сзади и выше)\n🔴🟢 бортовые + ⚪ кормовой",
         "Механическое судно на ходу длиной 50 м и более"),
        ("⚪ один мачтовый\n🔴🟢 бортовые + ⚪ кормовой",
         "Механическое судно на ходу длиной менее 50 м"),
        ("🔴🟢 бортовые + ⚪ кормовой (без мачтовых огней)",
         "Парусное судно на ходу (так же выглядит буксируемое судно)"),
        ("🔴 над 🟢 круговые на топе мачты (+ бортовые и кормовой)",
         "Парусное судно на ходу (дополнительные необязательные огни)"),
        ("⚪⚪ два мачтовых по вертикали\n🔴🟢 бортовые + ⚪ кормовой\n🟡 буксирный над кормовым",
         "Буксирующее судно, длина буксира не более 200 м"),
        ("⚪⚪⚪ три мачтовых по вертикали\n🔴🟢 бортовые + ⚪ кормовой\n🟡 буксирный над кормовым",
         "Буксирующее судно, длина буксира более 200 м"),
        ("⚪⚪ два мачтовых по вертикали\n🔴🟢 бортовые + ⚪ кормовой (без жёлтого)",
         "Судно, толкающее или буксирующее лагом (борт о борт)"),
    ]),
    "fish": ("light", "🎣 Рыболовные суда (пр. 26)", [
        ("🟢 над ⚪ круговые (на ходу + бортовые и кормовой)", "Судно, занятое тралением"),
        ("🔴 над ⚪ круговые (на ходу + бортовые и кормовой)", "Судно, занятое ловом рыбы (не тралом)"),
        ("🔴 над ⚪ круговые + ⚪ круговой в сторону снастей",
         "Рыболовное судно, снасти которого выступают более чем на 150 м"),
    ]),
    "lim": ("light", "⚠️ Ограниченные в манёвре (пр. 27–29)", [
        ("🔴\n🔴 (на ходу + бортовые и кормовой)", "Судно, не имеющее управления"),
        ("🔴\n⚪\n🔴 (на ходу + мачтовые, бортовые, кормовой)",
         "Судно, ограниченное в возможности маневрировать"),
        ("🔴\n🔴\n🔴 (+ огни механического судна)", "Судно, стеснённое своей осадкой"),
        ("🔴🔴 с одной стороны и 🟢🟢 с другой",
         "Судно, ограниченное в манёвре при дноуглубительных/подводных работах: красные — сторона препятствия, зелёные — сторона безопасного прохода"),
        ("⚪ над 🔴 круговые (на ходу + бортовые и кормовой)", "Лоцманское судно при исполнении обязанностей"),
    ]),
    "anc": ("light", "⚓ На якоре и на мели (пр. 30)", [
        ("⚪ один круговой", "Судно длиной менее 50 м на якоре"),
        ("⚪ в носу\n⚪ в корме, ниже носового", "Судно длиной 50 м и более на якоре"),
        ("Якорные огни + 🔴\n🔴 по вертикали", "Судно на мели"),
    ]),
    "day": ("day", "🔶 Дневные знаки", [
        ("⚫ один шар", "Судно на якоре"),
        ("⚫⚫ два шара по вертикали", "Судно, не имеющее управления"),
        ("⚫ ◆ ⚫ шар – ромб – шар", "Судно, ограниченное в возможности маневрировать"),
        ("▮ цилиндр", "Судно, стеснённое своей осадкой"),
        ("⚫⚫⚫ три шара по вертикали", "Судно на мели"),
        ("▼▲ два конуса вершинами друг к другу", "Судно, занятое ловом рыбы"),
        ("▲ конус вершиной вверх в сторону снастей",
         "Рыболовное судно, снасти которого выступают более чем на 150 м"),
        ("▼ конус вершиной вниз", "Парусное судно, идущее под парусами и работающей машиной"),
        ("◆ ромб", "Буксирующее судно и буксир при длине буксира более 200 м"),
    ]),
}

POOLS = {}
for _k, (_kind, _t, _es) in SECTIONS.items():
    POOLS.setdefault(_kind, []).extend(_es)

QTEXT = {
    "sound": "Что означает этот звуковой сигнал?",
    "light": "Какому судну соответствуют эти огни?",
    "day": "Какому судну соответствует этот дневной знак?",
}
MODES = {"sound": ["sound"], "light": ["light", "day"], "all": ["sound", "light", "day"]}

LEGEND = ("<b>Обозначения:</b>\n• — короткий звук (≈1 с)\n— — продолжительный (4–6 с)\n"
          "⚪ белый · 🔴 красный · 🟢 зелёный · 🟡 жёлтый")

WELCOME = ("⚓ <b>МППСС-72: сигналы</b>\n\nСправочник звуковых сигналов, огней и дневных знаков "
           "и тест для проверки знаний.\n\n" + LEGEND)

STATE: dict[int, dict] = {}

# ------------------------------------------------------------ КЛАВИАТУРЫ ---


def kb_main():
    b = InlineKeyboardBuilder()
    b.button(text="🔊 Звуковые сигналы", callback_data="cat:sound")
    b.button(text="💡 Огни и знаки", callback_data="cat:light")
    b.button(text="📝 Пройти тест", callback_data="test")
    b.adjust(1)
    return b.as_markup()


def kb_cat(cat):
    kinds = ["sound"] if cat == "sound" else ["light", "day"]
    b = InlineKeyboardBuilder()
    for key, (kind, title, _) in SECTIONS.items():
        if kind in kinds:
            b.button(text=title, callback_data=f"sec:{key}")
    b.button(text="⬅️ Меню", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


def kb_back(cat):
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад", callback_data=f"cat:{cat}")
    b.button(text="📝 Тест", callback_data="test")
    b.adjust(2)
    return b.as_markup()


def kb_modes():
    b = InlineKeyboardBuilder()
    b.button(text="🔊 Звуковые сигналы", callback_data="tm:sound")
    b.button(text="💡 Огни и знаки", callback_data="tm:light")
    b.button(text="🎲 Всё вместе", callback_data="tm:all")
    b.button(text="⬅️ Меню", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


# ----------------------------------------------------------------- ТЕСТ ----


def build_test(mode):
    items = []
    for kind in MODES[mode]:
        items += [(kind, s, m) for s, m in POOLS[kind]]
    # в режиме «всё» не даём перекос в сторону бедствия: берём случайные
    random.shuffle(items)
    items = items[:QUESTIONS_IN_TEST]
    qs = []
    for kind, signal, meaning in items:
        wrong = list({m for _, m in POOLS[kind] if m != meaning})
        options = random.sample(wrong, min(3, len(wrong))) + [meaning]
        random.shuffle(options)
        qs.append({"kind": kind, "signal": signal, "options": options,
                   "correct": options.index(meaning), "meaning": meaning})
    return qs


def question_text(st, feedback=""):
    q = st["qs"][st["i"]]
    opts = "\n".join(f"<b>{n + 1}.</b> {escape(o)}" for n, o in enumerate(q["options"]))
    return (f"<b>Вопрос {st['i'] + 1}/{len(st['qs'])}</b>\n{QTEXT[q['kind']]}\n\n"
            f"{escape(q['signal'])}\n\n{opts}{feedback}")


def kb_answers(q):
    b = InlineKeyboardBuilder()
    for n in range(len(q["options"])):
        b.button(text=str(n + 1), callback_data=f"a:{n}")
    b.adjust(4)
    return b.as_markup()


async def safe_edit(c: CallbackQuery, text, kb):
    try:
        await c.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest:
        pass


# ------------------------------------------------------------- ХЭНДЛЕРЫ ----
dp = Dispatcher()


@dp.message(Command("start", "menu"))
async def start(m: Message):
    await m.answer(WELCOME, reply_markup=kb_main())


@dp.callback_query(F.data == "menu")
async def cb_menu(c: CallbackQuery):
    await safe_edit(c, WELCOME, kb_main())
    await c.answer()


@dp.callback_query(F.data.startswith("cat:"))
async def cb_cat(c: CallbackQuery):
    cat = c.data.split(":")[1]
    title = "🔊 <b>Звуковые сигналы</b>" if cat == "sound" else "💡 <b>Огни и знаки</b>"
    await safe_edit(c, f"{title}\nВыберите раздел:", kb_cat(cat))
    await c.answer()


@dp.callback_query(F.data.startswith("sec:"))
async def cb_sec(c: CallbackQuery):
    key = c.data.split(":")[1]
    kind, title, entries = SECTIONS[key]
    lines = [f"<b>{escape(title)}</b>\n"]
    for signal, meaning in entries:
        lines.append(f"{escape(signal)}\n→ <i>{escape(meaning)}</i>\n")
    if kind == "sound":
        lines.append(LEGEND)
    cat = "sound" if kind == "sound" else "light"
    await safe_edit(c, "\n".join(lines), kb_back(cat))
    await c.answer()


@dp.callback_query(F.data == "test")
async def cb_test(c: CallbackQuery):
    await safe_edit(c, "📝 <b>Тест</b>\nЧто проверяем?", kb_modes())
    await c.answer()


@dp.callback_query(F.data.startswith("tm:"))
async def cb_start_test(c: CallbackQuery):
    mode = c.data.split(":")[1]
    STATE[c.from_user.id] = {"qs": build_test(mode), "i": 0, "score": 0, "wrong": [], "mode": mode}
    st = STATE[c.from_user.id]
    await safe_edit(c, question_text(st), kb_answers(st["qs"][0]))
    await c.answer()


@dp.callback_query(F.data.startswith("a:"))
async def cb_answer(c: CallbackQuery):
    st = STATE.get(c.from_user.id)
    if not st:
        await c.answer("Тест не начат. Нажмите /start", show_alert=True)
        return
    q = st["qs"][st["i"]]
    choice = int(c.data.split(":")[1])
    if choice == q["correct"]:
        st["score"] += 1
        fb = "\n\n✅ <b>Верно!</b>"
    else:
        st["wrong"].append(q)
        fb = f"\n\n❌ <b>Неверно.</b> Правильный ответ: <b>{q['correct'] + 1}</b>"
    last = st["i"] + 1 >= len(st["qs"])
    b = InlineKeyboardBuilder()
    b.button(text="🏁 Результат" if last else "Дальше ▶️", callback_data="next")
    await safe_edit(c, question_text(st, fb), b.as_markup())
    await c.answer()


@dp.callback_query(F.data == "next")
async def cb_next(c: CallbackQuery):
    st = STATE.get(c.from_user.id)
    if not st:
        await c.answer("Тест не начат. Нажмите /start", show_alert=True)
        return
    st["i"] += 1
    if st["i"] < len(st["qs"]):
        await safe_edit(c, question_text(st), kb_answers(st["qs"][st["i"]]))
    else:
        n = len(st["qs"])
        pct = round(100 * st["score"] / n)
        text = f"🏁 <b>Результат: {st['score']}/{n}</b> ({pct}%)\n"
        if st["wrong"]:
            text += "\n<b>Разбор ошибок:</b>\n"
            for q in st["wrong"]:
                text += f"\n{escape(q['signal'])}\n→ <i>{escape(q['meaning'])}</i>\n"
        b = InlineKeyboardBuilder()
        b.button(text="🔁 Ещё раз", callback_data=f"tm:{st['mode']}")
        b.button(text="⬅️ Меню", callback_data="menu")
        b.adjust(2)
        await safe_edit(c, text, b.as_markup())
    await c.answer()


def load_token():
    """Токен берётся из переменной BOT_TOKEN или из файла .env рядом со скриптом."""
    token = os.environ.get("BOT_TOKEN")
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not token and os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("BOT_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not token:
        raise SystemExit("Не найден BOT_TOKEN: создайте файл .env со строкой BOT_TOKEN=ваш_токен")
    return token


async def main():
    token = load_token()
    bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
