from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import CATEGORIES, SERVICES


def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    builder.row(InlineKeyboardButton(text="➕ Добавить подписку", callback_data="add_sub"))
    builder.row(
        InlineKeyboardButton(text="📋 Мои подписки", callback_data="my_subs"),
        InlineKeyboardButton(text="📊 Аналитика", callback_data="analytics")
    )
    builder.row(
        InlineKeyboardButton(text="⏱ Триалы", callback_data="trials"),
        InlineKeyboardButton(text="🔔 Ближайшие", callback_data="upcoming")
    )
    builder.row(
        InlineKeyboardButton(text="🔍 Дубликаты", callback_data="duplicates"),
        InlineKeyboardButton(text="🏆 Достижения", callback_data="achievements")
    )
    builder.row(InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings"))
    
    return builder.as_markup()


def back_button(to: str = "main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_{to}")]
    ])


def services_keyboard(page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    services = list(SERVICES.items())
    per_page = 8
    start = page * per_page
    end = start + per_page
    page_services = services[start:end]
    
    for name, data in page_services:
        builder.button(
            text=f"{data['icon']} {name}",
            callback_data=f"srv:{name[:20]}"
        )
    
    builder.adjust(2)
    
    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"srv_page:{page-1}"))
    
    total_pages = (len(services) + per_page - 1) // per_page
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"srv_page:{page+1}"))
    
    if nav:
        builder.row(*nav)
    
    builder.row(InlineKeyboardButton(text="✏️ Ввести своё", callback_data="srv:custom"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_main"))
    
    return builder.as_markup()


def categories_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for key, name in CATEGORIES.items():
        builder.button(text=name, callback_data=f"cat:{key}")
    
    builder.adjust(2)
    return builder.as_markup()


def cycle_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    cycles = [
        ("📅 Неделя", "weekly"),
        ("📆 Месяц", "monthly"),
        ("📆 Квартал", "quarterly"),
        ("📆 Год", "yearly"),
    ]
    
    for text, data in cycles:
        builder.button(text=text, callback_data=f"cycle:{data}")
    
    builder.adjust(2)
    return builder.as_markup()


def subscriptions_list(subs: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for s in subs[:15]:
        icon = s.get('icon', '📦')
        name = s['name'][:15]
        price = int(s['price'])
        builder.button(text=f"{icon} {name} — {price}₽", callback_data=f"view:{s['id']}")
    
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main"))
    
    return builder.as_markup()


def subscription_actions(sub_id: int, is_active: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    builder.row(InlineKeyboardButton(text="💰 Изменить цену", callback_data=f"edit_price:{sub_id}"))
    builder.row(InlineKeyboardButton(text="📋 Как отменить", callback_data=f"cancel_help:{sub_id}"))
    
    if is_active:
        builder.row(InlineKeyboardButton(text="⏸ Приостановить", callback_data=f"pause:{sub_id}"))
    else:
        builder.row(InlineKeyboardButton(text="▶️ Возобновить", callback_data=f"resume:{sub_id}"))
    
    builder.row(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete:{sub_id}"))
    builder.row(InlineKeyboardButton(text="◀️ К списку", callback_data="my_subs"))
    
    return builder.as_markup()


def confirm_delete(sub_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_del:{sub_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"view:{sub_id}")
    )
    return builder.as_markup()


def cancel_instruction_kb(sub_id: int, url: str = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    if url:
        builder.row(InlineKeyboardButton(text="🔗 Открыть сервис", url=url))
    
    builder.row(InlineKeyboardButton(text="✅ Отменил — удалить", callback_data=f"delete:{sub_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"view:{sub_id}"))
    
    return builder.as_markup()


def trials_list(trials: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for t in trials[:10]:
        name = t['name'][:20]
        builder.button(text=f"⏱ {name}", callback_data=f"trial:{t['id']}")
    
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="➕ Добавить триал", callback_data="add_trial"))
    builder.row(InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main"))
    
    return builder.as_markup()


def trial_actions(trial_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Отменил — удалить", callback_data=f"del_trial:{trial_id}"))
    builder.row(InlineKeyboardButton(text="➕ Оставить как подписку", callback_data=f"trial_to_sub:{trial_id}"))
    builder.row(InlineKeyboardButton(text="◀️ К триалам", callback_data="trials"))
    return builder.as_markup()


def analytics_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 По категориям", callback_data="analytics:cats"))
    builder.row(InlineKeyboardButton(text="💡 Советы по экономии", callback_data="analytics:tips"))
    builder.row(InlineKeyboardButton(text="📋 Месячный отчёт", callback_data="analytics:report"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_main"))
    return builder.as_markup()


def settings_keyboard(notify_on: bool, notify_days: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    status = "✅ Вкл" if notify_on else "❌ Выкл"
    builder.row(InlineKeyboardButton(text=f"🔔 Уведомления: {status}", callback_data="toggle_notify"))
    builder.row(InlineKeyboardButton(text=f"📅 За {notify_days} дн. до платежа", callback_data="set_days"))
    builder.row(InlineKeyboardButton(text="📤 Экспорт в CSV", callback_data="export"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_main"))
    
    return builder.as_markup()


def notify_days_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    for days in [1, 2, 3, 5, 7]:
        text = f"{days} день" if days == 1 else f"{days} дней"
        builder.button(text=text, callback_data=f"days:{days}")
    
    builder.adjust(3, 2)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="settings"))
    
    return builder.as_markup()