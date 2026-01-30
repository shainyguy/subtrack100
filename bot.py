import asyncio
import logging
from contextlib import asynccontextmanager
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn

from config import BOT_TOKEN
import database as db
from services.notifications import setup_scheduler
from handlers import start, subscriptions, trials, analytics, achievements, settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    
    # Запуск бота в фоне
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

# ========== API ROUTES ==========

@app.get("/")
async def root():
    return {"status": "ok", "app": "SubTracker"}

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

# ========== RUN ==========

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)