import math
import logging
from datetime import datetime, timezone
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiosqlite

import database as db
from config import (
    GROUP_ID, CHANNEL_URL, CHECK_CHANNEL,
    MIN_REFERRALS_FOR_RANDOM, ADMIN_IDS, DB_FILE
)
from keyboards import user_menu, admin_menu, join_keyboard, pagination_keyboard, transfer_confirm
from utils import check_membership, user_mention, time_remaining

logger = logging.getLogger(__name__)
router = Router()


class TransferState(StatesGroup):
    waiting_target = State()


# ─── START ───────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user = message.from_user

    if await db.is_blacklisted(user.id):
        await message.answer("🚫 Siz konkursda qatnashishdan mahrum etilgansiz.")
        return

    await db.register_user(user.id, user.username, user.full_name)
    is_admin = user.id in ADMIN_IDS

    is_member = await check_membership(bot, user.id)
    if not is_member:
        try:
            group_info = await bot.get_chat(GROUP_ID)
            invite = group_info.invite_link or "https://t.me/+qpPPqYGXKqs3ZmIy"
        except Exception:
            invite = "https://t.me/+qpPPqYGXKqs3ZmIy"
        await message.answer(
            "👋 Assalomu alaykum!\n\n"
            "⚠️ Botdan foydalanish uchun avval guruh va kanalga a'zo bo'ling:",
            reply_markup=join_keyboard(invite, CHANNEL_URL if CHECK_CHANNEL else None)
        )
        return

    await message.answer(
        f"👋 Assalomu alaykum, <b>{user.full_name}</b>!\n\n"
        f"🎉 <b>TO'RAQO'RG'ON _ NATYAJNOY</b> Give Away botiga xush kelibsiz!\n\n"
        f"📌 Shaxsiy linkingizni oling va do'stlaringizni taklif qiling!\n"
        f"🏆 Eng ko'p odam qo'shgan Top 3 sovg'a yutadi!\n\n"
        f"👇 Pastdagi tugmalardan foydalaning:",
        reply_markup=admin_menu() if is_admin else user_menu(),
        parse_mode='HTML'
    )


@router.callback_query(F.data == "check_membership")
async def check_join(callback: CallbackQuery, bot: Bot):
    user = callback.from_user
    is_member = await check_membership(bot, user.id)
    if is_member:
        await db.register_user(user.id, user.username, user.full_name)
        is_admin = user.id in ADMIN_IDS
        await callback.message.edit_text("✅ A'zolik tasdiqlandi!")
        await callback.message.answer(
            f"👋 Xush kelibsiz, <b>{user.full_name}</b>!\n\n"
            f"🎉 Give Away ga xush kelibsiz!\n"
            f"📌 Shaxsiy linkingizni oling va do'stlaringizni taklif qiling!\n\n"
            f"👇 Pastdagi tugmalardan foydalaning:",
            reply_markup=admin_menu() if is_admin else user_menu(),
            parse_mode="HTML"
        )
    else:
        try:
            group_info = await bot.get_chat(GROUP_ID)
            invite = group_info.invite_link or "https://t.me/+qpPPqYGXKqs3ZmIy"
        except Exception:
            invite = "https://t.me/+qpPPqYGXKqs3ZmIy"
        await callback.answer(
            "❌ Hali a'zo emassiz! Guruh va kanalga qo'shiling.",
            show_alert=True
        )


# ─── LINK ────────────────────────────────────────────────────

@router.message(F.text == "🔗 Linkimni olish")
async def my_link(message: Message, bot: Bot):
    if not await require_membership(message, bot):
        return
    user = message.from_user

    if await db.is_blacklisted(user.id):
        await message.answer("🚫 Siz konkursda qatnashishdan mahrum etilgansiz.")
        return

    gw = await db.get_giveaway()
    if not gw or not gw['is_active']:
        await message.answer("ℹ️ Hozirda faol give away yo'q.")
        return

    existing = await db.get_invite_link(user.id)
    if existing:
        link = existing
    else:
        try:
            invite = await bot.create_chat_invite_link(
                GROUP_ID,
                name=f"ref_{user.id}",
                creates_join_request=False
            )
            link = invite.invite_link
            await db.save_invite_link(user.id, link)
            await db.set_link_sent(user.id)
        except Exception as e:
            logger.error(f"Link yaratishda xato: {e}")
            await message.answer(
                "❌ Link yaratishda xato!\n"
                "Bot guruhda admin bo'lishi va 'Invite users via link' huquqi bo'lishi kerak."
            )
            return

    ref_count = await db.get_referral_count(user.id)
    ends = datetime.fromisoformat(str(gw['ends_at'])).replace(tzinfo=timezone.utc)
    time_left = time_remaining(ends)

    await message.answer(
        f"🔗 <b>Sizning shaxsiy taklif linkingiz:</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"👥 Qo'shgan odamlar: <b>{ref_count} ta</b>\n"
        f"⏰ Tugashiga: <b>{time_left}</b>\n\n"
        f"💡 Shu linkni do'stlaringizga yuboring!\n"
        f"Kim shu link orqali kirsa — siz ball olasiz! 🏆",
        parse_mode='HTML'
    )


# ─── ACHKOLARIM ──────────────────────────────────────────────

@router.message(F.text == "👥 Achkolarim")
async def my_invites(message: Message, bot: Bot):
    if not await require_membership(message, bot):
        return
    await show_invites_page(message, message.from_user.id, page=1)


