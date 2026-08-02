"""
Сервис выдачи мишек.
Логика:
  1. Кто-то заработал мишку → add_to_bear_queue()
  2. try_send_bear() — пытается взять из запаса и отправить через send_gift()
  3. Если запаса нет — остаётся в очереди, ждёт пополнения
  4. Админ пополняет запас → process_bear_queue() раздаёт всем ожидающим
"""
import logging
from aiogram import Bot
from config import ADMIN_IDS, BEAR_GIFT_ID, GIFT_TEXT

logger = logging.getLogger(__name__)


async def try_send_bear(bot: Bot, user_id: int, reason: str = "") -> str:
    """
    Пытается немедленно отправить мишку из запаса.
    Возвращает: 'sent' | 'queued' | 'error'
    """
    from database import take_bear_from_stock, add_to_bear_queue, mark_queue_sent

    has_stock = await take_bear_from_stock()
    if not has_stock:
        # Запаса нет — ставим в очередь
        await add_to_bear_queue(user_id, reason)
        logger.info(f"Мишка в очереди для {user_id} (запас пуст)")
        return "queued"

    # Есть запас — отправляем
    try:
        await bot.send_gift(
            user_id=user_id,
            gift_id=BEAR_GIFT_ID,
            text=GIFT_TEXT[:255]
        )
        logger.info(f"Мишка отправлен пользователю {user_id}")
        return "sent"
    except Exception as e:
        logger.error(f"Ошибка send_gift для {user_id}: {e}")
        # Возвращаем мишку в запас
        from database import add_bear_stock
        await add_bear_stock(1)
        # И ставим в очередь
        await add_to_bear_queue(user_id, reason)
        return "queued"


async def process_bear_queue(bot: Bot) -> tuple:
    """
    Обрабатывает очередь — раздаёт мишек всем ожидающим пока есть запас.
    Возвращает (sent_count, remaining_count).
    """
    from database import get_pending_queue, take_bear_from_stock, mark_queue_sent, get_queue_count

    queue = await get_pending_queue()
    sent = 0
    for item in queue:
        has_stock = await take_bear_from_stock()
        if not has_stock:
            break
        try:
            await bot.send_gift(
                user_id=item["user_id"],
                gift_id=BEAR_GIFT_ID,
                text=GIFT_TEXT[:255]
            )
            await mark_queue_sent(item["id"])
            # Уведомляем пользователя
            try:
                await bot.send_message(
                    item["user_id"],
                    "🎉 <b>Твой мишка пришёл!</b>\n\n"
                    "🧸 Подарок уже в твоём профиле Telegram!",
                    parse_mode="HTML"
                )
            except Exception:
                pass
            sent += 1
            logger.info(f"Мишка из очереди отправлен {item['user_id']}")
        except Exception as e:
            logger.error(f"Ошибка отправки из очереди {item['user_id']}: {e}")
            from database import add_bear_stock
            await add_bear_stock(1)

    remaining = await get_queue_count()
    return sent, remaining


async def send_gift_by_id(bot: Bot, user_id: int, gift_id: str, text: str = "") -> bool:
    """Отправляет любой подарок по gift_id (для магазина)."""
    try:
        await bot.send_gift(
            user_id=user_id,
            gift_id=gift_id,
            text=text[:255] if text else ""
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка send_gift {gift_id} -> {user_id}: {e}")
        return False


async def notify_admins(bot: Bot, text: str):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception:
            pass
