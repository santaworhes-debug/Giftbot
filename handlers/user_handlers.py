import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import REQUIRED_CHANNELS, REFERRALS_FOR_FREE_BEAR
from database import (
    get_user, register_user, is_new_user, add_referral, get_top_referrers,
    grant_free_gift, use_free_gift, add_gift_history, update_stats,
    get_bot_stats, get_check, activate_check, add_to_bear_queue, get_bear_stock
)
from keyboards import (
    main_menu_kb, gifts_menu_kb, gift_caption_kb, gift_recipient_kb,
    gift_recipient_choice_kb, back_main_kb, back_gifts_kb, free_bears_kb, subscribe_kb,
    bot_info_kb, check_activate_kb, gift_confirm_kb
)
from gifts import GIFTS
from gift_service import try_send_bear, send_gift_by_id, notify_admins

user_router = Router()
logger = logging.getLogger(__name__)

PRESET_CAPTIONS = [
    "🎁 Это тебе, просто так!",
    "❤️ Ты особенный человек!",
    "🌟 Ты заслуживаешь лучшего!",
    "🥳 Поздравляю тебя!",
    "💫 Держи подарочек от меня!",
    "🔥 Ты огонь, держи!",
    "🎉 Сюрприз для тебя!",
    "💝 С любовью для тебя!",
]

class BuyState(StatesGroup):
    choosing_recipient = State()
    choosing_caption   = State()
    waiting_username   = State()
    typing_caption     = State()

class CheckState(StatesGroup):
    waiting_password = State()


async def check_all_subscriptions(bot: Bot, user_id: int) -> list:
    """
    Проверяет подписку на все обязательные каналы.
    Возвращает список каналов, на которые пользователь НЕ подписан.
    Статусы подписан: member, administrator, creator, restricted (ограничен, но состоит).
    Статусы не подписан: left, kicked, banned.
    """
    not_subscribed = []
    for ch in REQUIRED_CHANNELS:
        chat_id = ch.get("chat_id")
        if not chat_id:
            # Пропускаем каналы без chat_id — не блокируем пользователя
            logger.warning(f"Канал '{ch.get('title', '?')}' не имеет chat_id, пропускаем")
            continue
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            # left и kicked = точно не подписан
            if member.status in ("left", "kicked"):
                not_subscribed.append(ch)
            # Все остальные статусы (member, administrator, creator, restricted) = подписан
        except Exception as e:
            err_text = str(e).lower()
            # Если бот не является участником канала — скипаем (не наказываем юзера)
            if "bot is not a member" in err_text or "chat not found" in err_text:
                logger.error(
                    f"❌ Бот не добавлен в канал '{ch.get('title', '?')}' (chat_id={chat_id}). "
                    f"Добавь бота как администратора! Канал пропущен."
                )
                # НЕ добавляем в not_subscribed — не блокируем юзеров из-за ошибки конфига
            else:
                logger.error(
                    f"Ошибка проверки подписки канала '{ch.get('title', '?')}' "
                    f"(chat_id={chat_id}) для user {user_id}: {e}"
                )
                # При прочих ошибках тоже не блокируем — лучше пропустить чем сломать
    return not_subscribed



async def send_main_menu(target, bot: Bot, edit: bool = False):
    stats = await get_bot_stats()
    gifts_sold   = stats["total_gifts_sold"]   if stats else 0
    stars_earned = stats["total_stars_earned"] if stats else 0

    text = (
        f"👋 <b>Приветствую тебя,\n"
        f"<i>Уважаемый пользователь ботика)</i></b> 🎊\n\n"
        f"🎁 Бот продал <b>{gifts_sold}</b> подарков\n"
        f"🔄 Звёздный оборот: <b>{stars_earned} ⭐</b>\n\n"
        f"Используй меню ниже 👇"
    )
    kb = main_menu_kb()
    if edit and hasattr(target, 'message'):
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    elif edit:
        await target.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=kb)


async def send_subscribe_prompt(target, channels: list, edit: bool = False):
    ch_list = "\n".join([f"   • <b>{ch['title']}</b>" for ch in channels])
    text = (
        f"⚠️ <b>Для доступа подпишись на каналы:</b>\n\n"
        f"{ch_list}\n\n"
        f"После подписки нажми <b>✅ Я подписался</b>"
    )
    kb = subscribe_kb(channels)
    if edit and hasattr(target, 'message'):
        try:
            await target.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await target.message.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=kb)


