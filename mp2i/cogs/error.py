import logging

import discord
from discord.app_commands import AppCommandError, MissingAnyRole
from discord.ext.commands import Bot

logger: logging.Logger = logging.getLogger(__name__)


async def setup(bot: Bot) -> None:
    """
    Setup error handler

    Parameters
    ----------
    bot : Bot
        The bot
    """

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction,
        error: AppCommandError,
    ) -> None:
        """
        Handle errors, log them and answer to the user

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction that has failed

        error : AppCommandError
            The triggered error

        Raises
        ------
        AppCommandError
            If the error is not handled
        """
        if not interaction.command:
            logger.fatal(
                "Interaction triggered on_app_command_error but is not a command."
            )
            raise error
        if isinstance(error, MissingAnyRole):
            logger.warning(
                "User %d tried to execute command `%s` but do not have the required role.",
                interaction.user.id,
                interaction.command.qualified_name,
            )
            await interaction.response.send_message(
                "Vous n'avez pas les rôles requis pour effectuer cette interaction.",
                ephemeral=True,
            )
        else:
            logger.fatal(
                "An error occured with user %d and command `%s`. %s",
                interaction.user.id,
                interaction.command.qualified_name,
                error,
                exc_info=True,
            )
