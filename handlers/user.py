import math
import logging
from datetime import datetime, timezone
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from config import (
    BOT_USERNAME, GROUP_ID, CHANNEL_URL, CHECK_CHANNEL,
    MIN_REFERRALS_FOR_RANDOM, MIN_ACCOUNT_AGE_DAYS,
    DAILY_GOAL, TOP_WINNERS_COUNT, ADMIN_IDS
)
from keyboards import (
    user_menu, admin_menu, lang_keyboard, join_keyboard,
    confirm_keyboard, pagination_keyboard, transfer_confirm
)
from utils import (
    check_membership, user_mention, time_remaining,
    format_dt, build_leaderboard_text, build_motivational_text, now_local
)

logger = logging.getLogger(__name__)
router = Router()

TEXTS = {
    'uz': {
        'welcome': (
            "👋 Assalomu alaykum, <b>{name}</b>!\n\n"
            "🎉 <b>TO'RAQO'RG'ON _ NATYAJNOY</b> guruhining rasmiy Give Away botiga xush kelibsiz!\n\n"
            "📌 <b>Qanday ishlaydi:</b>\n"
            "1️⃣ Guruhga a'zo bo'ling\n"
            "2️⃣ Shaxsiy linkingizni oling — <b>/mylink</b>\n"
            "3️⃣ Do'stlaringizni taklif qiling\n"
            "4️⃣ Top 3 ga kiring va <b>sovg'a yuting!</b> 🏆\n\n"
            "Boshlash uchun pastdagi tugmalardan foydalaning 👇"
        ),
        'already': "👋 Xush kelibsiz yana, <b>{name}</b>!",
        'join_first': "⚠️ Davom etish uchun avval guruhga a'zo bo'ling:",
        'joined': "✅ Zo'r! Ro'yxatdan o'tdingiz. Endi linkingizni oling:",
        'not_joined': "❌ A'zolik aniqlanmadi. Guruhga qo'shiling va qayta tekshiring.",
        'no_giveaway': "ℹ️ Hozirda faol give away yo'q.",
        'blacklisted': "🚫 Siz konkursda qatnashishdan mahrum etilgansiz.",
    },
    'ru': {
        'welcome': (
            "👋 Привет, <b>{name}</b>!\n\n"
            "🎉 Добро пожаловать в официальный Give Away бот группы <b>TO'RAQO'RG'ON _ NATYAJNOY</b>!\n\n"
            "📌 <b>Как это работает:</b>\n"
            "1️⃣ Вступите в группу\n"
            "2️⃣ Получите личную ссылку — <b>/mylink</b>\n"
            "3️⃣ Приглашайте друзей\n"
            "4️⃣ Войдите в топ 3 и <b>выиграйте приз!</b> 🏆\n\n"
            "Используйте кнопки ниже 👇"
        ),
        'already': "👋 С возвращением, <b>{name}</b>!",
        'join_first': "⚠️ Сначала вступите в группу:",
        'joined': "✅ Отлично! Вы зарегистрированы. Теперь получите вашу ссылку:",
        'not_joined': "❌ Членство не обнаружено. Вступите в группу и проверьте снова.",
        'no_giveaway': "ℹ️ Сейчас нет активного конкурса.",
        'blacklisted': "🚫 Вы отстранены от участия в конкурсе.",
    }
}


class TransferState(StatesGroup):
    waiting_target = State()


# ─── START ───────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user = message.from_user
    if await db.is_blacklisted(user.id):
        await message.answer("🚫 Siz konkursda qatnashishdan mahrum etilgansiz.")
        return

    is_new = await db.register_user(user.id, user.username, user.full_name)
    u = await db.get_user(user.id)
    lang = u['lang'] if u else 'uz'
    t = TEXTS[lang]

    is_admin = user.id in ADMIN_IDS

    if is_new:
        # A'zolikni tekshirish
        is_member = await check_membership(bot, user.id)
        if not is_member:
            group_info = await bot.get_chat(GROUP_ID)
            invite = group_info.invite_link or CHANNEL_URL
            await message.answer(
                t['join_first'],
                reply_markup=join_keyboard(invite, CHANNEL_URL if CHECK_CHANNEL else None)
            )
            return
        await message.answer(
            t['welcome'].format(name=user.full_name),
            reply_markup=admin_menu() if is_admin else user_menu(lang),
            parse_mode='HTML'
        )
    else:
        await message.answer(
            t['already'].format(name=user.full_name),
            reply_markup=admin_menu() if is_admin else user_menu(lang),
            parse_mode='HTML'
        )


