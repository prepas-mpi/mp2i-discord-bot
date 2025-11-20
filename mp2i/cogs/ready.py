import logging

from discord.ext.commands import Bot, Cog

from mp2i.wrappers.guild import GuildWrapper
from mp2i.wrappers.member import MemberWrapper

logger: logging.Logger = logging.getLogger(__name__)


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
        logger.info("Registering members")
        for guild_wrapper in map(GuildWrapper, self._bot.guilds):
            guild_wrapper.register()
            logger.debug("Chunking guild")
            await guild_wrapper.chunk()
            logger.debug("Begin registering members")
            for member in guild_wrapper.members:
                if not member.bot:
                    MemberWrapper(member).register()

        logger.info("Bot is ready and has register every member.")


async def setup(bot: Bot) -> None:
    """
    Register ready Cog
    """
    await bot.add_cog(Ready(bot))