# =================== /start ===================

@user_router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, state: FSMContext):
    await state.clear()
    user_id  = message.from_user.id
    username  = message.from_user.username or ""
    full_name = message.from_user.full_name or ""

    args = message.text.split(maxsplit=1)
    param = args[1].strip() if len(args) > 1 else ""

    referred_by = None
    check_code  = None

    if param.startswith("check_"):
        check_code = param[len("check_"):]
    elif param.isdigit():
        ref_id = int(param)
        if ref_id != user_id:
            referred_by = ref_id

    new_user = await is_new_user(user_id)
    await register_user(user_id, username, full_name, referred_by)

    if new_user and referred_by:
        new_ref_count = await add_referral(referred_by)
        if new_ref_count % REFERRALS_FOR_FREE_BEAR == 0:
            await grant_free_gift(referred_by)
            status = await try_send_bear(bot, referred_by, f"реферал #{new_ref_count}")
            if status == "sent":
                msg = (
                    f"🎉 <b>Ты набрал {new_ref_count} рефералов!</b>\n\n"
                    f"🧸 Мишка уже в твоём профиле!"
                )
            else:
                msg = (
                    f"🎉 <b>Ты набрал {new_ref_count} рефералов!</b>\n\n"
                    f"⏳ Мишка в очереди — придёт как только пополнится запас."
                )
            try:
                await bot.send_message(referred_by, msg, parse_mode="HTML")
            except Exception:
                pass

    user = await get_user(user_id)
    if user and user["is_banned"]:
        await message.answer("🚫 Ваш аккаунт заблокирован.")
        return

    missing = await check_all_subscriptions(bot, user_id)
    if missing:
        await send_subscribe_prompt(message, missing)
        if check_code:
            await state.update_data(pending_check=check_code)
        return

    if check_code:
        # Проверяем нужен ли пароль
        check = await get_check(check_code)
        if check and check["password"] and check["password"] != "":
            await state.update_data(pending_check=check_code)
            await state.set_state(CheckState.waiting_password)
            await message.answer(
                "🔐 <b>Этот чек защищён паролем!</b>\n\n"
                "🔑 Введи пароль для активации:",
                parse_mode="HTML"
            )
            return
        await process_check_activation(message, bot, check_code, user_id, state=state)
        return

    await send_main_menu(message, bot)