@router.callback_query(F.data == "check_membership")
async def check_join(callback: CallbackQuery, bot: Bot):
    user = callback.from_user
    u = await db.get_user(user.id)
    lang = u['lang'] if u else 'uz'
    t = TEXTS[lang]
    is_member = await check_membership(bot, user.id)
    if is_member:
        is_admin = user.id in ADMIN_IDS
        await callback.message.edit_text(t['joined'], parse_mode='HTML')
        await callback.message.answer(
            "👇 Menyudan foydalaning:",
            reply_markup=admin_menu() if is_admin else user_menu(lang)
        )
    else:
        await callback.answer(t['not_joined'], show_alert=True)


# ─── TIL ─────────────────────────────────────────────────────

@router.message(F.text.in_(["🌐 Til", "🌐 Язык"]))
async def choose_lang(message: Message):
    await message.answer("Tilni tanlang / Выберите язык:", reply_markup=lang_keyboard())


@router.callback_query(F.data.startswith("lang:"))
async def set_lang(callback: CallbackQuery):
    lang = callback.data.split(":")[1]
    await db.set_user_lang(callback.from_user.id, lang)
    u = await db.get_user(callback.from_user.id)
    is_admin = callback.from_user.id in ADMIN_IDS
    txt = "✅ Til o'zgartirildi!" if lang == 'uz' else "✅ Язык изменён!"
    await callback.message.edit_text(txt)
    await callback.message.answer(
        "👇",
        reply_markup=admin_menu() if is_admin else user_menu(lang)
    )


# ─── MY LINK ─────────────────────────────────────────────────

@router.message(F.text.in_(["🔗 Linkimni olish", "🔗 Получить ссылку"]))
async def my_link(message: Message, bot: Bot):
    user = message.from_user
    u = await db.get_user(user.id)
    lang = u['lang'] if u else 'uz'

    if await db.is_blacklisted(user.id):
        await message.answer(TEXTS[lang]['blacklisted'])
        return

    # Mavjud linkni tekshirish
    existing = await db.get_invite_link(user.id)
    if existing:
        link = existing
    else:
        # Yangi unique invite link yaratish
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
                "❌ Link yaratishda xato. Bot guruhda admin ekanligini tekshiring."
                if lang == 'uz' else
                "❌ Ошибка создания ссылки. Проверьте, что бот является администратором группы."
            )
            return

    ref_count = await db.get_referral_count(user.id)
    gw = await db.get_giveaway()
    time_left = time_remaining(gw['ends_at']) if gw and gw['is_active'] and gw['ends_at'] else "—"

    if lang == 'uz':
        text = (
            f"🔗 <b>Sizning shaxsiy taklif linkingiz:</b>\n\n"
            f"<code>{link}</code>\n\n"
            f"👥 Qo'shgan odamlar: <b>{ref_count} ta</b>\n"
            f"⏰ Tugashiga: <b>{time_left}</b>\n\n"
            f"💡 Ushbu linkni do'stlaringizga yuboring — kim shu link orqali kirsa, "
            f"siz ball olasiz!"
        )
    else:
        text = (
            f"🔗 <b>Ваша личная реферальная ссылка:</b>\n\n"
            f"<code>{link}</code>\n\n"
            f"👥 Приглашено: <b>{ref_count} чел.</b>\n"
            f"⏰ До конца: <b>{time_left}</b>\n\n"
            f"💡 Отправьте эту ссылку друзьям — когда они вступят по ней, вы получите балл!"
        )
    await message.answer(text, parse_mode='HTML')


# ─── STATISTIKA ──────────────────────────────────────────────

