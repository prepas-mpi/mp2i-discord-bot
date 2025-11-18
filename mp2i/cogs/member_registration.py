import discord
from discord.ext.commands import Bot, Cog

from mp2i.wrappers.member import MemberWrapper


class MemberRegistration(Cog):
    """
    Register member when they join a guild
    """

    @Cog.listener("on_member_join")
    async def register_member(self, member: discord.Member) -> None:
        """
        Register member in database

        Parameters
        ----------
        member : discord.Member
            the member that has just joined the guild
        """
        MemberWrapper(member).register()


async def setup(bot: Bot) -> None:
    """
    Setting up member registration behaviour

    Parameters
    ----------
    bot : Bot
        instance of the discord bot
    """
    await bot.add_cog(MemberRegistration())
