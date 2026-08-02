import aiosqlite
import secrets
import string
from datetime import datetime

DB_PATH = "bear_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id              INTEGER PRIMARY KEY,
                username             TEXT DEFAULT '',
                full_name            TEXT DEFAULT '',
                referred_by          INTEGER DEFAULT NULL,
                referral_count       INTEGER DEFAULT 0,
                gifts_received       INTEGER DEFAULT 0,
                free_gifts_available INTEGER DEFAULT 0,
                stars_spent          INTEGER DEFAULT 0,
                registered_at        TEXT DEFAULT '',
                is_banned            INTEGER DEFAULT 0
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS gift_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id   INTEGER,
                receiver_id INTEGER,
                gift_name   TEXT,
                gift_stars  INTEGER,
                sent_at     TEXT DEFAULT CURRENT_TIMESTAMP,
                status      TEXT DEFAULT 'sent'
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS checks (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                check_code      TEXT UNIQUE,
                creator_id      INTEGER,
                total_bears     INTEGER DEFAULT 1,
                used_count      INTEGER DEFAULT 0,
                max_activations INTEGER DEFAULT 1,
                created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
                is_active       INTEGER DEFAULT 1
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS check_activations (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                check_id     INTEGER,
                user_id      INTEGER,
                activated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(check_id, user_id)
            )
        """)

        # Очередь выдачи мишек — ожидают отправки
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bear_queue (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER,
                reason     TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status     TEXT DEFAULT 'pending'
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_stats (
                id                   INTEGER PRIMARY KEY DEFAULT 1,
                total_gifts_sold     INTEGER DEFAULT 0,
                total_stars_earned   INTEGER DEFAULT 0,
                total_bears_given    INTEGER DEFAULT 0,
                total_checks_created INTEGER DEFAULT 0,
                bear_stock           INTEGER DEFAULT 0
            )
        """)
        await db.execute("INSERT OR IGNORE INTO bot_stats (id) VALUES (1)")

        # Миграция: добавляем новые колонки если их нет (для старых баз)
        for col, default in [
            ("bear_stock", "0"),
            ("total_bears_given", "0"),
            ("total_checks_created", "0"),
        ]:
            try:
                await db.execute(f"ALTER TABLE bot_stats ADD COLUMN {col} INTEGER DEFAULT {default}")
            except Exception:
                pass  # Колонка уже существует

        # Миграция: таблица очереди мишек
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bear_queue (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER,
                reason     TEXT DEFAULT \'\',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status     TEXT DEFAULT \'pending\'
            )
        """)

        # Каналы/группы для рассылки чеков
        await db.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_channels (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id    INTEGER UNIQUE,
                title      TEXT DEFAULT '',
                chat_type  TEXT DEFAULT 'channel',
                added_at   TEXT DEFAULT CURRENT_TIMESTAMP,
                is_active  INTEGER DEFAULT 1
            )
        """)

        # Миграция: пароль для чеков
        try:
            await db.execute("ALTER TABLE checks ADD COLUMN password TEXT DEFAULT NULL")
        except Exception:
            pass

        # Миграция: субики для пользователей
        try:
            await db.execute("ALTER TABLE users ADD COLUMN subiki INTEGER DEFAULT 0")
        except Exception:
            pass

        await db.commit()

# ==================== USERS ====================

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cur:
            return await cur.fetchone()

async def register_user(user_id: int, username: str, full_name: str, referred_by: int = None):
    now = datetime.now().strftime("%d.%m.%Y")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id, username, full_name, referred_by, registered_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username or '', full_name or '', referred_by, now))
        await db.commit()

async def is_new_user(user_id: int) -> bool:
    return (await get_user(user_id)) is None

async def add_referral(referrer_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET referral_count = referral_count + 1 WHERE user_id=?",
            (referrer_id,)
        )
        await db.commit()
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT referral_count FROM users WHERE user_id=?", (referrer_id,)) as cur:
            row = await cur.fetchone()
            return row["referral_count"] if row else 0

async def grant_free_gift(user_id: int, amount: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET free_gifts_available = free_gifts_available + ? WHERE user_id=?",
            (amount, user_id)
        )
        await db.commit()

async def use_free_gift(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT free_gifts_available FROM users WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row or row[0] <= 0:
            return False
        await db.execute(
            "UPDATE users SET free_gifts_available = free_gifts_available - 1, gifts_received = gifts_received + 1 WHERE user_id=?",
            (user_id,)
        )
        await db.commit()
        return True

async def ban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
        await db.commit()

async def unban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT user_id FROM users WHERE is_banned=0") as cur:
            return await cur.fetchall()

async def get_user_count():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

async def get_top_referrers(limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT user_id, username, referral_count
            FROM users WHERE referral_count > 0
            ORDER BY referral_count DESC LIMIT ?
        """, (limit,)) as cur:
            return await cur.fetchall()

# ==================== ЗАПАС МИШЕК ====================

async def get_bear_stock() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT bear_stock FROM bot_stats WHERE id=1") as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

async def add_bear_stock(amount: int):
    """Пополнить запас мишек (вызывается из админки)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE bot_stats SET bear_stock = bear_stock + ? WHERE id=1",
            (amount,)
        )
        await db.commit()

async def take_bear_from_stock() -> bool:
    """Взять 1 мишку из запаса. Возвращает True если успешно."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT bear_stock FROM bot_stats WHERE id=1") as cur:
            row = await cur.fetchone()
        if not row or row[0] <= 0:
            return False
        await db.execute(
            "UPDATE bot_stats SET bear_stock = bear_stock - 1 WHERE id=1"
        )
        await db.commit()
        return True

# ==================== ОЧЕРЕДЬ МИШЕК ====================

async def add_to_bear_queue(user_id: int, reason: str):
    """Добавить пользователя в очередь на получение мишки."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bear_queue (user_id, reason) VALUES (?, ?)",
            (user_id, reason)
        )
        await db.commit()

