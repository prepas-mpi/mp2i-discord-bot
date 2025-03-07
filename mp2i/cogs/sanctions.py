import logging
from datetime import datetime
from typing import Optional
from math import ceil

import discord
from discord import AuditLogAction
from discord.ext.commands import Cog, hybrid_command, guild_only
from discord.app_commands import Choice, choices
from sqlalchemy import insert, select, delete

from mp2i.utils import database
from mp2i.models import SanctionModel
from mp2i.wrappers.guild import GuildWrapper
from mp2i.utils.discord import has_any_role

logger = logging.getLogger(__name__)


class Sanction(Cog):
    """
    Offers interface to manage sanctions to users
    """

    def __init__(self, bot):
        self.bot = bot

    def __register_sanction_in_database(
        self,
        staff: int,
        member: int,
        guild: int,
        date,
        type_: str,
        duration: Optional[int],
        reason: Optional[str],
    ):
        database.execute(
            insert(SanctionModel).values(
                by_id=staff,
                to_id=member,
                guild_id=guild,
                date=date,
                type=type_,
                duration=duration,
                reason=reason,
            )
        )

    @hybrid_command(name="warn")
    @guild_only()
    @has_any_role("Modérateur", "Administrateur")
    async def warn(self, ctx, member: discord.Member, dm: str, *,
                   reason: str) -> None:  # fmt: skip
        """
        Avertit un utilisateur pour une raison donnée.

        Parameters
        ----------
        member : discord.Member
            L'utilisateur à avertir.
        dm : str
            Si oui, l'utilisateur sera averti par message privé.
        reason : str
            La raison de l'avertissement.
        """
        self.__register_sanction_in_database(
            staff=ctx.author.id,
            member=member.id,
            guild=ctx.guild.id,
            date=datetime.now(),
            type_="warn",
            duration=None,
            reason=reason,
        )
        send_dm = dm == "oui"
        message_sent = False
        if send_dm:
            # Au cas où l'utilisateur visé a fermé ses messages privés.
            try:
                await member.send(
                    "Vous avez reçu un avertissement pour la raison suivante: \n"
                    f">>> {reason}"
                )
                message_sent = True
            except discord.Forbidden:
                message_sent = False

        embed = discord.Embed(
            title=f"{member.name} a reçu un avertissement",
            colour=0xFF00FF,
            timestamp=datetime.now(),
        )
        embed.add_field(name="Utilisateur", value=member.mention)
        embed.add_field(name="Staff", value=ctx.author.mention)
        embed.add_field(name="Raison", value=reason, inline=False)
        if send_dm and message_sent:
            embed.add_field(
                name="Message privé", value="L'utilisateur a été averti.", inline=False
            )
        elif send_dm:
            embed.add_field(
                name="Message privé",
                value=r"/!\ Aucun message n'a pu être envoyé à l'utilisateur.",
                inline=False,
            )

        await ctx.send(embed=embed, ephemeral=True)

        guild = GuildWrapper(ctx.guild)
        if not guild.sanctions_log_channel:
            return
        await guild.sanctions_log_channel.send(embed=embed)

    @hybrid_command(name="sanctionlist")
    @guild_only()
    @has_any_role("Modérateur", "Administrateur")
    @choices(
        type_=[
            Choice(name="Tout type", value="*"),
            Choice(name="Avertissement", value="warn"),
            Choice(name="Bâillonnage", value="to"),
            Choice(name="Bannissement", value="ban"),
            Choice(name="Débâillonnage", value="unto"),
            Choice(name="Débannissement", value="unban"),
        ]
    )
    async def sanction_list(
        self, ctx, type_: str, member: Optional[discord.Member]
    ) -> None:
        """
        Liste les sanctions reçues par un membre.

        Parameters
        ----------
        type_ : str
            Type des sanctions à afficher
        member : Optional[discord.Member]
            Le membre dont on veut lister les sanctions.
        """
        if member:
            request = select(SanctionModel).where(
                SanctionModel.to_id == member.id,
                SanctionModel.guild_id == ctx.guild.id,
                True if type_ == "*" else SanctionModel.type == type_,
            )
            title = f"Liste des sanctions de {member.name}"
        else:
            request = select(SanctionModel).where(
                SanctionModel.guild_id == ctx.guild.id,
                True if type_ == "*" else SanctionModel.type == type_,
            )
            title = "Liste des sanctions du serveur"

        sanctions = database.execute(request).scalars().all()
        content = f"**Nombre de sanctions :** {len(sanctions)}\n\n"

        for sanction in sanctions:
            content += f"**{sanction.id}** ━ Le {sanction.date:%d/%m/%Y à %H:%M}\n"
            content += f"> **Type :** {sanction.type}\n"
            if not member:
                to = ctx.guild.get_member(sanction.to_id)
                content += f"> **Membre :** {to.mention}\n"

            duration = sanction.get_duration
            if duration:
                content += f"> **Temps :** {duration}\n"

            by = ctx.guild.get_member(sanction.by_id)
            content += f"> **Modérateur :** {by.mention}\n"
            if sanction.reason:
                content += f"> **Raison :** {sanction.reason}\n"
            content += "\n"

        embed = discord.Embed(
            title=title, description=content, colour=0xFF00FF, timestamp=datetime.now()
        )
        await ctx.send(embed=embed)

    @hybrid_command(name="unwarn")
    @guild_only()
    @has_any_role("Modérateur", "Administrateur")
    async def unwarn(self, ctx, id: int) -> None:
        """
        Supprime un avertissement.

        Parameters
        ----------
        id : int
            L'identifiant de l'avertissement à supprimer.
        """
        database.execute(delete(SanctionModel).where(SanctionModel.id == id))
        message = f"L'avertissement {id} a été supprimé."
        await ctx.send(message)
        guild = GuildWrapper(ctx.guild)
        if not guild.sanctions_log_channel:
            return
        await guild.sanctions_log_channel.send(message)

    @Cog.listener("on_audit_log_entry_create")
    @guild_only()
    async def log_sanctions(self, entry) -> None:
        """
        Logue les sanctions envers les utilisateurs.

        Parameters
        ----------
        entry : LogActionEntry
            Entrée ajoutée dans le journal des actions du serveur.
        """
        guild = GuildWrapper(entry.guild)
        if not guild.sanctions_log_channel:
            return

        async def handle_log_ban(user, staff, reason):
            """
            Logue le banissement d'un utilisateur dans le salon des logs de sanctions.

            Parameters
            ----------
            user : Any
                Identifiant de l'utilisateur cible.
            staff: discord.Member
                Utilisateur initateur de l'action.
            reason: str
                Raison du bannissement.
            """

            embed = discord.Embed(
                title=f"{user.name} a été banni",
                colour=0xFF0000,
                timestamp=datetime.now(),
            )
            embed.add_field(name="Utilisateur", value=f"<@{user.id}>")
            embed.add_field(name="Staff", value=staff.mention)
            if reason:
                embed.add_field(name="Raison", value=reason, inline=False)

            await guild.sanctions_log_channel.send(embed=embed)


        async def handle_log_unban(user, staff):
            """
            Logue le débanissement d'un utilisateur dans le salon des logs de sanctions.

            Parameters
            ----------
            user : Any
                Utilisateur cible.
            staff: discord.Member
                Utilisateur initateur de l'action.
            """

            embed = discord.Embed(
                title=f"{user.name} a été débanni",
                colour=0xFA9C1B,
                timestamp=datetime.now(),
            )
            embed.add_field(name="Utilisateur", value=f"<@{user.id}>")
            embed.add_field(name="Staff", value=staff.mention)

            await guild.sanctions_log_channel.send(embed=embed)

        async def handle_log_to(user, staff, reason, time):
            """
            Logue le time out d'un utilisateur dans le salon des logs de sanctions.

            Parameters
            ----------
            user : Any
                Utilisateur cible.
            staff: discord.Member
                Utilisateur initateur de l'action.
            reason: str
                Raison du time out.
            time: int
                Timestamp de fin de sanction.
            """
            dm_sent = False
            try:
                await user.send(
                    f"Vous avez été TO jusqu'à <t:{time}:F> pour la raison : \n>>> {reason}"
                )
                dm_sent = True
            except discord.Forbidden:
                dm_sent = False

            embed = discord.Embed(
                title=f"{user.name} a été TO",
                colour=0xFDAC5B,
                timestamp=datetime.now(),
            )
            embed.add_field(name="Utilisateur", value=f"<@{user.id}>")
            embed.add_field(name="Staff", value=staff.mention)
            embed.add_field(
                name="Timestamp", value=f"<t:{time}:F>", inline=False
            )
            embed.add_field(
                name="Message Privé",
                value="Envoyé" if dm_sent else "Non envoyé"
            )
            embed.add_field(name="Raison", value=reason, inline=False)

            await guild.sanctions_log_channel.send(embed=embed)


        async def handle_log_unto(user, staff):
            """
            Logue la révocation d'un time out d'un utilisateur dans le salon des logs de sanctions.

            Parameters
            ----------
            user : Any
                Utilisateur cible.
            staff: discord.Member
                Utilisateur initateur de l'action.
            """

            embed = discord.Embed(
                title=f"{user.name} n'est plus TO",
                colour=0xFA9C1B,
                timestamp=datetime.now(),
            )
            embed.add_field(name="Utilisateur", value=f"<@{user.id}>")
            embed.add_field(name="Staff", value=staff.mention)

            await guild.sanctions_log_channel.send(embed=embed)

        try:
            user = entry.target
            entry.target.name  # génère une erreur si la cible n'est pas sur le serveur
        except Exception:
            try:
                user = await self.bot.fetch_user(entry.target.id)
            except Exception:
                logger.error(
                    f"Failed to fetch user {entry.target.id} ! Cannot log their sanction."
                )
                return
        staff = entry.user  # renommage pour meilleure compréhension

        def insert_in_database(type_, duration):
            try:
                self.__register_sanction_in_database(
                    staff=entry.user.id,
                    member=entry.target.id,
                    guild=entry.guild.id,
                    date=datetime.now(),
                    type_=type_,
                    duration=duration,
                    reason=entry.reason,
                )
            except Exception:
                logger.warning(
                    f"{staff.name} ({staff.id}) {type_} {user.name} ({user.id}) but member not in database."
                )

        if entry.action == AuditLogAction.ban:
            insert_in_database("ban", None)
            await handle_log_ban(user, staff, entry.reason)

        elif entry.action == AuditLogAction.unban:
            insert_in_database("unban", None)
            await handle_log_unban(user, staff)

        # Doit être étrangement avant la condition de TO sinon ne s'applique pas
        elif entry.action == AuditLogAction.member_update and (
            entry.before.timed_out_until and not entry.after.timed_out_until
        ):
            insert_in_database("unto", None)
            await handle_log_unto(user, staff)

        elif entry.action == AuditLogAction.member_update and (
            not entry.before.timed_out_until
            and entry.after.timed_out_until
            or entry.before.timed_out_until
            and entry.before.timed_out_until < entry.after.timed_out_until
        ):
            end_of_sanction = entry.after.timed_out_until.timestamp()
            insert_in_database(
                "to", int(ceil(end_of_sanction - datetime.now().timestamp()))
            )
            await handle_log_to(
                user,
                staff,
                entry.reason,
                int(
                    end_of_sanction + 60
                ),  # +60 indique la minute qui suit, mieux vaut large que pas assez
            )


async def setup(bot) -> None:
    await bot.add_cog(Sanction(bot))
