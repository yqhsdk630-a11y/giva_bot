import logging
from aiogram import Router, Bot, F
from aiogram.types import Message

import database as db
from config import ADMIN_IDS
from utils import user_mention

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.text == "📞 Admin bilan bog'lanish")
async def contact_admin(message: Message):
    await message.answer(
        "✍️ Adminga yozmoqchi bo'lgan xabaringizni yuboring.\n"
        "Bitta xabar yuboring — admin imkon topib javob beradi."
    )
    await db.set_support_mode(message.from_user.id, True)


@router.message(
    F.text,
    lambda m: m.from_user.id not in ADMIN_IDS and not m.text.startswith('/')
)
async def forward_to_admin(message: Message, bot: Bot):
    user_id = message.from_user.id

    in_support = await db.get_support_mode(user_id)
    if not in_support:
        return

    await db.set_support_mode(user_id, False)

    user = message.from_user
    header = (
        f"📩 <b>Yangi xabar foydalanuvchidan</b>\n"
        f"👤 {user_mention(user.full_name, user.id)}\n"
        f"🆔 <code>{user.id}</code>\n"
        f"{'@' + user.username if user.username else 'username yoq'}\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"{message.text}"
    )

    saved_msg_id = None
    for admin_id in ADMIN_IDS:
        try:
            sent = await bot.send_message(admin_id, header, parse_mode='HTML')
            if saved_msg_id is None:
                saved_msg_id = sent.message_id
                await db.save_ticket(user_id, message.message_id, sent.message_id, admin_id)
        except Exception as e:
            logger.error(f"Adminga yuborib bolmadi {admin_id}: {e}")

    await message.answer("✅ Xabaringiz adminga yetkazildi. Tez orada javob berishadi.")


@router.message(
    F.reply_to_message,
    lambda m: m.from_user.id in ADMIN_IDS
)
async def admin_reply(message: Message, bot: Bot):
    replied = message.reply_to_message
    if not replied:
        return

    ticket = await db.get_ticket_by_admin_msg(replied.message_id)
    if not ticket:
        return

    user_id = ticket[0]

    try:
        await bot.send_message(
            user_id,
            f"👨‍💼 <b>Admin javobi:</b>\n\n{message.text}",
            parse_mode='HTML'
        )
        await message.reply("✅ Javob foydalanuvchiga yetkazildi.")
    except Exception as e:
        await message.reply(f"❌ Yuborib bolmadi: {e}")
