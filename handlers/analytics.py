from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile
from datetime import datetime

import database as db
from config import CATEGORIES
from keyboards.inline import analytics_menu, main_menu, back_button

router = Router()


@router.callback_query(F.data == "analytics")
async def show_analytics(callback: CallbackQuery):
    stats = await db.get_stats(callback.from_user.id)
    
    if stats['count'] == 0:
        await callback.message.edit_text(
            "📊 <b>Аналитика</b>\n\nДобавьте подписки для анализа!",
            reply_markup=main_menu(),
            parse_mode="HTML"
        )
        return
    
    text = (
        f"📊 <b>Аналитика</b>\n\n"
        f"💰 <b>Расходы:</b>\n"
        f"├ В день: ~{int(stats['daily'])} ₽\n"
        f"├ В месяц: <b>{int(stats['monthly'])} ₽</b>\n"
        f"└ В год: <b>{int(stats['yearly'])} ₽</b>\n\n"
        f"📦 Подписок: {stats['count']}"
    )
    
    if stats['most_expensive']:
        s = stats['most_expensive']
        text += f"\n💎 Самая дорогая: {s['icon']} {s['name']} ({int(s['price'])}₽)"
    
    await callback.message.edit_text(text, reply_markup=analytics_menu(), parse_mode="HTML")


@router.callback_query(F.data == "analytics:cats")
async def show_categories(callback: CallbackQuery):
    stats = await db.get_stats(callback.from_user.id)
    
    if not stats['by_category']:
        await callback.answer("Нет данных")
        return
    
    text = "📊 <b>Расходы по категориям</b>\n\n"
    total = stats['monthly']
    
    sorted_cats = sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True)
    
    for cat, amount in sorted_cats:
        cat_name = CATEGORIES.get(cat, cat)
        percent = (amount / total * 100) if total > 0 else 0
        bar_len = int(percent / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        
        text += f"<b>{cat_name}</b>\n{bar}\n{int(amount)}₽ ({int(percent)}%)\n\n"
    
    await callback.message.edit_text(text, reply_markup=back_button("analytics"), parse_mode="HTML")


@router.callback_query(F.data == "analytics:tips")
async def show_tips(callback: CallbackQuery):
    subs = await db.get_subscriptions(callback.from_user.id)
    stats = await db.get_stats(callback.from_user.id)
    
    tips = []
    
    # Годовая оплата
    monthly_subs = [s for s in subs if s['cycle'] == 'monthly']
    if len(monthly_subs) >= 2:
        potential = sum(s['price'] for s in monthly_subs) * 12 * 0.17
        tips.append(
            f"📅 <b>Годовая оплата</b>\n"
            f"Переведите {len(monthly_subs)} подписок на год.\n"
            f"Экономия ~17%: <b>{int(potential)}₽/год</b>"
        )
    
    # Дорогие подписки
    expensive = [s for s in subs if s['price'] > 500]
    if expensive:
        tips.append(
            f"💰 <b>Дорогие подписки</b>\n"
            f"У вас {len(expensive)} подписок > 500₽.\n"
            f"Поищите альтернативы или семейные тарифы."
        )
    
    # Много в одной категории
    for cat, amount in stats.get('by_category', {}).items():
        if amount > stats['monthly'] * 0.4 and stats['monthly'] > 0:
            cat_name = CATEGORIES.get(cat, cat)
            tips.append(
                f"📊 <b>Перекос в {cat_name}</b>\n"
                f"Более 40% бюджета. Возможно, часть можно отменить."
            )
            break
    
    # Общий совет
    if stats['monthly'] > 2000:
        save = stats['monthly'] * 0.2
        tips.append(
            f"🎯 <b>Цель: -20%</b>\n"
            f"Сократите расходы на 20%.\n"
            f"Экономия: <b>{int(save)}₽/мес</b> или <b>{int(save * 12)}₽/год</b>"
        )
    
    if not tips:
        tips.append("✅ <b>Отлично!</b>\nВаши подписки выглядят оптимально!")
    
    text = "💡 <b>Советы по экономии</b>\n\n" + "\n\n".join(tips)
    
    await callback.message.edit_text(text, reply_markup=back_button("analytics"), parse_mode="HTML")


@router.callback_query(F.data == "analytics:report")
async def monthly_report(callback: CallbackQuery):
    subs = await db.get_subscriptions(callback.from_user.id)
    stats = await db.get_stats(callback.from_user.id)
    user = await db.get_user(callback.from_user.id)
    
    text = f"📋 <b>Месячный отчёт</b>\n"
    text += f"📅 {datetime.now().strftime('%B %Y')}\n\n"
    
    text += f"💰 <b>Расходы:</b> {int(stats['monthly'])}₽/мес\n"
    text += f"📦 <b>Подписок:</b> {stats['count']}\n"
    
    # Топ-3
    if subs:
        text += "\n🏆 <b>Топ по расходам:</b>\n"
        sorted_subs = sorted(subs, key=lambda x: x['price'], reverse=True)[:3]
        for i, s in enumerate(sorted_subs, 1):
            text += f"{i}. {s['icon']} {s['name']} — {int(s['price'])}₽\n"
    
    # Категории
    if stats['by_category']:
        text += "\n📊 <b>По категориям:</b>\n"
        sorted_cats = sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True)[:3]
        for cat, amount in sorted_cats:
            cat_name = CATEGORIES.get(cat, cat)
            text += f"• {cat_name}: {int(amount)}₽\n"
    
    # Сэкономлено
    if user and user.get('total_saved', 0) > 0:
        text += f"\n💚 <b>Сэкономлено:</b> {int(user['total_saved'])}₽"
    
    text += f"\n\n📅 <b>Прогноз на год:</b> {int(stats['yearly'])}₽"
    
    await callback.message.edit_text(text, reply_markup=back_button("analytics"), parse_mode="HTML")


@router.callback_query(F.data == "back_analytics")
async def back_to_analytics(callback: CallbackQuery):
    await show_analytics(callback)