@user_router.callback_query(F.data == "check_subscription")
async def cb_check_sub(callback: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    user = await get_user(user_id)
    if user and user["is_banned"]:
        await callback.answer("🚫 Вы заблокированы.", show_alert=True)
        return
    missing = await check_all_subscriptions(bot, user_id)
    if missing:
        await callback.answer(
            f"❌ Не подписан на: {', '.join([c['title'] for c in missing])}",
            show_alert=True
        )
        return
    await callback.answer("✅ Подписка подтверждена!")
    data = await state.get_data()
    pending_check = data.get("pending_check")
    await state.clear()
    if pending_check:
        await process_check_activation(callback.message, bot, pending_check, user_id)
        return
    await send_main_menu(callback, bot, edit=True)


@user_router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, bot: Bot, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    missing = await check_all_subscriptions(bot, user_id)
    if missing:
        await send_subscribe_prompt(callback, missing, edit=True)
        return
    await send_main_menu(callback, bot, edit=True)


# =================== МАГАЗИН ===================

@user_router.callback_query(F.data == "gifts_menu")
async def cb_gifts_menu(callback: CallbackQuery, bot: Bot):
    missing = await check_all_subscriptions(bot, callback.from_user.id)
    if missing:
        await callback.answer("❌ Сначала подпишись на каналы!", show_alert=True)
        return
    await callback.message.edit_text(
        "🎁 <b>Магазин подарков</b>\n\n"
        "⭐ Оплата через Telegram Stars\n"
        "🎀 Подарок другу или 🛍 себе — выбираешь ты!\n"
        "✅ Подарок отправляется сразу после оплаты!\n\n"
        "Выбери подарок 👇",
        parse_mode="HTML",
        reply_markup=gifts_menu_kb()
    )


@user_router.callback_query(F.data.startswith("buy_gift:"))
async def cb_buy_gift(callback: CallbackQuery, state: FSMContext):
    gift_id = callback.data.split(":")[1]
    gift = GIFTS.get(gift_id)
    if not gift:
        await callback.answer("❌ Подарок не найден", show_alert=True)
        return

    await state.update_data(gift_id=gift_id)
    await state.set_state(BuyState.choosing_recipient)

    # Метки категорий для отображения
    cat_labels = {"cheap": "💫 Бюджетный", "medium": "✨ Средний", "premium": "🌟 Премиум", "luxury": "💎 Люкс"}
    cat_label = cat_labels.get(gift.get("category", ""), "")

    await callback.message.edit_text(
        f"{gift['emoji']} <b>{gift['name']}</b>\n"
        f"<i>{cat_label}</i>\n\n"
        f"📖 {gift.get('description', '')}\n\n"
        f"💰 Цена: <b>{gift['stars']} ⭐</b>\n\n"
        f"🎯 <b>Кому отправить подарок?</b>",
        parse_mode="HTML",
        reply_markup=gift_recipient_choice_kb(gift_id)
    )


@user_router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()


@user_router.callback_query(F.data.startswith("recipient_self:"))
async def cb_recipient_self(callback: CallbackQuery, state: FSMContext):
    gift_id = callback.data.split(":")[1]
    gift = GIFTS.get(gift_id)
    if not gift:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    # Покупка себе — receiver = сам пользователь
    await state.update_data(gift_id=gift_id, recipient_type="self", receiver_id=callback.from_user.id)
    await state.set_state(BuyState.choosing_caption)

    custom_stars = gift['stars'] + 6
    await callback.message.edit_text(
        f"{gift['emoji']} <b>{gift['name']}</b> — <i>себе</i> 🛍\n\n"
        f"✏️ <u>Хотите добавить подпись к подарку?</u>\n\n"
        f"📝 Без подписи — <b>{gift['stars']} ⭐</b>\n"
        f"✏️ Своя подпись — <b>{custom_stars} ⭐</b> <i>(+6 ⭐)</i>",
        parse_mode="HTML",
        reply_markup=gift_caption_kb(gift_id, gift['stars'], "self")
    )


@user_router.callback_query(F.data.startswith("recipient_friend:"))
async def cb_recipient_friend(callback: CallbackQuery, state: FSMContext):
    gift_id = callback.data.split(":")[1]
    gift = GIFTS.get(gift_id)
    if not gift:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    await state.update_data(gift_id=gift_id, recipient_type="friend")
    await state.set_state(BuyState.waiting_username)

    await callback.message.edit_text(
        f"{gift['emoji']} <b>{gift['name']}</b> — <i>другу</i> 🎀\n\n"
        f"👤 <b>Введите @username или ID друга:</b>\n\n"
        f"<i>Например: @username или 123456789</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"buy_gift:{gift_id}")]
        ])
    )


@user_router.message(BuyState.waiting_username)
async def msg_waiting_username(message: Message, state: FSMContext, bot: Bot):
    text = message.text.strip() if message.text else ""
    data = await state.get_data()
    gift_id = data.get("gift_id")
    gift = GIFTS.get(gift_id)
    if not gift:
        await state.clear()
        await message.answer("❌ Ошибка. Начни заново.", reply_markup=main_menu_kb())
        return

    receiver_id = None
    receiver_name = text

    # Пробуем получить ID пользователя
    if text.startswith("@"):
        username = text[1:]
        try:
            chat = await bot.get_chat(f"@{username}")
            receiver_id = chat.id
            receiver_name = f"@{username}"
        except Exception:
            await message.answer(
                "❌ <b>Пользователь не найден!</b>\n\n"
                "Убедитесь, что:\n"
                "• Username написан правильно\n"
                "• Пользователь хотя бы раз запускал ботов\n\n"
                "Попробуй ещё раз или введи числовой ID:",
                parse_mode="HTML"
            )
            return
    elif text.isdigit():
        receiver_id = int(text)
        receiver_name = f"ID:{text}"
    else:
        await message.answer(
            "❌ Неверный формат!\n\nВведи <b>@username</b> или числовой <b>ID</b>:",
            parse_mode="HTML"
        )
        return

    if receiver_id == message.from_user.id:
        await message.answer(
            "⚠️ Это ваш собственный ID!\n\n"
            "Используйте кнопку <b>🛍 Купить себе</b>, или введите ID другого пользователя.",
            parse_mode="HTML"
        )
        return

    await state.update_data(receiver_id=receiver_id, receiver_name=receiver_name)
    await state.set_state(BuyState.choosing_caption)

    custom_stars = gift['stars'] + 6
    await message.answer(
        f"{gift['emoji']} <b>{gift['name']}</b> → <b>{receiver_name}</b> 🎀\n\n"
        f"✏️ <u>Хотите добавить подпись к подарку?</u>\n\n"
        f"📝 Без подписи — <b>{gift['stars']} ⭐</b>\n"
        f"✏️ Своя подпись — <b>{custom_stars} ⭐</b> <i>(+6 ⭐)</i>",
        parse_mode="HTML",
        reply_markup=gift_caption_kb(gift_id, gift['stars'], "friend")
    )


