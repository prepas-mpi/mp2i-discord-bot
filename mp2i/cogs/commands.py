import re
import logging
from typing import Optional

import discord
from discord.ext.commands import Cog, Range
from discord.ext.commands import (
    hybrid_command,
    guild_only,
    has_permissions,
    errors,
)

from mp2i.wrappers.guild import GuildWrapper
from mp2i.wrappers.member import MemberWrapper
from mp2i.utils.discord import defer, has_any_role

logger = logging.getLogger(__name__)


class Commands(Cog):

    def __init__(self, bot):
        self.bot = bot

    @Cog.listener("on_ready")
    async def set_default_status(self) -> None:
        """
        Initialise le status du bot à /help.
        """
        help_status = "/help"
        await self.bot.change_presence(activity=discord.Game(help_status))

    @hybrid_command(name="clear")
    @guild_only()
    @has_permissions(manage_messages=True)
    async def clear(self, ctx, number: Range[int, 1, 100]) -> None:
        """
        Supprime les n derniers messages du salon.

        Parameters
        ----------
        number : int
            Nombre de messages à supprimer.
        """
        await ctx.channel.purge(limit=int(number) + (ctx.prefix != "/"))
        await ctx.reply(f"{number} messages ont bien été supprimés.", ephemeral=True)

    @clear.error
    async def clear_error(self, ctx, error) -> None:
        """
        Local error handler for clear command.
        """
        if isinstance(error, errors.RangeError):
            msg = f"Le nombre de messages doit être compris entre 1 et {error.maximum}."
            await ctx.reply(msg, ephemeral=True)

    @hybrid_command(name="say")
    @guild_only()
    @has_any_role("Modérateur", "Administrateur")
    async def say(self, ctx, channel: discord.TextChannel, *, message: str) -> None:
        """
        Envoie un message dans un salon.

        Parameters
        ----------
        channel : discord.TextChannel
            Salon où envoyer le message.
        message : str
            Message à envoyer.
        """
        if ctx.prefix == "/":
            await ctx.reply(f"Message envoyé dans {channel.mention}.", ephemeral=True)
        await channel.send(message)

    @hybrid_command(name="profilecolor")
    @guild_only()
    async def change_profile_color(self, ctx, color: str) -> None:
        """Change la couleur de profil.

        Parameters
        ----------
        color : str
            Couleur en hexadécimal.
        """
        member = MemberWrapper(ctx.author)
        hexa_color = color.upper().strip("#")
        if re.match(r"^[0-9A-F]{6}$", hexa_color):
            member.profile_color = color.upper().strip("#")
            await ctx.reply(
                f"Couleur de profil changée en #{hexa_color}.", ephemeral=True
            )
        else:
            await ctx.reply("Format de couleur invalide.", ephemeral=True)

    @hybrid_command(name="servinfos")
    @guild_only()
    async def server_info(self, ctx) -> None:
        """
        Affiche des informations sur les roles du serveur.
        """
        guild = GuildWrapper(ctx.guild)
        embed = discord.Embed(title="Infos du serveur", colour=0xFFA325)
        embed.set_author(name=guild.name)
        embed.set_thumbnail(url=guild.icon.url)
        emoji_people = guild.get_emoji_by_name("silhouettes")
        embed.add_field(name=f"{emoji_people} Membres", value=len(guild.members))

        for role_name, role_cfg in guild.config.roles.items():
            if role_cfg.choice:
                number = len(guild.get_role(role_cfg.id).members)
                emoji = guild.get_emoji_by_name(role_cfg.emoji)
                embed.add_field(name=f"{emoji} {role_name}", value=number)
        await ctx.send(embed=embed)

async def setup(bot) -> None:
    await bot.add_cog(Commands(bot))
