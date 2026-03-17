import logging
from aiogram import Router, Bot, F
from aiogram.types import Message
from aiogram.filters import Command

import database as db
from config import ADMIN_IDS
from utils import user_mention

logger = logging.getLogger(__name__)
router = Router()

SUPPORT_TAG = "📞 Admin bilan bog'lanish"
SUPPORT_TAG_RU = "📞 Связаться с админом"


@router.message(F.text.in_([SUPPORT_TAG, SUPPORT_TAG_RU]))
async def contact_admin(message: Message):
    u = await db.get_user(message.from_user.id)
    lang = u['lang'] if u else 'uz'
    if lang == 'uz':
        await message.answer(
            "✍️ Adminga yozmoqchi bo'lgan xabaringizni yuboring.\n"
            "Bitta xabar yuboring — admin imkon topib javob beradi."
        )
    else:
        await message.answer(
            "✍️ Напишите ваш вопрос или сообщение для администратора.\n"
            "Отправьте одно сообщение — админ ответит при первой возможности."
        )
    # FSM ishlatmasdan — keyingi xabar support sifatida qabul qilinadi
    # Buning uchun alohida flag saqlaymiz (oddiy yechim)
    await db.set_user_lang(message.from_user.id, lang + "_support")


@router.message(lambda m: m.from_user.id not in ADMIN_IDS and not m.text.startswith('/'))
async def forward_to_admin(message: Message, bot: Bot):
    u = await db.get_user(message.from_user.id)
    lang_raw = u['lang'] if u else 'uz'

    if not lang_raw.endswith('_support'):
        return

    # Haqiqiy tilni tiklash
    real_lang = lang_raw.replace('_support', '')
    await db.set_user_lang(message.from_user.id, real_lang)

    user = message.from_user
    header = (
        f"📩 <b>Yangi xabar</b>\n"
        f"👤 {user_mention(user.full_name, user.id)}\n"
        f"🆔 <code>{user.id}</code>\n"
        f"{'@' + user.username if user.username else 'username yoq'}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
    )

    # Barcha adminlarga yuborish
    for admin_id in ADMIN_IDS:
        try:
            sent = await bot.send_message(admin_id, header, parse_mode='HTML')
            # Xabarni forward qilish
            fwd = await message.forward(admin_id)
            # Ticket saqlash (oxirgi admin msg ID bilan)
            await db.update_ticket_admin_msg(user.id, message.message_id, fwd.message_id)
        except Exception as e:
            logger.error(f"Adminga yuborib bo'lmadi {admin_id}: {e}")

    await db.save_ticket(user.id, message.message_id)

    # Foydalanuvchiga tasdiqlash
    if real_lang == 'uz':
        await message.answer("✅ Xabaringiz adminga yetkazildi. Tez orada javob berishadi.")
    else:
        await message.answer("✅ Ваше сообщение отправлено администратору. Скоро ответят.")


@router.message(lambda m: m.from_user.id in ADMIN_IDS and m.reply_to_message is not None)
async def admin_reply(message: Message, bot: Bot):
    """Admin forward qilingan xabarga reply qilganda foydalanuvchiga yetkazish"""
    replied = message.reply_to_message
    if not replied:
        return

    # Ticket ni topish
    ticket = await db.get_ticket_by_admin_msg(replied.message_id)
    if not ticket:
        return

    user_id = ticket[0]
    u = await db.get_user(user_id)
    lang = u['lang'] if u else 'uz'

    prefix = "👨‍💼 <b>Admin javobi:</b>\n\n" if lang == 'uz' else "👨‍💼 <b>Ответ администратора:</b>\n\n"

    try:
        await bot.send_message(
            user_id,
            prefix + message.text,
            parse_mode='HTML'
        )
        await message.reply("✅ Javob foydalanuvchiga yetkazildi.")
    except Exception as e:
        await message.reply(f"❌ Yuborib bo'lmadi: {e}")
