from discord.ext.commands import Bot, Cog

from mp2i.wrappers.guild import GuildWrapper
from mp2i.wrappers.member import MemberWrapper


class Ready(Cog):
    """
    Perform tasks when bot is ready
    """

    def __init__(self, bot: Bot) -> None:
        """
        Initialize class' variable

        Parameters
        ----------
        bot : Bot
            Instance of the bot
        """
        self._bot: Bot = bot

    @Cog.listener("on_ready")
    async def register_guild_and_members(self) -> None:
        """
        Registering guilds and members in database
        """
        for guild_wrapper in map(GuildWrapper, self._bot.guilds):
            guild_wrapper.register()
            async for member in guild_wrapper._boxed.fetch_members():
                MemberWrapper(member).register()


async def setup(bot: Bot) -> None:
    """
    Register ready Cog
    """
    await bot.add_cog(Ready(bot))
