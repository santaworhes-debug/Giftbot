import logging
import random
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_user, register_user
from gift_service import try_send_bear

games_router = Router()
logger = logging.getLogger(__name__)

# =================== ИГРЫ ===================
# Цены в Stars за 1 попытку
GAMES = {
    "dice": {
        "name": "🎲 КУБИК",
        "stars": 5,
        "emoji": "🎲",
        "description": (
            "🎲 <b>КУБИК!</b>\n"
            "1 попытка — 5 ⭐\n\n"
            "📊 Правила:\n"
            "• Выпадает 4, 5, 6 → 🎯 +50 субиков\n"
            "• Выпадает 1, 2, 3 → 🎯 +10 субиков\n\n"
            "🎯 50 субиков = 🧸 Мишка\n"
            "♻️ Субики копятся со всех игр!\n"
            "💳 1 оплата = 1 ход"
        ),
        "telegram_dice": "🎲",
        "win_values": [4, 5, 6],
        "win_subiki": 50,
        "lose_subiki": 10,
    },
    "coin": {
        "name": "🪙 Монетка",
        "stars": 8,
        "emoji": "🪙",
        "description": (
            "🪙 <b>Монетка!</b>\n"
            "1 попытка — 8 ⭐\n\n"
            "📊 Правила:\n"
            "• ОРЁЛ → 🎯 +50 субиков\n"
            "• РЕШКА → 🎯 +10 субиков\n\n"
            "🎯 50 субиков = 🧸 Мишка\n"
            "♻️ Субики копятся со всех игр!\n"
            "💳 1 оплата = 1 ход"
        ),
        "telegram_dice": None,  # эмулируем сами
        "win_values": None,
        "win_subiki": 50,
        "lose_subiki": 10,
    },
    "slots": {
        "name": "🎰 777",
        "stars": 3,
        "emoji": "🎰",
        "description": (
            "🎰 <b>777!</b>\n"
            "1 попытка — 3 ⭐\n\n"
            "📊 Правила:\n"
            "• Если выпадает 777 → 🎯 +50 субиков\n"
            "• Если нет → 🎯 +10 субиков\n\n"
            "🎯 50 субиков = 🧸 Мишка\n"
            "♻️ Субики копятся со всех игр!\n"
            "💳 1 оплата = 1 ход"
        ),
        "telegram_dice": "🎰",
        "win_values": [64],  # 64 = 777 в Telegram
        "win_subiki": 50,
        "lose_subiki": 10,
    },
    "bowling": {
        "name": "🎳 БОУЛИНГ",
        "stars": 4,
        "emoji": "🎳",
        "description": (
            "🎳 <b>БОУЛИНГ!</b>\n"
            "1 попытка — 4 ⭐\n\n"
            "📊 Правила:\n"
            "• Страйк (6) или 5 → 🎯 +50 субиков\n"
            "• Иначе → 🎯 +10 субиков\n\n"
            "🎯 50 субиков = 🧸 Мишка\n"
            "♻️ Субики копятся со всех игр!\n"
            "💳 1 оплата = 1 ход"
        ),
        "telegram_dice": "🎳",
        "win_values": [5, 6],
        "win_subiki": 50,
        "lose_subiki": 10,
    },
    "basketball": {
        "name": "🏀 БАСКЕТБОЛ",
        "stars": 8,
        "emoji": "🏀",
        "description": (
            "🏀 <b>БАСКЕТБОЛ!</b>\n"
            "1 попытка — 8 ⭐\n\n"
            "📊 Правила:\n"
            "• Гол! → 🎯 +50 субиков\n"
            "• Мимо → 🎯 +10 субиков\n\n"
            "🎯 50 субиков = 🧸 Мишка\n"
            "♻️ Субики копятся со всех игр!\n"
            "💳 1 оплата = 1 ход"
        ),
        "telegram_dice": "🏀",
        "win_values": [4, 5],
        "win_subiki": 50,
        "lose_subiki": 10,
    },
    "football": {
        "name": "⚽ ФУТБОЛ",
        "stars": 8,
        "emoji": "⚽",
        "description": (
            "⚽ <b>ФУТБОЛ!</b>\n"
            "1 попытка — 8 ⭐\n\n"
            "📊 Правила:\n"
            "• Гол → 🎯 +50 субиков\n"
            "• Мимо → 🎯 +10 субиков\n\n"
            "🎯 50 субиков = 🧸 Мишка\n"
            "♻️ Субики копятся со всех игр!\n"
            "💳 1 оплата = 1 ход"
        ),
        "telegram_dice": "⚽",
        "win_values": [3, 4, 5],
        "win_subiki": 50,
        "lose_subiki": 10,
    },
    "darts": {
        "name": "🎯 ДАРТС",
        "stars": 5,
        "emoji": "🎯",
        "description": (
            "🎯 <b>ДАРТС!</b>\n"
            "1 попытка — 5 ⭐\n\n"
            "📊 Правила:\n"
            "• Попадание в центр → 🎯 +50 субиков\n"
            "• Мимо → 🎯 +10 субиков\n\n"
            "🎯 50 субиков = 🧸 Мишка\n"
            "♻️ Субики копятся со всех игр!\n"
            "💳 1 оплата = 1 ход"
        ),
        "telegram_dice": "🎯",
        "win_values": [6],
        "win_subiki": 50,
        "lose_subiki": 10,
    },
}