async def show_invites_page(message: Message, user_id: int, page: int):
    per_page = 50
    offset = (page - 1) * per_page
    rows = await db.get_referrals_list(user_id, offset=offset, limit=per_page)
    total = await db.get_referral_count(user_id)
    total_pages = max(1, math.ceil(total / per_page))
    rank = await db.get_user_rank(user_id)

    if not rows:
        await message.answer(
            "👥 Hali hech kimni qo'shmadingiz.\n\n"
            "🔗 Linkingizni oling va tarqating!"
        )
        return

    lines = [f"👥 <b>Sizning achkolaringiz</b> ({total} ta) | 🏆 {rank}-o'rin\n"]
    for i, (full_name, username, joined_at) in enumerate(rows, offset + 1):
        uname = f"@{username}" if username else "—"
        lines.append(f"{i}. {full_name} — {uname}")

    kb = pagination_keyboard(page, total_pages, f"invites:{user_id}") if total_pages > 1 else None
    await message.answer("\n".join(lines), parse_mode='HTML', reply_markup=kb)


@router.callback_query(F.data.startswith("invites:"))
async def invites_page(callback: CallbackQuery):
    parts = callback.data.split(":")
    user_id = int(parts[1])
    page = int(parts[2])
    await callback.message.delete()
    await show_invites_page(callback.message, user_id, page)
    await callback.answer()


# ─── BAL BERISH ──────────────────────────────────────────────

@router.message(F.text == "🎁 Bal berish")
async def give_points_start(message: Message, state: FSMContext, bot: Bot):
    if not await require_membership(message, bot):
        return
    user = message.from_user
    u = await db.get_user(user.id)

    if u and u['transfer_done']:
        await message.answer(
            "❌ Siz allaqachon balingizni berdingiz.\n"
            "Bu bir martalik imkoniyat."
        )
        return

    ref_count = await db.get_referral_count(user.id)
    if ref_count == 0:
        await message.answer(
            "❌ Sizda beradigan ball yo'q.\n"
            "Avval do'stlaringizni taklif qiling!"
        )
        return

    await state.set_state(TransferState.waiting_target)
    await state.update_data(ref_count=ref_count)

    await message.answer(
        f"👥 Sizda <b>{ref_count} ta</b> ball bor.\n\n"
        f"Kimga berishni xohlaysiz?\n"
        f"Username yoki ID yuboring:\n\n"
        f"Misol: <code>@username</code> yoki <code>123456789</code>\n\n"
        f"Bekor qilish: /cancel",
        parse_mode='HTML'
    )


@router.message(TransferState.waiting_target)
async def give_points_target(message: Message, state: FSMContext):
    data = await state.get_data()
    ref_count = data.get('ref_count', 0)
    text = message.text.strip().lstrip('@')

    if text == '/cancel':
        await state.clear()
        await message.answer("❌ Bekor qilindi.")
        return

    target = None
    async with aiosqlite.connect(DB_FILE) as conn:
        if text.lstrip('-').isdigit():
            async with conn.execute(
                "SELECT user_id, full_name FROM users WHERE user_id=?", (int(text),)
            ) as c:
                row = await c.fetchone()
        else:
            async with conn.execute(
                "SELECT user_id, full_name FROM users WHERE username=?", (text,)
            ) as c:
                row = await c.fetchone()

    if row:
        target = {'user_id': row[0], 'full_name': row[1]}

    if not target:
        await message.answer(
            "❌ Foydalanuvchi topilmadi.\n"
            "Username yoki ID ni to'g'ri kiriting."
        )
        return

    if target['user_id'] == message.from_user.id:
        await message.answer("❌ O'zingizga bera olmaysiz.")
        return

    await state.update_data(target_id=target['user_id'], target_name=target['full_name'])

    await message.answer(
        f"⚠️ <b>Tasdiqlaysizmi?</b>\n\n"
        f"<b>{ref_count} ta</b> ball → {user_mention(target['full_name'], target['user_id'])}\n\n"
        f"⚠️ Bu <b>bir martalik</b> amal. Qaytarib bo'lmaydi!",
        parse_mode='HTML',
        reply_markup=transfer_confirm(target['full_name'], ref_count)
    )


@router.callback_query(F.data == "confirm:transfer")
async def confirm_transfer(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_id = data.get('target_id')
    target_name = data.get('target_name')
    ref_count = data.get('ref_count', 0)

    success = await db.transfer_points(callback.from_user.id, target_id)
    await state.clear()

    if success:
        new_count = await db.get_referral_count(target_id)
        await callback.message.edit_text(
            f"✅ Ball muvaffaqiyatli o'tkazildi!\n"
            f"→ {target_name} endi <b>{new_count} ta</b> ballga ega.",
            parse_mode='HTML'
        )
        try:
            await bot.send_message(
                target_id,
                f"🎁 {user_mention(callback.from_user.full_name, callback.from_user.id)} "
                f"sizga <b>{ref_count} ta</b> ball o'tkazdi!\n"
                f"Endi sizda <b>{new_count} ta</b> ball bor. 🏆",
                parse_mode='HTML'
            )
        except Exception:
            pass
    else:
        await callback.message.edit_text(
            "❌ Transfer amalga oshmadi. Allaqachon bergan bo'lishingiz mumkin."
        )


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()