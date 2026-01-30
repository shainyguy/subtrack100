from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta

import database as db
from config import SERVICES, CATEGORIES, get_cancel_instruction, ACHIEVEMENTS
from keyboards.inline import (
    services_keyboard, categories_keyboard, cycle_keyboard,
    subscriptions_list, subscription_actions, confirm_delete,
    cancel_instruction_kb, main_menu, back_button
)

router = Router()


class AddSub(StatesGroup):
    name = State()
    price = State()
    cycle = State()
    date = State()
    category = State()


class EditPrice(StatesGroup):
    new_price = State()


# ========== ДОБАВЛЕНИЕ ==========

@router.callback_query(F.data == "add_sub")
async def start_add(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "➕ <b>Добавление подписки</b>\n\nВыберите сервис или введите свой:",
        reply_markup=services_keyboard(0),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("srv_page:"))
async def services_page(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    await callback.message.edit_reply_markup(reply_markup=services_keyboard(page))


@router.callback_query(F.data.startswith("srv:"))
async def select_service(callback: CallbackQuery, state: FSMContext):
    service_name = callback.data.split(":", 1)[1]
    
    if service_name == "custom":
        await state.set_state(AddSub.name)
        await callback.message.edit_text(
            "✏️ Введите название подписки:",
            reply_markup=back_button("main")
        )
    else:
        service = SERVICES.get(service_name, {})
        await state.update_data(
            name=service_name,
            icon=service.get("icon", "📦"),
            category=service.get("cat", "other")
        )
        
        hint = f"\n💡 Средняя цена: ~{service.get('price', 0)}₽" if service.get('price') else ""
        
        await state.set_state(AddSub.price)
        await callback.message.edit_text(
            f"💰 Введите стоимость <b>{service_name}</b> в рублях:{hint}",
            parse_mode="HTML"
        )


@router.message(AddSub.name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()[:50]
    await state.update_data(name=name, icon="📦", category="other")
    await state.set_state(AddSub.price)
    await message.answer(f"💰 Введите стоимость <b>{name}</b> в рублях:", parse_mode="HTML")


@router.message(AddSub.price)
async def process_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", ".").replace(" ", ""))
        if price <= 0 or price > 1_000_000:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Введите корректную сумму (например: 299)")
        return
    
    await state.update_data(price=price)
    await state.set_state(AddSub.cycle)
    await message.answer("📅 Как часто списывается?", reply_markup=cycle_keyboard())


@router.callback_query(F.data.startswith("cycle:"), AddSub.cycle)
async def process_cycle(callback: CallbackQuery, state: FSMContext):
    cycle = callback.data.split(":")[1]
    await state.update_data(cycle=cycle)
    await state.set_state(AddSub.date)
    
    example = (datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y")
    
    await callback.message.edit_text(
        f"📆 Когда следующее списание?\n\n"
        f"Введите дату: <b>{example}</b>\n"
        f"Или: <b>сегодня</b> / <b>завтра</b> / <b>7</b> (дней)",
        parse_mode="HTML"
    )


@router.message(AddSub.date)
async def process_date(message: Message, state: FSMContext):
    text = message.text.strip().lower()
    
    try:
        if text in ["сегодня", "today"]:
            date = datetime.now()
        elif text in ["завтра", "tomorrow"]:
            date = datetime.now() + timedelta(days=1)
        elif text.isdigit():
            date = datetime.now() + timedelta(days=int(text))
        else:
            for fmt in ["%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%d/%m/%Y"]:
                try:
                    date = datetime.strptime(text, fmt)
                    break
                except:
                    continue
            else:
                raise ValueError()
    except:
        await message.answer("❌ Не понял дату. Формат: 25.12.2024 или число дней")
        return
    
    await state.update_data(next_payment=date.strftime("%Y-%m-%d"))
    await state.set_state(AddSub.category)
    
    data = await state.get_data()
    
    # Если категория уже есть (из сервиса), пропускаем
    if data.get('category') and data['category'] != 'other':
        await save_subscription(message, state)
    else:
        await message.answer("📁 Выберите категорию:", reply_markup=categories_keyboard())


@router.callback_query(F.data.startswith("cat:"), AddSub.category)
async def process_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split(":")[1]
    await state.update_data(category=category)
    await save_subscription(callback, state, is_callback=True)


async def save_subscription(event, state: FSMContext, is_callback: bool = False):
    data = await state.get_data()
    user_id = event.from_user.id
    
    await db.add_subscription(
        user_id=user_id,
        name=data['name'],
        price=data['price'],
        cycle=data['cycle'],
        next_payment=data['next_payment'],
        category=data.get('category', 'other'),
        icon=data.get('icon', '📦')
    )
    
    await state.clear()
    
    # Проверяем достижения
    count = await db.count_subscriptions(user_id)
    
    if count == 1:
        if await db.unlock_achievement(user_id, "first_sub"):
            await db.add_xp(user_id, ACHIEVEMENTS['first_sub']['xp'])
    elif count == 5:
        if await db.unlock_achievement(user_id, "five_subs"):
            await db.add_xp(user_id, ACHIEVEMENTS['five_subs']['xp'])
    elif count == 10:
        if await db.unlock_achievement(user_id, "ten_subs"):
            await db.add_xp(user_id, ACHIEVEMENTS['ten_subs']['xp'])
    
    cycles_ru = {"weekly": "неделя", "monthly": "месяц", "quarterly": "квартал", "yearly": "год"}
    
    text = (
        f"✅ <b>Подписка добавлена!</b>\n\n"
        f"{data.get('icon', '📦')} <b>{data['name']}</b>\n"
        f"├ 💰 {data['price']} ₽ / {cycles_ru.get(data['cycle'], data['cycle'])}\n"
        f"└ 📅 Следующий платёж: {data['next_payment']}\n\n"
        f"🔔 Напомню за день до списания!"
    )
    
    if is_callback:
        await event.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=main_menu(), parse_mode="HTML")


# ========== ПРОСМОТР ==========

@router.callback_query(F.data == "my_subs")
@router.message(Command("list"))
async def show_subscriptions(event):
    user_id = event.from_user.id
    subs = await db.get_subscriptions(user_id)
    
    if not subs:
        text = "📋 <b>Подписок пока нет</b>\n\nДобавьте первую!"
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")
        else:
            await event.answer(text, reply_markup=main_menu(), parse_mode="HTML")
        return
    
    total = await db.get_monthly_total(user_id)
    
    text = f"📋 <b>Ваши подписки</b> ({len(subs)})\n\n"
    text += f"💰 В месяц: <b>{int(total)} ₽</b>\n\n"
    text += "Нажмите для управления:"
    
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=subscriptions_list(subs), parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=subscriptions_list(subs), parse_mode="HTML")


@router.callback_query(F.data.startswith("view:"))
async def view_subscription(callback: CallbackQuery):
    sub_id = int(callback.data.split(":")[1])
    sub = await db.get_subscription(sub_id)
    
    if not sub:
        await callback.answer("Подписка не найдена", show_alert=True)
        return
    
    cycles = {"weekly": "неделя", "monthly": "месяц", "quarterly": "квартал", "yearly": "год"}
    status = "✅ Активна" if sub['is_active'] else "⏸ Приостановлена"
    cat = CATEGORIES.get(sub['category'], sub['category'])
    
    # Дней до платежа
    try:
        days = (datetime.strptime(sub['next_payment'], "%Y-%m-%d") - datetime.now()).days
        if days == 0:
            days_text = "⚠️ Сегодня!"
        elif days == 1:
            days_text = "Завтра"
        elif days < 0:
            days_text = "Просрочено"
        else:
            days_text = f"Через {days} дн."
    except:
        days_text = sub['next_payment']
    
    text = (
        f"{sub['icon']} <b>{sub['name']}</b>\n\n"
        f"├ 💰 Цена: <b>{int(sub['price'])} ₽</b> / {cycles.get(sub['cycle'], sub['cycle'])}\n"
        f"├ 📅 Следующий платёж: <b>{sub['next_payment']}</b>\n"
        f"├ ⏳ {days_text}\n"
        f"├ 📁 Категория: {cat}\n"
        f"└ 📊 Статус: {status}"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=subscription_actions(sub_id, sub['is_active']),
        parse_mode="HTML"
    )


# ========== РЕДАКТИРОВАНИЕ ==========

@router.callback_query(F.data.startswith("edit_price:"))
async def start_edit_price(callback: CallbackQuery, state: FSMContext):
    sub_id = int(callback.data.split(":")[1])
    sub = await db.get_subscription(sub_id)
    
    await state.set_state(EditPrice.new_price)
    await state.update_data(sub_id=sub_id)
    
    await callback.message.edit_text(
        f"💰 Текущая цена: <b>{int(sub['price'])} ₽</b>\n\nВведите новую цену:",
        parse_mode="HTML"
    )


@router.message(EditPrice.new_price)
async def process_new_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", ".").replace(" ", ""))
        if price <= 0:
            raise ValueError()
    except:
        await message.answer("❌ Введите корректную сумму")
        return
    
    data = await state.get_data()
    await db.update_subscription(data['sub_id'], price=price)
    await state.clear()
    
    await message.answer(f"✅ Цена обновлена: <b>{int(price)} ₽</b>", reply_markup=main_menu(), parse_mode="HTML")


@router.callback_query(F.data.startswith("pause:"))
async def pause_sub(callback: CallbackQuery):
    sub_id = int(callback.data.split(":")[1])
    await db.update_subscription(sub_id, is_active=0)
    await callback.answer("⏸ Подписка приостановлена")
    
    sub = await db.get_subscription(sub_id)
    await callback.message.edit_reply_markup(reply_markup=subscription_actions(sub_id, False))


@router.callback_query(F.data.startswith("resume:"))
async def resume_sub(callback: CallbackQuery):
    sub_id = int(callback.data.split(":")[1])
    await db.update_subscription(sub_id, is_active=1)
    await callback.answer("▶️ Подписка возобновлена")
    
    await callback.message.edit_reply_markup(reply_markup=subscription_actions(sub_id, True))


# ========== УДАЛЕНИЕ ==========

@router.callback_query(F.data.startswith("delete:"))
async def ask_delete(callback: CallbackQuery):
    sub_id = int(callback.data.split(":")[1])
    sub = await db.get_subscription(sub_id)
    
    await callback.message.edit_text(
        f"🗑 <b>Удалить подписку?</b>\n\n"
        f"{sub['icon']} {sub['name']} — {int(sub['price'])} ₽\n\n"
        f"Это действие нельзя отменить.",
        reply_markup=confirm_delete(sub_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("confirm_del:"))
async def confirm_delete_sub(callback: CallbackQuery):
    sub_id = int(callback.data.split(":")[1])
    sub = await db.get_subscription(sub_id)
    
    if sub:
        await db.delete_subscription(sub_id)
        await db.add_saved(callback.from_user.id, sub['price'])
        
        # Достижение
        if await db.unlock_achievement(callback.from_user.id, "first_delete"):
            await db.add_xp(callback.from_user.id, ACHIEVEMENTS['first_delete']['xp'])
    
    await callback.answer("🗑 Подписка удалена!", show_alert=True)
    await callback.message.edit_text("✅ Подписка удалена.", reply_markup=main_menu())


# ========== ИНСТРУКЦИЯ ПО ОТМЕНЕ ==========

@router.callback_query(F.data.startswith("cancel_help:"))
async def show_cancel_help(callback: CallbackQuery):
    sub_id = int(callback.data.split(":")[1])
    sub = await db.get_subscription(sub_id)
    
    instruction = get_cancel_instruction(sub['name'])
    steps = "\n".join(f"{i+1}. {s}" for i, s in enumerate(instruction['steps']))
    
    text = f"📋 <b>Как отменить {instruction['name']}</b>\n\n{steps}"
    
    if instruction.get('warning'):
        text += f"\n\n⚠️ {instruction['warning']}"
    
    await callback.message.edit_text(
        text,
        reply_markup=cancel_instruction_kb(sub_id, instruction.get('url')),
        parse_mode="HTML"
    )


# ========== БЛИЖАЙШИЕ ==========

@router.callback_query(F.data == "upcoming")
async def show_upcoming(callback: CallbackQuery):
    upcoming = await db.get_upcoming(callback.from_user.id, days=30)
    
    if not upcoming:
        await callback.message.edit_text(
            "🔔 <b>Ближайшие платежи</b>\n\nВ ближайшие 30 дней списаний нет.",
            reply_markup=main_menu(),
            parse_mode="HTML"
        )
        return
    
    total = sum(s['price'] for s in upcoming)
    
    text = f"🔔 <b>Ближайшие 30 дней</b>\n\n💰 К оплате: <b>{int(total)} ₽</b>\n\n"
    
    for s in upcoming[:10]:
        try:
            days = (datetime.strptime(s['next_payment'], "%Y-%m-%d") - datetime.now()).days
            if days == 0:
                days_text = "сегодня ⚠️"
            elif days == 1:
                days_text = "завтра"
            else:
                days_text = f"через {days} дн."
        except:
            days_text = s['next_payment']
        
        text += f"{s['icon']} <b>{s['name']}</b>\n└ {int(s['price'])}₽ — {days_text}\n\n"
    
    await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")


# ========== ДУБЛИКАТЫ ==========

@router.callback_query(F.data == "duplicates")
async def check_duplicates(callback: CallbackQuery):
    from config import OVERLAPS
    
    subs = await db.get_subscriptions(callback.from_user.id)
    sub_names = [s['name'].lower() for s in subs]
    
    issues = []
    
    for ecosystem, data in OVERLAPS.items():
        has_eco = any(ecosystem.lower() in n for n in sub_names)
        
        if has_eco:
            for included in data['includes']:
                if any(included.lower() in n for n in sub_names):
                    price = next((s['price'] for s in subs if included.lower() in s['name'].lower()), 0)
                    issues.append({
                        "eco": ecosystem,
                        "dup": included,
                        "hint": data['hint'],
                        "price": price
                    })
    
    if not issues:
        await callback.message.edit_text(
            "🔍 <b>Проверка на дубликаты</b>\n\n"
            "✅ Отлично! Пересечений не найдено.\n\n"
            "Ваши подписки оптимизированы!",
            reply_markup=main_menu(),
            parse_mode="HTML"
        )
        return
    
    # Достижение
    if await db.unlock_achievement(callback.from_user.id, "duplicate_found"):
        await db.add_xp(callback.from_user.id, ACHIEVEMENTS['duplicate_found']['xp'])
    
    total_saving = sum(i['price'] for i in issues)
    
    text = "🔍 <b>Найдены пересечения!</b>\n\n"
    
    for issue in issues:
        text += f"🔄 <b>{issue['eco']}</b> + <b>{issue['dup']}</b>\n"
        text += f"└ {issue['hint']}\n"
        text += f"💰 Можно сэкономить: {int(issue['price'])}₽/мес\n\n"
    
    text += f"\n<b>Потенциальная экономия: {int(total_saving)}₽/мес ({int(total_saving * 12)}₽/год)</b>"
    

    await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")