async def get_pending_queue():
    """Получить всех ожидающих мишку."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM bear_queue WHERE status='pending' ORDER BY created_at"
        ) as cur:
            return await cur.fetchall()

async def mark_queue_sent(queue_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE bear_queue SET status='sent' WHERE id=?", (queue_id,)
        )
        # Увеличиваем счётчик выданных мишек
        await db.execute(
            "UPDATE bot_stats SET total_bears_given = total_bears_given + 1 WHERE id=1"
        )
        await db.commit()

async def get_queue_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM bear_queue WHERE status='pending'"
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

# ==================== STATS ====================

async def get_bot_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bot_stats WHERE id=1") as cur:
            return await cur.fetchone()

async def update_stats(gifts_delta=0, stars_delta=0, bears_delta=0, checks_delta=0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE bot_stats SET
                total_gifts_sold     = total_gifts_sold + ?,
                total_stars_earned   = total_stars_earned + ?,
                total_bears_given    = total_bears_given + ?,
                total_checks_created = total_checks_created + ?
            WHERE id=1
        """, (gifts_delta, stars_delta, bears_delta, checks_delta))
        await db.commit()

async def add_gift_history(sender_id, receiver_id, gift_name, gift_stars):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO gift_history (sender_id, receiver_id, gift_name, gift_stars)
            VALUES (?, ?, ?, ?)
        """, (sender_id, receiver_id, gift_name, gift_stars))
        await db.execute(
            "UPDATE users SET stars_spent = stars_spent + ? WHERE user_id=?",
            (gift_stars, sender_id)
        )
        await db.commit()

# ==================== ЧЕКИ ====================

def generate_check_code(length=12) -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

async def create_check(creator_id: int, bears_count: int, max_activations: int, password: str = None) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        for _ in range(10):
            code = generate_check_code()
            try:
                await db.execute("""
                    INSERT INTO checks (check_code, creator_id, total_bears, max_activations, password)
                    VALUES (?, ?, ?, ?, ?)
                """, (code, creator_id, bears_count, max_activations, password or None))
                await db.commit()
                return code
            except Exception:
                continue
    raise RuntimeError("Не удалось создать код чека")

async def get_check(check_code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM checks WHERE check_code=?", (check_code,)) as cur:
            return await cur.fetchone()

async def activate_check(check_code: str, user_id: int, password: str = None) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM checks WHERE check_code=?", (check_code,)) as cur:
            check = await cur.fetchone()
        if not check:
            return {"success": False, "reason": "not_found"}
        if not check["is_active"]:
            return {"success": False, "reason": "inactive"}
        if check["used_count"] >= check["max_activations"]:
            return {"success": False, "reason": "exhausted"}
        # Проверка пароля
        check_password = check["password"]
        if check_password is not None and check_password != "":
            if password is None or password.strip() != check_password:
                return {"success": False, "reason": "wrong_password"}
        async with db.execute(
            "SELECT id FROM check_activations WHERE check_id=? AND user_id=?",
            (check["id"], user_id)
        ) as cur:
            already = await cur.fetchone()
        if already:
            return {"success": False, "reason": "already_used"}
        await db.execute(
            "INSERT INTO check_activations (check_id, user_id) VALUES (?, ?)",
            (check["id"], user_id)
        )
        new_used = check["used_count"] + 1
        await db.execute(
            "UPDATE checks SET used_count = ? WHERE id=?",
            (new_used, check["id"])
        )
        if new_used >= check["max_activations"]:
            await db.execute("UPDATE checks SET is_active=0 WHERE id=?", (check["id"],))
        await db.commit()
        return {
            "success": True,
            "reason": "ok",
            "check_id": check["id"],
            "creator_id": check["creator_id"],
            "remaining": check["max_activations"] - new_used,
            "has_password": check_password is not None and check_password != ""
        }

async def deactivate_check(check_code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE checks SET is_active=0 WHERE check_code=?", (check_code,))
        await db.commit()

async def get_admin_checks(creator_id: int, limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM checks WHERE creator_id=?
            ORDER BY created_at DESC LIMIT ?
        """, (creator_id, limit)) as cur:
            return await cur.fetchall()

async def get_all_checks_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) as active,
                   SUM(used_count) as total_activations,
                   SUM(total_bears) as total_bears
            FROM checks
        """) as cur:
            return await cur.fetchone()


# ==================== BROADCAST CHANNELS ====================

async def add_broadcast_channel(chat_id: int, title: str, chat_type: str = "channel"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO broadcast_channels (chat_id, title, chat_type)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title, is_active=1
        """, (chat_id, title, chat_type))
        await db.commit()


async def remove_broadcast_channel(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE broadcast_channels SET is_active=0 WHERE chat_id=?", (chat_id,)
        )
        await db.commit()


async def get_broadcast_channels() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM broadcast_channels WHERE is_active=1 ORDER BY added_at DESC"
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