SUBIKI_FOR_BEAR = 50


def games_menu_kb():
    buttons = []
    for game_id, game in GAMES.items():
        buttons.append([InlineKeyboardButton(
            text=f"{game['emoji']} {game['name'].split(' ', 1)[-1]} — {game['stars']} ⭐",
            callback_data=f"game_info:{game_id}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def game_pay_kb(game_id: str, stars: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"Заплатить ⭐ {stars}",
            callback_data=f"game_pay:{game_id}"
        )],
        [InlineKeyboardButton(text="◀️ К играм", callback_data="games_menu")],
    ])


# =================== ХЭНДЛЕРЫ ===================

@games_router.callback_query(F.data == "games_menu")
async def cb_games_menu(callback: CallbackQuery, bot: Bot):
    import aiosqlite
    from database import DB_PATH
    user_id = callback.from_user.id

    # Получаем баланс субиков
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT subiki FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
    subiki = row[0] if row else 0
    need = max(0, SUBIKI_FOR_BEAR - subiki)

    text = (
        f"🎮 <b>Мини-игры:</b>\n\n"
        f"🎯 Твой баланс субиков — <u>{subiki}</u>\n"
        f"<i>Осталось {need} субиков чтобы получить 🧸 Мишку!</i>\n\n"
        f"Играй в мини-игры ниже\nчтобы получить субики 🎯 👇"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=games_menu_kb())


@games_router.callback_query(F.data.startswith("game_info:"))
async def cb_game_info(callback: CallbackQuery, bot: Bot):
    game_id = callback.data.split(":", 1)[1]
    game = GAMES.get(game_id)
    if not game:
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return

    # Показываем правила и кнопку оплаты
    text = (
        game["description"] + "\n\n"
        "👇 Нажми кнопку ниже, чтобы оплатить ход.\n"
        "<b>После оплаты звёздного счёта вы сможете произвести ход.</b>"
    )
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=game_pay_kb(game_id, game["stars"])
    )


@games_router.callback_query(F.data.startswith("game_pay:"))
async def cb_game_pay(callback: CallbackQuery, bot: Bot):
    game_id = callback.data.split(":", 1)[1]
    game = GAMES.get(game_id)
    if not game:
        await callback.answer("❌ Игра не найдена", show_alert=True)
        return

    await callback.answer()
    # Отправляем инвойс
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=game["name"],
        description=f"1 попытка в игре {game['name']}",
        payload=f"game:{game_id}:{callback.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label=game["name"], amount=game["stars"])],
        provider_token="",
    )

    await callback.message.edit_text(
        f"☝️ Счёт для оплаты хода отправлен.\n"
        f"Ознакомьтесь с правилами перед игрой. "
        f"<b>После оплаты звёздного счёта вы сможете произвести ход.</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ К играм", callback_data="games_menu")]
        ])
    )


@games_router.pre_checkout_query(lambda q: q.invoice_payload.startswith("game:"))
async def game_pre_checkout(pcq, bot: Bot):
    await bot.answer_pre_checkout_query(pcq.id, ok=True)


