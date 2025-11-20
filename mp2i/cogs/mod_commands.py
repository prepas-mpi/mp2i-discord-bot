import logging

import discord
from discord.app_commands import Range, command, describe
from discord.app_commands.checks import has_permissions
from discord.ext.commands import Bot, Cog, guild_only

logger: logging.Logger = logging.getLogger(__name__)


class ModCommands(Cog):
    """
    Commands for moderation
    """

    __MAX_DELETED_MESSAGES: int = 100

    @command(
        name="clear",
        description="Supprime les `num` messages derniers messages.",
    )
    @describe(num="Nombre de messages à supprimer")
    @has_permissions(manage_messages=True)
    @guild_only()
    async def clear(
        self,
        interaction: discord.Interaction,
        num: Range[int, 1, __MAX_DELETED_MESSAGES],
    ) -> None:
        if not interaction.channel:
            logger.warning(
                "User %d can not delete message as they are not in a channel.",
                interaction.user.id,
            )
            await interaction.response.send_message("Vous n'êtes pas dans un salon.")
            return

        if not isinstance(interaction.channel, discord.TextChannel):
            logger.warning(
                "User %d can not delete message in channel %d.",
                interaction.user.id,
                interaction.channel.id,
            )
            await interaction.response.send_message(
                "La commande ne supporte pas ce type de canal"
            )
            return

        await interaction.response.send_message(
            "Suppression des messages en cours...", ephemeral=True
        )
        await interaction.channel.purge(limit=num)
        logger.info(
            "User %d deleted %d messages in channel %d.",
            interaction.user.id,
            num,
            interaction.channel.id,
        )
        await interaction.edit_original_response(content=f"{num} messages supprimés.")

    @command(name="say", description="Envoyer un message au nom du bot")
    @describe(
        channel="Canal discord dans lequel envoyer un message",
        message="Message à envoyer à travers le bot",
    )
    @has_permissions(manage_messages=True)
    @guild_only()
    async def say(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str,
    ) -> None:
        logger.info(
            "User %d send message through bot in channel %d. Message: %s",
            interaction.user.id,
            channel.id,
            message,
        )
        await channel.send(message)
        await interaction.response.send_message(
            f"Un message a été envoyé dans le salon {channel.jump_url}", ephemeral=True
        )


async def setup(bot: Bot) -> None:
    """
    Setting up moderation commands

    Parameters
    ----------
    bot : Bot
        instance of the discord bot
    """
    await bot.add_cog(ModCommands(bot))
