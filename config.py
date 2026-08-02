# =============================================
#   БЕСПЛАТНЫЙ МИШКА BOT — КОНФИГУРАЦИЯ
# =============================================

# Токен бота от @BotFather
BOT_TOKEN = "8981547481:AAGkcLgc8bJ9DnPby56CtMsHiP-y0UMg86Y"

# ID администраторов (список Telegram ID)
ADMIN_IDS = [8907033178,8981547481]  # замени на свой ID

# Каналы для обязательной подписки
# Формат: {"username": "channel_name", "title": "Красивое название", "url": "https://t.me/giftbotwerty"}
# Каналы для обязательной подписки
# Формат: {"chat_id": -1001234567890, "title": "Название канала", "url": "https://t.me/giftbotwerty"}
# chat_id можно узнать через @userinfobot или переслать сообщение из канала боту @getidsbot
REQUIRED_CHANNELS = [

]

# Рефералов для получения бесплатного мишки
REFERRALS_FOR_FREE_BEAR = 10

# Ссылка на поддержку
SUPPORT_URL = "https://t.me/dev_werty"

# Название бота
BOT_NAME = "WERTY GIFTS"

# Автоматическая выдача мишки через send_gift
# True = бот сам отправляет подарок автоматически
# False = администратор отправляет вручную
AUTO_SEND_GIFT = True

# ID подарка "Мишка" в Telegram (получи через getAvailableGifts)
# Запрос: https://api.telegram.org/botТВОЙ_ТОКЕН/getAvailableGifts
BEAR_GIFT_ID = "5170233102089322756"  # замени на реальный ID

# Текст который показывается при отправке подарка (до 255 символов)
GIFT_TEXT = "⭐🎉 Раздаю всем подарки!\nСмотри профиль! 🎁"