@games_router.message(F.successful_payment, lambda m: m.successful_payment.invoice_payload.startswith("game:"))
async def game_successful_payment(message: Message, bot: Bot):
    import aiosqlite
    from database import DB_PATH, grant_free_gift
    payload = message.successful_payment.invoice_payload
    parts = payload.split(":")
    if len(parts) < 3:
        return

    game_id = parts[1]
    game = GAMES.get(game_id)
    if not game:
        return

    user_id = message.from_user.id

    # Делаем ход — бросаем кубик/монетку/etc
    dice_emoji = game.get("telegram_dice")
    win_values = game.get("win_values")

    if game_id == "coin":
        # Монетка — эмулируем сами
        result = random.choice(["ОРЁЛ", "РЕШКА"])
        is_win = result == "ОРЁЛ"
        result_text = f"🪙 Выпало: <b>{result}</b>"
    else:
        # Telegram dice
        dice_msg = await bot.send_dice(chat_id=user_id, emoji=dice_emoji)
        dice_value = dice_msg.dice.value
        is_win = dice_value in win_values if win_values else False
        result_text = f"{dice_emoji} Выпало: <b>{dice_value}</b>"

    subiki_earned = game["win_subiki"] if is_win else game["lose_subiki"]

    # Обновляем субики в БД
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET subiki = subiki + ? WHERE user_id=?",
            (subiki_earned, user_id)
        )
        await db.commit()
        async with db.execute("SELECT subiki FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
    total_subiki = row[0] if row else subiki_earned

    result_emoji = "🎉 Выиграл!" if is_win else "😔 Мимо!"
    need = max(0, SUBIKI_FOR_BEAR - total_subiki)

    text = (
        f"{result_emoji}\n"
        f"{result_text}\n\n"
        f"🎯 +{subiki_earned} субиков\n\n"
        f"📊 Твой баланс: <b>{total_subiki}</b> субиков\n"
    )

    # Если набрали 50+ — даём мишку
    if total_subiki >= SUBIKI_FOR_BEAR:
        # Списываем 50 субиков и выдаём мишку
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET subiki = subiki - ? WHERE user_id=?",
                (SUBIKI_FOR_BEAR, user_id)
            )
            await db.commit()
        await grant_free_gift(user_id)
        status = await try_send_bear(bot, user_id, "мини-игра: набрал 50 субиков")
        if status == "sent":
            text += f"\n🎉 <b>50 субиков набрано! Мишка уже в твоём профиле! 🧸</b>"
        else:
            text += f"\n🎉 <b>50 субиков набрано! Мишка в очереди — придёт как только пополнится запас! 🧸</b>"
    else:
        text += f"<i>Ещё {need} субиков до 🧸 Мишки!</i>"

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🔄 Играть ещё — {game['stars']} ⭐", callback_data=f"game_info:{game_id}")],
            [InlineKeyboardButton(text="🎮 К играм", callback_data="games_menu")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")],
        ])
    )


# =================== ОБМЕН СУБИКОВ ===================

@games_router.callback_query(F.data == "exchange_subiki")
async def cb_exchange_subiki(callback: CallbackQuery, bot: Bot):
    import aiosqlite
    from database import DB_PATH, grant_free_gift
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT subiki FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
    subiki = row[0] if row else 0

    if subiki < SUBIKI_FOR_BEAR:
        await callback.answer(
            f"❌ Не хватает субиков! У тебя {subiki}, нужно {SUBIKI_FOR_BEAR}",
            show_alert=True
        )
        return

    # Списываем и выдаём
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET subiki = subiki - ? WHERE user_id=?",
            (SUBIKI_FOR_BEAR, user_id)
        )
        await db.commit()
    await grant_free_gift(user_id)
    status = await try_send_bear(bot, user_id, "обмен субиков")
    await callback.answer()

    if status == "sent":
        text = "🎉 <b>Обмен успешен!</b>\n\n🧸 Мишка уже в твоём профиле!"
    else:
        text = "🎉 <b>Обмен успешен!</b>\n\n⏳ Мишка в очереди — придёт как только пополнится запас."

    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ К играм", callback_data="games_menu")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")],
        ])
    )
