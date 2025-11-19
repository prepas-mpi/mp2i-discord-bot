import asyncio
import logging
import os

import dotenv

from mp2i.utils.config import has_config

from .bot import Bot
from .database import setup as database_setup

logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)


async def main() -> None:
    """
    Main function of program
    """
    dotenv.load_dotenv()

    if not has_config():
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
