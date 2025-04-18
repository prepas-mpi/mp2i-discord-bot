from typing import Optional

import asyncio
import logging
from datetime import datetime

import discord
from discord.ext.commands import Cog, hybrid_command, is_owner

from mp2i import STATIC_DIR
from mp2i.wrappers.member import MemberWrapper
from mp2i.wrappers.guild import GuildWrapper

from mp2i.utils import email

logger = logging.getLogger(__name__)


class Roles(Cog):
    """
    Offers an interface to manage roles and send messages
    to choice his roles inside the guild.
    """

    def __init__(self, bot):
        self.bot = bot

    @hybrid_command(name="roles", hidden=True)
    @is_owner()
    async def roles(self, ctx, message_id: Optional[str] = "") -> None:
        """
        Génère ou définit le message pour choisir ses rôles.
        """
        guild = GuildWrapper(ctx.guild)
        if message_id:
            guild.roles_message_id = int(message_id)
            await ctx.reply(f"Le bot écoute désormais le message `{message_id}`")
        else:
            guild.roles_message_id = await self._send_selection(guild, ctx.channel)

    async def _send_selection(
        self, guild: GuildWrapper, channel: discord.TextChannel
    ) -> int:
        """
        Send a message to select roles in the current channel.
        """
        with open(STATIC_DIR / "text/roles.md", encoding="utf-8") as f:
            content = f.read()
            for qualifier, role_cfg in guild.config.roles.items():
                if emoji := guild.get_emoji_by_name(role_cfg.emoji):
                    content = content.replace(f"({qualifier})", str(emoji))

            emoji_rond = guild.get_emoji_by_name("rond")
            embed = discord.Embed(
                colour=0xFF22FF,
                title="Sélectionnez votre rôle !",
                description=content.replace(":rond:", str(emoji_rond)),
                timestamp=datetime.now(),
            )
            embed.set_footer(text=self.bot.user.name)
            message = await channel.send(embed=embed)

        # Add reactions to the message
        for role_cfg in guild.config.roles.values():
            if not role_cfg.choice:
                continue
            if emoji := guild.get_emoji_by_name(role_cfg.emoji):
                await message.add_reaction(emoji)
            else:
                logger.error(f"{role_cfg.emoji} emoji not found")

        return message.id

    @Cog.listener("on_raw_reaction_add")
    async def on_selection(self, payload) -> None:
        """
        Update role from the user selection.
        """
        if not hasattr(payload, "guild_id") or payload.member.id == self.bot.user.id:
            return  # Ignore DM and bot reaction

        guild = GuildWrapper(self.bot.get_guild(payload.guild_id))
        if guild.roles_message_id != payload.message_id:
            return  # Ignore if it is not the good message

        member = MemberWrapper(payload.member)
        if not member.exists():
            logger.warning(f"The user {member.name} was not a registered member")
            member.register()

        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        mpi_role = guild.get_role_by_qualifier("MPI")
        ex_mpi_role = guild.get_role_by_qualifier("Ex MPI")

        for qualifier, role_cfg in guild.config.roles.items():
            if not role_cfg.choice:
                continue
            role = guild.get_role(role_cfg.id)

            if role_cfg.emoji == payload.emoji.name:
                # Add the role
                if qualifier == "Prof":
                    prof_role = guild.get_role_by_qualifier("Prof")
                    await self._add_prof_role(member, prof_role)
                elif qualifier == "Intégré" and member.role == mpi_role:
                    await member.add_roles(role, ex_mpi_role)
                else:
                    await member.add_roles(role)
                member.update(role=qualifier)
            else:
                # Remove the role
                if emoji := guild.get_emoji_by_name(role_cfg.emoji):
                    await message.remove_reaction(emoji, member)
                await member.remove_roles(role)

    async def _add_prof_role(self, member: MemberWrapper, prof_role: discord.Role):
        """
        Procedure to verify a member and add the prof role.
        """
        await member.send(
            "Afin de vous attribuer le rôle Prof, "
            "nous devons effectuer quelques vérifications.\n"
            "**Veuillez nous fournir un email académique :**"
        )
        try:
            message = await self.bot.wait_for(
                "message",
                check=lambda msg: msg.channel == member.dm_channel,
                timeout=300,
            )
            receiver_email = message.content.strip()
            if not email.is_academic_email(receiver_email):
                await member.send("L'email fourni n'est pas un mail académique valide.")
                return

            verification_code = email.generate_verification_code()
            with open(STATIC_DIR / "text/mail.md", encoding="utf-8") as f:
                message = f.read()
            message = message.replace("(username)", member.name)
            message = message.replace("(verification_code)", verification_code)

            if not email.send(receiver_email, message):
                await member.send("Une erreur est survenue lors de l'envoi de l'email.")
                return
            await member.send(
                "Un email de vérification vous a été envoyé. \n"
                "**Veuillez entrer le code à 6 chiffres reçu :**"
            )
            message = await self.bot.wait_for(
                "message",
                check=lambda msg: msg.channel == member.dm_channel,
                timeout=300,
            )
            if message.content.strip() != verification_code:
                await member.send("Le code de vérification est invalide.")
                return
        except asyncio.TimeoutError:
            await member.send("Vous avez mis trop de temps à répondre.")
        else:
            await member.add_roles(prof_role)
            await member.send("Merci, le rôle Prof vous été attribué.")


async def setup(bot) -> None:
    await bot.add_cog(Roles(bot))
