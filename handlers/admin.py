import io
import logging
import random
from datetime import datetime, timezone
from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from config import (
    ADMIN_IDS, GROUP_ID, TOP_WINNERS_COUNT,
    TOP_RANDOM_POOL_START, TOP_RANDOM_POOL_END, TOP_RANDOM_COUNT,
    GLOBAL_RANDOM_COUNT, MIN_REFERRALS_FOR_RANDOM, BACKUP_WINNERS_COUNT
)
from filters import IsAdmin
from keyboards import end_giveaway_confirm, winner_contact_keyboard
from utils import (
    send_to_admins, build_leaderboard_text, format_dt,
    time_remaining, user_mention, generate_csv, now_local
)

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())


class GiveawaySetup(StatesGroup):
    start_time = State()
    end_time = State()
    confirm = State()


class BroadcastState(StatesGroup):
    waiting_text = State()


class BanState(StatesGroup):
    waiting_user = State()


# ─── GIVE AWAY BOSHLASH ──────────────────────────────────────

@router.message(F.text == "🚀 Give Away boshlash")
async def start_giveaway_cmd(message: Message, state: FSMContext):
    gw = await db.get_giveaway()
    if gw and gw['is_active']:
        await message.answer("⚠️ Give away allaqachon faol! Avval tugatish kerak.")
        return
    await state.set_state(GiveawaySetup.start_time)
    await message.answer(
        "📅 <b>Give away boshlanish vaqtini kiriting:</b>\n\n"
        "Format: <code>25.01.2025 20:00</code>\n"
        "⏰ Toshkent vaqti (UTC+5) da kiriting",
        parse_mode='HTML'
    )


