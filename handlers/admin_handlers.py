import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS, REFERRALS_FOR_FREE_BEAR, REQUIRED_CHANNELS
from database import (
    get_bot_stats, get_all_users, get_user, ban_user, unban_user,
    grant_free_gift, get_user_count, get_top_referrers,
    create_check, get_check, deactivate_check, get_admin_checks,
    get_all_checks_stats, update_stats,
    add_bear_stock, get_bear_stock, get_queue_count, get_pending_queue,
    add_broadcast_channel, remove_broadcast_channel, get_broadcast_channels
)
from keyboards import admin_main_kb, admin_back_kb, admin_cancel_kb, check_activate_kb
from gift_service import try_send_bear, process_bear_queue, notify_admins

admin_router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class AdminState(StatesGroup):
    broadcast_text           = State()
    give_bear_id             = State()
    ban_id                   = State()
    find_user                = State()
    check_bears_count        = State()
    check_activations        = State()
    check_password           = State()   # пароль для чека
    broadcast_check_code     = State()
    add_stock_amount         = State()
    add_channel_id           = State()   # добавление канала для рассылки
    broadcast_check_channels = State()   # рассылка чека в каналы
    topup_custom_amount      = State()   # своё количество Stars


class TopupState(StatesGroup):
    custom_amount = State()


async def get_stats_text(bot: Bot) -> str:
    stats        = await get_bot_stats()
    user_cnt     = await get_user_count()
    checks_stats = await get_all_checks_stats()
    stock        = await get_bear_stock()
    queue_cnt    = await get_queue_count()
    bot_info     = await bot.me()

    total_stars  = stats['total_stars_earned']   if stats else 0
    total_gifts  = stats['total_gifts_sold']     if stats else 0
    total_bears  = stats['total_bears_given']    if stats else 0
    total_checks = checks_stats['total']         if checks_stats else 0
    active_checks= checks_stats['active']        if checks_stats else 0
    total_acts   = checks_stats['total_activations'] if checks_stats else 0

    stock_line = f"✅ <b>{stock}</b>" if stock > 0 else f"⚠️ <b>0</b> (пополни!)"
    queue_line = f"⏳ В очереди на мишку: <b>{queue_cnt}</b>" if queue_cnt > 0 else ""

    return (
        f"🔧 <b>АДМИН-ПАНЕЛЬ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Бот: @{bot_info.username}\n"
        f"👥 Пользователей: <b>{user_cnt}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 Продано подарков: <b>{total_gifts}</b>\n"
        f"⭐ Звёздный оборот: <b>{total_stars} ⭐</b>\n"
        f"💰 Примерный доход: <b>${total_stars * 0.013:.2f}</b>\n\n"
        f"🧸 Мишек роздано: <b>{total_bears}</b>\n"
        f"📦 Запас мишек: {stock_line}\n"
        + (f"{queue_line}\n" if queue_line else "") +
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎟 Чеков создано: <b>{total_checks}</b>\n"
        f"✅ Активных чеков: <b>{active_checks}</b>\n"
        f"🎯 Всего активаций: <b>{total_acts}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )


# =================== /admin ===================

@admin_router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    text = await get_stats_text(bot)
    await message.answer(text, parse_mode="HTML", reply_markup=admin_main_kb())


@admin_router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    text = await get_stats_text(bot)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_main_kb())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=admin_main_kb())


@admin_router.callback_query(F.data == "admin_close")
async def cb_admin_close(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.delete()


# =================== СТАТИСТИКА ===================

@admin_router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    text = await get_stats_text(bot)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_back_kb())


# =================== ЗАПАС МИШЕК ===================

@admin_router.callback_query(F.data == "admin_give_bear")
async def cb_give_bear_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    stock     = await get_bear_stock()
    queue_cnt = await get_queue_count()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Пополнить запас мишек", callback_data="admin_add_stock")],
        [InlineKeyboardButton(text="🧸 Выдать мишку вручную (ID)", callback_data="admin_manual_bear")],
        [InlineKeyboardButton(text="◀️ Назад в панель", callback_data="admin_panel")],
    ])

    stock_str = f"✅ {stock}" if stock > 0 else "⚠️ 0 — пополни!"
    queue_str = f"⏳ {queue_cnt} человек ждут мишку" if queue_cnt > 0 else "✅ Очередь пуста"

    await callback.message.edit_text(
        f"🧸 <b>Управление мишками</b>\n\n"
        f"📦 Запас: <b>{stock_str}</b>\n"
        f"👥 Очередь: <b>{queue_str}</b>\n\n"
        f"<b>Как пополнить запас:</b>\n"
        f"1. Нажми «Пополнить запас мишек»\n"
        f"2. Введи количество\n"
        f"3. Бот автоматически разошлёт мишек всем из очереди\n\n"
        f"<i>Звёзды для отправки должны быть на балансе бота!</i>",
        parse_mode="HTML",
        reply_markup=kb
    )


@admin_router.callback_query(F.data == "admin_add_stock")
async def cb_add_stock_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.add_stock_amount)
    await callback.message.edit_text(
        "📦 <b>Пополнение запаса мишек</b>\n\n"
        "Сколько мишек добавить в запас?\n"
        "<i>Введи число, например: 10</i>\n\n"
        "⚠️ Убедись что на балансе бота достаточно Stars!\n"
        "Баланс пополняется через @BotFather → Bot Settings → Stars",
        parse_mode="HTML",
        reply_markup=admin_cancel_kb()
    )


