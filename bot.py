import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import uvicorn

from config import (
    BOT_TOKEN, BOT_USERNAME,
    YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, SUPPORT_PRICE
)
import database as db
from services.notifications import setup_scheduler
from handlers import start, subscriptions, trials, analytics, achievements, settings

# ЮКасса
try:
    from yookassa import Configuration, Payment
    Configuration.account_id = YOOKASSA_SHOP_ID
    Configuration.secret_key = YOOKASSA_SECRET_KEY
    YOOKASSA_ENABLED = bool(YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY)
except ImportError:
    YOOKASSA_ENABLED = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

# ========== PYDANTIC MODELS ==========

class UserAuth(BaseModel):
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None

class SubscriptionCreate(BaseModel):
    name: str
    price: float
    cycle: str = "monthly"
    next_payment: Optional[str] = None
    category: str = "other"
    icon: str = "📦"

class SubscriptionUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    cycle: Optional[str] = None
    next_payment: Optional[str] = None
    category: Optional[str] = None
    icon: Optional[str] = None
    is_active: Optional[int] = None

class TrialCreate(BaseModel):
    name: str
    end_date: str
    price_after: float = 0
    icon: str = "⏱"

class SettingsUpdate(BaseModel):
    notify_enabled: Optional[int] = None
    notify_days: Optional[int] = None

class PaymentCreate(BaseModel):
    user_id: int
    amount: float = SUPPORT_PRICE
    payment_type: str = "support"
    description: str = "Поддержка проекта SubTrack"

# ========== FASTAPI ==========

bot_instance: Bot = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_instance
    
    await db.init_db()
    logger.info("✅ Database initialized")
    
    if YOOKASSA_ENABLED:
        logger.info("✅ YooKassa configured")
    else:
        logger.warning("⚠️ YooKassa not configured")
    
    bot_instance = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    dp.include_router(start.router)
    dp.include_router(subscriptions.router)
    dp.include_router(trials.router)
    dp.include_router(analytics.router)
    dp.include_router(achievements.router)
    dp.include_router(settings.router)
    
    scheduler = setup_scheduler(bot_instance)
    scheduler.start()
    
    polling_task = asyncio.create_task(dp.start_polling(bot_instance))
    logger.info("🚀 Bot started")
    logger.info(f"📱 Mini App ready at /")
    
    yield
    
    polling_task.cancel()
    scheduler.shutdown()
    await bot_instance.session.close()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== MINI APP ==========

@app.get("/", response_class=HTMLResponse)
async def root_page():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>SubTrack</h1><p>Mini App not found</p>")

@app.get("/app", response_class=HTMLResponse)
async def mini_app():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>Mini App not found</h1>")

@app.get("/health")
async def health():
    return {"status": "ok", "app": "SubTracker", "yookassa": YOOKASSA_ENABLED}

# ========== PAYMENT API ==========

@app.post("/api/payment/create")
async def create_payment(data: PaymentCreate):
    """Создать платёж через ЮКассу"""
    
    # Сначала убедимся что пользователь существует
    user = await db.get_user(data.user_id)
    if not user:
        # Создаём пользователя если его нет
        user = await db.create_user(data.user_id)
    
    if not YOOKASSA_ENABLED:
        # Если ЮКасса не настроена — возвращаем ссылку на бота
        return {
            "success": True,
            "payment_url": f"https://t.me/{BOT_USERNAME}?start=donate_{int(data.amount)}",
            "method": "bot"
        }
    
    try:
        # Создаём платёж в ЮКассе
        idempotence_key = str(uuid.uuid4())
        
        payment = Payment.create({
            "amount": {
                "value": str(data.amount),
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": f"https://t.me/{BOT_USERNAME}?start=payment_success"
            },
            "capture": True,
            "description": data.description,
            "metadata": {
                "user_id": data.user_id,
                "payment_type": data.payment_type
            }
        }, idempotence_key)
        
        # Сохраняем платёж в БД
        await db.create_payment(
            user_id=data.user_id,
            payment_id=payment.id,
            amount=data.amount,
            payment_type=data.payment_type,
            status="pending"
        )
        
        logger.info(f"💳 Payment created: {payment.id} for user {data.user_id}")
        
        return {
            "success": True,
            "payment_id": payment.id,
            "payment_url": payment.confirmation.confirmation_url,
            "method": "yookassa"
        }
        
    except Exception as e:
        logger.error(f"Payment error: {e}")
        # Fallback на бота
        return {
            "success": True,
            "payment_url": f"https://t.me/{BOT_USERNAME}?start=donate_{int(data.amount)}",
            "method": "bot",
            "error": str(e)
        }


