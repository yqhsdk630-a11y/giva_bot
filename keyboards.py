from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


# ─── FOYDALANUVCHI MENU ──────────────────────────────────────

def user_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(
        KeyboardButton(text="🔗 Linkimni olish", style="success"),
        KeyboardButton(text="👥 Achkolarim", style="success")
    )
    kb.row(
        KeyboardButton(text="🎁 Bal berish", style="success"),
        KeyboardButton(text="📞 Admin bilan bog'lanish", style="primary")
    )
    return kb.as_markup(resize_keyboard=True)


def admin_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(
        KeyboardButton(text="🚀 Give Away boshlash", style="success"),
        KeyboardButton(text="⛔ Tugatish", style="danger")
    )
    kb.row(
        KeyboardButton(text="📢 Reklama", style="primary"),
        KeyboardButton(text="📈 Admin statistika", style="primary")
    )
    kb.row(
        KeyboardButton(text="🏆 G'oliblar", style="success"),
        KeyboardButton(text="💾 Backup olish", style="primary")
    )
    kb.row(
        KeyboardButton(text="🚫 Ban", style="danger"),
        KeyboardButton(text="✉️ Foydalanuvchiga yozish", style="success")
    )
    kb.row(
        KeyboardButton(text="🔗 Linkimni olish", style="primary"),
        KeyboardButton(text="👥 Achkolarim", style="success")
    )
    return kb.as_markup(resize_keyboard=True)


# ─── A'ZOLIK TEKSHIRUV ───────────────────────────────────────

def join_keyboard(group_url: str, channel_url: str = None) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="👥 Guruhga qo'shilish", url=group_url, style="primary")
    if channel_url:
        kb.button(text="📢 Kanalga qo'shilish", url=channel_url, style="primary")
    kb.button(text="✅ Tekshirish", callback_data="check_membership", style="primary")
    kb.adjust(1)
    return kb.as_markup()


# ─── TASDIQLASH ──────────────────────────────────────────────

def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Tasdiqlash", callback_data=f"confirm:{action}", style="primary")
    kb.button(text="❌ Bekor qilish", callback_data="cancel", style="danger")
    kb.adjust(2)
    return kb.as_markup()


def end_giveaway_confirm() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⛔ Ha, tugatish", callback_data="confirm:end_giveaway", style="primary")
    kb.button(text="❌ Yo'q, davom etsin", callback_data="cancel", style="danger")
    kb.adjust(1)
    return kb.as_markup()


# ─── SAHIFALASH ──────────────────────────────────────────────

def pagination_keyboard(current: int, total_pages: int, prefix: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if current > 1:
        kb.button(text="⬅️", callback_data=f"{prefix}:{current - 1}", style="primary")
    kb.button(text=f"{current}/{total_pages}", callback_data="noop", style="primary")
    if current < total_pages:
        kb.button(text="➡️", callback_data=f"{prefix}:{current + 1}", style="primary")
    kb.adjust(3)
    return kb.as_markup()


# ─── TRANSFER ────────────────────────────────────────────────

def transfer_confirm(to_name: str, count: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=f"✅ Ha, {count} ta ball beraman",
        callback_data="confirm:transfer", style="success"
    )
    kb.button(text="❌ Bekor", callback_data="cancel", style="danger")
    kb.adjust(1)
    return kb.as_markup()


# ─── G'OLIBLAR ───────────────────────────────────────────────

def winner_contact_keyboard(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Yozish", url=f"tg://user?id={user_id}", style="primary")
    kb.adjust(1)
    return kb.as_markup()
