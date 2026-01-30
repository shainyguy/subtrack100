from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta

import database as db
from config import ACHIEVEMENTS
from keyboards.inline import trials_list, trial_actions, main_menu

router = Router()


class AddTrial(StatesGroup):
    name = State()
    end_date = State()
    price_after = State()


@router.callback_query(F.data == "trials")
@router.message(Command("trials"))
async def show_trials(event):
    user_id = event.from_user.id
    trials = await db.get_trials(user_id)
    
    text = "⏱ <b>Пробные периоды</b>\n\n"
    
    if not trials:
        text += "Нет отслеживаемых триалов.\n\nДобавьте, чтобы не забыть отменить!"
    else:
        text += "Нажмите для управления:\n"
    
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=trials_list(trials), parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=trials_list(trials), parse_mode="HTML")


@router.callback_query(F.data == "add_trial")
async def start_add_trial(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddTrial.name)
    
    await callback.message.edit_text(
        "⏱ <b>Добавить пробный период</b>\n\n"
        "Я напомню отменить до списания!\n\n"
        "Введите название сервиса:",
        parse_mode="HTML"
    )


@router.message(AddTrial.name)
async def process_trial_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip()[:50])
    await state.set_state(AddTrial.end_date)
    
    today = datetime.now()
    
    await message.answer(
        "📅 Когда заканчивается триал?\n\n"
        f"• 7 дней: {(today + timedelta(days=7)).strftime('%d.%m.%Y')}\n"
        f"• 14 дней: {(today + timedelta(days=14)).strftime('%d.%m.%Y')}\n"
        f"• 30 дней: {(today + timedelta(days=30)).strftime('%d.%m.%Y')}\n\n"
        "Введите дату или число дней:"
    )


@router.message(AddTrial.end_date)
async def process_trial_date(message: Message, state: FSMContext):
    text = message.text.strip()
    
    try:
        if text.isdigit():
            date = datetime.now() + timedelta(days=int(text))
        else:
            for fmt in ["%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"]:
                try:
                    date = datetime.strptime(text, fmt)
                    break
                except:
                    continue
            else:
                raise ValueError()
    except:
        await message.answer("❌ Не понял. Введите 7 или 25.12.2024")
        return
    
    await state.update_data(end_date=date.strftime("%Y-%m-%d"))
    await state.set_state(AddTrial.price_after)
    
    await message.answer("💰 Сколько будут списывать после триала?\n\nВведите сумму (или 0):")


@router.message(AddTrial.price_after)
async def process_trial_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", ".").replace(" ", ""))
    except:
        price = 0
    
    data = await state.get_data()
    
    await db.add_trial(
        user_id=message.from_user.id,
        name=data['name'],
        end_date=data['end_date'],
        price_after=max(0, price)
    )
    
    await state.clear()
    
    days = (datetime.strptime(data['end_date'], "%Y-%m-%d") - datetime.now()).days
    
    await message.answer(
        f"✅ <b>Триал добавлен!</b>\n\n"
        f"📦 {data['name']}\n"
        f"⏱ Осталось: {days} дней\n"
        f"💰 После: {int(price)}₽/мес\n\n"
        f"🔔 Напомню за 2 дня до окончания!",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("trial:"))
async def view_trial(callback: CallbackQuery):
    trial_id = int(callback.data.split(":")[1])
    trial = await db.get_trial(trial_id)
    
    if not trial:
        await callback.answer("Не найдено", show_alert=True)
        return
    
    try:
        days = (datetime.strptime(trial['end_date'], "%Y-%m-%d") - datetime.now()).days
        if days < 0:
            days_text = "⚠️ Уже закончился!"
        elif days == 0:
            days_text = "⚠️ Заканчивается сегодня!"
        elif days == 1:
            days_text = "⚠️ Заканчивается завтра!"
        else:
            days_text = f"Осталось {days} дней"
    except:
        days_text = trial['end_date']
    
    await callback.message.edit_text(
        f"⏱ <b>{trial['name']}</b>\n\n"
        f"📅 Дата окончания: {trial['end_date']}\n"
        f"⏳ {days_text}\n"
        f"💰 После триала: {int(trial['price_after'])}₽/мес",
        reply_markup=trial_actions(trial_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("del_trial:"))
async def delete_trial(callback: CallbackQuery):
    trial_id = int(callback.data.split(":")[1])
    trial = await db.get_trial(trial_id)
    
    if trial:
        await db.delete_trial(trial_id)
        
        # Достижение
        if await db.unlock_achievement(callback.from_user.id, "trial_saved"):
            await db.add_xp(callback.from_user.id, ACHIEVEMENTS['trial_saved']['xp'])
            await db.add_saved(callback.from_user.id, trial.get('price_after', 0))
    
    await callback.answer("✅ Триал удалён!", show_alert=True)
    
    trials = await db.get_trials(callback.from_user.id)
    await callback.message.edit_text(
        "⏱ <b>Пробные периоды</b>",
        reply_markup=trials_list(trials),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("trial_to_sub:"))
async def trial_to_subscription(callback: CallbackQuery):
    trial_id = int(callback.data.split(":")[1])
    trial = await db.get_trial(trial_id)
    
    if not trial:
        await callback.answer("Не найдено", show_alert=True)
        return
    
    await db.add_subscription(
        user_id=callback.from_user.id,
        name=trial['name'],
        price=trial['price_after'],
        cycle="monthly",
        next_payment=trial['end_date'],
        icon="📦"
    )
    
    await db.delete_trial(trial_id)
    
    await callback.answer("✅ Добавлено в подписки!", show_alert=True)
    await callback.message.edit_text(
        f"✅ <b>{trial['name']}</b> добавлен в подписки!",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )



from aiogram.filters import Command
