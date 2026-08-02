import uuid
import logging
from aiogram import Router, Bot, F
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ChosenInlineResult,
)

from database import get_admin_checks, get_check

inline_router = Router()
logger = logging.getLogger(__name__)


def check_inline_kb(check_code: str, bot_username: str) -> InlineKeyboardMarkup:
    url = f"https://t.me/{bot_username}?start=check_{check_code}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Получить мишку!", url=url)]
    ])


@inline_router.inline_query()
async def inline_handler(query: InlineQuery, bot: Bot):
    bot_me = await bot.me()
    user_id = query.from_user.id
    search = query.query.strip().lower()

    results = []

    # Получаем активные чеки этого пользователя (если он админ)
    try:
        user_checks = await get_admin_checks(user_id, limit=20)
    except Exception:
        user_checks = []

    active_checks = [c for c in user_checks if c["is_active"]]

    if active_checks:
        for check in active_checks:
            code = check["check_code"]
            remaining = check["max_activations"] - check["used_count"]
            has_password = bool(check.get("password"))
            password_label = "🔐 Пароль требуется" if has_password else "🔓 Без пароля"

            # Фильтрация по поиску
            if search and search not in code.lower():
                continue

            check_url = f"https://t.me/{bot_me.username}?start=check_{code}"

            text = (
                f"🎁 <b>ПОДАРОЧНЫЙ ЧЕК</b>\n"
                f"——————————————\n"
                f"📦 Товар: <b>Мишка</b>\n"
                f"👥 Мест осталось: <b>{remaining}</b>\n"
                f"🔒 {password_label}\n"
                f"——————————————\n"
                f"👇 Нажми кнопку, чтобы забрать!"
            )

            results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title=f"🎁 Чек — {remaining} мест осталось",
                    description=f"{password_label} • Код: {code}",
                    input_message_content=InputTextMessageContent(
                        message_text=text,
                        parse_mode="HTML",
                    ),
                    reply_markup=check_inline_kb(code, bot_me.username),
                )
            )

    # Если нет чеков или не админ — показываем общую рекламу бота
    if not results:
        bot_url = f"https://t.me/{bot_me.username}?start=ref_{user_id}"
        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="🎁 Поделиться ботом с подарками",
                description="Отправить реферальную ссылку в чат",
                input_message_content=InputTextMessageContent(
                    message_text=(
                        f"🎁 <b>Хочешь бесплатного мишку?</b>\n\n"
                        f"🧸 Переходи в бот и забирай подарки!\n"
                        f"🎮 Игры, кейсы, чеки — всё бесплатно!"
                    ),
                    parse_mode="HTML",
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🎁 Открыть бота", url=bot_url)]
                ]),
            )
        )

    await query.answer(
        results,
        cache_time=10,
        is_personal=True,
    )
