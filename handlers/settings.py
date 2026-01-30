from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile
from datetime import datetime

import database as db
from keyboards.inline import settings_keyboard, notify_days_keyboard, main_menu

router = Router()


@router.callback_query(F.data == "settings")
async def show_settings(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    
    notify_on = user.get('notify_enabled', 1) if user else 1
    notify_days = user.get('notify_days', 1) if user else 1
    
    await callback.message.edit_text(
        "⚙️ <b>Настройки</b>",
        reply_markup=settings_keyboard(notify_on, notify_days),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "toggle_notify")
async def toggle_notify(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    new_value = 0 if user.get('notify_enabled', 1) else 1
    
    await db.update_user(callback.from_user.id, notify_enabled=new_value)
    
    status = "включены ✅" if new_value else "отключены ❌"
    await callback.answer(f"Уведомления {status}")
    
    await show_settings(callback)


@router.callback_query(F.data == "set_days")
async def set_days_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "📅 <b>За сколько дней напоминать?</b>",
        reply_markup=notify_days_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("days:"))
async def set_days(callback: CallbackQuery):
    days = int(callback.data.split(":")[1])
    
    await db.update_user(callback.from_user.id, notify_days=days)
    await callback.answer(f"Буду напоминать за {days} дн.")
    
    await show_settings(callback)


@router.callback_query(F.data == "export")
async def export_data(callback: CallbackQuery):
    subs = await db.get_subscriptions(callback.from_user.id, active_only=False)
    
    if not subs:
        await callback.answer("Нет данных для экспорта")
        return
    
    csv = "Название,Цена,Период,Следующий платёж,Категория,Статус\n"
    
    cycles = {"weekly": "Неделя", "monthly": "Месяц", "quarterly": "Квартал", "yearly": "Год"}
    
    for s in subs:
        status = "Активна" if s['is_active'] else "Приостановлена"
        csv += f'"{s["name"]}",{s["price"]},{cycles.get(s["cycle"], s["cycle"])},{s["next_payment"]},{s["category"]},{status}\n'
    
    file = BufferedInputFile(
        csv.encode('utf-8-sig'),
        filename=f"subscriptions_{datetime.now().strftime('%Y%m%d')}.csv"
    )
    
    await callback.message.answer_document(file, caption="📤 Ваши подписки")
    await callback.answer()