@user_router.callback_query(F.data.startswith("caption_default:"))
async def cb_caption_default(callback: CallbackQuery, state: FSMContext, bot: Bot):
    parts = callback.data.split(":")
    gift_id = parts[1]
    recipient_type = parts[2] if len(parts) > 2 else "friend"
    gift = GIFTS.get(gift_id)
    if not gift:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    data = await state.get_data()
    receiver_id = data.get("receiver_id", callback.from_user.id)
    receiver_name = data.get("receiver_name", "себе" if recipient_type == "self" else "другу")
    await state.clear()

    caption = "🎁 Подарок для тебя!" if recipient_type == "friend" else "🎁 Подарок самому себе!"
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"{gift['emoji']} {gift['name']}",
        description=caption,
        payload=f"gift:{gift_id}:{receiver_id}:{caption}",
        currency="XTR",
        prices=[LabeledPrice(label=gift['name'], amount=gift['stars'])],
        provider_token="",
    )
    await callback.message.edit_text(
        f"💳 <b>Счёт выставлен!</b>\n\n"
        f"{gift['emoji']} {gift['name']} → <b>{receiver_name}</b>\n"
        f"💰 Оплата: <b>{gift['stars']} ⭐</b>\n\n"
        f"<i>Подтвердите оплату в счёте выше 👆</i>",
        parse_mode="HTML",
        reply_markup=back_gifts_kb()
    )


