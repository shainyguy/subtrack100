import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "ssubby_bot")

# ЮКасса
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY")

# Цены
SUPPORT_PRICE = 399

# Лимиты
FREE_SUBS_LIMIT = 15

# Категории
CATEGORIES = {
    "entertainment": "🎬 Кино и ТВ",
    "music": "🎵 Музыка",
    "bundle": "📦 Экосистемы",
    "books": "📚 Книги",
    "cloud": "☁️ Облако",
    "education": "🎓 Образование",
    "productivity": "💼 Работа",
    "gaming": "🎮 Игры",
    "health": "💪 Здоровье",
    "other": "📦 Другое",
}

# Популярные сервисы
SERVICES = {
    "Яндекс Плюс": {"icon": "🅰️", "price": 299, "cat": "bundle"},
    "Кинопоиск": {"icon": "🎬", "price": 299, "cat": "entertainment"},
    "Okko": {"icon": "🎬", "price": 399, "cat": "entertainment"},
    "Иви": {"icon": "🎬", "price": 399, "cat": "entertainment"},
    "Wink": {"icon": "📺", "price": 299, "cat": "entertainment"},
    "Start": {"icon": "🎬", "price": 299, "cat": "entertainment"},
    "Premier": {"icon": "🎬", "price": 399, "cat": "entertainment"},
    "KION": {"icon": "🎬", "price": 299, "cat": "entertainment"},
    "Netflix": {"icon": "🎬", "price": 999, "cat": "entertainment"},
    "YouTube Premium": {"icon": "📺", "price": 299, "cat": "entertainment"},
    
    "Яндекс Музыка": {"icon": "🎵", "price": 299, "cat": "music"},
    "VK Музыка": {"icon": "🎵", "price": 149, "cat": "music"},
    "Spotify": {"icon": "🎵", "price": 299, "cat": "music"},
    "Apple Music": {"icon": "🎵", "price": 299, "cat": "music"},
    "СберЗвук": {"icon": "🎵", "price": 249, "cat": "music"},
    
    "СберПрайм": {"icon": "💚", "price": 399, "cat": "bundle"},
    "VK Combo": {"icon": "💙", "price": 199, "cat": "bundle"},
    "МТС Premium": {"icon": "🔴", "price": 299, "cat": "bundle"},
    
    "Литрес": {"icon": "📚", "price": 399, "cat": "books"},
    "MyBook": {"icon": "📖", "price": 399, "cat": "books"},
    "Букмейт": {"icon": "📖", "price": 399, "cat": "books"},
    
    "Telegram Premium": {"icon": "⭐", "price": 299, "cat": "other"},
    "ChatGPT Plus": {"icon": "🤖", "price": 2000, "cat": "productivity"},
    "iCloud 50ГБ": {"icon": "☁️", "price": 99, "cat": "cloud"},
    "iCloud 200ГБ": {"icon": "☁️", "price": 299, "cat": "cloud"},
    
    "Фитнес-клуб": {"icon": "💪", "price": 3000, "cat": "health"},
}

# Пересечения сервисов
OVERLAPS = {
    "Яндекс Плюс": {
        "includes": ["Яндекс Музыка", "Кинопоиск"],
        "hint": "Яндекс Плюс уже включает Музыку и Кинопоиск!"
    },
    "СберПрайм": {
        "includes": ["Okko", "СберЗвук"],
        "hint": "СберПрайм включает Okko и СберЗвук"
    },
    "VK Combo": {
        "includes": ["VK Музыка", "Букмейт"],
        "hint": "VK Combo включает VK Музыку и Букмейт!"
    },
    "МТС Premium": {
        "includes": ["KION"],
        "hint": "МТС Premium включает KION"
    },
    "YouTube Premium": {
        "includes": ["YouTube Music"],
        "hint": "YouTube Premium включает YouTube Music!"
    },
}

# Инструкции по отмене
CANCEL_INSTRUCTIONS = {
    "Яндекс Плюс": {
        "url": "https://plus.yandex.ru/settings",
        "steps": ["Откройте plus.yandex.ru", "Настройки → Управление подпиской", "Отменить подписку"]
    },
    "Spotify": {
        "url": "https://spotify.com/account",
        "steps": ["Откройте spotify.com/account", "Подписка → Изменить или отменить", "Подтвердите"]
    },
    "Netflix": {
        "url": "https://netflix.com/cancelplan",
        "steps": ["Откройте netflix.com", "Аккаунт → Отменить подписку"]
    },
    "YouTube Premium": {
        "url": "https://youtube.com/paid_memberships",
        "steps": ["Откройте youtube.com/paid_memberships", "Управление → Отменить"]
    },
    "Telegram Premium": {
        "steps": ["Настройки Telegram", "Telegram Premium", "Управление подпиской → Отменить"]
    },
    "Apple подписки": {
        "steps": ["Настройки iPhone → Ваше имя", "Подписки", "Выберите → Отменить"]
    },
    "СберПрайм": {
        "steps": ["СберБанк Онлайн", "Прайм → Управление", "Отменить"]
    },
}

# Достижения
ACHIEVEMENTS = {
    "first_sub": {"icon": "🎉", "title": "Первый шаг", "desc": "Добавить первую подписку", "xp": 10},
    "five_subs": {"icon": "📦", "title": "Коллекционер", "desc": "Добавить 5 подписок", "xp": 25},
    "ten_subs": {"icon": "🏆", "title": "Магнат подписок", "desc": "Добавить 10 подписок", "xp": 50},
    "first_delete": {"icon": "✂️", "title": "Экономия", "desc": "Удалить подписку", "xp": 20},
    "saved_500": {"icon": "💰", "title": "Экономист", "desc": "Сэкономить 500₽", "xp": 40},
    "saved_1000": {"icon": "💎", "title": "Тысяча!", "desc": "Сэкономить 1000₽", "xp": 75},
    "duplicate_found": {"icon": "🔍", "title": "Детектив", "desc": "Найти дубликат", "xp": 30},
    "trial_saved": {"icon": "⏱", "title": "Охотник за триалами", "desc": "Отменить триал вовремя", "xp": 25},
    "week_streak": {"icon": "🔥", "title": "На связи", "desc": "Заходить 7 дней подряд", "xp": 50},
}

# Уровни
LEVELS = [
    (0, "🌱 Новичок"),
    (50, "📊 Учётчик"),
    (150, "💼 Менеджер"),
    (300, "📈 Аналитик"),
    (500, "🏆 Эксперт"),
    (800, "👑 Мастер"),
]


def get_level(xp: int) -> dict:
    current = LEVELS[0]
    next_lvl = LEVELS[1] if len(LEVELS) > 1 else None
    
    for i, (req_xp, name) in enumerate(LEVELS):
        if xp >= req_xp:
            current = (req_xp, name)
            next_lvl = LEVELS[i + 1] if i + 1 < len(LEVELS) else None
    
    progress = 0
    if next_lvl:
        progress = (xp - current[0]) / (next_lvl[0] - current[0]) * 100
    
    return {
        "name": current[1],
        "xp": xp,
        "next": next_lvl[1] if next_lvl else None,
        "next_xp": next_lvl[0] if next_lvl else None,
        "progress": min(progress, 100)
    }


def get_cancel_instruction(name: str) -> dict:
    for service, data in CANCEL_INSTRUCTIONS.items():
        if service.lower() in name.lower() or name.lower() in service.lower():
            return {"name": service, **data}
    
    return {
        "name": name,
        "steps": [
            "Зайдите на сайт/в приложение сервиса",
            "Найдите Профиль или Настройки",
            "Раздел Подписка → Отменить"
        ]

    }
