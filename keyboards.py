from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# ─── FOYDALANUVCHI MENU ──────────────────────────────────────

def user_menu(lang: str = 'uz') -> ReplyKeyboardMarkup:
    uz = {
        'stats':   '📊 Statistika',
        'link':    '🔗 Linkimni olish',
        'invites': '👥 Achkolarim',
        'top':     '🏆 Top 10',
        'give':    '🎁 Bal berish',
        'support': '📞 Admin bilan bog\'lanish',
        'lang':    '🌐 Til',
    }
    ru = {
        'stats':   '📊 Статистика',
        'link':    '🔗 Получить ссылку',
        'invites': '👥 Мои рефералы',
        'top':     '🏆 Топ 10',
        'give':    '🎁 Передать баллы',
        'support': '📞 Связаться с админом',
        'lang':    '🌐 Язык',
    }
    t = uz if lang == 'uz' else ru
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text=t['stats']), KeyboardButton(text=t['link']))
    kb.row(KeyboardButton(text=t['invites']), KeyboardButton(text=t['top']))
    kb.row(KeyboardButton(text=t['give']), KeyboardButton(text=t['support']))
    kb.row(KeyboardButton(text=t['lang']))
    return kb.as_markup(resize_keyboard=True)


def admin_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text='🚀 Give Away boshlash'), KeyboardButton(text='⛔ Tugatish'))
    kb.row(KeyboardButton(text='📢 Reklama'), KeyboardButton(text='📈 Admin statistika'))
    kb.row(KeyboardButton(text='🏆 G\'oliblar'), KeyboardButton(text='✉️ Foydalanuvchiga yozish'))
    kb.row(KeyboardButton(text='💾 Backup olish'), KeyboardButton(text='🚫 Ban'))
    kb.row(KeyboardButton(text='📊 Statistika'), KeyboardButton(text='🔗 Linkimni olish'))
    kb.row(KeyboardButton(text='👥 Achkolarim'), KeyboardButton(text='🏅 Top 10'))
    return kb.as_markup(resize_keyboard=True)


# ─── TIL TANLASH ─────────────────────────────────────────────

def lang_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🇺🇿 O'zbek", callback_data="lang:uz")
    kb.button(text="🇷🇺 Русский", callback_data="lang:ru")
    kb.adjust(2)
    return kb.as_markup()


# ─── A'ZOLIK TEKSHIRUV ───────────────────────────────────────

def join_keyboard(group_url: str, channel_url: str = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="👥 Guruhga qo'shilish", url=group_url)
    if channel_url:
        kb.button(text="📢 Kanalga qo'shilish", url=channel_url)
    kb.button(text="✅ Tekshirish", callback_data="check_membership")
    kb.adjust(1)
    return kb.as_markup()


# ─── TASDIQLASH ──────────────────────────────────────────────

def confirm_keyboard(action: str, lang: str = 'uz') -> InlineKeyboardMarkup:
    yes = "✅ Tasdiqlash" if lang == 'uz' else "✅ Подтвердить"
    no = "❌ Bekor qilish" if lang == 'uz' else "❌ Отмена"
    kb = InlineKeyboardBuilder()
    kb.button(text=yes, callback_data=f"confirm:{action}")
    kb.button(text=no, callback_data="cancel")
    kb.adjust(2)
    return kb.as_markup()


def end_giveaway_confirm() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⛔ Ha, tugatish", callback_data="confirm:end_giveaway")
    kb.button(text="❌ Yo'q, davom etsin", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()


# ─── SAHIFALASH ──────────────────────────────────────────────

def pagination_keyboard(current: int, total_pages: int, prefix: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if current > 1:
        kb.button(text="⬅️", callback_data=f"{prefix}:{current - 1}")
    kb.button(text=f"{current}/{total_pages}", callback_data="noop")
    if current < total_pages:
        kb.button(text="➡️", callback_data=f"{prefix}:{current + 1}")
    kb.adjust(3)
    return kb.as_markup()


# ─── TRANSFER ────────────────────────────────────────────────

def transfer_confirm(to_name: str, count: int, lang: str = 'uz') -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=f"✅ Ha, {to_name}ga {count} ta ball beraman",
        callback_data="confirm:transfer"
    )
    kb.button(text="❌ Bekor", callback_data="cancel")
    kb.adjust(1)
    return kb.as_markup()


# ─── G'OLIBLAR ───────────────────────────────────────────────

def winner_contact_keyboard(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Yozish", url=f"tg://user?id={user_id}")
    kb.adjust(1)
    return kb.as_markup()