@router.message(GiveawaySetup.start_time)
async def gw_get_start(message: Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        await state.update_data(started_at=dt)
        await state.set_state(GiveawaySetup.end_time)
        await message.answer(
            "📅 <b>Tugash vaqtini kiriting:</b>\n\n"
            "Format: <code>02.02.2025 20:00</code>\n"
            "⚠️ Kamida 1 kun, ko'pi bilan 60 kun bo'lishi kerak",
            parse_mode='HTML'
        )
    except ValueError:
        await message.answer(
            "❌ Format noto'g'ri!\n"
            "To'g'ri misol: <code>25.01.2025 20:00</code>",
            parse_mode='HTML'
        )


@router.message(GiveawaySetup.end_time)
async def gw_get_end(message: Message, state: FSMContext):
    try:
        end_dt = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        data = await state.get_data()
        start_dt = data['started_at']

        if end_dt <= start_dt:
            await message.answer("❌ Tugash vaqti boshlanishdan keyin bo'lishi kerak!")
            return

        diff = end_dt - start_dt
        if diff.days > 60:
            await message.answer("❌ Davomiylik 60 kundan oshmasligi kerak!")
            return

        await state.update_data(ends_at=end_dt)
        await state.set_state(GiveawaySetup.confirm)

        days = diff.days
        hours = diff.seconds // 3600

        await message.answer(
            f"✅ <b>Tekshirib ko'ring:</b>\n\n"
            f"🚀 Boshlanish: <b>{start_dt.strftime('%d %B %Y, soat %H:%M')}</b>\n"
            f"🏁 Tugash: <b>{end_dt.strftime('%d %B %Y, soat %H:%M')}</b>\n"
            f"⏳ Davomiyligi: <b>{days} kun {hours} soat</b>\n\n"
            f"Tasdiqlaysizmi?",
            parse_mode='HTML',
            reply_markup=_confirm_start_kb()
        )
    except ValueError:
        await message.answer(
            "❌ Format noto'g'ri!\n"
            "To'g'ri misol: <code>02.02.2025 20:00</code>",
            parse_mode='HTML'
        )


def _confirm_start_kb():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Ha, boshlash", callback_data="confirm:start_giveaway")
    kb.button(text="❌ Bekor", callback_data="cancel_setup")
    kb.adjust(2)
    return kb.as_markup()


@router.callback_query(F.data == "confirm:start_giveaway")
async def confirm_start_giveaway(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    start_dt = data['started_at']
    end_dt = data['ends_at']
    await state.clear()

    # UTC ga o'tkazish (Toshkent UTC+5)
    from datetime import timedelta
    start_utc = start_dt - timedelta(hours=5)
    end_utc = end_dt - timedelta(hours=5)

    await db.start_giveaway(start_utc, end_utc)

    await callback.message.edit_text(
        f"🎉 <b>Give Away boshlandi!</b>\n\n"
        f"🚀 Boshlanish: {start_dt.strftime('%d.%m.%Y %H:%M')}\n"
        f"🏁 Tugash: {end_dt.strftime('%d.%m.%Y %H:%M')}",
        parse_mode='HTML'
    )

    # Guruhga e'lon
    try:
        await bot.send_message(
            GROUP_ID,
            f"🎉 <b>GIVE AWAY BOSHLANDI!</b>\n\n"
            f"🏁 Tugash: <b>{end_dt.strftime('%d %B %Y, soat %H:%M')}</b>\n\n"
            f"🏆 Top 3 sovrin oladi!\n"
            f"🎲 Random sovg'alar ham bor!\n\n"
            f"📌 Qatnashish uchun guruhga odam qo'shing!\n"
            f"🤖 Bot: @give_mebot",
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Guruhga xabar yuborib bo'lmadi: {e}")


@router.callback_query(F.data == "cancel_setup")
async def cancel_setup(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")


# ─── GIVE AWAY TUGATISH ──────────────────────────────────────

@router.message(F.text == "⛔ Tugatish")
async def end_giveaway_cmd(message: Message):
    gw = await db.get_giveaway()
    if not gw or not gw['is_active']:
        await message.answer("ℹ️ Hozirda faol give away yo'q.")
        return
    await message.answer(
        "⚠️ <b>Give awayni vaqtidan oldin tugatmoqchimisiz?</b>\n\n"
        "G'oliblar hoziroq e'lon qilinadi!",
        parse_mode='HTML',
        reply_markup=end_giveaway_confirm()
    )


@router.callback_query(F.data == "confirm:end_giveaway")
async def confirm_end_giveaway(callback: CallbackQuery, bot: Bot):
    await callback.message.edit_text("⏳ G'oliblar aniqlanmoqda...")
    await announce_winners(bot)


# ─── G'OLIBLARNI E'LON QILISH ────────────────────────────────

async def announce_winners(bot: Bot):
    """Asosiy g'oliblarni aniqlash va e'lon qilish"""
    await db.finish_giveaway()

    won_ids = []

    # 1. Top 3
    top = await db.get_top_winners(TOP_WINNERS_COUNT)
    top_text = ["🏆 <b>GIVE AWAY YAKUNLANDI!</b>\n\n🥇 <b>ASOSIY G'OLIBLAR:</b>\n"]
    for i, (uid, username, full_name, cnt) in enumerate(top, 1):
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        top_text.append(f"{medals[i]} {user_mention(full_name, uid)}")
        await db.save_winner(uid, 'top', rank=i)
        won_ids.append(uid)

        # Zaxira g'oliblar
        zaxira = await db.get_top_winners(TOP_WINNERS_COUNT + BACKUP_WINNERS_COUNT)
        for j, (buid, _, bname, _) in enumerate(zaxira[TOP_WINNERS_COUNT:], 1):
            await db.save_winner(buid, 'top_backup', rank=i + j, backup=True)

    # 2. Top 4-10 dan random
    pool_winners = await db.get_random_pool_winners(
        TOP_RANDOM_POOL_START, TOP_RANDOM_POOL_END, TOP_RANDOM_COUNT, won_ids
    )
    random_text = ["\n\n🎲 <b>RANDOM SOVG'A (Top 4-10):</b>\n"]
    for uid, username, full_name, cnt in pool_winners:
        random_text.append(f"🎁 {user_mention(full_name, uid)}")
        await db.save_winner(uid, 'pool_random')
        won_ids.append(uid)

    # 3. Global random
    global_winner = await db.get_global_random_winner(won_ids, MIN_REFERRALS_FOR_RANDOM)
    global_text = ["\n\n🌟 <b>UMUMIY RANDOM G'OLIB:</b>\n"]
    if global_winner:
        uid, username, full_name, cnt = global_winner
        global_text.append(f"🌟 {user_mention(full_name, uid)}")
        await db.save_winner(uid, 'global_random')
        won_ids.append(uid)
    else:
        global_text.append("Hech kim shart bajarмadi")

    full_text = (
        "".join(top_text) +
        "".join(random_text) +
        "".join(global_text) +
        "\n\n🎊 Tabriklaymiz!"
    )

    # Guruhga e'lon
    try:
        await bot.send_message(GROUP_ID, full_text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Guruhga e'lon yuborib bo'lmadi: {e}")

    # G'oliblarga DM
    winners = await db.get_winners()
    for uid, prize_type, rank, username, full_name in winners:
        prize_names = {
            'top': f"🥇 {rank}-o'rin sovrin",
            'pool_random': "🎲 Random sovg'a (top 4-10)",
            'global_random': "🌟 Umumiy random sovg'a"
        }
        try:
            await bot.send_message(
                uid,
                f"🎉 <b>Tabriklaymiz!</b>\n\n"
                f"Siz <b>Give Away</b> da <b>{prize_names.get(prize_type, 'sovrin')}</b>ni yutdingiz!\n\n"
                f"Admin tez orada siz bilan bog'lanadi. 📩",
                parse_mode='HTML'
            )
        except Exception:
            pass

    # Adminlarga g'oliblar ro'yxati va kontaktlar
    admin_text = ["📋 <b>G'OLIBLAR KONTAKTLARI:</b>\n"]
    for uid, prize_type, rank, username, full_name in winners:
        uname = f"@{username}" if username else "username yo'q"
        admin_text.append(
            f"\n{'🥇🥈🥉'[rank-1] if rank and rank <= 3 else '🎁'} {full_name}\n"
            f"   {uname} | ID: <code>{uid}</code>"
        )

    await send_to_admins(
        bot,
        "".join(admin_text),
        parse_mode='HTML'
    )

    # Har bir g'olib uchun alohida "yozish" tugmasi
    for uid, prize_type, rank, username, full_name in winners:
        await send_to_admins(
            bot,
            f"👤 {user_mention(full_name, uid)} ({prize_type})",
            parse_mode='HTML'
        )


# ─── REKLAMA ─────────────────────────────────────────────────

@router.message(F.text == "📢 Reklama")
async def broadcast_start(message: Message, state: FSMContext):
    await state.set_state(BroadcastState.waiting_text)
    await message.answer(
        "✍️ Reklama xabarini yuboring (matn, rasm yoki video bo'lishi mumkin):\n\n"
        "Bekor qilish: /cancel"
    )


@router.message(BroadcastState.waiting_text)
async def broadcast_send(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    users = await db.get_all_active_users()
    success = 0
    failed = 0
    status_msg = await message.answer(f"📢 Yuborilmoqda... (0/{len(users)})")

    for i, user_id in enumerate(users):
        try:
            await message.copy_to(user_id)
            success += 1
        except Exception:
            failed += 1
            await db.set_bot_blocked(user_id, True)

        if i % 50 == 0:
            try:
                await status_msg.edit_text(f"📢 Yuborilmoqda... ({i}/{len(users)})")
            except Exception:
                pass

    await status_msg.edit_text(
        f"✅ Reklama yakunlandi!\n"
        f"✔️ Muvaffaqiyatli: {success}\n"
        f"❌ Yuborilmadi: {failed}"
    )


# ─── ADMIN STATISTIKA ────────────────────────────────────────

@router.message(F.text.in_(["📈 Admin statistika", "📈 Админ статистика"]))
async def admin_stats(message: Message):
    total_users = await db.get_total_users()
    total_refs = await db.get_total_referrals()
    today_joins = await db.get_today_joins()
    top = await db.get_leaderboard(3)
    gw = await db.get_giveaway()

    gw_status = "✅ Faol" if gw and gw['is_active'] else "❌ Faol emas"
    time_left = "—"
    if gw and gw['is_active'] and gw['ends_at']:
        ends = datetime.fromisoformat(str(gw['ends_at'])).replace(tzinfo=timezone.utc)
        time_left = time_remaining(ends)

    top_text = ""
    for i, (uid, username, full_name, cnt) in enumerate(top, 1):
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        top_text += f"\n{medals[i]} {full_name} — {cnt} ta"

    await message.answer(
        f"📈 <b>ADMIN STATISTIKA</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"🔗 Jami referrallar: <b>{total_refs}</b>\n"
        f"📅 Bugun qo'shildi: <b>{today_joins}</b>\n\n"
        f"🎮 Give Away: {gw_status}\n"
        f"⏰ Tugashiga: <b>{time_left}</b>\n\n"
        f"🏆 Hozirgi Top 3:{top_text}",
        parse_mode='HTML'
    )


# ─── G'OLIBLAR ───────────────────────────────────────────────

@router.message(F.text == "🏆 G'oliblar")
async def show_winners(message: Message):
    winners = await db.get_winners()
    if not winners:
        await message.answer("ℹ️ Hali g'oliblar aniqlanmagan.")
        return

    text = ["🏆 <b>G'OLIBLAR:</b>\n"]
    for uid, prize_type, rank, username, full_name in winners:
        uname = f"@{username}" if username else "username yo'q"
        prize_names = {
            'top': f"{rank}-o'rin",
            'pool_random': "Random (top 4-10)",
            'global_random': "Global random"
        }
        text.append(f"\n👤 {full_name} ({uname})\n   {prize_names.get(prize_type, '?')}")

    await message.answer("\n".join(text), parse_mode='HTML')

    # Har bir g'olib uchun kontakt tugmasi
    for uid, prize_type, rank, username, full_name in winners:
        await message.answer(
            f"👤 {user_mention(full_name, uid)}",
            parse_mode='HTML',
            reply_markup=winner_contact_keyboard(uid)
        )


# ─── BACKUP ──────────────────────────────────────────────────

@router.message(F.text == "💾 Backup olish")
async def manual_backup(message: Message, bot: Bot):
    await send_backup(bot, message.from_user.id)


async def send_backup(bot: Bot, chat_id: int = None):
    from config import ADMIN_IDS
    users_data, referrals_data = await db.export_all_data()
    csv_bytes = await generate_csv(users_data, referrals_data)

    now = datetime.now()
    filename = f"backup_{now.strftime('%Y%m%d_%H%M')}.csv"

    targets = [chat_id] if chat_id else ADMIN_IDS
    for admin_id in targets:
        try:
            await bot.send_document(
                admin_id,
                BufferedInputFile(csv_bytes.getvalue(), filename=filename),
                caption=(
                    f"💾 <b>Ma'lumotlar zaxirasi</b>\n"
                    f"📅 {now.strftime('%d.%m.%Y %H:%M')}\n"
                    f"👥 Foydalanuvchilar: {len(users_data)}\n"
                    f"🔗 Referrallar: {len(referrals_data)}"
                ),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Backup yuborib bo'lmadi {admin_id}: {e}")


# ─── BAN ─────────────────────────────────────────────────────

@router.message(F.text == "🚫 Ban")
async def ban_start(message: Message, state: FSMContext):
    await state.set_state(BanState.waiting_user)
    await message.answer(
        "🚫 Ban qilish uchun username yoki ID yuboring:\n"
        "Misol: <code>@username</code> yoki <code>123456789</code>\n\n"
        "Banni ochish uchun: <code>unban @username</code>",
        parse_mode='HTML'
    )


@router.message(BanState.waiting_user)
async def ban_user(message: Message, state: FSMContext):
    await state.clear()
    text = message.text.strip()
    unban = text.lower().startswith('unban')
    if unban:
        text = text[5:].strip().lstrip('@')
    else:
        text = text.lstrip('@')

    # Foydalanuvchini topish
    async with __import__('aiosqlite').connect(__import__('config').DB_FILE) as conn:
        if text.lstrip('-').isdigit():
            async with conn.execute("SELECT user_id, full_name FROM users WHERE user_id=?", (int(text),)) as c:
                row = await c.fetchone()
        else:
            async with conn.execute("SELECT user_id, full_name FROM users WHERE username=?", (text,)) as c:
                row = await c.fetchone()

    if not row:
        await message.answer("❌ Foydalanuvchi topilmadi.")
        return

    uid, full_name = row
    await db.blacklist_user(uid, not unban)
    action = "bandi ochildi ✅" if unban else "ban qilindi 🚫"
    await message.answer(f"👤 {full_name} ({uid}) — {action}")


# ─── CANCEL ──────────────────────────────────────────────────

@router.message(F.text == "/cancel")
async def cancel_admin(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Bekor qilindi.")