@app.post("/api/payment/webhook")
async def payment_webhook(request: Request):
    """Webhook от ЮКассы для подтверждения платежа"""
    try:
        body = await request.json()
        
        event = body.get("event")
        payment_data = body.get("object", {})
        payment_id = payment_data.get("id")
        status = payment_data.get("status")
        
        logger.info(f"📩 Webhook: {event}, payment {payment_id}, status {status}")
        
        if event == "payment.succeeded" and status == "succeeded":
            # Получаем метаданные
            metadata = payment_data.get("metadata", {})
            user_id = metadata.get("user_id")
            payment_type = metadata.get("payment_type", "support")
            
            if user_id:
                # Обновляем статус платежа
                await db.update_payment_status(payment_id, "succeeded")
                
                # Если это поддержка — даём премиум
                if payment_type == "support":
                    await db.set_premium(int(user_id), days=30)
                    logger.info(f"⭐ Premium activated for user {user_id}")
                    
                    # Отправляем уведомление пользователю
                    if bot_instance:
                        try:
                            await bot_instance.send_message(
                                int(user_id),
                                "🎉 <b>Спасибо за поддержку!</b>\n\n"
                                "Ваш платёж успешно обработан.\n"
                                "Премиум-статус активирован на 30 дней! ⭐"
                            )
                        except Exception as e:
                            logger.error(f"Failed to notify user: {e}")
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/payment/check/{payment_id}")
async def check_payment(payment_id: str):
    """Проверить статус платежа"""
    if not YOOKASSA_ENABLED:
        return {"status": "unknown", "message": "YooKassa not configured"}
    
    try:
        payment = Payment.find_one(payment_id)
        return {
            "status": payment.status,
            "paid": payment.paid,
            "amount": payment.amount.value
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ========== USER API ==========

@app.post("/api/auth")
async def auth(data: UserAuth):
    """Авторизация/регистрация пользователя"""
    user = await db.get_or_create_user(data.user_id, data.username, data.first_name)
    return user


@app.get("/api/user/{user_id}")
async def get_user(user_id: int):
    """Получить пользователя"""
    user = await db.get_user(user_id)
    if not user:
        user = await db.create_user(user_id)
    return user


@app.put("/api/user/{user_id}/settings")
async def update_settings(user_id: int, data: SettingsUpdate):
    await db.update_user(user_id, 
                         notify_enabled=data.notify_enabled, 
                         notify_days=data.notify_days)
    return {"status": "ok"}


# ========== SUBSCRIPTIONS API ==========

@app.get("/api/subscriptions/{user_id}")
async def get_subscriptions(user_id: int):
    # Убедимся что пользователь существует
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id)
    
    subs = await db.get_subscriptions(user_id)
    stats = await db.get_stats(user_id)
    return {"subscriptions": subs, "stats": stats}


@app.post("/api/subscriptions/{user_id}")
async def create_subscription(user_id: int, data: SubscriptionCreate):
    # Убедимся что пользователь существует
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id)
    
    sub_id = await db.add_subscription(
        user_id=user_id,
        name=data.name,
        price=data.price,
        cycle=data.cycle,
        next_payment=data.next_payment,
        category=data.category,
        icon=data.icon
    )
    return {"id": sub_id, "status": "created"}


@app.put("/api/subscriptions/{sub_id}")
async def update_subscription(sub_id: int, data: SubscriptionUpdate):
    await db.update_subscription(sub_id, **data.model_dump(exclude_none=True))
    return {"status": "updated"}


@app.delete("/api/subscriptions/{sub_id}")
async def delete_subscription(sub_id: int):
    sub = await db.get_subscription(sub_id)
    if sub:
        await db.delete_subscription(sub_id)
    return {"status": "deleted"}


# ========== TRIALS API ==========

@app.get("/api/trials/{user_id}")
async def get_trials(user_id: int):
    # Убедимся что пользователь существует
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id)
    
    trials_list = await db.get_trials(user_id)
    return {"trials": trials_list}


