import logging
import os

import discord
import discord.ext.commands as commands

logger = logging.getLogger(__name__)


class Bot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="/", intents=discord.Intents.all())

    async def setup_hook(self) -> None:
        logger.info("Loading all cogs files.")
        for filename in filter(
            lambda file_name: file_name.endswith(".py"), os.listdir("./mp2i/cogs")
        ):
            try:
                await self.load_extension(f"mp2i.cogs.{filename[:-3]}")
            except Exception as e:
                logger.fatal(f"Failed to load {filename}: {e}")

        await self.tree.sync()