@router.message(F.text.in_(["📊 Statistika", "📊 Статистика"]))
async def my_stats(message: Message):
    user = message.from_user
    u = await db.get_user(user.id)
    lang = u['lang'] if u else 'uz'

    ref_count = await db.get_referral_count(user.id)
    rank = await db.get_user_rank(user.id)
    gw = await db.get_giveaway()

    random_status = ""
    if ref_count >= MIN_REFERRALS_FOR_RANDOM:
        random_status = "✅ Random sovg'a uchun huquqingiz bor!" if lang == 'uz' else "✅ Вы участвуете в случайном розыгрыше!"
    else:
        need = MIN_REFERRALS_FOR_RANDOM - ref_count
        random_status = (
            f"🎲 Random sovg'aga yana <b>{need} ta</b> odam yetishmayapti!"
            if lang == 'uz' else
            f"🎲 До розыгрыша не хватает ещё <b>{need} чел.</b>"
        )

    transfer_done = u['transfer_done'] if u else 0
    transfer_status = (
        ("✅ Balingizni berdingiz (bir martalik)" if lang == 'uz' else "✅ Вы передали баллы (однократно)")
        if transfer_done else
        ("🔄 Balingizni bir marta boshqaga berishingiz mumkin" if lang == 'uz' else "🔄 Вы можете передать баллы один раз")
    )

    time_left = "—"
    if gw and gw['is_active'] and gw['ends_at']:
        ends = datetime.fromisoformat(str(gw['ends_at'])).replace(tzinfo=timezone.utc)
        time_left = time_remaining(ends)

    if lang == 'uz':
        text = (
            f"📊 <b>Sizning statistikangiz</b>\n\n"
            f"👤 Ism: {user_mention(user.full_name, user.id)}\n"
            f"👥 Qo'shgan odamlar: <b>{ref_count} ta</b>\n"
            f"🏆 O'rningiz: <b>{rank}-o'rin</b>\n"
            f"⏰ Tugashiga: <b>{time_left}</b>\n\n"
            f"{random_status}\n"
            f"{transfer_status}\n\n"
            f"🎯 Bugungi maqsad: <b>{DAILY_GOAL} ta odam</b> qo'shing"
        )
    else:
        text = (
            f"📊 <b>Ваша статистика</b>\n\n"
            f"👤 Имя: {user_mention(user.full_name, user.id)}\n"
            f"👥 Приглашено: <b>{ref_count} чел.</b>\n"
            f"🏆 Место: <b>{rank}</b>\n"
            f"⏰ До конца: <b>{time_left}</b>\n\n"
            f"{random_status}\n"
            f"{transfer_status}\n\n"
            f"🎯 Дневная цель: пригласить <b>{DAILY_GOAL} чел.</b>"
        )
    await message.answer(text, parse_mode='HTML')


# ─── ACHKOLAR ────────────────────────────────────────────────

@router.message(F.text.in_(["👥 Achkolarim", "👥 Мои рефералы"]))
async def my_invites(message: Message):
    user = message.from_user
    u = await db.get_user(user.id)
    lang = u['lang'] if u else 'uz'
    await show_invites_page(message, user.id, lang, page=1)


async def show_invites_page(message: Message, user_id: int, lang: str, page: int):
    per_page = 50
    offset = (page - 1) * per_page
    rows = await db.get_referrals_list(user_id, offset=offset, limit=per_page)
    total = await db.get_referral_count(user_id)
    total_pages = max(1, math.ceil(total / per_page))

    if not rows:
        text = (
            "👥 Hali hech kimni qo'shmadingiz.\n\n"
            "🔗 /mylink buyrug'i bilan linkingizni oling va tarqating!"
            if lang == 'uz' else
            "👥 Вы ещё никого не пригласили.\n\n"
            "🔗 Получите ссылку командой /mylink и делитесь ею!"
        )
        await message.answer(text)
        return

    lines = [f"👥 <b>Sizning achkolaringiz</b> ({total} ta)\n" if lang == 'uz'
             else f"👥 <b>Ваши рефералы</b> ({total} чел.)\n"]
    for i, (full_name, username, joined_at) in enumerate(rows, offset + 1):
        uname = f"@{username}" if username else "username yo'q"
        lines.append(f"{i}. {full_name} — {uname}")

    kb = pagination_keyboard(page, total_pages, f"invites:{user_id}") if total_pages > 1 else None
    await message.answer("\n".join(lines), parse_mode='HTML', reply_markup=kb)


@router.callback_query(F.data.startswith("invites:"))
async def invites_page(callback: CallbackQuery):
    parts = callback.data.split(":")
    user_id = int(parts[1])
    page = int(parts[2])
    u = await db.get_user(callback.from_user.id)
    lang = u['lang'] if u else 'uz'
    await callback.message.delete()
    await show_invites_page(callback.message, user_id, lang, page)
    await callback.answer()


# ─── TOP 10 ──────────────────────────────────────────────────

@router.message(F.text.in_(["🏆 Top 10", "🏅 Top 10"]))
async def top10(message: Message):
    u = await db.get_user(message.from_user.id)
    lang = u['lang'] if u else 'uz'
    rows = await db.get_leaderboard(10)
    text = build_leaderboard_text(rows, lang, show_counts=False)
    await message.answer(text, parse_mode='HTML')


# ─── BAL BERISH ──────────────────────────────────────────────

