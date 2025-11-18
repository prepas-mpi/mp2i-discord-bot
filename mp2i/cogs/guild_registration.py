import logging

import discord
from discord.ext.commands import Bot, Cog

from mp2i.wrappers.guild import GuildWrapper
from mp2i.wrappers.member import MemberWrapper

logger: logging.Logger = logging.getLogger(__name__)


class GuildRegistration(Cog):
    """
    Register guild and unregistered it when leaving
    """

    @Cog.listener("on_guild_join")
    async def register_guild(self, guild: discord.Guild) -> None:
        """
        Register guild and its members in database

        Parameters
        ----------
        guild : discord.Guild
            the guild that has just been joined
        """
        GuildWrapper(guild).register()
        async for member in guild.fetch_members():
            MemberWrapper(member).register()

    @Cog.listener("on_guild_leave")
    async def unregister_guild(self, guild: discord.Guild) -> None:
        """
        Unregister guild

        Parameters
        ----------
        guild : discord.Guild
            the guild that has just been left
        """
        GuildWrapper(guild).delete()


async def setup(bot: Bot) -> None:
    """
    Setting up guild registration behaviour

    Parameters
    ----------
    bot : Bot
        instance of the discord bot
    """
    await bot.add_cog(GuildRegistration())
