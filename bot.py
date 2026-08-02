import asyncio
import logging
from aiogram import Bot, Dispatcher, BaseMiddleware, F
from aiogram.types import Message, CallbackQuery, Update, PreCheckoutQuery
from aiogram.fsm.storage.memory import MemoryStorage
from typing import Callable, Dict, Any, Awaitable

from config import BOT_TOKEN
from handlers import user_router, admin_router, games_router, inline_router
from handlers.cases_handlers import cases_router, handle_case_payment, ensure_daily_case_column
from database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class PrivateChatOnlyMiddleware(BaseMiddleware):
    """Блокирует все сообщения и коллбэки из групп/каналов.
    Бот отвечает ТОЛЬКО в личных сообщениях (private)."""

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        # Проверяем сообщения
        if isinstance(event, Message):
            if event.chat.type != "private":
                return  # Игнорируем
        # Проверяем коллбэки (могут прийти из inline в группах)
        elif isinstance(event, CallbackQuery):
            if event.message and event.message.chat.type != "private":
                return  # Игнорируем
        return await handler(event, data)


async def main():
    logger.info("Запуск бота...")
    await init_db()
    await ensure_daily_case_column()
    logger.info("База данных инициализирована")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Middleware — только личка
    dp.message.middleware(PrivateChatOnlyMiddleware())
    dp.callback_query.middleware(PrivateChatOnlyMiddleware())

    dp.include_router(admin_router)
    dp.include_router(inline_router)
    dp.include_router(cases_router)
    dp.include_router(games_router)
    dp.include_router(user_router)

    # Глобальный fallback для pre_checkout — подтверждаем все незахваченные запросы
    @dp.pre_checkout_query()
    async def fallback_pre_checkout(pcq: PreCheckoutQuery, bot: Bot):
        await bot.answer_pre_checkout_query(pcq.id, ok=True)

    me = await bot.me()
    logger.info(f"Бот запущен: @{me.username}")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
