import logging
import os

import discord
import discord.ext.commands as commands

logger = logging.getLogger(__name__)


class Bot(commands.Bot):
    """
    Class to represent the discord bot
    """

    def __init__(self) -> None:
        """
        Initialize parent classes
        """
        super().__init__(command_prefix="/", intents=discord.Intents.all())

    async def setup_hook(self) -> None:
        """
        Load cogs file before starting the bot
        """
        logger.info("Loading all cogs files.")
        base_dir = "./mp2i/cogs"
        for root, _, files in os.walk(base_dir):
            for filename in files:
                # skip files that aren't python script or start with _ as __init__ or __main__
                if not filename.endswith(".py") or filename.startswith("_"):
                    continue
                rel_path = os.path.relpath(root, "./mp2i")
                module_path = (
                    "mp2i." + rel_path.replace(os.sep, ".") + "." + filename[:-3]
                )
                try:
                    await self.load_extension(module_path)
                except Exception as e:
                    logger.fatal("Failed to load %s: %s", module_path, e, exc_info=True)

        await self.tree.sync()
