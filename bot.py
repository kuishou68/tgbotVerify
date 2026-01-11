"""Telegram 机器人主程序"""
import logging
import os
import time
from functools import partial

from telegram.ext import Application, CommandHandler

from config import BOT_TOKEN
from database_mysql import Database
from handlers.user_commands import (
    start_command,
    about_command,
    help_command,
    balance_command,
    checkin_command,
    invite_command,
    use_command,
)
from handlers.verify_commands import (
    verify_command,
    verify2_command,
    verify3_command,
    verify4_command,
    verify5_command,
    verify6_command,
    getV4Code_command,
)
from handlers.admin_commands import (
    addbalance_command,
    block_command,
    white_command,
    blacklist_command,
    genkey_command,
    listkeys_command,
    broadcast_command,
)
from handlers.email_commands import email_register_command, gen_emails_command

# 配置日志
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def error_handler(update: object, context) -> None:
    """全局错误处理"""
    logger.exception("处理更新时发生异常: %s", context.error, exc_info=context.error)


def main():
    """主函数"""
    local_mode = os.getenv("LOCAL_MODE", "").strip().lower() in {"1", "true", "yes"}
    if local_mode:
        logger.warning("LOCAL_MODE 启用：跳过 Telegram 启动和数据库初始化。")
        logger.info("本地模式运行中，按 Ctrl+C 退出。")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            logger.info("本地模式已退出。")
        return

    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("未设置 BOT_TOKEN。请配置 BOT_TOKEN 或设置 LOCAL_MODE=1。")

    # 初始化数据库
    db = Database()

    # 创建应用 - 启用并发处理
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)  # 🔥 关键：启用并发处理多个命令
        .build()
    )

    # 注册用户命令（使用 partial 传递 db 参数）
    application.add_handler(CommandHandler("start", partial(start_command, db=db)))
    application.add_handler(CommandHandler("about", partial(about_command, db=db)))
    application.add_handler(CommandHandler("help", partial(help_command, db=db)))
    application.add_handler(CommandHandler("balance", partial(balance_command, db=db)))
    application.add_handler(CommandHandler("qd", partial(checkin_command, db=db)))
    application.add_handler(CommandHandler("invite", partial(invite_command, db=db)))
    application.add_handler(CommandHandler("use", partial(use_command, db=db)))

    # 注册验证命令
    application.add_handler(CommandHandler("verify", partial(verify_command, db=db)))
    application.add_handler(CommandHandler("verify2", partial(verify2_command, db=db)))
    application.add_handler(CommandHandler("verify3", partial(verify3_command, db=db)))
    application.add_handler(CommandHandler("verify4", partial(verify4_command, db=db)))
    application.add_handler(CommandHandler("verify5", partial(verify5_command, db=db)))
    application.add_handler(CommandHandler("verify6", partial(verify6_command, db=db)))
    application.add_handler(CommandHandler("getV4Code", partial(getV4Code_command, db=db)))

    # 注册管理员命令
    application.add_handler(CommandHandler("addbalance", partial(addbalance_command, db=db)))
    application.add_handler(CommandHandler("block", partial(block_command, db=db)))
    application.add_handler(CommandHandler("white", partial(white_command, db=db)))
    application.add_handler(CommandHandler("blacklist", partial(blacklist_command, db=db)))
    application.add_handler(CommandHandler("genkey", partial(genkey_command, db=db)))
    application.add_handler(CommandHandler("listkeys", partial(listkeys_command, db=db)))
    application.add_handler(CommandHandler("broadcast", partial(broadcast_command, db=db)))

    # 注册邮箱注册命令
    application.add_handler(CommandHandler("email_register", email_register_command))
    application.add_handler(CommandHandler("gen_emails", gen_emails_command))

    # 注册错误处理器
    application.add_error_handler(error_handler)

    logger.info("机器人启动中...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