@admin_router.message(AdminState.add_stock_amount)
async def msg_add_stock(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=admin_main_kb())
        return
    try:
        amount = int(message.text.strip())
        if amount < 1 or amount > 10000:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи число от 1 до 10000")
        return

    await add_bear_stock(amount)
    await state.clear()

    stock = await get_bear_stock()
    queue_cnt = await get_queue_count()

    status_msg = await message.answer(
        f"✅ <b>Запас пополнен на {amount} мишек!</b>\n"
        f"📦 Текущий запас: <b>{stock}</b>\n\n"
        + (f"⏳ В очереди: <b>{queue_cnt}</b> человек — начинаю раздачу..." if queue_cnt > 0 else "✅ Очередь пуста"),
        parse_mode="HTML",
        reply_markup=admin_main_kb()
    )

    # Автоматически раздаём очередь
    if queue_cnt > 0:
        sent, remaining = await process_bear_queue(bot)
        await message.answer(
            f"🎉 <b>Раздача завершена!</b>\n\n"
            f"🧸 Отправлено: <b>{sent}</b>\n"
            f"⏳ Осталось в очереди: <b>{remaining}</b>",
            parse_mode="HTML",
            reply_markup=admin_main_kb()
        )


@admin_router.callback_query(F.data == "admin_manual_bear")
async def cb_manual_bear_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.give_bear_id)
    await callback.message.edit_text(
        "🧸 <b>Ручная выдача мишки</b>\n\nВведи Telegram ID пользователя:",
        parse_mode="HTML",
        reply_markup=admin_cancel_kb()
    )


@admin_router.message(AdminState.give_bear_id)
async def msg_give_bear(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=admin_main_kb())
        return
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи числовой ID")
        return

    user = await get_user(uid)
    if not user:
        await message.answer("❌ Пользователь не найден в базе")
        return

    await grant_free_gift(uid)
    status = await try_send_bear(bot, uid, "ручная выдача от админа")
    await update_stats(bears_delta=1)

    try:
        notif = "🎉 <b>Администратор выдал тебе 🧸 Мишку!</b>"
        if status != "sent":
            notif += "\n\n⏳ Придёт автоматически как только пополнится запас."
        await bot.send_message(uid, notif, parse_mode="HTML")
    except Exception:
        pass

    await state.clear()
    result = "отправлен автоматически ✅" if status == "sent" else "в очереди ⏳"
    await message.answer(
        f"🧸 Мишка {result} → {uid}",
        reply_markup=admin_main_kb()
    )


# =================== ПОЛЬЗОВАТЕЛИ ===================

@admin_router.callback_query(F.data == "admin_users")
async def cb_admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    user_cnt = await get_user_count()
    top      = await get_top_referrers(5)
    text     = f"👥 <b>Пользователи бота</b>\n\nВсего: <b>{user_cnt}</b>\n\n"
    text    += "🏆 <b>Топ рефоводов:</b>\n"
    for i, u in enumerate(top, 1):
        uname = f"@{u['username']}" if u['username'] else f"ID {u['user_id']}"
        text += f"{i}. {uname} — {u['referral_count']} рефералов\n"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_back_kb())


@admin_router.callback_query(F.data == "admin_find_user")
async def cb_find_user_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.find_user)
    await callback.message.edit_text(
        "🔍 <b>Поиск пользователя</b>\n\nВведи Telegram ID:",
        parse_mode="HTML", reply_markup=admin_cancel_kb()
    )


@admin_router.message(AdminState.find_user)
async def msg_find_user(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        uid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи числовой ID")
        return
    user = await get_user(uid)
    if not user:
        await message.answer("❌ Пользователь не найден.")
        await state.clear()
        return
    uname  = f"@{user['username']}" if user['username'] else "нет username"
    banned = "🚫 Да" if user['is_banned'] else "✅ Нет"
    text = (
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"📛 Имя: {user['full_name']}\n"
        f"🔗 Username: {uname}\n"
        f"📅 Регистрация: {user['registered_at']}\n"
        f"🚫 Забанен: {banned}\n\n"
        f"👥 Рефералов: {user['referral_count']}\n"
        f"🎁 Мишек получено: {user['gifts_received']}\n"
        f"✅ Мишек доступно: {user['free_gifts_available']}\n"
        f"⭐ Stars потрачено: {user['stars_spent']}\n\n"
        f"<code>/givebear {uid}</code> — выдать мишку\n"
        f"<code>/ban {uid}</code> — забанить"
    )
    await state.clear()
    await message.answer(text, parse_mode="HTML", reply_markup=admin_main_kb())


# =================== РАССЫЛКА ===================

@admin_router.callback_query(F.data == "admin_broadcast")
async def cb_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.broadcast_text)
    await callback.message.edit_text(
        "📣 <b>Рассылка</b>\n\nОтправь текст или перешли сообщение.\n<i>/cancel — отмена</i>",
        parse_mode="HTML", reply_markup=admin_cancel_kb()
    )


@admin_router.message(AdminState.broadcast_text)
async def msg_broadcast(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=admin_main_kb())
        return
    users  = await get_all_users()
    sent   = failed = 0
    status = await message.answer(f"⏳ Рассылка... 0/{len(users)}")
    for i, u in enumerate(users):
        try:
            if message.text:
                await bot.send_message(u["user_id"], message.html_text, parse_mode="HTML")
            elif message.photo:
                await bot.send_photo(u["user_id"], message.photo[-1].file_id, caption=message.caption or "", parse_mode="HTML")
            elif message.video:
                await bot.send_video(u["user_id"], message.video.file_id, caption=message.caption or "", parse_mode="HTML")
            else:
                await bot.copy_message(u["user_id"], message.chat.id, message.message_id)
            sent += 1
        except Exception:
            failed += 1
        if (i + 1) % 30 == 0:
            try:
                await status.edit_text(f"⏳ Рассылка... {i+1}/{len(users)}")
            except Exception:
                pass
    await state.clear()
    await status.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n📤 Отправлено: <b>{sent}</b>\n❌ Ошибок: <b>{failed}</b>",
        parse_mode="HTML", reply_markup=admin_main_kb()
    )


