from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import logging

import database as db

logger = logging.getLogger(__name__)


async def send_subscription_notifications(bot):
    """Отправка уведомлений о платежах"""
    logger.info("🔔 Checking subscription notifications...")
    
    for days in [1, 2, 3, 5, 7]:
        notifications = await db.get_users_for_notification(days)
        
        for notif in notifications:
            if notif.get('notify_days', 1) != days:
                continue
            
            days_text = {
                1: "завтра",
                2: "через 2 дня",
                3: "через 3 дня"
            }.get(days, f"через {days} дней")
            
            text = (
                f"🔔 <b>Напоминание о платеже!</b>\n\n"
                f"{notif['icon']} <b>{notif['name']}</b>\n"
                f"💰 Сумма: <b>{int(notif['price'])}₽</b>\n"
                f"📅 Списание: <b>{days_text}</b>\n\n"
                f"Убедитесь, что на карте достаточно средств."
            )
            
            try:
                await bot.send_message(notif['user_id'], text, parse_mode="HTML")
                await db.log_notification(notif['id'], notif['user_id'])
                logger.info(f"Sent notification to {notif['user_id']}")
            except Exception as e:
                logger.error(f"Failed to send to {notif['user_id']}: {e}")
    
    logger.info("✅ Subscription notifications done")


async def send_trial_notifications(bot):
    """Отправка уведомлений о триалах"""
    logger.info("⏱ Checking trial notifications...")
    
    trials = await db.get_expiring_trials(days=2)
    
    for trial in trials:
        text = (
            f"⏱ <b>Пробный период заканчивается!</b>\n\n"
            f"📦 <b>{trial['name']}</b>\n"
            f"📅 Осталось: <b>2 дня</b>\n"
            f"💰 После триала: <b>{int(trial['price_after'])}₽/мес</b>\n\n"
            f"Не забудьте отменить, если подписка не нужна!"
        )
        
        try:
            await bot.send_message(trial['user_id'], text, parse_mode="HTML")
            await db.mark_trial_notified(trial['id'])
            logger.info(f"Sent trial notification to {trial['user_id']}")
        except Exception as e:
            logger.error(f"Failed to send trial to {trial['user_id']}: {e}")
    
    logger.info("✅ Trial notifications done")


async def update_payment_dates():
    """Обновление просроченных дат платежей"""
    logger.info("🔄 Updating payment dates...")
    
    import aiosqlite
    
    async with aiosqlite.connect(db.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        today = datetime.now().strftime("%Y-%m-%d")
        
        cursor = await conn.execute("""
            SELECT * FROM subscriptions 
            WHERE is_active = 1 AND next_payment < ?
        """, (today,))
        
        rows = await cursor.fetchall()
        
        for row in rows:
            await db.update_next_payment(row['id'])
    
    logger.info(f"✅ Updated {len(rows)} payment dates")


def setup_scheduler(bot):
    """Настройка планировщика"""
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    
    # Уведомления в 10:00 и 18:00
    scheduler.add_job(
        send_subscription_notifications,
        'cron',
        hour=10,
        minute=0,
        args=[bot]
    )
    
    scheduler.add_job(
        send_subscription_notifications,
        'cron',
        hour=18,
        minute=0,
        args=[bot]
    )
    
    # Триалы в 10:05
    scheduler.add_job(
        send_trial_notifications,
        'cron',
        hour=10,
        minute=5,
        args=[bot]
    )
    
    # Обновление дат в 00:05
    scheduler.add_job(
        update_payment_dates,
        'cron',
        hour=0,
        minute=5
    )
    
    return scheduler