import logging

from discord.ext.commands import Bot, Cog

from mp2i.utils.config import get_config_deep
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
        if get_config_deep("system.startup.registering_guilds"):
            logger.info("Registering members")
            for guild_wrapper in map(GuildWrapper, self._bot.guilds):
                guild_wrapper.register()
                logger.debug("Chunking guild")
                logger.info(f"Begin registering members {len(guild_wrapper.members)}")
                index: int = 0
                for member in guild_wrapper.members:
                    if index % 200 == 0:
                        logger.info(
                            f"... @ {index * 100 // len(guild_wrapper.members)}"
                        )
                    if not member.bot:
                        MemberWrapper(member).register()
                    index += 1
            logger.info("Bot is ready and has register every member.")
        else:
            logger.info("Skipping members registration.")
            logger.info("Bot is ready.")


async def setup(bot: Bot) -> None:
    """
    Register ready Cog
    """
    await bot.add_cog(Ready(bot))