# =================== ПОПОЛНЕНИЕ STARS ===================

class TopupState(StatesGroup):
    custom_amount = State()


@admin_router.callback_query(F.data == "admin_topup_stars")
async def cb_topup_stars_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    amounts = [50, 100, 250, 500, 1000, 2500]
    buttons = []
    row = []
    for amount in amounts:
        row.append(InlineKeyboardButton(text=f"⭐ {amount}", callback_data=f"topup_stars:{amount}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="✏️ Своё количество", callback_data="topup_stars_custom")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад в панель", callback_data="admin_panel")])
    await callback.message.edit_text(
        "⭐ <b>Пополнение Stars бота</b>\n\n"
        "Stars нужны для отправки мишек пользователям.\n\n"
        "📌 <b>Выбери количество Stars:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@admin_router.callback_query(F.data == "topup_stars_custom")
async def cb_topup_stars_custom(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(TopupState.custom_amount)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_topup_stars")]
    ])
    await callback.message.edit_text(
        "⭐ <b>Своё количество Stars</b>\n\n"
        "Введи количество Stars (от 1 до 10000):\n"
        "<i>Например: 300</i>",
        parse_mode="HTML",
        reply_markup=kb
    )


@admin_router.message(TopupState.custom_amount)
async def msg_topup_custom_amount(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    try:
        amount = int(message.text.strip())
        if amount < 1 or amount > 10000:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи число от 1 до 10000")
        return
    await state.clear()
    from aiogram.types import LabeledPrice
    await bot.send_invoice(
        chat_id=message.from_user.id,
        title=f"⭐ Пополнение {amount} Stars",
        description=f"Пополнение баланса бота на {amount} Telegram Stars для отправки мишек",
        payload=f"admin_topup:{amount}",
        currency="XTR",
        prices=[LabeledPrice(label=f"⭐ {amount} Stars", amount=amount)],
        provider_token="",
    )
    await message.answer(
        f"💳 Счёт выставлен на <b>{amount} ⭐</b>\n"
        f"Подтвердите оплату в счёте выше 👆",
        parse_mode="HTML"
    )


@admin_router.callback_query(F.data.startswith("topup_stars:"))
async def cb_topup_stars_pay(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    amount = int(callback.data.split(":")[1])
    from aiogram.types import LabeledPrice
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"⭐ Пополнение {amount} Stars",
        description=f"Пополнение баланса бота на {amount} Telegram Stars для отправки мишек",
        payload=f"admin_topup:{amount}",
        currency="XTR",
        prices=[LabeledPrice(label=f"⭐ {amount} Stars", amount=amount)],
        provider_token="",
    )
    await callback.answer()
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await callback.message.edit_text(
        f"💳 Счёт выставлен на <b>{amount} ⭐</b>\n"
        f"Подтвердите оплату в счёте выше 👆",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_topup_stars")]
        ])
    )


# =================== ЧЕКИ ===================


@admin_router.callback_query(F.data == "admin_create_check")
async def cb_create_check_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.check_bears_count)
    await callback.message.edit_text(
        "🎟 <b>Создание чека</b>\n\n"
        "Шаг 1/3: Сколько человек могут активировать?\n<i>Например: 10</i>",
        parse_mode="HTML", reply_markup=admin_cancel_kb()
    )


@admin_router.message(AdminState.check_bears_count)
async def msg_check_activations(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=admin_main_kb())
        return
    try:
        n = int(message.text.strip())
        if n < 1 or n > 10000:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи число от 1 до 10000")
        return
    await state.update_data(max_activations=n)
    await state.set_state(AdminState.check_activations)
    await message.answer(
        f"✅ Активаций: <b>{n}</b>\n\nШаг 2/3: Сколько мишек за одну активацию?\n<i>Обычно: 1</i>",
        parse_mode="HTML", reply_markup=admin_cancel_kb()
    )


@admin_router.message(AdminState.check_activations)
async def msg_check_bears(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=admin_main_kb())
        return
    try:
        n = int(message.text.strip())
        if n < 1 or n > 10:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи число от 1 до 10")
        return
    await state.update_data(bears_count=n)
    await state.set_state(AdminState.check_password)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔓 Без пароля", callback_data="check_no_password")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel")],
    ])
    await message.answer(
        f"✅ Мишек за активацию: <b>{n}</b>\n\n"
        f"Шаг 3/3: Установить пароль на чек?\n"
        f"<i>Напиши пароль или нажми «Без пароля»</i>",
        parse_mode="HTML", reply_markup=kb
    )


