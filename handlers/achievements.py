from aiogram import Router, F
from aiogram.types import CallbackQuery

import database as db
from config import ACHIEVEMENTS, get_level
from keyboards.inline import main_menu

router = Router()


@router.callback_query(F.data == "achievements")
async def show_achievements(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    unlocked = await db.get_achievements(user_id)
    
    xp = user.get('xp', 0) if user else 0
    level = get_level(xp)
    
    text = f"🏆 <b>Достижения</b>\n\n"
    text += f"Уровень: <b>{level['name']}</b>\n"
    text += f"Опыт: {xp} XP\n"
    
    if level['next']:
        progress = int(level['progress'] / 5)
        bar = "█" * progress + "░" * (20 - progress)
        text += f"\n{bar}\n"
        text += f"До <b>{level['next']}</b>: {level['next_xp'] - xp} XP\n"
    
    text += "\n<b>Разблокировано:</b>\n"
    
    unlocked_count = 0
    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id in unlocked:
            text += f"✅ {ach['icon']} <b>{ach['title']}</b> (+{ach['xp']} XP)\n"
            text += f"    └ {ach['desc']}\n"
            unlocked_count += 1
    
    if unlocked_count == 0:
        text += "Пока нет. Начните добавлять подписки!\n"
    
    # Заблокированные
    locked = [a for a in ACHIEVEMENTS if a not in unlocked]
    if locked:
        text += f"\n🔒 <b>Заблокировано:</b> {len(locked)}\n"
        for ach_id in locked[:3]:
            ach = ACHIEVEMENTS[ach_id]
            text += f"• {ach['icon']} {ach['title']} — {ach['desc']}\n"
    
    await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")