from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from datetime import datetime

import database as db
from keyboards.inline import main_menu

router = Router()


def get_greeting() -> str:
    hour = datetime.now().hour
    if hour < 6:
        return "🌙 Доброй ночи"
    elif hour < 12:
        return "🌅 Доброе утро"
    elif hour < 18:
        return "☀️ Добрый день"
    return "🌆 Добрый вечер"


@router.message(CommandStart())
async def cmd_start(message: Message):
    user = await db.get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )
    
    stats = await db.get_stats(message.from_user.id)
    upcoming = await db.get_upcoming(message.from_user.id, days=3)
    trials = await db.get_trials(message.from_user.id)
    
    name = message.from_user.first_name or "друг"
    greeting = get_greeting()
    
    text = f"{greeting}, <b>{name}</b>! 👋\n\n"
    text += "Я <b>SUBBY</b> — помогу контролировать подписки.\n\n"
    
    text += f"📊 <b>Статистика:</b>\n"
    text += f"├ Подписок: <b>{stats['count']}</b>\n"
    text += f"├ В месяц: <b>{int(stats['monthly'])} ₽</b>\n"
    text += f"└ В год: <b>{int(stats['yearly'])} ₽</b>\n"
    
    if upcoming:
        text += "\n🔔 <b>Скоро списание:</b>\n"
        for s in upcoming[:3]:
            days = (datetime.strptime(s['next_payment'], "%Y-%m-%d") - datetime.now()).days
            days_text = "сегодня!" if days == 0 else f"через {days} дн."
            text += f"• {s['icon']} {s['name']} — {int(s['price'])}₽ ({days_text})\n"
    
    expiring_trials = [t for t in trials if (datetime.strptime(t['end_date'], "%Y-%m-%d") - datetime.now()).days <= 3]
    if expiring_trials:
        text += "\n⏱ <b>Триалы заканчиваются:</b>\n"
        for t in expiring_trials[:2]:
            days = (datetime.strptime(t['end_date'], "%Y-%m-%d") - datetime.now()).days
            text += f"• {t['name']} — {days} дн.\n"
    
    text += "\n⬇️ Выберите действие:"
    
    await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")


@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    stats = await db.get_stats(callback.from_user.id)
    upcoming = await db.get_upcoming(callback.from_user.id, days=3)
    
    text = f"🏠 <b>Главное меню</b>\n\n"
    text += f"📊 <b>Статистика:</b>\n"
    text += f"├ Подписок: <b>{stats['count']}</b>\n"
    text += f"├ В месяц: <b>{int(stats['monthly'])} ₽</b>\n"
    text += f"└ В год: <b>{int(stats['yearly'])} ₽</b>\n"
    
    if upcoming:
        text += "\n🔔 <b>Ближайшие:</b>\n"
        for s in upcoming[:3]:
            text += f"• {s['icon']} {s['name']} — {int(s['price'])}₽\n"
    
    await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    text = """
📖 <b>Команды бота:</b>

/start — Главное меню
/add — Добавить подписку
/list — Мои подписки
/stats — Статистика
/trials — Пробные периоды
/settings — Настройки
/help — Эта справка

<b>Возможности:</b>
• ➕ Учёт подписок
• 🔔 Напоминания о платежах
• 🔍 Поиск дубликатов
• ⏱ Трекер триалов
• 📊 Аналитика расходов
• 🏆 Достижения
"""
    await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    stats = await db.get_stats(message.from_user.id)
    
    text = f"📊 <b>Ваша статистика</b>\n\n"
    text += f"💰 В месяц: <b>{int(stats['monthly'])} ₽</b>\n"
    text += f"📅 В год: <b>{int(stats['yearly'])} ₽</b>\n"
    text += f"📦 Подписок: <b>{stats['count']}</b>\n"
    
    if stats['most_expensive']:
        s = stats['most_expensive']
        text += f"\n💎 Самая дорогая: {s['icon']} {s['name']} — {int(s['price'])}₽"
    

    await message.answer(text, reply_markup=main_menu(), parse_mode="HTML")