@admin_router.callback_query(F.data == "check_no_password")
async def cb_check_no_password(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    await _finish_check_creation(callback.message, state, bot, password=None, creator_id=callback.from_user.id)


@admin_router.message(AdminState.check_password)
async def msg_check_password(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=admin_main_kb())
        return
    password = message.text.strip()
    if len(password) > 50:
        await message.answer("❌ Пароль слишком длинный (максимум 50 символов)")
        return
    await _finish_check_creation(message, state, bot, password=password, creator_id=message.from_user.id)


async def _finish_check_creation(message, state: FSMContext, bot: Bot, password=None, creator_id: int = None):
    data = await state.get_data()
    max_activations = data["max_activations"]
    bears_count = data.get("bears_count", 1)
    check_code = await create_check(
        creator_id=creator_id,
        bears_count=bears_count,
        max_activations=max_activations,
        password=password
    )
    await update_stats(checks_delta=1)
    await state.clear()

    bot_me = await bot.me()
    check_link = f"https://t.me/{bot_me.username}?start=check_{check_code}"

    password_line = "🔐 Пароль: <b>Требуется</b>" if password else "🔓 Пароль: <b>Не требуется</b>"

    check_text = (
        f"🎁 ПОДАРОЧНЫЙ ЧЕК\n"
        f"——————————————\n"
        f"📦 Товар: <b>Мишка</b>\n"
        f"👥 Мест: <b>{max_activations}</b>\n"
        f"🔒 {password_line}\n"
        f"——————————————\n"
        f"👇 Жми кнопку, чтобы забрать!"
    )

    import os
    photo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "img", "check.png")
    from keyboards import check_activate_kb
    if os.path.exists(photo_path):
        from aiogram.types import FSInputFile
        photo = FSInputFile(photo_path)
        await message.answer_photo(
            photo=photo,
            caption=check_text,
            parse_mode="HTML",
            reply_markup=check_activate_kb(check_code)
        )
    else:
        await message.answer(
            check_text,
            parse_mode="HTML",
            reply_markup=check_activate_kb(check_code)
        )
    await message.answer(
        f"✅ <b>Чек создан!</b>\n\n"
        f"🔑 Код: <code>{check_code}</code>\n"
        f"🔗 Ссылка: <code>{check_link}</code>\n"
        f"{'🔐 Пароль: <b>' + password + '</b>' if password else '🔓 Без пароля'}",
        parse_mode="HTML",
        reply_markup=admin_main_kb()
    )


@admin_router.callback_query(F.data == "admin_my_checks")
async def cb_my_checks(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    checks = await get_admin_checks(callback.from_user.id, limit=10)
    bot_me = await bot.me()
    if not checks:
        await callback.message.edit_text(
            "📋 <b>Твои чеки</b>\n\n<i>Чеков нет. Создай первый!</i>",
            parse_mode="HTML", reply_markup=admin_back_kb()
        )
        return
    text = "📋 <b>Последние 10 чеков:</b>\n\n"
    for ch in checks:
        status = "✅" if ch["is_active"] else "❌"
        link   = f"https://t.me/{bot_me.username}?start=check_{ch['check_code']}"
        text  += (
            f"{status} <code>{ch['check_code']}</code>\n"
            f"   🧸 {ch['total_bears']} мишка | 🔄 {ch['used_count']}/{ch['max_activations']}\n"
            f"   🔗 <a href='{link}'>Ссылка</a>\n\n"
        )
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=admin_back_kb(),
        disable_web_page_preview=True
    )


@admin_router.callback_query(F.data == "admin_broadcast_check")
async def cb_broadcast_check_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    checks = await get_admin_checks(callback.from_user.id, limit=5)
    active = [c for c in checks if c["is_active"]]
    if not active:
        await callback.answer("❌ Нет активных чеков. Создай сначала.", show_alert=True)
        return
    await state.set_state(AdminState.broadcast_check_code)
    text = "📨 <b>Рассылка чека</b>\n\nВведи код чека:\n\n"
    for ch in active:
        text += f"• <code>{ch['check_code']}</code> — {ch['used_count']}/{ch['max_activations']}\n"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_cancel_kb())


@admin_router.message(AdminState.broadcast_check_code)
async def msg_broadcast_check(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=admin_main_kb())
        return
    check_code = message.text.strip()
    check      = await get_check(check_code)
    if not check:
        await message.answer("❌ Чек не найден")
        return
    if not check["is_active"]:
        await message.answer("❌ Чек исчерпан")
        return

    users      = await get_all_users()
    remaining  = check["max_activations"] - check["used_count"]
    password_line = "🔐 Пароль: <b>Требуется</b>" if check["password"] else "🔓 Пароль: <b>Не требуется</b>"
    check_text = (
        f"🎁 ПОДАРОЧНЫЙ ЧЕК\n"
        f"——————————————\n"
        f"📦 Товар: <b>Мишка</b>\n"
        f"👥 Мест: <b>{remaining}</b>\n"
        f"🔒 {password_line}\n"
        f"——————————————\n"
        f"👇 Жми кнопку, чтобы забрать!"
    )
    from keyboards import check_activate_kb
    check_kb = check_activate_kb(check_code)

    import os
    photo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "img", "check.png")
    use_photo = os.path.exists(photo_path)
    photo_file_id = None  # Кэшируем file_id после первой отправки

    sent = failed = 0
    status = await message.answer(f"⏳ Рассылка чека... 0/{len(users)}")
    for i, u in enumerate(users):
        try:
            if use_photo:
                if photo_file_id:
                    await bot.send_photo(u["user_id"], photo_file_id, caption=check_text, parse_mode="HTML", reply_markup=check_kb)
                else:
                    from aiogram.types import FSInputFile
                    photo = FSInputFile(photo_path)
                    sent_msg = await bot.send_photo(u["user_id"], photo, caption=check_text, parse_mode="HTML", reply_markup=check_kb)
                    photo_file_id = sent_msg.photo[-1].file_id
            else:
                await bot.send_message(u["user_id"], check_text, parse_mode="HTML", reply_markup=check_kb)
            sent += 1
        except Exception:
            failed += 1
        if (i + 1) % 30 == 0:
            try:
                await status.edit_text(f"⏳ Рассылка чека... {i+1}/{len(users)}")
            except Exception:
                pass
    await state.clear()
    await status.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n📤 Отправлено: <b>{sent}</b>\n❌ Ошибок: <b>{failed}</b>",
        parse_mode="HTML", reply_markup=admin_main_kb()
    )


