"""
Telegram-бот: звуковые и световые сигналы МППСС-72 (COLREG-72) + тест.

Установка:   pip install "aiogram>=3.7"
Запуск:      BOT_TOKEN=123:ABC python colreg_bot.py
Картинки лежат рядом со скриптом в архиве images.zip.
"""
import asyncio
import os
import random
import zipfile
from html import escape
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import (BufferedInputFile, CallbackQuery, InlineKeyboardButton,
                           InputMediaPhoto, Message)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

QUESTIONS_IN_TEST = 30
BASE_DIR = Path(__file__).resolve().parent


def load_images():
    """Картинки читаются из images.zip (или из отдельных файлов img_*.png) рядом со скриптом."""
    imgs = {}
    zp = BASE_DIR / "images.zip"
    if zp.exists():
        with zipfile.ZipFile(zp) as z:
            for n in z.namelist():
                if n.lower().endswith(".png"):
                    imgs[Path(n).name] = z.read(n)
    for p in BASE_DIR.glob("img_*_*.png"):
        imgs.setdefault(p.name, p.read_bytes())
    return imgs


IMAGES = load_images()
VIEWS = [("bow", "Нос"), ("stern", "Корма"), ("port", "Л. борт"), ("stbd", "П. борт"), ("day", "Днём")]


def img_base(img):
    return img[4:-4]  # "img_sail.png" -> "sail"


def view_file(img, view="bow"):
    return f"img_{img_base(img)}_{view}.png"


def photo(name):
    return BufferedInputFile(IMAGES[name], filename=name)


def has_pic(img):
    return bool(img) and view_file(img) in IMAGES


def view_rows(img):
    """Кнопки переключения видов под картинкой."""
    btns = [InlineKeyboardButton(text=label, callback_data=f"v:{img_base(img)}:{v}")
            for v, label in VIEWS if view_file(img, v) in IMAGES]
    return [btns[:3], btns[3:]] if len(btns) > 3 else [btns]

