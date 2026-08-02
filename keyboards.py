from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from gifts import GIFTS

# =================== ПОЛЬЗОВАТЕЛЬ ===================

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 ОБЫЧНЫЕ ПОДАРКИ", callback_data="gifts_menu")],
        [InlineKeyboardButton(text="📦 МАГАЗИН КЕЙСОВ", callback_data="cases_shop")],
        [InlineKeyboardButton(text="🐻 БЕСПЛАТНЫЕ МИШКИ", callback_data="free_bears")],
        [InlineKeyboardButton(text="🎮 МИНИ-ИГРЫ", callback_data="games_menu")],
        [InlineKeyboardButton(text="🏆 Топ рефоводов", callback_data="top_referrers"),
         InlineKeyboardButton(text="👤 Мой профиль", callback_data="my_profile")],
        [InlineKeyboardButton(text="ℹ️ Информация о боте", callback_data="bot_info")],
    ])

def gifts_menu_kb():
    from gifts import CATEGORY_LABELS
    buttons = []

    # Группируем по категориям
    categories = {}
    for gift_id, gift in GIFTS.items():
        cat = gift.get("category", "medium")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((gift_id, gift))

    cat_order = ["cheap", "medium", "premium", "luxury"]
    cat_emojis = {
        "cheap":   "💫",
        "medium":  "✨",
        "premium": "🌟",
        "luxury":  "💎",
    }

    for cat in cat_order:
        if cat not in categories:
            continue
        label = CATEGORY_LABELS.get(cat, cat)
        buttons.append([InlineKeyboardButton(text=f"━━━ {label} ━━━", callback_data="noop")])
        for gift_id, gift in categories[cat]:
            name_part = gift['name'].split(' ', 1)[-1] if ' ' in gift['name'] else gift['name']
            btn_text = f"{gift['emoji']} {name_part} — {gift['stars']} ⭐"
            buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"buy_gift:{gift_id}")])

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def gift_recipient_choice_kb(gift_id: str):
    """Выбор: купить себе или другу."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎀 Купить другу",
            callback_data=f"recipient_friend:{gift_id}"
        )],
        [InlineKeyboardButton(
            text="🛍 Купить себе",
            callback_data=f"recipient_self:{gift_id}"
        )],
        [InlineKeyboardButton(text="◀️ Назад к подаркам", callback_data="gifts_menu")],
    ])

def gift_caption_kb(gift_id: str, base_stars: int, recipient_type: str = "friend"):
    custom_stars = base_stars + 6
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"✏️ Своя подпись — {custom_stars} ⭐",
            callback_data=f"caption_custom:{gift_id}:{recipient_type}"
        )],
        [InlineKeyboardButton(
            text=f"📝 Без подписи — {base_stars} ⭐",
            callback_data=f"caption_default:{gift_id}:{recipient_type}"
        )],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"buy_gift:{gift_id}")],
    ])

def gift_recipient_kb(gift_id: str, recipient_type: str = "friend"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"buy_gift:{gift_id}")]
    ])

def gift_confirm_kb(gift_id: str, receiver_id: int, final_stars: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"✅ Оплатить {final_stars} ⭐",
            callback_data=f"confirm_gift:{gift_id}:{receiver_id}:{final_stars}"
        )],
        [InlineKeyboardButton(text="◀️ Назад к подаркам", callback_data="gifts_menu")],
    ])

def back_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="main_menu")]
    ])

def back_gifts_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к подаркам", callback_data="gifts_menu")]
    ])

def free_bears_kb(has_free: bool, ref_link: str, user_id: int):
    buttons = []
    if has_free:
        buttons.append([InlineKeyboardButton(text="🐻 Забрать мишку!", callback_data="claim_bear")])
    buttons.append([
        InlineKeyboardButton(
            text="📨 Поделиться ссылкой",
            switch_inline_query=f"🐻 Получи бесплатного мишку! {ref_link}"
        )
    ])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def subscribe_kb(channels: list):
    buttons = []
    for ch in channels:
        buttons.append([InlineKeyboardButton(text=f"➡️ {ch['title']}", url=ch['url'])])
    buttons.append([InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def bot_info_kb():
    from config import SUPPORT_URL
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Поддержка если проблемы", url=SUPPORT_URL)],
        [InlineKeyboardButton(text="📋 Пользовательское соглашение", callback_data="terms")],
        [InlineKeyboardButton(text="✅ Гарантии бота", callback_data="guarantees")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")],
    ])

def check_activate_kb(check_code: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Активировать чек", callback_data=f"activate_check:{check_code}")]
    ])

def check_activate_channel_kb(check_code: str, bot_username: str):
    """Клавиатура для каналов/групп — использует URL deeplink вместо callback."""
    url = f"https://t.me/{bot_username}?start=check_{check_code}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Получить мишку!", url=url)]
    ])

# =================== ADMIN ===================

def admin_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"),
        ],
        [InlineKeyboardButton(text="📣 Рассылка всем", callback_data="admin_broadcast")],
        [
            InlineKeyboardButton(text="🎟 Создать чек", callback_data="admin_create_check"),
            InlineKeyboardButton(text="📋 Мои чеки", callback_data="admin_my_checks"),
        ],
        [InlineKeyboardButton(text="📨 Разослать чек пользователям", callback_data="admin_broadcast_check")],
        [InlineKeyboardButton(text="📢 Разослать чек в каналы/группы", callback_data="admin_broadcast_check_channels")],
        [InlineKeyboardButton(text="⚙️ Каналы для рассылки чеков", callback_data="admin_manage_channels")],
        [
            InlineKeyboardButton(text="🐻 Выдать мишку", callback_data="admin_give_bear"),
            InlineKeyboardButton(text="🚫 Бан / Разбан", callback_data="admin_ban_menu"),
        ],
        [InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin_find_user")],
        [InlineKeyboardButton(text="📢 Каналы обязат. подписки", callback_data="admin_channels")],
        [InlineKeyboardButton(text="⭐ Пополнить Stars бота", callback_data="admin_topup_stars")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_close")],
    ])

def admin_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад в панель", callback_data="admin_panel")]
    ])

def admin_cancel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel")]
    ])

def admin_broadcast_confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить рассылку", callback_data="admin_broadcast_confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_panel")],
    ])