# =================== БАН ===================

@admin_router.callback_query(F.data == "admin_ban_menu")
async def cb_ban_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.ban_id)
    await callback.message.edit_text(
        "🚫 <b>Бан / Разбан</b>\n\n"
        "<code>ban 123456789</code> — забанить\n"
        "<code>unban 123456789</code> — разбанить\n\n"
        "<i>/cancel — отмена</i>",
        parse_mode="HTML", reply_markup=admin_cancel_kb()
    )


@admin_router.message(AdminState.ban_id)
async def msg_ban(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=admin_main_kb())
        return
    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("❌ Формат: ban/unban ID")
        return
    action, uid_str = parts
    try:
        uid = int(uid_str)
    except ValueError:
        await message.answer("❌ Неверный ID")
        return
    if action.lower() == "ban":
        await ban_user(uid)
        try:
            await bot.send_message(uid, "🚫 Ваш аккаунт заблокирован.")
        except Exception:
            pass
        await message.answer(f"✅ {uid} заблокирован", reply_markup=admin_main_kb())
    elif action.lower() == "unban":
        await unban_user(uid)
        try:
            await bot.send_message(uid, "✅ Ваш аккаунт разблокирован!")
        except Exception:
            pass
        await message.answer(f"✅ {uid} разблокирован", reply_markup=admin_main_kb())
    else:
        await message.answer("❌ Используй ban или unban")
        return
    await state.clear()


# =================== КАНАЛЫ ===================

class ChannelSubState(StatesGroup):
    adding_channel = State()


@admin_router.callback_query(F.data == "admin_channels")
async def cb_admin_channels(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    await _show_sub_channels(callback.message, bot, edit=True)


async def _show_sub_channels(message, bot: Bot, edit: bool = False):
    from config import REQUIRED_CHANNELS as channels
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    lines = []
    for i, ch in enumerate(channels):
        cid = ch.get("chat_id")
        status_icon = "❓"
        if cid:
            try:
                bot_member = await bot.get_chat_member(cid, (await bot.me()).id)
                if bot_member.status in ("administrator", "creator"):
                    status_icon = "✅"
                else:
                    status_icon = "⚠️"
            except Exception:
                status_icon = "❌"
        lines.append(
            f"{status_icon} <b>{ch['title']}</b>\n"
            f"   ID: <code>{cid}</code> | <a href='{ch['url']}'>ссылка</a>"
        )

    ch_text = "\n\n".join(lines) if lines else "<i>Каналов нет</i>"

    legend = (
        "✅ — бот admin в канале\n"
        "⚠️ — бот участник, но не admin\n"
        "❌ — бот не добавлен в канал\n\n"
        "⚠️ Для работы подписки бот должен быть <b>администратором</b> каждого канала!"
    )

    buttons = [
        [InlineKeyboardButton(text="➕ Добавить канал подписки", callback_data="admin_sub_add_channel")],
        [InlineKeyboardButton(text="🗑 Удалить канал", callback_data="admin_sub_remove_channel")],
        [InlineKeyboardButton(text="🔄 Обновить статусы", callback_data="admin_channels")],
        [InlineKeyboardButton(text="◀️ Назад в панель", callback_data="admin_panel")],
    ]

    text = (
        f"📢 <b>Каналы обязательной подписки</b>\n\n"
        f"{ch_text}\n\n"
        f"<i>{legend}</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    if edit:
        try:
            await message.edit_text(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
        except Exception:
            await message.answer(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)


@admin_router.callback_query(F.data == "admin_sub_add_channel")
async def cb_sub_add_channel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(ChannelSubState.adding_channel)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await callback.message.edit_text(
        "➕ <b>Добавление канала обязательной подписки</b>\n\n"
        "Отправь данные в формате:\n"
        "<code>chat_id | Название | https://t.me/username</code>\n\n"
        "Пример:\n"
        "<code>-1001234567890 | МОЙ КАНАЛ | https://t.me/mychannel</code>\n\n"
        "📌 <b>Как узнать chat_id:</b>\n"
        "Перешли любое сообщение из канала боту @getidsbot\n\n"
        "⚠️ Бот должен быть <b>администратором</b> в канале!\n\n"
        "<i>/cancel — отмена</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_channels")]
        ])
    )


