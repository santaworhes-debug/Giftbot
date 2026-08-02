import logging
import asyncio
import random
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, Message

from database import get_user
from cases import CASES, roll_case, get_reel_items
from gifts import GIFTS
from gift_service import send_gift_by_id, try_send_bear

cases_router = Router()
logger = logging.getLogger(__name__)


# =================== КЛАВИАТУРЫ ===================

def cases_menu_kb():
    buttons = []
    for case_key, case in CASES.items():
        price_text = "Бесплатно 🎁" if case["price"] == 0 else f"{case['price']} ⭐"
        buttons.append([InlineKeyboardButton(
            text=f"{case['emoji']} {case['name']} — {price_text}",
            callback_data=f"case_view:{case_key}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def case_result_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Магазин кейсов", callback_data="cases_shop")],
        [InlineKeyboardButton(text="◀️ В меню", callback_data="main_menu")],
    ])


# =================== ДЕЙЛИ КУЛДАУН ===================

async def get_daily_case_status(user_id: int) -> tuple:
    """Возвращает (can_open: bool, next_open_time: str | None)"""
    import aiosqlite
    from database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT last_daily_case FROM users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()

    if not row or not row["last_daily_case"]:
        return True, None

    last = datetime.fromisoformat(row["last_daily_case"])
    next_time = last + timedelta(hours=24)
    now = datetime.now()
    if now >= next_time:
        return True, None

    remaining = next_time - now
    hours = int(remaining.total_seconds() // 3600)
    minutes = int((remaining.total_seconds() % 3600) // 60)
    return False, f"{hours}ч {minutes}м"


async def set_daily_case_used(user_id: int):
    import aiosqlite
    from database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_daily_case=? WHERE user_id=?",
            (datetime.now().isoformat(), user_id)
        )
        await db.commit()


async def ensure_daily_case_column():
    import aiosqlite
    from database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("ALTER TABLE users ADD COLUMN last_daily_case TEXT DEFAULT NULL")
            await db.commit()
        except Exception:
            pass


# =================== ТЕКСТ КЕЙСА ===================

def build_case_text(case_key: str) -> str:
    case = CASES[case_key]
    items_text = ""
    for item in case["items"]:
        chance = item["chance"]
        if chance <= 1:
            rarity = "🔴"
        elif chance <= 3:
            rarity = "🟠"
        elif chance <= 10:
            rarity = "🟡"
        else:
            rarity = "🟢"
        items_text += f"{rarity} {item['name']} — {chance}%\n"

    daily_note = "\n⏰ <i>Доступен раз в 24 часа</i>" if case.get("daily") else ""
    price_text = "Бесплатно!" if case["price"] == 0 else f"{case['price']} ⭐"

    return (
        f"{case['emoji']} <b>{case['name']}</b>\n"
        f"——————————————\n"
        f"📝 {case['description']}\n"
        f"💰 Цена: <b>{price_text}</b>"
        f"{daily_note}\n\n"
        f"📊 <b>Содержимое:</b>\n"
        f"{items_text}"
        f"——————————————\n"
        f"🟢 Часто  🟡 Редко  🟠 Очень редко  🔴 Эпик"
    )


# =================== АНИМАЦИЯ ПРОКРУТКИ ===================

SPIN_FRAMES = [
    # (кадр, задержка сек)
    ("speed_fast",  0.25),
    ("speed_fast",  0.25),
    ("speed_fast",  0.3),
    ("speed_mid",   0.4),
    ("speed_mid",   0.5),
    ("speed_slow",  0.65),
    ("speed_slow",  0.8),
    ("speed_final", 0.0),   # финальный кадр — задержка не нужна
]

def _render_reel(reel: list, frame_idx: int, won_item: dict) -> str:
    """Рендерит ленту с подсветкой центра"""
    center = len(reel) // 2
    lines = []
    # Показываем 5 элементов вокруг центра на разных фазах
    if frame_idx < 3:
        window = 5
    elif frame_idx < 6:
        window = 5
    else:
        window = 5

    start = max(0, center - window // 2)
    end = min(len(reel), start + window)

    for i in range(start, end):
        item = reel[i]
        if i == center:
            lines.append(f"▶️  {item['name']}  ◀️")
        else:
            lines.append(f"     {item['name']}")
    return "\n".join(lines)


async def animate_case_spin(
    message: Message,
    case_key: str,
    won_item: dict,
):
    """
    Показывает анимацию прокрутки рулетки через редактирование сообщения.
    """
    case = CASES[case_key]
    reel = get_reel_items(case_key, won_item, reel_size=21)
    center = len(reel) // 2

    # Фазы прокрутки: смещение ленты
    # Начинаем с начала ленты и постепенно доходим до центра
    total_frames = 8
    phases = []
    for i in range(total_frames):
        # Прогресс от 0 до center
        progress = i / (total_frames - 1)
        offset = int(progress * center)
        phases.append(offset)

    delays = [0.22, 0.22, 0.28, 0.35, 0.45, 0.6, 0.75, 0.0]

    spin_emojis = ["🎰", "💫", "✨", "⭐", "🌟", "💥", "🎆", "🎊"]

    for frame_i, (offset, delay) in enumerate(zip(phases, delays)):
        is_final = (frame_i == total_frames - 1)

        # Строим окошко рулетки (5 ячеек, центральная — цель)
        view_start = offset
        view_end = min(view_start + 5, len(reel))
        view = reel[view_start:view_end]
        while len(view) < 5:
            view.append(random.choice(reel))

        pointer_idx = min(frame_i, 4) if not is_final else 2  # двигается к центру

        lines = []
        for j, item in enumerate(view):
            if j == pointer_idx and is_final:
                lines.append(f"🎯  <b>{item['name']}</b>  🎯")
            elif j == pointer_idx:
                lines.append(f"▶️  {item['name']}")
            else:
                lines.append(f"　　{item['name']}")

        reel_text = "\n".join(lines)

        if is_final:
            spin_icon = "🏁"
            status = "Результат:"
        else:
            spin_icon = spin_emojis[frame_i % len(spin_emojis)]
            bars = "█" * (frame_i + 1) + "░" * (total_frames - frame_i - 1)
            status = f"Крутится... [{bars}]"

        text = (
            f"{case['emoji']} <b>{case['name']}</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"{spin_icon} <i>{status}</i>\n"
            f"━━━━━━━━━━━━━━\n"
            f"{reel_text}\n"
            f"━━━━━━━━━━━━━━"
        )

        try:
            await message.edit_text(text, parse_mode="HTML")
        except Exception:
            pass

        if not is_final and delay > 0:
            await asyncio.sleep(delay)


# =================== ВЫДАЧА ПРИЗА ===================

async def _send_result(
    message: Message,
    bot: Bot,
    user_id: int,
    case_key: str,
    won: dict,
):
    """Выдаёт приз и показывает финальное сообщение."""
    case = CASES[case_key]

    if won["type"] == "nothing":
        await message.edit_text(
            f"📦 <b>{case['name']}</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"💩 <b>Ничего не выпало...</b>\n\n"
            f"😔 В этот раз не повезло! Попробуй ещё раз!\n"
            f"🍀 Удача обязательно придёт!",
            parse_mode="HTML",
            reply_markup=case_result_kb()
        )
        return

    gift_key = won.get("gift_key")
    gift = GIFTS.get(gift_key)
    if not gift:
        await message.edit_text("❌ Ошибка при выдаче приза", parse_mode="HTML", reply_markup=case_result_kb())
        return

    if gift_key == "bear":
        result = await try_send_bear(bot, user_id, f"case_{case_key}")
        sent = result == "sent"
    else:
        sent = await send_gift_by_id(bot, user_id, gift["gift_id"], f"🎁 Приз из кейса: {gift['name']}")

    if sent:
        result_text = (
            f"🎉 <b>ПОЗДРАВЛЯЕМ!</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"{gift['emoji']} <b>{gift['name']}</b>\n\n"
            f"✅ Подарок уже отправлен тебе в Telegram!"
        )
    else:
        result_text = (
            f"🎉 Выпало: {gift['emoji']} <b>{gift['name']}</b>\n"
            f"━━━━━━━━━━━━━━\n"
            f"⏳ Подарок добавлен в очередь — получишь как только появится на складе!"
        )

    await message.edit_text(result_text, parse_mode="HTML", reply_markup=case_result_kb())


# =================== ХЕНДЛЕРЫ ===================

@cases_router.callback_query(F.data == "cases_shop")
async def cb_cases_shop(callback: CallbackQuery):
    await callback.message.edit_text(
        "📦 <b>МАГАЗИН КЕЙСОВ</b>\n"
        "━━━━━━━━━━━━━━\n"
        "Открывай кейсы и получай подарки!\n"
        "💎 Алмаз, 🚀 Ракета — редкие призы\n"
        "🎁 Бесплатный кейс доступен каждые 24ч\n\n"
        "Выберите кейс 👇",
        parse_mode="HTML",
        reply_markup=cases_menu_kb()
    )


@cases_router.callback_query(F.data.startswith("case_view:"))
async def cb_case_view(callback: CallbackQuery):
    case_key = callback.data.split(":")[1]
    case = CASES.get(case_key)
    if not case:
        await callback.answer("❌ Кейс не найден", show_alert=True)
        return

    text = build_case_text(case_key)

    if case["price"] == 0:
        can_open, wait_time = await get_daily_case_status(callback.from_user.id)
        if not can_open:
            text += f"\n\n⏳ <b>Следующий кейс через: {wait_time}</b>"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="cases_shop")]
            ])
        else:
            text += "\n\n✅ <b>Доступен прямо сейчас!</b>"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎁 Открыть бесплатно!", callback_data=f"case_open:{case_key}")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="cases_shop")],
            ])
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"🚀 Открыть за {case['price']} ⭐",
                callback_data=f"case_buy:{case_key}"
            )],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="cases_shop")]
        ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@cases_router.callback_query(F.data.startswith("case_open:"))