# ---------------------------------------------------------------- ДАННЫЕ ---
# kind: sound | light | day
# запись: (сигнал, значение) или (сигнал, значение, "имя_картинки.png")
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
         "Механическое судно на ходу длиной 50 м и более", "img_mech_ge50.png"),
        ("⚪ один мачтовый\n🔴🟢 бортовые + ⚪ кормовой",
         "Механическое судно на ходу длиной менее 50 м", "img_mech_lt50.png"),
        ("🔴🟢 бортовые + ⚪ кормовой (без мачтовых огней)",
         "Парусное судно на ходу (так же выглядит буксируемое судно)", "img_sail.png"),
        ("🔴 над 🟢 круговые на топе мачты (+ бортовые и кормовой)",
         "Парусное судно на ходу (дополнительные необязательные огни)", "img_sail_rg.png"),
        ("Ночью как у механического судна; днём ▼ конус вершиной вниз",
         "Парусное судно, идущее под парусами и машиной", "img_sail_power.png"),
        ("⚪⚪ два мачтовых по вертикали\n🔴🟢 бортовые + ⚪ кормовой\n🟡 буксирный над кормовым",
         "Буксирующее судно, длина буксира не более 200 м", "img_tow_le200.png"),
        ("⚪⚪⚪ три мачтовых по вертикали\n🔴🟢 бортовые + ⚪ кормовой\n🟡 буксирный над кормовым; днём ◆ ромб",
         "Буксирующее судно, длина буксира более 200 м", "img_tow_gt200.png"),
        ("⚪⚪ два мачтовых по вертикали\n🔴🟢 бортовые + ⚪ кормовой (без жёлтого)",
         "Судно, толкающее или буксирующее лагом (борт о борт)"),
    ]),
    "fish": ("light", "🎣 Рыболовные суда (пр. 26)", [
        ("🟢 над ⚪ круговые (на ходу + бортовые и кормовой)", "Судно, занятое тралением", "img_trawl.png"),
        ("🔴 над ⚪ круговые (на ходу + бортовые и кормовой)",
         "Судно, занятое ловом рыбы (не тралом)", "img_fishing.png"),
        ("🔴 над ⚪ круговые + ⚪ круговой в сторону снастей",
         "Рыболовное судно, снасти которого выступают более чем на 150 м"),
    ]),
    "lim": ("light", "⚠️ Ограниченные в манёвре (пр. 27–29)", [
        ("🔴\n🔴 (на ходу + бортовые и кормовой)", "Судно, не имеющее управления", "img_nuc.png"),
        ("🔴\n⚪\n🔴 (на ходу + мачтовые, бортовые, кормовой)",
         "Судно, ограниченное в возможности маневрировать", "img_ram.png"),
        ("🔴\n🔴\n🔴 (+ огни механического судна)", "Судно, стеснённое своей осадкой", "img_draught.png"),
        ("🟢 на топе мачты и по 🟢 на концах рея (+ огни механического судна)",
         "Судно, занятое работами по устранению минной опасности", "img_mine.png"),
        ("🔴\n⚪\n🔴 + 🔴🔴 с одной стороны и 🟢🟢 с другой",
         "Судно при дноуглубительных/подводных работах: красные — сторона препятствия, зелёные — сторона прохода",
         "img_dredging.png"),
        ("⚪ над 🔴 круговые (на ходу + бортовые и кормовой)",
         "Лоцманское судно при исполнении обязанностей", "img_pilot.png"),
    ]),
    "anc": ("light", "⚓ На якоре и на мели (пр. 30)", [
        ("⚪ один круговой", "Судно длиной менее 50 м на якоре", "img_anchor_lt50.png"),
        ("⚪ в носу\n⚪ в корме, ниже носового", "Судно длиной 50 м и более на якоре", "img_anchor_ge50.png"),
        ("Якорные огни + 🔴\n🔴 по вертикали", "Судно на мели", "img_aground.png"),
    ]),
    "spec": ("light", "🛥 Особые суда (пр. 23)", [
        ("🟡 мигающий круговой\n⚪ мачтовый\n🔴🟢 бортовые + ⚪ кормовой",
         "Судно на воздушной подушке в неводоизмещающем режиме", "img_hovercraft.png"),
        ("🔴 мигающий круговой высокой интенсивности + огни механического судна",
         "Экраноплан при взлёте, посадке и полёте вблизи поверхности", "img_wig.png"),
    ]),
    "day": ("day", "🔶 Дневные знаки", [
        ("⚫ один шар", "Судно на якоре"),
        ("⚫⚫ два шара по вертикали", "Судно, не имеющее управления"),
        ("⚫ ◆ ⚫ шар – ромб – шар", "Судно, ограниченное в возможности маневрировать"),
        ("▮ цилиндр", "Судно, стеснённое своей осадкой"),
        ("⚫⚫⚫ три шара по вертикали", "Судно на мели"),
        ("⚫⚫⚫ три шара треугольником (на топе мачты и по концам рея)",
         "Судно, занятое работами по устранению минной опасности"),
        ("⚫ ◆ ⚫ + два ⚫ с одной стороны и два ◆ с другой",
         "Судно при дноуглубительных/подводных работах: шары — сторона препятствия, ромбы — сторона прохода"),
        ("▼▲ два конуса вершинами друг к другу", "Судно, занятое ловом рыбы"),
        ("▲ конус вершиной вверх в сторону снастей",
         "Рыболовное судно, снасти которого выступают более чем на 150 м"),
        ("▼ конус вершиной вниз", "Парусное судно, идущее под парусами и работающей машиной"),
        ("◆ ромб", "Буксирующее судно и буксир при длине буксира более 200 м"),
    ]),
}


def norm(e):
    return (e[0], e[1], e[2] if len(e) > 2 else None)


POOLS = {}
for _k, (_kind, _t, _es) in SECTIONS.items():
    POOLS.setdefault(_kind, []).extend(norm(e) for e in _es)

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


BTN_SOUND = "🔊 Звуковые сигналы"
BTN_LIGHT = "💡 Огни и знаки"
BTN_TEST = "📝 Пройти тест"
BTN_LEGEND = "ℹ️ Обозначения"


def kb_reply():
    """Постоянные кнопки внизу экрана (под полем ввода)."""
    b = ReplyKeyboardBuilder()
    for t in (BTN_SOUND, BTN_LIGHT, BTN_TEST, BTN_LEGEND):
        b.button(text=t)
    b.adjust(2, 2)
    return b.as_markup(resize_keyboard=True, is_persistent=True)