@admin_router.message(ChannelSubState.adding_channel)
async def msg_sub_add_channel(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.strip() in ("/cancel", "отмена"):
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=admin_main_kb())
        return

    text = message.text.strip() if message.text else ""
    parts = [p.strip() for p in text.split("|")]
    if len(parts) != 3:
        await message.answer(
            "❌ Неверный формат!\n\n"
            "Отправь в формате:\n"
            "<code>chat_id | Название | https://t.me/username</code>",
            parse_mode="HTML"
        )
        return

    try:
        chat_id = int(parts[0])
    except ValueError:
        await message.answer("❌ chat_id должен быть числом (например: <code>-1001234567890</code>)", parse_mode="HTML")
        return

    title = parts[1]
    url = parts[2]

    if not url.startswith("https://t.me/"):
        await message.answer("❌ Ссылка должна начинаться с https://t.me/")
        return

    # Проверяем доступность канала
    try:
        chat_info = await bot.get_chat(chat_id)
        bot_member = await bot.get_chat_member(chat_id, (await bot.me()).id)
        if bot_member.status not in ("administrator", "creator"):
            await message.answer(
                f"⚠️ <b>Канал найден, но бот не является администратором!</b>\n\n"
                f"Канал: <b>{chat_info.title}</b>\n\n"
                f"Добавь бота как администратора, затем попробуй снова.",
                parse_mode="HTML"
            )
            return
        status_msg = f"✅ Бот является администратором в <b>{chat_info.title}</b>"
    except Exception as e:
        status_msg = f"⚠️ Не удалось проверить канал: {e}\nКанал добавлен, но убедись что бот — администратор!"

    # Добавляем в config динамически (в runtime)
    import config as cfg
    # Проверяем дубликат
    for ch in cfg.REQUIRED_CHANNELS:
        if ch.get("chat_id") == chat_id:
            await message.answer(f"⚠️ Канал с chat_id <code>{chat_id}</code> уже есть в списке!", parse_mode="HTML")
            await state.clear()
            return

    cfg.REQUIRED_CHANNELS.append({
        "chat_id": chat_id,
        "title": title,
        "url": url
    })

    # Сохраняем в config.py на диск
    await _save_channels_to_config(cfg.REQUIRED_CHANNELS)

    await state.clear()
    await message.answer(
        f"✅ <b>Канал добавлен!</b>\n\n"
        f"📢 <b>{title}</b>\n"
        f"🆔 <code>{chat_id}</code>\n"
        f"🔗 {url}\n\n"
        f"{status_msg}",
        parse_mode="HTML",
        reply_markup=admin_main_kb()
    )