@router.message(F.text.in_(["🎁 Bal berish", "🎁 Передать баллы"]))
async def give_points_start(message: Message, state: FSMContext):
    user = message.from_user
    u = await db.get_user(user.id)
    lang = u['lang'] if u else 'uz'

    if u and u['transfer_done']:
        await message.answer(
            "❌ Siz allaqachon balingizni berdingiz. Bu bir martalik imkoniyat."
            if lang == 'uz' else
            "❌ Вы уже передали свои баллы. Это можно сделать только один раз."
        )
        return

    ref_count = await db.get_referral_count(user.id)
    if ref_count == 0:
        await message.answer(
            "❌ Sizda beradigan ball yo'q."
            if lang == 'uz' else
            "❌ У вас нет баллов для передачи."
        )
        return

    await state.set_state(TransferState.waiting_target)
    await state.update_data(ref_count=ref_count, lang=lang)

    await message.answer(
        f"👥 Sizda <b>{ref_count} ta</b> ball bor.\n\n"
        f"Kimga berishni xohlaysiz? Username yoki ID yuboring:\n"
        f"Misol: <code>@username</code> yoki <code>@sardor_uz</code>"
        if lang == 'uz' else
        f"👥 У вас <b>{ref_count}</b> баллов.\n\n"
        f"Кому передать? Отправьте username или ID:\n"
        f"Пример: <code>@username</code>",
        parse_mode='HTML'
    )


@router.message(TransferState.waiting_target)
async def give_points_target(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = data.get('lang', 'uz')
    ref_count = data.get('ref_count', 0)
    text = message.text.strip().lstrip('@')

    # Foydalanuvchini topish
    target = None
    async for uid in _find_user(text):
        target = uid
        break

    if not target:
        await message.answer(
            "❌ Foydalanuvchi topilmadi. Username yoki ID to'g'ri ekanligini tekshiring.\n"
            "Eslatma: u avval botga /start bosgan bo'lishi kerak."
            if lang == 'uz' else
            "❌ Пользователь не найден. Убедитесь, что он запускал бота."
        )
        return

    if target['user_id'] == message.from_user.id:
        await message.answer("❌ O'zingizga bera olmaysiz." if lang == 'uz' else "❌ Нельзя передать самому себе.")
        return

    await state.update_data(target_id=target['user_id'], target_name=target['full_name'])

    await message.answer(
        f"⚠️ Tasdiqlaysizmi?\n\n"
        f"<b>{ref_count} ta</b> ball → {user_mention(target['full_name'], target['user_id'])}\n\n"
        f"⚠️ Bu <b>bir martalik</b> amal. Qaytarib bo'lmaydi!"
        if lang == 'uz' else
        f"⚠️ Подтвердите:\n\n"
        f"<b>{ref_count}</b> баллов → {user_mention(target['full_name'], target['user_id'])}\n\n"
        f"⚠️ Это действие <b>необратимо!</b>",
        parse_mode='HTML',
        reply_markup=transfer_confirm(target['full_name'], ref_count, lang)
    )


async def _find_user(text: str):
    import database as db
    # username yoki ID bo'yicha qidirish
    async with __import__('aiosqlite').connect(__import__('config').DB_FILE) as conn:
        if text.lstrip('-').isdigit():
            async with conn.execute("SELECT user_id, full_name, username FROM users WHERE user_id=?", (int(text),)) as c:
                row = await c.fetchone()
        else:
            async with conn.execute("SELECT user_id, full_name, username FROM users WHERE username=?", (text,)) as c:
                row = await c.fetchone()
    if row:
        yield {'user_id': row[0], 'full_name': row[1], 'username': row[2]}


@router.callback_query(F.data == "confirm:transfer")
async def confirm_transfer(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = data.get('lang', 'uz')
    target_id = data.get('target_id')
    target_name = data.get('target_name')

    success = await db.transfer_points(callback.from_user.id, target_id)
    await state.clear()

    if success:
        ref_count = await db.get_referral_count(target_id)
        await callback.message.edit_text(
            f"✅ Ball muvaffaqiyatli o'tkazildi!\n"
            f"→ {target_name} endi <b>{ref_count} ta</b> ballga ega."
            if lang == 'uz' else
            f"✅ Баллы успешно переданы!\n"
            f"→ У {target_name} теперь <b>{ref_count}</b> баллов.",
            parse_mode='HTML'
        )
        # Qabul qiluvchiga xabar
        try:
            await bot.send_message(
                target_id,
                f"🎁 {user_mention(callback.from_user.full_name, callback.from_user.id)} sizga "
                f"<b>{data.get('ref_count')} ta</b> ball o'tkazdi!\n"
                f"Endi sizda <b>{ref_count} ta</b> ball bor. 🏆"
                if lang == 'uz' else
                f"🎁 {user_mention(callback.from_user.full_name, callback.from_user.id)} передал вам "
                f"<b>{data.get('ref_count')}</b> баллов!\n"
                f"Теперь у вас <b>{ref_count}</b> баллов. 🏆",
                parse_mode='HTML'
            )
        except Exception:
            pass
    else:
        await callback.message.edit_text(
            "❌ Transfer amalga oshmadi. Allaqachon bergan bo'lishingiz mumkin."
            if lang == 'uz' else
            "❌ Не удалось передать баллы. Возможно, вы уже передавали их."
        )


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi." if True else "❌ Отменено.")
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()
