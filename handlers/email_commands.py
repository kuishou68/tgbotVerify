import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from outlook.register import run_registration_flow

logger = logging.getLogger(__name__)

async def email_register_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for /email_register command.
    Triggers the Outlook account registration automation in a background task.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"User {user.id} ({user.username}) triggered email registration.")

    # Send initial message
    status_msg = await update.message.reply_text(
        "🚀 Starting Outlook registration process...\n"
        "1. Launching browser (Headful mode).\n"
        "2. Filling details.\n"
        "3. You will need to solve the CAPTCHA manually.\n"
        "4. If the flow pauses on the birth date page, please select month/day manually and click Next.\n"
        "Please wait... (I will notify you when done)"
    )

    # Define the background task
    async def run_and_notify():
        try:
            # Run the automation
            success, result_msg, account = await run_registration_flow()
            
            status_emoji = "✅" if success else "⚠️"
            
            # Use escape to prevent markdown errors with random passwords/status
            email = account.get('email', 'N/A').replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')
            password = account.get('password', 'N/A').replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')
            safe_msg = result_msg.replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')

            response_text = (
                f"{status_emoji} *Process Finished.*\n\n"
                f"📧 *Email:* `{email}`\n"
                f"🔑 *Password:* `{password}`\n\n"
                f"📝 *Status:* {safe_msg}\n\n"
                f"Data saved to Excel locally."
            )
            
            # Send a NEW message or edit the old one if it's not too old
            # To be safe against timeouts, we send a new one quoting the user
            await context.bot.send_message(
                chat_id=chat_id,
                text=response_text,
                parse_mode="Markdown",
                reply_to_message_id=update.message.id
            )
            
        except Exception as e:
            logger.error(f"Background registration task failed: {e}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Critical error in registration task: {str(e)}",
                reply_to_message_id=update.message.id
            )

    # Schedule the task on the current event loop
    asyncio.create_task(run_and_notify())