def kb_cat(cat):
    kinds = ["sound"] if cat == "sound" else ["light", "day"]
    b = InlineKeyboardBuilder()
    for key, (kind, title, _) in SECTIONS.items():
        if kind in kinds:
            b.button(text=title, callback_data=f"sec:{key}")
    b.button(text="⬅️ Меню", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


def short(text, n=34):
    return text if len(text) <= n else text[: n - 1] + "…"


def kb_section(key):
    kind, _, entries = SECTIONS[key]
    cat = "sound" if kind == "sound" else "light"
    b = InlineKeyboardBuilder()
    n_img = 0
    for idx, e in enumerate(entries):
        _, meaning, img = norm(e)
        if img:
            b.button(text=f"🖼 {short(meaning)}", callback_data=f"img:{key}:{idx}")
            n_img += 1
    b.button(text="⬅️ Назад", callback_data=f"cat:{cat}")
    b.button(text="📝 Тест", callback_data="test")
    b.adjust(*([1] * n_img), 2)
    return b.as_markup()


def kb_img_back(key, img):
    b = InlineKeyboardBuilder()
    for row in view_rows(img):
        b.row(*row)
    b.row(InlineKeyboardButton(text="⬅️ К разделу", callback_data=f"sec:{key}"))
    return b.as_markup()


def kb_modes():
    b = InlineKeyboardBuilder()
    b.button(text="🔊 Звуковые сигналы", callback_data="tm:sound")
    b.button(text="💡 Огни и знаки", callback_data="tm:light")
    b.button(text="🎲 Всё вместе", callback_data="tm:all")
    b.button(text="⬅️ Меню", callback_data="menu")
    b.adjust(1)
    return b.as_markup()


# ---------------------------------------------------------- ОТОБРАЖЕНИЕ ----


async def show(c: CallbackQuery, text, kb, pic=None, same=False):
    """pic — имя файла картинки из IMAGES. same=True — поправить текущее сообщение."""
    msg = c.message
    if pic is not None and pic not in IMAGES:
        pic = None
    try:
        if same:
            if msg.photo:
                await msg.edit_caption(caption=text, reply_markup=kb)
            else:
                await msg.edit_text(text, reply_markup=kb)
            return
        if pic is None and not msg.photo:
            await msg.edit_text(text, reply_markup=kb)
            return
        try:
            await msg.delete()
        except TelegramBadRequest:
            pass
        if pic is None:
            await msg.answer(text, reply_markup=kb)
        else:
            await msg.answer_photo(photo(pic), caption=text, reply_markup=kb)
    except TelegramBadRequest:
        pass


# ----------------------------------------------------------------- ТЕСТ ----


def build_test(mode):
    items = []
    for kind in MODES[mode]:
        items += [(kind, s, m, img) for s, m, img in POOLS[kind]]
    random.shuffle(items)
    items = items[:QUESTIONS_IN_TEST]
    qs = []
    for kind, signal, meaning, img in items:
        wrong = list({m for _, m, _ in POOLS[kind] if m != meaning})
        options = random.sample(wrong, min(3, len(wrong))) + [meaning]
        random.shuffle(options)
        qs.append({"kind": kind, "signal": signal, "img": img, "options": options,
                   "correct": options.index(meaning), "meaning": meaning})
    return qs


def question_text(st, feedback=""):
    q = st["qs"][st["i"]]
    opts = "\n".join(f"<b>{n + 1}.</b> {escape(o)}" for n, o in enumerate(q["options"]))
    sig = "" if has_pic(q["img"]) else f"{escape(q['signal'])}\n\n"
    hint = "<i>Другие виды — кнопками под картинкой.</i>\n\n" if has_pic(q["img"]) else ""
    return (f"<b>Вопрос {st['i'] + 1}/{len(st['qs'])}</b>\n{QTEXT[q['kind']]}\n\n"
            f"{sig}{hint}{opts}{feedback}")


def kb_answers(q):
    b = InlineKeyboardBuilder()
    b.row(*[InlineKeyboardButton(text=str(n + 1), callback_data=f"a:{n}") for n in range(len(q["options"]))])
    if has_pic(q["img"]):
        for row in view_rows(q["img"]):
            b.row(*row)
    return b.as_markup()


# ------------------------------------------------------------- ХЭНДЛЕРЫ ----
dp = Dispatcher()


@dp.message(Command("start", "menu"))
async def start(m: Message):
    await m.answer(WELCOME, reply_markup=kb_reply())


@dp.message(F.text == BTN_SOUND)
async def m_sound(m: Message):
    await m.answer("🔊 <b>Звуковые сигналы</b>\nВыберите раздел:", reply_markup=kb_cat("sound"))


@dp.message(F.text == BTN_LIGHT)
async def m_light(m: Message):
    await m.answer("💡 <b>Огни и знаки</b>\nВыберите раздел:", reply_markup=kb_cat("light"))


@dp.message(F.text == BTN_TEST)
async def m_test(m: Message):
    await m.answer("📝 <b>Тест</b>\nЧто проверяем?", reply_markup=kb_modes())


@dp.message(F.text == BTN_LEGEND)
async def m_legend(m: Message):
    await m.answer(LEGEND)


@dp.callback_query(F.data == "menu")
async def cb_menu(c: CallbackQuery):
    await show(c, "Выберите раздел кнопками внизу 👇", None)
    await c.answer()


@dp.callback_query(F.data.startswith("cat:"))
async def cb_cat(c: CallbackQuery):
    cat = c.data.split(":")[1]
    title = "🔊 <b>Звуковые сигналы</b>" if cat == "sound" else "💡 <b>Огни и знаки</b>"
    await show(c, f"{title}\nВыберите раздел:", kb_cat(cat))
    await c.answer()


@dp.callback_query(F.data.startswith("sec:"))
async def cb_sec(c: CallbackQuery):
    key = c.data.split(":")[1]
    kind, title, entries = SECTIONS[key]
    lines = [f"<b>{escape(title)}</b>\n"]
    for e in entries:
        signal, meaning, img = norm(e)
        mark = " 🖼" if img else ""
        lines.append(f"{escape(signal)}\n→ <i>{escape(meaning)}</i>{mark}\n")
    if kind == "sound":
        lines.append(LEGEND)
    elif any(norm(e)[2] for e in entries):
        lines.append("🖼 — нажмите кнопку ниже, чтобы увидеть, как это выглядит со всех сторон.")
    await show(c, "\n".join(lines), kb_section(key))
    await c.answer()


@dp.callback_query(F.data.startswith("img:"))
async def cb_img(c: CallbackQuery):
    _, key, idx = c.data.split(":")
    signal, meaning, img = norm(SECTIONS[key][2][int(idx)])
    caption = f"<b>{escape(meaning)}</b>\n\n{escape(signal)}"
    await show(c, caption, kb_img_back(key, img), pic=view_file(img))
    await c.answer()


@dp.callback_query(F.data.startswith("v:"))
async def cb_view(c: CallbackQuery):
    """Переключение вида (нос / корма / борта / дневной знак) под картинкой."""
    _, base, view = c.data.split(":")
    name = f"img_{base}_{view}.png"
    if name not in IMAGES or not c.message.photo:
        await c.answer("Этого вида нет")
        return
    try:
        await c.message.edit_media(
            InputMediaPhoto(media=photo(name), caption=c.message.html_text, parse_mode=ParseMode.HTML),
            reply_markup=c.message.reply_markup)
    except TelegramBadRequest:
        pass
    await c.answer()


@dp.callback_query(F.data == "test")
async def cb_test(c: CallbackQuery):
    await show(c, "📝 <b>Тест</b>\nЧто проверяем?", kb_modes())
    await c.answer()


@dp.callback_query(F.data.startswith("tm:"))
async def cb_start_test(c: CallbackQuery):
    mode = c.data.split(":")[1]
    st = STATE[c.from_user.id] = {"qs": build_test(mode), "i": 0, "score": 0, "wrong": [], "mode": mode}
    q = st["qs"][0]
    await show(c, question_text(st), kb_answers(q), pic=view_file(q["img"]) if q["img"] else None)
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
    b.row(InlineKeyboardButton(text="🏁 Результат" if last else "Дальше ▶️", callback_data="next"))
    if has_pic(q["img"]):
        for row in view_rows(q["img"]):
            b.row(*row)
    await show(c, question_text(st, fb), b.as_markup(), same=True)
    await c.answer()


@dp.callback_query(F.data == "next")
async def cb_next(c: CallbackQuery):
    st = STATE.get(c.from_user.id)
    if not st:
        await c.answer("Тест не начат. Нажмите /start", show_alert=True)
        return
    st["i"] += 1
    if st["i"] < len(st["qs"]):
        q = st["qs"][st["i"]]
        await show(c, question_text(st), kb_answers(q), pic=view_file(q["img"]) if q["img"] else None)
    else:
        n = len(st["qs"])
        pct = round(100 * st["score"] / n)
        text = f"🏁 <b>Результат: {st['score']}/{n}</b> ({pct}%)\n"
        if st["wrong"]:
            text += "\n<b>Разбор ошибок:</b>\n"
            for q in st["wrong"]:
                sig = "🖼 (картинка)" if q["img"] else escape(q["signal"])
                text += f"\n{sig}\n→ <i>{escape(q['meaning'])}</i>\n"
        b = InlineKeyboardBuilder()
        b.button(text="🔁 Ещё раз", callback_data=f"tm:{st['mode']}")
        b.button(text="⬅️ Меню", callback_data="menu")
        b.adjust(2)
        await show(c, text, b.as_markup())
    await c.answer()


def load_token():
    """Токен берётся из переменной BOT_TOKEN или из файла .env рядом со скриптом."""
    token = os.environ.get("BOT_TOKEN")
    env_path = BASE_DIR / ".env"
    if not token and env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("BOT_TOKEN="):
                token = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not token:
        raise SystemExit("Не найден BOT_TOKEN: задайте переменную окружения или создайте файл .env")
    return token


async def main():
    bot = Bot(load_token(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
