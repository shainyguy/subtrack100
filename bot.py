import asyncio
import logging
from contextlib import asynccontextmanager
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import uvicorn

from config import BOT_TOKEN
import database as db
from services.notifications import setup_scheduler
from handlers import start, subscriptions, trials, analytics, achievements, settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Путь к статическим файлам
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

# ========== FASTAPI ==========

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    logger.info("✅ Database initialized")
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    dp.include_router(start.router)
    dp.include_router(subscriptions.router)
    dp.include_router(trials.router)
    dp.include_router(analytics.router)
    dp.include_router(achievements.router)
    dp.include_router(settings.router)
    
    scheduler = setup_scheduler(bot)
    scheduler.start()
    
    polling_task = asyncio.create_task(dp.start_polling(bot))
    logger.info("🚀 Bot started")
    logger.info(f"📱 Mini App ready at /app")
    
    yield
    
    polling_task.cancel()
    scheduler.shutdown()
    await bot.session.close()

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
    """Главная страница — Mini App"""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>SubTrack</h1><p>Mini App not found. Check /static/index.html</p>")

@app.get("/app", response_class=HTMLResponse)
async def mini_app():
    """Mini App страница"""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>Mini App not found</h1>")

@app.get("/health")
async def health():
    return {"status": "ok", "app": "SubTracker", "mini_app": "ready"}

# ========== API ROUTES ==========

@app.post("/api/auth")
async def auth(data: UserAuth):
    user = await db.get_or_create_user(data.user_id, data.username, data.first_name)
    return user

@app.get("/api/user/{user_id}")
async def get_user(user_id: int):
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

# Subscriptions
@app.get("/api/subscriptions/{user_id}")
async def get_subscriptions(user_id: int):
    subs = await db.get_subscriptions(user_id)
    stats = await db.get_stats(user_id)
    return {"subscriptions": subs, "stats": stats}

@app.post("/api/subscriptions/{user_id}")
async def create_subscription(user_id: int, data: SubscriptionCreate):
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

# Trials
@app.get("/api/trials/{user_id}")
async def get_trials(user_id: int):
    trials = await db.get_trials(user_id)
    return {"trials": trials}

@app.post("/api/trials/{user_id}")
async def create_trial(user_id: int, data: TrialCreate):
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

# Stats
@app.get("/api/stats/{user_id}")
async def get_stats(user_id: int):
    stats = await db.get_stats(user_id)
    subs = await db.get_subscriptions(user_id)
    upcoming = await db.get_upcoming(user_id, days=30)
    return {**stats, "subscriptions": subs, "upcoming": upcoming}

# Achievements
@app.get("/api/achievements/{user_id}")
async def get_achievements(user_id: int):
    user = await db.get_user(user_id)
    achievements = await db.get_achievements(user_id)
    return {
        "xp": user.get('xp', 0) if user else 0,
        "total_saved": user.get('total_saved', 0) if user else 0,
        "achievements": achievements
    }

# Duplicates check
@app.get("/api/duplicates/{user_id}")
async def check_duplicates(user_id: int):
    from config import OVERLAPS
    
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
        'steps': [
            'Откройте plus.yandex.ru или приложение Яндекс',
            'Нажмите на иконку профиля',
            'Выберите "Управление подпиской"',
            'Нажмите "Отменить подписку"',
            'Подтвердите отмену'
        ],
        'note': 'Подписка будет активна до конца оплаченного периода.'
    },
    'кинопоиск': {
        'steps': [
            'Откройте kinopoisk.ru',
            'Перейдите в профиль → Настройки',
            'Найдите раздел "Подписка"',
            'Нажмите "Отменить"'
        ],
        'note': 'Если подписка через Яндекс Плюс — отменяйте там.'
    },
    'spotify': {
        'steps': [
            'Откройте spotify.com/account',
            'Войдите в аккаунт',
            'Нажмите "Управление подпиской"',
            'Выберите "Отменить Premium"'
        ],
        'note': 'Отмена только через сайт! В приложении нельзя.'
    },
    'youtube premium': {
        'steps': [
            'Откройте youtube.com/paid_memberships',
            'Войдите в аккаунт',
            'Нажмите "Управление"',
            'Выберите "Отменить подписку"'
        ],
        'note': 'Можно приостановить до 6 месяцев вместо отмены.'
    },
    'netflix': {
        'steps': [
            'Откройте netflix.com/account',
            'В разделе "Подписка" нажмите "Отменить"',
            'Подтвердите отмену'
        ],
        'note': 'Доступ сохранится до конца периода.'
    },
    'telegram premium': {
        'steps': [
            'Откройте Telegram → Настройки',
            'Нажмите на "Telegram Premium"',
            'Прокрутите до "Управление подпиской"',
            'Отмените через App Store / Google Play'
        ],
        'note': 'Отмена через магазин приложений.'
    },
    'apple music': {
        'steps': [
            'Откройте Настройки на iPhone',
            'Нажмите на своё имя → Подписки',
            'Выберите Apple Music',
            'Нажмите "Отменить подписку"'
        ],
        'note': 'На Android: Apple Music → Настройки → Управление подпиской.'
    },
    'vk музыка': {
        'steps': [
            'Откройте vk.com/settings?act=payments',
            'Найдите раздел "Подписки"',
            'Выберите VK Музыка',
            'Нажмите "Отменить"'
        ],
        'note': 'Также можно через приложение VK.'
    },
    'okko': {
        'steps': [
            'Откройте okko.tv/account',
            'Перейдите в "Подписка"',
            'Нажмите "Отключить автопродление"'
        ],
        'note': 'Если через СберПрайм — отменяйте в приложении СберБанк.'
    },
    'ivi': {
        'steps': [
            'Откройте ivi.ru → Профиль',
            'Перейдите в "Подписка"',
            'Нажмите "Отменить подписку"'
        ],
        'note': 'Доступ сохранится до конца периода.'
    },
    'сберпрайм': {
        'steps': [
            'Откройте приложение СберБанк',
            'Перейдите в "Прайм" или "Подписки"',
            'Выберите СберПрайм',
            'Нажмите "Отключить"'
        ],
        'note': 'При отключении потеряете Okko, СберЗвук и бонусы.'
    },
    'мтс premium': {
        'steps': [
            'Откройте приложение Мой МТС',
            'Перейдите в "Услуги" → "Подписки"',
            'Найдите МТС Premium',
            'Нажмите "Отключить"'
        ],
        'note': 'Также можно через mts.ru'
    }
}

@app.get("/api/cancel-guide/{service}")
async def get_cancel_guide(service: str):
    service_lower = service.lower()
    
    # Ищем точное совпадение или частичное
    guide = CANCEL_GUIDES.get(service_lower)
    
    if not guide:
        for key, value in CANCEL_GUIDES.items():
            if key in service_lower or service_lower in key:
                guide = value
                break
    
    if not guide:
        guide = {
            'steps': [
                'Откройте официальный сайт или приложение сервиса',
                'Войдите в свой аккаунт',
                'Найдите раздел "Настройки" или "Профиль"',
                'Перейдите в "Подписка" или "Оплата"',
                'Нажмите "Отменить подписку"'
            ],
            'note': 'Если не получается — обратитесь в поддержку сервиса.'
        }
    
    return {"service": service, "guide": guide}

# ========== RUN ==========

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
