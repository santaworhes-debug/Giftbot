# =================== КЕЙСЫ ===================
# Система кейсов с редкими наградами

from gifts import GIFTS

# Определение кейсов — ШАНСЫ ПОНИЖЕНЫ
CASES = {
    "daily_free": {
        "name": "🎁 Бесплатный ежедневный кейс",
        "emoji": "🎁",
        "price": 0,
        "daily": True,
        "description": "Бесплатный кейс каждые 24 часа!",
        "items": [
            {"type": "nothing",  "name": "💩 Ничего",    "chance": 80},
            {"type": "gift",     "name": "🧸 Мишка",     "chance": 13, "gift_key": "bear"},
            {"type": "gift",     "name": "🌹 Роза",      "chance": 4,  "gift_key": "rose"},
            {"type": "gift",     "name": "💎 Алмаз",     "chance": 2,  "gift_key": "diamond"},
            {"type": "gift",     "name": "🚀 Ракета",    "chance": 1,  "gift_key": "rocket"},
        ]
    },
    "easy": {
        "name": "😊 Изи кейс",
        "emoji": "😊",
        "price": 5,
        "daily": False,
        "description": "Самый дешёвый кейс — попробуй удачу!",
        "items": [
            {"type": "nothing",  "name": "💩 Ничего",    "chance": 78},
            {"type": "gift",     "name": "🧸 Мишка",     "chance": 15, "gift_key": "bear"},
            {"type": "gift",     "name": "💝 Сердечко",  "chance": 5,  "gift_key": "heart"},
            {"type": "gift",     "name": "🚀 Ракета",    "chance": 1.5,"gift_key": "rocket"},
            {"type": "gift",     "name": "💎 Алмаз",     "chance": 0.5,"gift_key": "diamond"},
        ]
    },
    "yesno": {
        "name": "🎯 Да да нет нет",
        "emoji": "🎯",
        "price": 10,
        "daily": False,
        "description": "Либо подарок, либо ничего!",
        "items": [
            {"type": "nothing",  "name": "💩 Ничего",    "chance": 62},
            {"type": "gift",     "name": "🧸 Мишка",     "chance": 20, "gift_key": "bear"},
            {"type": "gift",     "name": "🌹 Роза",      "chance": 10, "gift_key": "rose"},
            {"type": "gift",     "name": "🚀 Ракета",    "chance": 4,  "gift_key": "rocket"},
            {"type": "gift",     "name": "💎 Алмаз",     "chance": 2.5,"gift_key": "diamond"},
            {"type": "gift",     "name": "🏆 Кубок",     "chance": 1.5,"gift_key": "trophy"},
        ]
    },
    "starter": {
        "name": "🌟 Стартовый кейс",
        "emoji": "🌟",
        "price": 20,
        "daily": False,
        "description": "Доступный кейс для начинающих",
        "items": [
            {"type": "nothing",  "name": "💩 Ничего",    "chance": 60},
            {"type": "gift",     "name": "🧸 Мишка",     "chance": 22, "gift_key": "bear"},
            {"type": "gift",     "name": "💝 Сердечко",  "chance": 10, "gift_key": "heart"},
            {"type": "gift",     "name": "🌹 Роза",      "chance": 5,  "gift_key": "rose"},
            {"type": "gift",     "name": "💎 Алмаз",     "chance": 2,  "gift_key": "diamond"},
            {"type": "gift",     "name": "🚀 Ракета",    "chance": 1,  "gift_key": "rocket"},
        ]
    },
    "normal": {
        "name": "✨ Нормальный кейс",
        "emoji": "✨",
        "price": 40,
        "daily": False,
        "description": "Средний уровень — больше шансов на хорошее!",
        "items": [
            {"type": "nothing",  "name": "💩 Ничего",    "chance": 45},
            {"type": "gift",     "name": "🧸 Мишка",     "chance": 22, "gift_key": "bear"},
            {"type": "gift",     "name": "💝 Сердечко",  "chance": 13, "gift_key": "heart"},
            {"type": "gift",     "name": "🌹 Роза",      "chance": 10, "gift_key": "rose"},
            {"type": "gift",     "name": "🎂 Торт",      "chance": 5,  "gift_key": "cake"},
            {"type": "gift",     "name": "🍾 Шампанское","chance": 3,  "gift_key": "champagne"},
            {"type": "gift",     "name": "💎 Алмаз",     "chance": 1.5,"gift_key": "diamond"},
            {"type": "gift",     "name": "🚀 Ракета",    "chance": 0.5,"gift_key": "rocket"},
        ]
    },
    "referral": {
        "name": "🔗 Реферальный кейс",
        "emoji": "🔗",
        "price": 50,
        "daily": False,
        "description": "Кейс для активных рефереров",
        "items": [
            {"type": "nothing",  "name": "💩 Ничего",    "chance": 38},
            {"type": "gift",     "name": "🧸 Мишка",     "chance": 28, "gift_key": "bear"},
            {"type": "gift",     "name": "🌹 Роза",      "chance": 17, "gift_key": "rose"},
            {"type": "gift",     "name": "🎂 Торт",      "chance": 9,  "gift_key": "cake"},
            {"type": "gift",     "name": "🚀 Ракета",    "chance": 4,  "gift_key": "rocket"},
            {"type": "gift",     "name": "💎 Алмаз",     "chance": 3,  "gift_key": "diamond"},
            {"type": "gift",     "name": "🏆 Кубок",     "chance": 1,  "gift_key": "trophy"},
        ]
    },
    "rich": {
        "name": "💰 Богатство",
        "emoji": "💰",
        "price": 80,
        "daily": False,
        "description": "Премиум кейс с шикарными наградами!",
        "items": [
            {"type": "nothing",  "name": "💩 Ничего",    "chance": 28},
            {"type": "gift",     "name": "🌹 Роза",      "chance": 22, "gift_key": "rose"},
            {"type": "gift",     "name": "🎁 Подарок",   "chance": 18, "gift_key": "gift_box"},
            {"type": "gift",     "name": "🎂 Торт",      "chance": 13, "gift_key": "cake"},
            {"type": "gift",     "name": "💐 Букет",     "chance": 9,  "gift_key": "bouquet"},
            {"type": "gift",     "name": "🍾 Шампанское","chance": 5,  "gift_key": "champagne"},
            {"type": "gift",     "name": "🏆 Кубок",     "chance": 3,  "gift_key": "trophy"},
            {"type": "gift",     "name": "💍 Кольцо",    "chance": 1.5,"gift_key": "ring"},
            {"type": "gift",     "name": "💎 Алмаз",     "chance": 0.5,"gift_key": "diamond"},
        ]
    },
}


import random

def roll_case(case_key: str) -> dict:
    """Крутим кейс, возвращаем выпавший предмет"""
    case = CASES.get(case_key)
    if not case:
        return None

    items = case["items"]
    chances = [item["chance"] for item in items]
    total = sum(chances)

    roll = random.uniform(0, total)
    cumulative = 0
    for item in items:
        cumulative += item["chance"]
        if roll <= cumulative:
            return item

    return items[-1]  # Fallback


def get_reel_items(case_key: str, won_item: dict, reel_size: int = 21) -> list:
    """
    Генерирует ленту предметов для анимации прокрутки.
    won_item всегда будет на позиции [reel_size // 2] (по центру).
    """
    case = CASES.get(case_key)
    if not case:
        return []

    items = case["items"]
    # Взвешенная выборка для случайных позиций
    weights = [i["chance"] for i in items]
    total = sum(weights)
    norm = [w / total for w in weights]

    reel = []
    center = reel_size // 2
    for i in range(reel_size):
        if i == center:
            reel.append(won_item)
        else:
            reel.append(random.choices(items, weights=norm, k=1)[0])
    return reel