@user_router.callback_query(F.data.startswith("caption_custom:"))
async def cb_caption_custom(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    gift_id = parts[1]
    recipient_type = parts[2] if len(parts) > 2 else "friend"
    gift = GIFTS.get(gift_id)
    if not gift:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    custom_stars = gift['stars'] + 6
    data = await state.get_data()
    await state.update_data(gift_id=gift_id, final_stars=custom_stars, recipient_type=recipient_type)
    await state.set_state(BuyState.typing_caption)

    buttons = []
    for i, cap in enumerate(PRESET_CAPTIONS):
        buttons.append([InlineKeyboardButton(text=cap, callback_data=f"preset_caption:{gift_id}:{i}:{recipient_type}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"buy_gift:{gift_id}")])

    await callback.message.edit_text(
        f"{gift['emoji']} <b>{gift['name']}</b>\n"
        f"💰 Цена со своей подписью: <b>{custom_stars} ⭐</b>\n\n"
        f"✏️ <b>Выбери готовую подпись</b> или напиши свою (до 255 символов):",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@user_router.callback_query(F.data.startswith("preset_caption:"))
async def cb_preset_caption(callback: CallbackQuery, state: FSMContext, bot: Bot):
    parts = callback.data.split(":")
    gift_id = parts[1]
    cap_idx = int(parts[2])
    recipient_type = parts[3] if len(parts) > 3 else "friend"
    gift = GIFTS.get(gift_id)
    if not gift:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    caption = PRESET_CAPTIONS[cap_idx]
    data = await state.get_data()
    final_stars = data.get("final_stars", gift['stars'] + 6)
    receiver_id = data.get("receiver_id", callback.from_user.id)
    receiver_name = data.get("receiver_name", "себе" if recipient_type == "self" else "другу")
    await state.clear()

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"{gift['emoji']} {gift['name']}",
        description=caption,
        payload=f"gift:{gift_id}:{receiver_id}:{caption}",
        currency="XTR",
        prices=[LabeledPrice(label=gift['name'], amount=final_stars)],
        provider_token="",
    )
    await callback.message.edit_text(
        f"💳 <b>Счёт выставлен!</b>\n\n"
        f"{gift['emoji']} {gift['name']} → <b>{receiver_name}</b>\n"
        f"📝 <i>{caption}</i>\n"
        f"💰 Оплата: <b>{final_stars} ⭐</b>\n\n"
        f"<i>Подтвердите оплату в счёте выше 👆</i>",
        parse_mode="HTML",
        reply_markup=back_gifts_kb()
    )


@user_router.message(BuyState.typing_caption)
async def msg_custom_caption(message: Message, state: FSMContext, bot: Bot):
    caption = message.text.strip() if message.text else ""
    if len(caption) > 255:
        await message.answer("❌ Подпись слишком длинная (максимум 255 символов).")
        return
    data = await state.get_data()
    gift_id = data.get("gift_id")
    gift = GIFTS.get(gift_id)
    if not gift:
        await state.clear()
        await message.answer("❌ Ошибка. Начни заново.", reply_markup=main_menu_kb())
        return
    final_stars = data.get("final_stars", gift['stars'] + 6)
    recipient_type = data.get("recipient_type", "friend")
    receiver_id = data.get("receiver_id", message.from_user.id)
    receiver_name = data.get("receiver_name", "себе" if recipient_type == "self" else "другу")
    await state.clear()

    await bot.send_invoice(
        chat_id=message.from_user.id,
        title=f"{gift['emoji']} {gift['name']}",
        description=caption,
        payload=f"gift:{gift_id}:{receiver_id}:{caption}",
        currency="XTR",
        prices=[LabeledPrice(label=gift['name'], amount=final_stars)],
        provider_token="",
    )
    await message.answer(
        f"💳 <b>Счёт выставлен!</b>\n\n"
        f"{gift['emoji']} {gift['name']} → <b>{receiver_name}</b>\n"
        f"📝 <i>{caption[:100]}</i>\n"
        f"💰 Оплата: <b>{final_stars} ⭐</b>\n\n"
        f"<i>Подтвердите оплату в счёте выше 👆</i>",
        parse_mode="HTML",
        reply_markup=back_gifts_kb()
    )


# =================== ОПЛАТА ===================

@user_router.pre_checkout_query(lambda q: q.invoice_payload.startswith("gift:"))
async def pre_checkout(pcq, bot: Bot):
    await bot.answer_pre_checkout_query(pcq.id, ok=True)


@user_router.message(F.successful_payment)
async def handle_successful_payment(message: Message, bot: Bot):
    """Централизованный обработчик всех успешных платежей пользователя"""
    payload = message.successful_payment.invoice_payload
    stars_paid = message.successful_payment.total_amount

    if payload.startswith("gift:"):
        await _handle_gift_payment(message, bot, payload, stars_paid)
    elif payload.startswith("case:"):
        from handlers.cases_handlers import handle_case_payment
        parts = payload.split(":")
        if len(parts) >= 3:
            case_key = parts[1]
            await handle_case_payment(bot, message.from_user.id, case_key, message)


async def _handle_gift_payment(message: Message, bot: Bot, payload: str, stars_paid: int):
    """Обработка оплаченного подарка из магазина"""
    # payload: "gift:gift_id:receiver_id:caption"
    parts = payload.split(":", 3)
    if len(parts) < 3 or parts[0] != "gift":
        return

    gift_id     = parts[1]
    receiver_id = int(parts[2])
    caption     = parts[3] if len(parts) > 3 else "🎁 Подарок для тебя!"
    gift        = GIFTS.get(gift_id)

    if not gift:
        await message.answer("⚠️ Ошибка обработки. Обратись в поддержку.")
        return

    sender_id = message.from_user.id
    is_self = (sender_id == receiver_id)

    # Отправляем подарок
    sent = await send_gift_by_id(bot, receiver_id, gift["gift_id"], text=caption[:255])
    await add_gift_history(sender_id, receiver_id, gift['name'], stars_paid)
    await update_stats(gifts_delta=1, stars_delta=stars_paid)

    if sent:
        if is_self:
            success_text = (
                f"✅ <b>Подарок отправлен себе!</b>\n\n"
                f"{gift['emoji']} <b>{gift['name']}</b>\n"
                f"📝 <i>{caption[:100]}</i>\n"
                f"💰 Оплачено: <b>{stars_paid} ⭐</b>\n\n"
                f"🎀 Подарок уже в вашем профиле Telegram!"
            )
        else:
            success_text = (
                f"✅ <b>Подарок отправлен другу!</b>\n\n"
                f"{gift['emoji']} <b>{gift['name']}</b>\n"
                f"📝 <i>{caption[:100]}</i>\n"
                f"💰 Оплачено: <b>{stars_paid} ⭐</b>"
            )
        await message.answer(
            success_text,
            parse_mode="HTML",
            reply_markup=main_menu_kb()
        )
    else:
        await message.answer(
            f"⚠️ <b>Оплата получена ({stars_paid} ⭐), но ошибка при отправке.</b>\n"
            f"Администратор отправит вручную в течение 24 часов.",
            parse_mode="HTML",
            reply_markup=bot_info_kb()
        )
        await notify_admins(
            bot,
            f"⚠️ <b>ОШИБКА ОТПРАВКИ ПОДАРКА</b>\n"
            f"От: {message.from_user.id} (@{message.from_user.username})\n"
            f"Кому: {receiver_id}\n"
            f"Подарок: {gift['name']}\n"
            f"Stars: {stars_paid}\n"
            f"Подпись: {caption}"
        )


# =================== ЧЕКИ ===================

async def _do_activate_and_reply(message: Message, bot: Bot, check_code: str, user_id: int, password: str = None):
    """Активирует чек и отвечает пользователю."""
    result = await activate_check(check_code, user_id, password=password)
    if result["success"]:
        await grant_free_gift(user_id)
        status = await try_send_bear(bot, user_id, f"чек {check_code}")
        remaining = result.get("remaining", 0)
        if status == "sent":
            text = (
                f"🎉 <b>Чек активирован!</b>\n\n"
                f"🧸 Мишка уже в твоём профиле!\n"
                f"📊 Осталось активаций: <b>{remaining}</b>"
            )
        else:
            text = (
                f"🎉 <b>Чек активирован!</b>\n\n"
                f"⏳ Мишка в очереди — придёт как только пополнится запас.\n"
                f"📊 Осталось активаций: <b>{remaining}</b>"
            )
        await message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb())
    else:
        reasons = {
            "not_found":      "❌ Чек не найден.",
            "inactive":       "❌ Чек исчерпан.",
            "exhausted":      "❌ Все активации использованы.",
            "already_used":   "⚠️ Ты уже активировал этот чек.",
            "wrong_password": "🔐 Неверный пароль!",
        }
        await message.answer(
            reasons.get(result["reason"], "❌ Ошибка активации."),
            reply_markup=main_menu_kb()
        )
    return result


async def process_check_activation(message: Message, bot: Bot, check_code: str, user_id: int, state: FSMContext = None, password: str = None):
    """Проверяет пароль и запускает активацию чека."""
    check = await get_check(check_code)
    if not check:
        await message.answer("❌ Чек не найден.", reply_markup=main_menu_kb())
        return

    needs_password = check["password"] and check["password"] != ""

    if needs_password and password is None:
        if state is not None:
            await state.update_data(pending_check=check_code)
            await state.set_state(CheckState.waiting_password)
        await message.answer(
            "🔐 <b>Этот чек защищён паролем!</b>\n\n"
            "🔑 Введи пароль для активации:",
            parse_mode="HTML"
        )
        return

    await _do_activate_and_reply(message, bot, check_code, user_id, password=password)


@user_router.callback_query(F.data.startswith("activate_check:"))
async def cb_activate_check(callback: CallbackQuery, bot: Bot, state: FSMContext):
    check_code = callback.data.split(":", 1)[1]
    user_id    = callback.from_user.id
    missing    = await check_all_subscriptions(bot, user_id)
    if missing:
        await callback.answer("❌ Сначала подпишись на каналы!", show_alert=True)
        return
    await callback.answer("✅ Переходи в бота для активации!", show_alert=True)
    try:
        await bot.send_message(
            user_id,
            f"🎁 <b>Активируй свой чек!</b>\n\nНажми кнопку ниже 👇",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="🎁 Активировать чек",
                    callback_data=f"do_activate_check:{check_code}"
                )
            ]])
        )
    except Exception:
        pass


