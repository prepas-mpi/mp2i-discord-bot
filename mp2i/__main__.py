import asyncio
import logging
import os

import dotenv

from mp2i.bot import Bot
from mp2i.utils import database

logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)


async def main() -> None:
    """
    Main function of program
    """
    dotenv.load_dotenv()

    if not (token := os.getenv("MP2I__DISCORD_BOT_TOKEN")):
        logger.fatal("Token not found.")
        return

    if not database.test_connection():
        logger.fatal("Stopping bot startup due to the absence of database.")
        return

    logger.info("Starting bot")
    bot: Bot = Bot()

    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