@admin_router.callback_query(F.data == "admin_sub_remove_channel")
async def cb_sub_remove_channel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    import config as cfg
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    if not cfg.REQUIRED_CHANNELS:
        await callback.answer("Список каналов пуст", show_alert=True)
        return

    buttons = []
    for ch in cfg.REQUIRED_CHANNELS:
        cid = ch.get("chat_id", 0)
        buttons.append([InlineKeyboardButton(
            text=f"🗑 {ch['title']} ({cid})",
            callback_data=f"sub_del_ch:{cid}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_channels")])

    await callback.message.edit_text(
        "🗑 <b>Удалить канал обязательной подписки</b>\n\n"
        "Нажми на канал который хочешь удалить:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@admin_router.callback_query(F.data.startswith("sub_del_ch:"))
async def cb_sub_del_ch(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    import config as cfg
    try:
        chat_id = int(callback.data.split(":")[1])
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    removed = None
    cfg.REQUIRED_CHANNELS = [ch for ch in cfg.REQUIRED_CHANNELS if ch.get("chat_id") != chat_id]
    await _save_channels_to_config(cfg.REQUIRED_CHANNELS)

    await callback.answer(f"✅ Канал удалён из списка подписки", show_alert=True)
    await _show_sub_channels(callback.message, bot, edit=True)


async def _save_channels_to_config(channels: list):
    """Сохраняет список каналов обратно в config.py"""
    import os
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.py")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Строим новый блок REQUIRED_CHANNELS
        new_block = "REQUIRED_CHANNELS = [\n"
        for ch in channels:
            new_block += (
                f"    {{\n"
                f"        \"chat_id\": {ch['chat_id']},\n"
                f"        \"title\": \"{ch['title']}\",\n"
                f"        \"url\": \"{ch['url']}\"\n"
                f"    }},\n"
            )
        new_block += "]"

        import re
        new_content = re.sub(
            r"REQUIRED_CHANNELS\s*=\s*\[.*?\]",
            new_block,
            content,
            flags=re.DOTALL
        )
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        logger.info("config.py обновлён успешно")
    except Exception as e:
        logger.error(f"Не удалось сохранить config.py: {e}")


# =================== КОМАНДЫ ===================

@admin_router.message(Command("givebear"))
async def cmd_givebear(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /givebear USER_ID")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID")
        return
    await grant_free_gift(uid)
    status = await try_send_bear(bot, uid, "команда /givebear")
    await update_stats(bears_delta=1)
    try:
        await bot.send_message(uid, "🎉 <b>Администратор выдал тебе 🧸 Мишку!</b>", parse_mode="HTML")
    except Exception:
        pass
    result = "отправлен ✅" if status == "sent" else "в очереди ⏳"
    await message.answer(f"🧸 Мишка {result} → {uid}")


@admin_router.message(Command("addstock"))
async def cmd_addstock(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /addstock КОЛИЧЕСТВО")
        return
    try:
        amount = int(parts[1])
    except ValueError:
        await message.answer("❌ Введи число")
        return
    await add_bear_stock(amount)
    stock = await get_bear_stock()
    await message.answer(f"✅ Добавлено {amount} мишек. Запас: {stock}")
    # Раздаём очередь
    sent, remaining = await process_bear_queue(bot)
    if sent > 0:
        await message.answer(f"🧸 Из очереди отправлено: {sent}. Осталось: {remaining}")


@admin_router.message(Command("stock"))
async def cmd_stock(message: Message):
    if not is_admin(message.from_user.id):
        return
    stock     = await get_bear_stock()
    queue_cnt = await get_queue_count()
    await message.answer(
        f"📦 Запас мишек: <b>{stock}</b>\n"
        f"⏳ В очереди: <b>{queue_cnt}</b>",
        parse_mode="HTML"
    )


@admin_router.message(Command("ban"))
async def cmd_ban(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /ban USER_ID")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID")
        return
    await ban_user(uid)
    try:
        await bot.send_message(uid, "🚫 Ваш аккаунт заблокирован.")
    except Exception:
        pass
    await message.answer(f"✅ {uid} заблокирован")


@admin_router.message(Command("unban"))
async def cmd_unban(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /unban USER_ID")
        return
    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID")
        return
    await unban_user(uid)
    try:
        await bot.send_message(uid, "✅ Ваш аккаунт разблокирован!")
    except Exception:
        pass
    await message.answer(f"✅ {uid} разблокирован")


@admin_router.message(Command("stats"))
async def cmd_stats(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    text = await get_stats_text(bot)
    await message.answer(text, parse_mode="HTML", reply_markup=admin_main_kb())


@admin_router.pre_checkout_query(lambda q: q.invoice_payload.startswith("admin_topup:"))
async def admin_pre_checkout(pcq, bot: Bot):
    """Подтверждение оплаты Stars от админа — ОБЯЗАТЕЛЬНО для работы платежа"""
    await bot.answer_pre_checkout_query(pcq.id, ok=True)


@admin_router.message(
    F.successful_payment,
    lambda m: m.successful_payment and m.successful_payment.invoice_payload.startswith("admin_topup:")
)
async def admin_successful_payment(message: Message, bot: Bot):
    """Обработка пополнения Stars от админа"""
    if not is_admin(message.from_user.id):
        return
    amount = message.successful_payment.total_amount
    await update_stats(stars_delta=amount)
    await message.answer(
        f"✅ <b>Баланс бота пополнен на {amount} ⭐!</b>\n\n"
        f"Stars зачислены на баланс бота.\n"
        f"Теперь можно отправлять мишек пользователям!\n\n"
        f"<i>Для пополнения запаса мишек перейди в 🐻 Выдать мишку</i>",
        parse_mode="HTML",
        reply_markup=admin_main_kb()
    )


# =================== УПРАВЛЕНИЕ КАНАЛАМИ ДЛЯ РАССЫЛКИ ===================

@admin_router.callback_query(F.data == "admin_manage_channels")
async def cb_manage_channels(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    channels = await get_broadcast_channels()

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for ch in channels:
        icon = "📢" if ch["chat_type"] == "channel" else "👥"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {ch['title']}  ✖️ удалить",
            callback_data=f"del_bchan:{ch['chat_id']}"
        )])
    buttons.append([InlineKeyboardButton(text="➕ Добавить канал / группу", callback_data="admin_add_channel")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад в панель", callback_data="admin_panel")])

    if channels:
        text = (
            "⚙️ <b>Каналы/группы для рассылки чеков</b>\n\n"
            "Нажми на канал чтобы <b>удалить</b> его из списка:\n"
        )
    else:
        text = (
            "⚙️ <b>Каналы/группы для рассылки чеков</b>\n\n"
            "<i>Список пуст. Добавь канал или группу!</i>\n\n"
            "📌 <b>Как добавить:</b>\n"
            "1. Добавь бота в канал/группу как <b>администратора</b>\n"
            "2. Нажми «Добавить» и введи chat_id\n"
            "3. Узнать chat_id: перешли сообщение из канала боту @userinfobot\n"
        )

    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@admin_router.callback_query(F.data.startswith("del_bchan:"))
async def cb_delete_broadcast_channel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    chat_id = int(callback.data.split(":")[1])
    await remove_broadcast_channel(chat_id)
    await callback.answer("✅ Канал удалён из списка рассылки", show_alert=True)

    # Обновляем список
    channels = await get_broadcast_channels()
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for ch in channels:
        icon = "📢" if ch["chat_type"] == "channel" else "👥"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {ch['title']}  ✖️ удалить",
            callback_data=f"del_bchan:{ch['chat_id']}"
        )])
    buttons.append([InlineKeyboardButton(text="➕ Добавить канал / группу", callback_data="admin_add_channel")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад в панель", callback_data="admin_panel")])

    text = (
        "⚙️ <b>Каналы/группы для рассылки чеков</b>\n\n"
        + ("Нажми на канал чтобы <b>удалить</b>:\n" if channels else "<i>Список пуст.</i>")
    )
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@admin_router.callback_query(F.data == "admin_add_channel")
async def cb_add_channel_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.add_channel_id)
    await callback.message.edit_text(
        "➕ <b>Добавление канала / группы</b>\n\n"
        "Введи <b>chat_id</b> канала или группы.\n\n"
        "📌 <b>Как узнать chat_id:</b>\n"
        "• Перешли любое сообщение из канала/группы боту @userinfobot\n"
        "• Для каналов обычно формат: <code>-1001234567890</code>\n\n"
        "⚠️ Бот должен быть <b>администратором</b> в канале/группе!\n\n"
        "<i>/cancel — отмена</i>",
        parse_mode="HTML",
        reply_markup=admin_cancel_kb()
    )


@admin_router.message(AdminState.add_channel_id)
async def msg_add_channel(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=admin_main_kb())
        return

    raw = message.text.strip()
    try:
        chat_id = int(raw)
    except ValueError:
        await message.answer(
            "❌ Введи числовой chat_id\n"
            "Например: <code>-1001234567890</code>",
            parse_mode="HTML"
        )
        return

    # Проверяем что бот имеет доступ к этому чату
    try:
        chat_info = await bot.get_chat(chat_id)
    except Exception as e:
        await message.answer(
            f"❌ <b>Не могу получить информацию о чате!</b>\n\n"
            f"Убедись что:\n"
            f"• Бот добавлен в канал/группу как <b>администратор</b>\n"
            f"• chat_id введён верно\n\n"
            f"<i>Ошибка: {e}</i>",
            parse_mode="HTML"
        )
        return

    title = chat_info.title or str(chat_id)
    chat_type = "channel" if chat_info.type == "channel" else "group"
    await add_broadcast_channel(chat_id, title, chat_type)
    await state.clear()

    icon = "📢" if chat_type == "channel" else "👥"
    await message.answer(
        f"✅ <b>Добавлено!</b>\n\n"
        f"{icon} <b>{title}</b>\n"
        f"🆔 ID: <code>{chat_id}</code>\n"
        f"📁 Тип: {chat_type}\n\n"
        f"Теперь можно делать рассылку чеков в этот {'канал' if chat_type == 'channel' else 'чат'}.",
        parse_mode="HTML",
        reply_markup=admin_main_kb()
    )


# =================== РАССЫЛКА ЧЕКА В КАНАЛЫ/ГРУППЫ ===================

@admin_router.callback_query(F.data == "admin_broadcast_check_channels")
async def cb_broadcast_check_channels_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    channels = await get_broadcast_channels()
    if not channels:
        await callback.answer(
            "❌ Нет каналов/групп для рассылки.\n"
            "Сначала добавь их через «Каналы для рассылки чеков».",
            show_alert=True
        )
        return

    checks = await get_admin_checks(callback.from_user.id, limit=10)
    active = [c for c in checks if c["is_active"]]
    if not active:
        await callback.answer("❌ Нет активных чеков. Сначала создай чек.", show_alert=True)
        return

    await state.set_state(AdminState.broadcast_check_channels)

    ch_list = "\n".join([
        f"  {'📢' if ch['chat_type'] == 'channel' else '👥'} {ch['title']}"
        for ch in channels
    ])
    checks_list = "\n".join([
        f"  • <code>{ch['check_code']}</code> — {ch['used_count']}/{ch['max_activations']} активаций, {ch['total_bears']} 🧸"
        for ch in active
    ])

    await callback.message.edit_text(
        f"📢 <b>Рассылка чека в каналы/группы</b>\n\n"
        f"<b>Каналы для отправки ({len(channels)}):</b>\n{ch_list}\n\n"
        f"<b>Активные чеки:</b>\n{checks_list}\n\n"
        f"Введи <b>код чека</b> для рассылки:\n"
        f"<i>/cancel — отмена</i>",
        parse_mode="HTML",
        reply_markup=admin_cancel_kb()
    )


@admin_router.message(AdminState.broadcast_check_channels)
async def msg_broadcast_check_channels(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=admin_main_kb())
        return

    check_code = message.text.strip()
    check = await get_check(check_code)
    if not check:
        await message.answer("❌ Чек не найден. Проверь код и попробуй снова.")
        return
    if not check["is_active"]:
        await message.answer("❌ Чек неактивен или исчерпан.")
        return

    channels = await get_broadcast_channels()
    if not channels:
        await message.answer("❌ Нет каналов для рассылки.")
        await state.clear()
        return

    remaining = check["max_activations"] - check["used_count"]
    password_line = "🔐 Пароль: <b>Требуется</b>" if check["password"] else "🔓 Пароль: <b>Не требуется</b>"
    check_text = (
        f"🎁 ПОДАРОЧНЫЙ ЧЕК\n"
        f"——————————————\n"
        f"📦 Товар: <b>Мишка</b>\n"
        f"👥 Мест: <b>{remaining}</b>\n"
        f"🔒 {password_line}\n"
        f"——————————————\n"
        f"👇 Жми кнопку, чтобы забрать!"
    )
    check_kb = check_activate_kb(check_code)

    import os
    photo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "img", "check.png")
    use_photo = os.path.exists(photo_path)
    photo_file_id = None

    sent = 0
    failed = 0
    errors = []

    status_msg = await message.answer(f"⏳ Отправляю в каналы... 0/{len(channels)}")

    # Получаем username бота для deeplink кнопки
    bot_me = await bot.me()
    from keyboards import check_activate_channel_kb
    channel_kb = check_activate_channel_kb(check_code, bot_me.username)

    for i, ch in enumerate(channels):
        try:
            if use_photo:
                if photo_file_id:
                    await bot.send_photo(
                        ch["chat_id"], photo_file_id,
                        caption=check_text, parse_mode="HTML", reply_markup=channel_kb
                    )
                else:
                    from aiogram.types import FSInputFile
                    photo = FSInputFile(photo_path)
                    sent_msg = await bot.send_photo(
                        ch["chat_id"], photo,
                        caption=check_text, parse_mode="HTML", reply_markup=channel_kb
                    )
                    photo_file_id = sent_msg.photo[-1].file_id
            else:
                await bot.send_message(
                    ch["chat_id"], check_text,
                    parse_mode="HTML", reply_markup=channel_kb
                )
            sent += 1
        except Exception as e:
            failed += 1
            errors.append(f"❌ {ch['title']}: {e}")
            logger.error(f"Ошибка отправки чека в {ch['title']} ({ch['chat_id']}): {e}")

        try:
            await status_msg.edit_text(f"⏳ Отправляю в каналы... {i+1}/{len(channels)}")
        except Exception:
            pass

    await state.clear()

    result_text = (
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📤 Отправлено: <b>{sent}</b> каналов/групп\n"
        f"❌ Ошибок: <b>{failed}</b>\n"
    )
    if errors:
        result_text += "\n<b>Каналы с ошибками:</b>\n" + "\n".join(errors[:5])
        result_text += "\n\n⚠️ Убедись что бот является <b>администратором</b> в этих каналах!"

    await status_msg.edit_text(result_text, parse_mode="HTML", reply_markup=admin_main_kb())

