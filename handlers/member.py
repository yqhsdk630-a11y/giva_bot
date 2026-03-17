import logging
from datetime import datetime, timezone, timedelta
from aiogram import Router, Bot, F
from aiogram.types import ChatMemberUpdated

import database as db
from config import GROUP_ID, ADMIN_IDS, SUSPICIOUS_REFERRAL_LIMIT, MIN_ACCOUNT_AGE_DAYS
from utils import send_to_admins, user_mention

logger = logging.getLogger(__name__)
router = Router()


@router.chat_member(F.chat.id == GROUP_ID)
async def on_chat_member(event: ChatMemberUpdated, bot: Bot):
    new_status = event.new_chat_member.status
    old_status = event.old_chat_member.status

    user = event.new_chat_member.user
    if user.is_bot:
        return

    # Guruhga qo'shildi
    if new_status in ('member', 'administrator') and old_status in ('left', 'kicked', 'restricted'):
        await handle_join(event, bot)

    # Guruhdan chiqdi
    elif new_status in ('left', 'kicked') and old_status in ('member', 'administrator', 'restricted'):
        await db.set_bot_blocked(user.id, False)  # member flag uchun alohida field kerak bo'lsa


async def handle_join(event: ChatMemberUpdated, bot: Bot):
    user = event.new_chat_member.user

    # Account yoshi tekshiruvi (anti-cheat)
    if user.id > 0:
        # Telegram ID dan taxminiy account yoshi (aniq emas, lekin ishlaydi)
        # Haqiqiy usul: foydalanuvchi bot bilan /start orqali kelganda tekshiriladi
        pass

    referrer_id = None

    # Invite link orqali kim taklif qilganini aniqlash
    if event.invite_link:
        link = event.invite_link.invite_link
        referrer_id = await db.get_user_id_by_link(link)

    if referrer_id and referrer_id != user.id:
        # Anti-cheat: referrer blacklistda emas
        if await db.is_blacklisted(referrer_id):
            return

        success = await db.add_referral(referrer_id, user.id)
        if success:
            ref_count = await db.get_referral_count(referrer_id)
            logger.info(f"Yangi referral: {referrer_id} → {user.id} (jami: {ref_count})")

            # Shubhali faollik tekshiruvi
            now = datetime.utcnow()
            date_str = now.strftime("%Y-%m-%d")
            hour_count = await db.get_hourly_referrals(referrer_id, now.hour, date_str)

            if hour_count >= SUSPICIOUS_REFERRAL_LIMIT:
                referrer = await db.get_user(referrer_id)
                name = referrer['full_name'] if referrer else str(referrer_id)
                await send_to_admins(
                    bot,
                    f"⚠️ <b>SHUBHALI FAOLLIK!</b>\n\n"
                    f"Foydalanuvchi: {user_mention(name, referrer_id)}\n"
                    f"1 soatda <b>{hour_count} ta</b> odam qo'shdi!\n\n"
                    f"Tekshirish tavsiya etiladi. /ban buyrug'i bilan bloklashingiz mumkin.",
                    parse_mode='HTML'
                )

            # Rekord tekshiruvi (eng ko'p bir kunda)
            # Kelajakda qo'shish mumkin

    # Foydalanuvchini DBga qo'shish (agar yo'q bo'lsa)
    await db.register_user(user.id, user.username, user.full_name)
