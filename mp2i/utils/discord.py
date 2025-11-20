import logging
from typing import List

import discord
from discord.app_commands import MissingAnyRole, check

from mp2i.wrappers.guild import GuildWrapper

logger: logging.Logger = logging.getLogger(__name__)


def has_any_role(*roles):
    """
    Decorator to control access to specific commands

    Parameters
    ----------
    roles : tuple[str]
        Tuple of roles required

    Returns
    -------
    Check[Any]
        Predicate
    """

    async def predicate(ctx: discord.Interaction):
        """
        Predicate that check if user has one of the required roles

        Parameters
        ----------
        ctx : Context
            Context of an interaction

        Returns
        -------
        bool
            True if the user has one of the required role, False otherwise
        """
        if not ctx.guild:
            logger.warning("Using has_config_role in a non guild context.")
            raise MissingAnyRole(list(roles))

        guild: GuildWrapper = GuildWrapper(ctx.guild)
        member: discord.Member | discord.User = (
            ctx.user if isinstance(ctx, discord.Interaction) else ctx.author
        )
        if isinstance(member, discord.User):
            logger.error("User is not member in the guild %d.", guild.id)
            raise MissingAnyRole(list(roles))
        needed_role: List[discord.Role] = guild.mapping_roles(list(roles))
        for role in needed_role:
            if role in member.roles:
                return True
        raise MissingAnyRole(list(roles))

    return check(predicate)
