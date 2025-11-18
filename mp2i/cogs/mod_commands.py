import logging

import discord
from discord.app_commands import describe
from discord.app_commands.checks import has_permissions
from discord.ext.commands import Bot, Cog, Context, Range, guild_only, hybrid_command

logger: logging.Logger = logging.getLogger(__name__)


class ModCommands(Cog):
    """
    Commands for moderation
    """

    __MAX_DELETED_MESSAGES: int = 100

    @hybrid_command(
        name="clear",
        description="Supprime les `num` messages derniers messages.",
    )
    @describe(num="Nombre de messages à supprimer")
    @has_permissions(manage_messages=True)
    @guild_only()
    async def clear(
        self, ctx: Context, num: Range[int, 1, __MAX_DELETED_MESSAGES]
    ) -> None:
        if not isinstance(ctx.channel, discord.TextChannel):
            logger.warning(
                "User %d can not delete message in channel %d.",
                ctx.author.id,
                ctx.channel.id,
            )
            await ctx.reply("La commande ne supporte pas ce type de canal")
            return

        replied = await ctx.reply(
            "Suppression des messages en cours...", ephemeral=True
        )
        await ctx.channel.purge(limit=num)
        logger.info(
            "User %d deleted %d messages in channel %d.",
            ctx.author.id,
            num,
            ctx.channel.id,
        )
        await replied.edit(content=f"{num} messages supprimés.")

    @hybrid_command(name="say", description="Envoyer un message au nom du bot")
    @describe(
        channel="Canal discord dans lequel envoyer un message",
        message="Message à envoyer à travers le bot",
    )
    @has_permissions(manage_messages=True)
    @guild_only()
    async def say(
        self, ctx: Context, channel: discord.TextChannel, message: str
    ) -> None:
        logger.info(
            "User %d send message through bot in channel %d. Message: %s",
            ctx.author.id,
            channel.id,
            message,
        )
        await channel.send(message)
        await ctx.reply(
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