async def cb_case_open_free(callback: CallbackQuery, bot: Bot):
    """Открытие бесплатного ежедневного кейса с анимацией"""
    case_key = callback.data.split(":")[1]
    case = CASES.get(case_key)

    if not case or case["price"] != 0:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    can_open, wait_time = await get_daily_case_status(callback.from_user.id)
    if not can_open:
        await callback.answer(f"⏳ Следующий кейс через {wait_time}", show_alert=True)
        return

    await set_daily_case_used(callback.from_user.id)
    await callback.answer()

    won = roll_case(case_key)

    # Запускаем анимацию
    await animate_case_spin(callback.message, case_key, won)

    # Небольшая пауза перед показом результата
    await asyncio.sleep(0.5)

    await _send_result(callback.message, bot, callback.from_user.id, case_key, won)


@cases_router.callback_query(F.data.startswith("case_buy:"))
async def cb_case_buy(callback: CallbackQuery, bot: Bot):
    """Оплата платного кейса через Stars"""
    case_key = callback.data.split(":")[1]
    case = CASES.get(case_key)
    if not case or case["price"] == 0:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"{case['emoji']} {case['name']}",
        description=case["description"],
        payload=f"case:{case_key}:{callback.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label=case["name"], amount=case["price"])],
        provider_token="",
    )
    await callback.answer()


async def handle_case_payment(bot: Bot, user_id: int, case_key: str, message: Message):
    """Вызывается после успешной оплаты кейса — с анимацией"""
    case = CASES.get(case_key)
    if not case:
        return

    won = roll_case(case_key)

    # Отправляем отдельное сообщение с анимацией (т.к. message — это successful_payment)
    spin_msg = await message.answer(
        f"{case['emoji']} <b>{case['name']}</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"🎰 <i>Запускаем рулетку...</i>\n"
        f"━━━━━━━━━━━━━━",
        parse_mode="HTML"
    )

    await animate_case_spin(spin_msg, case_key, won)
    await asyncio.sleep(0.5)
    await _send_result(spin_msg, bot, user_id, case_key, won)