@app.post("/api/trials/{user_id}")
async def create_trial(user_id: int, data: TrialCreate):
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id)
    
    trial_id = await db.add_trial(
        user_id=user_id,
        name=data.name,
        end_date=data.end_date,
        price_after=data.price_after,
        icon=data.icon
    )
    return {"id": trial_id, "status": "created"}


@app.delete("/api/trials/{trial_id}")
async def delete_trial(trial_id: int):
    await db.delete_trial(trial_id)
    return {"status": "deleted"}


# ========== STATS & ANALYTICS ==========

@app.get("/api/stats/{user_id}")
async def get_stats(user_id: int):
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id)
    
    stats = await db.get_stats(user_id)
    subs = await db.get_subscriptions(user_id)
    upcoming = await db.get_upcoming(user_id, days=30)
    return {**stats, "subscriptions": subs, "upcoming": upcoming}


@app.get("/api/achievements/{user_id}")
async def get_achievements(user_id: int):
    user = await db.get_user(user_id)
    if not user:
        user = await db.create_user(user_id)
    
    achievements = await db.get_achievements(user_id)
    return {
        "xp": user.get('xp', 0) if user else 0,
        "total_saved": user.get('total_saved', 0) if user else 0,
        "achievements": achievements
    }


@app.get("/api/duplicates/{user_id}")
async def check_duplicates(user_id: int):
    from config import OVERLAPS
    
    user = await db.get_user(user_id)
    if not user:
        await db.create_user(user_id)
    
    subs = await db.get_subscriptions(user_id)
    sub_names = [s['name'].lower() for s in subs]
    
    issues = []
    
    for ecosystem, data in OVERLAPS.items():
        has_eco = any(ecosystem.lower() in n for n in sub_names)
        
        if has_eco:
            for included in data['includes']:
                if any(included.lower() in n for n in sub_names):
                    price = next((s['price'] for s in subs if included.lower() in s['name'].lower()), 0)
                    issues.append({
                        "ecosystem": ecosystem,
                        "duplicate": included,
                        "hint": data['hint'],
                        "saving": price
                    })
    
    return {"issues": issues, "total_saving": sum(i['saving'] for i in issues)}


# ========== CANCEL GUIDES ==========

CANCEL_GUIDES = {
    'яндекс плюс': {
        'steps': ['Откройте plus.yandex.ru', 'Нажмите на профиль', 'Выберите "Управление подпиской"', 'Нажмите "Отменить подписку"', 'Подтвердите'],
        'note': 'Подписка будет активна до конца периода.'
    },
    'кинопоиск': {
        'steps': ['Откройте kinopoisk.ru', 'Перейдите в профиль', 'Найдите "Подписка"', 'Нажмите "Отменить"'],
        'note': 'Если через Яндекс Плюс — отменяйте там.'
    },
    'spotify': {
        'steps': ['Откройте spotify.com/account', 'Войдите в аккаунт', 'Нажмите "Управление подпиской"', 'Выберите "Отменить Premium"'],
        'note': 'Отмена только через сайт!'
    },
    'youtube premium': {
        'steps': ['Откройте youtube.com/paid_memberships', 'Войдите', 'Нажмите "Управление"', 'Выберите "Отменить"'],
        'note': 'Можно приостановить до 6 месяцев.'
    },
    'netflix': {
        'steps': ['Откройте netflix.com/account', 'Нажмите "Отменить подписку"', 'Подтвердите'],
        'note': 'Доступ сохранится до конца периода.'
    },
    'telegram premium': {
        'steps': ['Откройте Telegram → Настройки', 'Нажмите на "Telegram Premium"', 'Перейдите в "Управление подпиской"', 'Отмените через App Store / Google Play'],
        'note': 'Отмена через магазин приложений.'
    },
}

@app.get("/api/cancel-guide/{service}")
async def get_cancel_guide(service: str):
    service_lower = service.lower()
    guide = CANCEL_GUIDES.get(service_lower)
    
    if not guide:
        for key, value in CANCEL_GUIDES.items():
            if key in service_lower or service_lower in key:
                guide = value
                break
    
    if not guide:
        guide = {
            'steps': ['Откройте сайт или приложение', 'Войдите в аккаунт', 'Найдите "Настройки" или "Профиль"', 'Перейдите в "Подписка"', 'Нажмите "Отменить"'],
            'note': 'Если не получается — обратитесь в поддержку.'
        }
    
    return {"service": service, "guide": guide}


# ========== RUN ==========

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
