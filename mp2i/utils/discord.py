import logging
from typing import Any, Callable, List

import discord
from discord.app_commands import MissingAnyRole, check

from mp2i.wrappers.guild import GuildWrapper

logger: logging.Logger = logging.getLogger(__name__)


async def has_any_roles_predicate(
    interaction: discord.Interaction, *roles: str
) -> bool:
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

    Raises
    ------
    MissingAnyRole
        Error if the check do not pass, contains a list of required roles
    """
    if not interaction.guild:
        logger.warning("Using has_config_role in a non guild context.")
        raise MissingAnyRole(list(roles))

    guild: GuildWrapper = GuildWrapper(interaction.guild)
    member: discord.Member | discord.User = interaction.user
    if isinstance(member, discord.User):
        logger.error("User is not member in the guild %d.", guild.id)
        raise MissingAnyRole(list(roles))
    needed_role: List[discord.Role] = guild.mapping_roles(list(roles))
    for role in needed_role:
        if role in member.roles:
            return True
    raise MissingAnyRole(list(roles))


def has_any_role(*roles: str) -> Callable[[Any], Any]:
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

    return check(lambda interaction: has_any_roles_predicate(interaction, *roles))
