import asyncio
import logging
import logging.config as logging_config
import os

import dotenv
import humanize.i18n as i18n

import mp2i.utils.config as config

from .bot import Bot
from .database import setup as database_setup

logger: logging.Logger = logging.getLogger(__name__)


async def main() -> None:
    """
    Main function of program
    """
    dotenv.load_dotenv()
    i18n.activate("fr_FR")

    try:
        if not os.path.exists("logs"):
            os.makedirs("logs")
        logging_config.dictConfig(config.get_logger_config())
    except FileNotFoundError:
        logger.warning(
            "No configuration found for logger. Logs will only appear in the console."
        )

    if not config.has_config():
        logger.fatal("No config has been found.")
        return

    if not (token := os.getenv("MP2I__DISCORD_BOT_TOKEN")):
        logger.fatal("Token not found.")
        return

    if not database_setup.test_connection():
        logger.fatal("Stopping bot startup due to the absence of database.")
        return

    if not database_setup.initialize_database():
        logger.fatal(
            "Stopping bot startup due to the failing database intialize process."
        )
        return

    logger.info("Starting bot")
    bot: Bot = Bot()

    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
