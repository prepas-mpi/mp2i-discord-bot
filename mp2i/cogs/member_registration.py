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

    @Cog.listener("on_member_remove")
    async def remove_member(self, member: discord.Member) -> None:
        """
        Update presence of the member

        Parameters
        ----------
        member : discord.Member
            the member that has just joined the guild
        """
        MemberWrapper(member).presence = False

    @Cog.listener("on_member_update")
    async def update_member(self, _: discord.Member, member: discord.Member) -> None:
        """
        Update display name of the member

        Parameters
        ----------
        _ : discord.Member
            the member before the update

        member : discord.Member
            the member after the update
        """
        MemberWrapper(member).display_name = member.display_name


async def setup(bot: Bot) -> None:
    """
    Setting up member registration behaviour

    Parameters
    ----------
    bot : Bot
        instance of the discord bot
    """
    await bot.add_cog(MemberRegistration())
