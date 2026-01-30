import aiosqlite
from datetime import datetime, timedelta
from typing import List, Optional

DB_PATH = "subtracker.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notify_enabled INTEGER DEFAULT 1,
                notify_days INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                total_saved REAL DEFAULT 0,
                last_visit DATE
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                cycle TEXT DEFAULT 'monthly',
                next_payment DATE,
                category TEXT DEFAULT 'other',
                icon TEXT DEFAULT '📦',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS trials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                end_date DATE NOT NULL,
                price_after REAL DEFAULT 0,
                icon TEXT DEFAULT '⏱',
                notified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                achievement_id TEXT NOT NULL,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, achievement_id)
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notification_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                sub_id INTEGER,
                sent_at DATE DEFAULT CURRENT_DATE
            )
        """)
        
        await db.commit()


# ========== USERS ==========

async def get_user(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_user(user_id: int, username: str = None, first_name: str = None) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name, last_visit)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, first_name, datetime.now().strftime("%Y-%m-%d")))
        await db.commit()
    return await get_user(user_id)


async def get_or_create_user(user_id: int, username: str = None, first_name: str = None) -> dict:
    user = await get_user(user_id)
    if not user:
        user = await create_user(user_id, username, first_name)
    
    # Обновляем last_visit
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_visit = ? WHERE user_id = ?",
            (datetime.now().strftime("%Y-%m-%d"), user_id)
        )
        await db.commit()
    
    return user


async def update_user(user_id: int, **kwargs):
    allowed = ['notify_enabled', 'notify_days', 'xp', 'total_saved']
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    
    if not updates:
        return
    
    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [user_id]
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", values)
        await db.commit()


async def add_xp(user_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET xp = xp + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()


async def add_saved(user_id: int, amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET total_saved = total_saved + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()


# ========== SUBSCRIPTIONS ==========

async def get_subscriptions(user_id: int, active_only: bool = True) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM subscriptions WHERE user_id = ?"
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY next_payment ASC"
        
        cursor = await db.execute(query, (user_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_subscription(sub_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM subscriptions WHERE id = ?", (sub_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def add_subscription(user_id: int, name: str, price: float, cycle: str = "monthly",
                           next_payment: str = None, category: str = "other", icon: str = "📦") -> int:
    if not next_payment:
        next_payment = datetime.now().strftime("%Y-%m-%d")
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO subscriptions (user_id, name, price, cycle, next_payment, category, icon)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, name, price, cycle, next_payment, category, icon))
        await db.commit()
        return cursor.lastrowid


async def update_subscription(sub_id: int, **kwargs):
    allowed = ['name', 'price', 'cycle', 'next_payment', 'category', 'icon', 'is_active']
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    
    if not updates:
        return
    
    set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
    values = list(updates.values()) + [sub_id]
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE subscriptions SET {set_clause} WHERE id = ?", values)
        await db.commit()


async def delete_subscription(sub_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM subscriptions WHERE id = ?", (sub_id,))
        await db.commit()


async def count_subscriptions(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM subscriptions WHERE user_id = ? AND is_active = 1",
            (user_id,)
        )
        result = await cursor.fetchone()
        return result[0]


async def get_monthly_total(user_id: int) -> float:
    subs = await get_subscriptions(user_id)
    total = 0.0
    
    for s in subs:
        price = s['price']
        cycle = s['cycle']
        
        if cycle == 'yearly':
            total += price / 12
        elif cycle == 'weekly':
            total += price * 4.33
        elif cycle == 'quarterly':
            total += price / 3
        else:
            total += price
    
    return round(total, 2)


async def get_upcoming(user_id: int, days: int = 7) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        today = datetime.now().strftime("%Y-%m-%d")
        future = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        
        cursor = await db.execute("""
            SELECT * FROM subscriptions
            WHERE user_id = ? AND is_active = 1 AND next_payment BETWEEN ? AND ?
            ORDER BY next_payment ASC
        """, (user_id, today, future))
        
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# ========== TRIALS ==========

async def get_trials(user_id: int) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM trials WHERE user_id = ? ORDER BY end_date ASC",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_trial(trial_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM trials WHERE id = ?", (trial_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def add_trial(user_id: int, name: str, end_date: str, price_after: float = 0, icon: str = "⏱") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO trials (user_id, name, end_date, price_after, icon)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, name, end_date, price_after, icon))
        await db.commit()
        return cursor.lastrowid


async def delete_trial(trial_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM trials WHERE id = ?", (trial_id,))
        await db.commit()


# ========== ACHIEVEMENTS ==========

async def get_achievements(user_id: int) -> List[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT achievement_id FROM achievements WHERE user_id = ?",
            (user_id,)
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def unlock_achievement(user_id: int, achievement_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO achievements (user_id, achievement_id) VALUES (?, ?)",
                (user_id, achievement_id)
            )
            await db.commit()
            return True
        except:
            return False


async def has_achievement(user_id: int, achievement_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM achievements WHERE user_id = ? AND achievement_id = ?",
            (user_id, achievement_id)
        )
        return await cursor.fetchone() is not None


# ========== STATS ==========

async def get_stats(user_id: int) -> dict:
    subs = await get_subscriptions(user_id)
    monthly = await get_monthly_total(user_id)
    
    by_category = {}
    for s in subs:
        cat = s['category']
        price = s['price']
        cycle = s['cycle']
        
        if cycle == 'yearly':
            price = price / 12
        elif cycle == 'weekly':
            price = price * 4.33
        elif cycle == 'quarterly':
            price = price / 3
        
        by_category[cat] = by_category.get(cat, 0) + price
    
    most_expensive = max(subs, key=lambda x: x['price']) if subs else None
    
    return {
        "count": len(subs),
        "monthly": monthly,
        "yearly": round(monthly * 12, 2),
        "daily": round(monthly / 30, 2),
        "by_category": by_category,
        "most_expensive": most_expensive,
    }


# ========== NOTIFICATIONS ==========

async def get_users_for_notification(days: int) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        target = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")
        
        cursor = await db.execute("""
            SELECT s.*, u.notify_enabled, u.notify_days
            FROM subscriptions s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.is_active = 1 AND s.next_payment = ? AND u.notify_enabled = 1
            AND NOT EXISTS (
                SELECT 1 FROM notification_log n
                WHERE n.sub_id = s.id AND n.sent_at = ?
            )
        """, (target, today))
        
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_expiring_trials(days: int = 2) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        target = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        
        cursor = await db.execute("""
            SELECT t.*, u.notify_enabled
            FROM trials t
            JOIN users u ON t.user_id = u.user_id
            WHERE t.end_date = ? AND t.notified = 0 AND u.notify_enabled = 1
        """, (target,))
        
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def log_notification(sub_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO notification_log (user_id, sub_id) VALUES (?, ?)",
            (user_id, sub_id)
        )
        await db.commit()


async def mark_trial_notified(trial_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE trials SET notified = 1 WHERE id = ?", (trial_id,))
        await db.commit()


async def update_next_payment(sub_id: int):
    sub = await get_subscription(sub_id)
    if not sub:
        return
    
    current = datetime.strptime(sub['next_payment'], "%Y-%m-%d")
    cycle = sub['cycle']
    
    deltas = {'weekly': 7, 'monthly': 30, 'quarterly': 90, 'yearly': 365}
    next_date = current + timedelta(days=deltas.get(cycle, 30))
    
    today = datetime.now()
    while next_date < today:
        next_date += timedelta(days=deltas.get(cycle, 30))
    
    await update_subscription(sub_id, next_payment=next_date.strftime("%Y-%m-%d"))