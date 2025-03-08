import logging
import os

import discord
import humanize
from discord.ext import commands

from mp2i.utils import database, resolver

# Create a logger for this file, __name__ will take the package name if this file
# will do not run as a script
logger = logging.getLogger(__name__)
TOKEN = os.getenv("DISCORD_TOKEN")


async def run(token=None) -> None:
    """
    Runs the bot.
    token: Optional. You can pass your Discord token here or in a .env file
    """
    # Try to connect to the database or raise error
    database.test_connection()

    # Create a bot instance and activate all intents (more access to members infos)
    humanize.i18n.activate("fr_FR")
    bot = commands.Bot(
        command_prefix="=",
        intents=discord.Intents.all(),
        self_bot=False,
        help_command=None,
    )
    # loads all available cogs
    for cog in resolver.find_available_cogs():
        await bot.load_extension(cog.__name__)

    await bot.start(token or TOKEN)  # raise LoginFailure if the token is invalid