@user_router.callback_query(F.data.startswith("do_activate_check:"))
async def cb_do_activate_check(callback: CallbackQuery, bot: Bot, state: FSMContext):
    check_code = callback.data.split(":", 1)[1]
    user_id    = callback.from_user.id
    missing    = await check_all_subscriptions(bot, user_id)
    if missing:
        await callback.answer("❌ Сначала подпишись на каналы!", show_alert=True)
        return
    await callback.answer()
    await process_check_activation(callback.message, bot, check_code, user_id, state=state)


@user_router.message(CheckState.waiting_password)
async def msg_check_password(message: Message, bot: Bot, state: FSMContext):
    data = await state.get_data()
    check_code = data.get("pending_check")
    if not check_code:
        await state.clear()
        await message.answer("❌ Ошибка. Начни заново.", reply_markup=main_menu_kb())
        return

    password = message.text.strip() if message.text else ""
    result = await activate_check(check_code, message.from_user.id, password=password)

    if result.get("reason") == "wrong_password":
        # Оставляем state, даём ещё шанс
        await message.answer(
            "🔐 <b>Неверный пароль!</b>\n\nПопробуй ещё раз 👇",
            parse_mode="HTML"
        )
        return

    await state.clear()

    if result["success"]:
        await grant_free_gift(message.from_user.id)
        status = await try_send_bear(bot, message.from_user.id, f"чек {check_code}")
        remaining = result.get("remaining", 0)
        if status == "sent":
            text = (
                f"🎉 <b>Чек активирован!</b>\n\n"
                f"🧸 Мишка уже в твоём профиле!\n"
                f"📊 Осталось активаций: <b>{remaining}</b>"
            )
        else:
            text = (
                f"🎉 <b>Чек активирован!</b>\n\n"
                f"⏳ Мишка в очереди — придёт как только пополнится запас.\n"
                f"📊 Осталось активаций: <b>{remaining}</b>"
            )
        await message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb())
    else:
        reasons = {
            "not_found":    "❌ Чек не найден.",
            "inactive":     "❌ Чек исчерпан.",
            "exhausted":    "❌ Все активации использованы.",
            "already_used": "⚠️ Ты уже активировал этот чек.",
        }
        await message.answer(
            reasons.get(result["reason"], "❌ Ошибка активации."),
            reply_markup=main_menu_kb()
        )




# =================== БЕСПЛАТНЫЕ МИШКИ ===================

@user_router.callback_query(F.data == "free_bears")
async def cb_free_bears(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    user    = await get_user(user_id)
    if not user:
        await callback.answer("❌ Сначала /start", show_alert=True)
        return

    bot_me   = await bot.me()
    refs     = user["referral_count"]
    free     = user["free_gifts_available"]
    recv     = user["gifts_received"]
    ref_link = f"https://t.me/{bot_me.username}?start={user_id}"

    progress     = refs % REFERRALS_FOR_FREE_BEAR
    next_bear_at = REFERRALS_FOR_FREE_BEAR - progress
    bar_filled   = "🟩" * progress
    bar_empty    = "⬜" * (REFERRALS_FOR_FREE_BEAR - progress)

    stock = await get_bear_stock()
    stock_info = f"✅ Запас мишек: <b>{stock}</b>" if stock > 0 else "⚠️ Запас мишек пуст — они в очереди"

    text = (
        f"🧸 <b>БЕСПЛАТНЫЕ МИШКИ</b>\n\n"
        f"👥 Приглашено друзей: <b>{refs}</b>\n"
        f"🎁 Получено мишек: <b>{recv}</b>\n"
        f"✅ Доступно сейчас: <b>{free}</b>\n\n"
        f"📊 Прогресс:\n"
        f"{bar_filled}{bar_empty} <b>{progress}/{REFERRALS_FOR_FREE_BEAR}</b>\n"
        f"<i>Ещё {next_bear_at} рефералов</i>\n\n"
        f"{stock_info}\n\n"
        f"⚠️ <i>Накрученные и не русскоязычные пользователи не засчитываются!</i>\n\n"
        f"🔗 Твоя ссылка:\n<code>{ref_link}</code>"
    )
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=free_bears_kb(free > 0, ref_link, user_id)
    )


@user_router.callback_query(F.data == "claim_bear")
async def cb_claim_bear(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    success = await use_free_gift(user_id)
    if not success:
        await callback.answer("❌ У тебя нет доступных мишек!", show_alert=True)
        return
    await callback.answer()
    status = await try_send_bear(bot, user_id, "ручное получение")
    if status == "sent":
        await callback.message.edit_text(
            "🎉 <b>Мишка отправлен!</b>\n\n🧸 Подарок уже в твоём профиле!",
            parse_mode="HTML", reply_markup=back_main_kb()
        )
    else:
        await callback.message.edit_text(
            "⏳ <b>Заявка принята!</b>\n\n"
            "Мишки временно закончились, но ты в очереди.\n"
            "Придёт автоматически как только запас пополнится!",
            parse_mode="HTML", reply_markup=back_main_kb()
        )


# =================== ПРОЧЕЕ ===================

@user_router.callback_query(F.data == "top_referrers")
async def cb_top_ref(callback: CallbackQuery):
    top    = await get_top_referrers(10)
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    text   = "🏆 <b>Топ-10 рефоводов:</b>\n\n"
    if top:
        for i, u in enumerate(top):
            un = u["username"] or "нет username"
            if u["username"]:
                half = len(u["username"]) // 2
                un   = f"@{u['username'][:half]}***"
            m    = medals[i] if i < len(medals) else f"{i+1}."
            text += f"{m} {un} — <b>{u['referral_count']}</b> друзей\n"
    else:
        text += "<i>Пока нет рефоводов. Стань первым!</i>"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_main_kb())


@user_router.callback_query(F.data == "my_profile")
async def cb_my_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    user    = await get_user(user_id)
    if not user:
        await callback.answer("❌ Профиль не найден", show_alert=True)
        return
    uname  = f"@{callback.from_user.username}" if callback.from_user.username else "—"
    text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"📛 Имя: {callback.from_user.full_name}\n"
        f"🔗 Username: {uname}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📅 Регистрация: <b>{user['registered_at']}</b>\n\n"
        f"👥 Рефералов: <b>{user['referral_count']}</b>\n"
        f"🎁 Мишек получено: <b>{user['gifts_received']}</b>\n"
        f"✅ Мишек доступно: <b>{user['free_gifts_available']}</b>\n"
        f"⭐ Stars потрачено: <b>{user['stars_spent']}</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_main_kb())


@user_router.callback_query(F.data == "bot_info")
async def cb_bot_info(callback: CallbackQuery):
    await callback.message.edit_text(
        "ℹ️ <b>Информация о боте</b>\n\nВыбери раздел 👇",
        parse_mode="HTML", reply_markup=bot_info_kb()
    )


@user_router.callback_query(F.data == "terms")
async def cb_terms(callback: CallbackQuery):
    await callback.message.edit_text(
        "📋 <b>Пользовательское соглашение</b>\n\n"
        "1. Бот работает по правилам Telegram\n"
        "2. Накрутка рефералов = бан\n"
        "3. Возврат Stars только при технической ошибке\n"
        "4. Администрация проверяет качество рефералов",
        parse_mode="HTML", reply_markup=back_main_kb()
    )


@user_router.callback_query(F.data == "guarantees")
async def cb_guarantees(callback: CallbackQuery):
    await callback.message.edit_text(
        "✅ <b>Гарантии бота</b>\n\n"
        "🔒 Оплата напрямую через Telegram Stars\n"
        "🧸 Мишки выдаются автоматически из запаса\n"
        "⏳ Если запас пуст — встаёшь в очередь и получишь при пополнении\n"
        "💬 При проблемах — поддержка",
        parse_mode="HTML", reply_markup=back_main_kb()
    )
