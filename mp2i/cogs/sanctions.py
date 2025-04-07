import logging
from datetime import datetime
from typing import Optional, Union
from math import ceil

import discord
from discord import AuditLogAction, app_commands, TextStyle, AppCommandType
from discord.ext.commands import Cog, hybrid_command, guild_only
from discord.app_commands import Choice, choices
from discord.ui import Modal, TextInput
from sqlalchemy import insert, select, delete

from mp2i.utils import database
from mp2i.models import SanctionModel
from mp2i.wrappers.guild import GuildWrapper
from mp2i.utils.discord import has_any_role, EmbedPaginator
from mp2i.wrappers.member import MemberWrapper

logger = logging.getLogger(__name__)


class Sanction(Cog):
    """
    Offers interface to manage sanctions to users
    """

    def __init__(self, bot):
        self.bot = bot
        ctx_menu = app_commands.ContextMenu(
            name='Avertir',
            callback=self.warn_interaction,
            type=AppCommandType.user
        )
        ctx_menu.guild_only = True
        ctx_menu.checks.append(has_any_role("Modérateur", "Administrateur").predicate)
        self.bot.tree.add_command(ctx_menu)

    def __register_sanction_in_database(
        self,
        staff: int,
        member: int,
        guild: int,
        date,
        type: str,
        duration: Optional[int],
        reason: Optional[str],
    ):
        database.execute(
            insert(SanctionModel).values(
                by_id=staff,
                to_id=member,
                guild_id=guild,
                date=date,
                type=type,
                duration=duration,
                reason=reason,
            )
        )

    async def warn(self, ctx, guild, member: Union[discord.User, discord.Member], staff: discord.User,
                   send_dm: bool, reason: str) -> None:
        """
        Avertit un utilisateur pour une raison donnée.

        Parameters
        ----------
        guild: discord.Guild
            Le serveur sur lequel l'avertissement est donné.
        member : discord.User
            L'utilisateur à avertir.
        staff : discord.User
            L'utilisateur qui avertit.
        send_dm : bool
            Si True, l'utilisateur sera averti par message privé.
        reason : str
            La raison de l'avertissement.
        """
        self.__register_sanction_in_database(
            staff=staff.id,
            member=member.id,
            guild=guild.id,
            date=datetime.now(),
            type="warn",
            duration=None,
            reason=reason,
        )
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
        embed.add_field(name="Staff", value=staff.mention)
        embed.add_field(name="Raison", value=reason, inline=False)
        if send_dm and message_sent:
            embed.add_field(name="Message privé", value="L'utilisateur a été averti.", inline=False)
        elif send_dm:
            embed.add_field(
                name="Message privé",
                value=r"/!\ Aucun message n'a pu être envoyé à l'utilisateur.",
                inline=False,
            )

        await ctx.send(embed=embed, ephemeral=True)

        guild = GuildWrapper(guild)
        if not guild.sanctions_log_channel:
            return
        await guild.sanctions_log_channel.send(embed=embed)


    async def warn_interaction(self, interaction: discord.Interaction, member: discord.Member) -> None:
        await interaction.response.send_modal(self.WarnModal(self, member))

    @hybrid_command(name="warn")
    @guild_only()
    @has_any_role("Modérateur", "Administrateur")
    async def warn_command(self, ctx, member: discord.Member, send_dm: bool, reason: str) -> None:
        """
        Avertit un utilisateur pour une raison donnée.

        Parameters
        ----------
        member : discord.Member
            L'utilisateur à avertir.
        send_dm : bool
            Si True, l'utilisateur sera averti par message privé.
        reason : str
            La raison de l'avertissement.
        """
        await self.warn(ctx, ctx.guild, member, ctx.author, send_dm, reason)

    @hybrid_command(name="sanctionlist")
    @guild_only()
    @has_any_role("Modérateur", "Administrateur")
    @choices(
        type=[
            Choice(name="Tout type", value="*"),
            Choice(name="Avertissement", value="warn"),
            Choice(name="Exclusion temporaire", value="to"),
            Choice(name="Bannissement", value="ban"),
            Choice(name="Réintégration", value="unto"),
            Choice(name="Débannissement", value="unban"),
        ]
    )
    async def sanction_list(
        self, ctx, type: str, member: Optional[discord.Member]
    ) -> None:
        """
        Liste les sanctions reçues par un membre.

        Parameters
        ----------
        type : str
            Type des sanctions à afficher
        member : Optional[discord.Member]
            Le membre dont on veut lister les sanctions.
        """
        if member:
            target = MemberWrapper(member)
            request = select(SanctionModel).where(
                SanctionModel.to_id == member.id,
                SanctionModel.guild_id == ctx.guild.id,
                True if type == "*" else SanctionModel.type == type,
            )
            try:
                title = f"Liste des sanctions de {target.name}"
            except AttributeError:
                title = f"Liste des sanctions de {target.cached_name}"
        else:
            request = select(SanctionModel).where(
                SanctionModel.guild_id == ctx.guild.id,
                True if type == "*" else SanctionModel.type == type,
            )
            title = "Liste des sanctions du serveur"

        sanctions = database.execute(request).scalars().all()
        content_header = f"**Nombre de sanctions :** {len(sanctions)}\n\n"
        
        content_body = []
        for sanction in sanctions:
            content = f"**{sanction.id}** ━ Le {sanction.date:%d/%m/%Y à %H:%M}\n"
            content += f"> **Type :** {sanction.type}\n"
            if not member:
                content += f"> **Membre :** <@{sanction.to_id}>\n"

            duration = sanction.get_duration
            if duration:
                content += f"> **Temps :** {duration}\n"

            by = ctx.guild.get_member(sanction.by_id)
            content += f"> **Modérateur :** {by.mention}\n"
            if sanction.reason:
                reason = sanction.reason.replace("\n", "\n> ")
                content += f"> **Raison :** {reason}\n"
            content += "\n"
            content_body.append(content)

        
        embed = EmbedPaginator(
            title=title,
            colour=0xFF00FF,
            content_header=content_header,
            content_body=content_body,
            nb_by_pages=5,
            footer=self.bot.user.name,
            author_id=ctx.author.id,
            timeout=500,
        )
        await embed.send(ctx)

    @hybrid_command(name="rmsanction")
    @guild_only()
    @has_any_role("Modérateur", "Administrateur")
    async def rmsanction(self, ctx, id: int) -> None:
        """
        Supprime une sanction.

        Parameters
        ----------
        id : int
            L'identifiant de la sanction à supprimer.
        """
        database.execute(delete(SanctionModel).where(SanctionModel.id == id))
        message = f"La sanction d'identifiant {id} a été supprimée."
        await ctx.send(message, ephemeral=True)
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
            if reason:
                try:
                    await user.send(f"Vous avez été TO jusqu'à <t:{time}:F> pour la raison : \n>>> {reason}")
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

        if not (entry.action == AuditLogAction.ban
                or entry.action == AuditLogAction.unban
                or entry.action == AuditLogAction.member_update):
            return
            
        try:
            user = entry.target
            entry.target.name  # génère une erreur si la cible n'est pas sur le serveur
        except Exception:  # pas la peine de cibler l'erreur.
            try:
                user = await self.bot.fetch_user(entry.target.id)
            except discord.NotFound:
                logger.error(f"Failed to fetch user {entry.target.id} ! Cannot log their sanction.")
                return
        staff = entry.user  # renommage pour meilleure compréhension

        def insert_in_database(type, duration):
            self.__register_sanction_in_database(
                staff=entry.user.id,
                member=entry.target.id,
                guild=entry.guild.id,
                date=datetime.now(),
                type=type,
                duration=duration,
                reason=entry.reason
            )
            logger.info(f"{staff.name} ({staff.id}) {type} {user.name} ({user.id}).")

        if entry.action == AuditLogAction.ban:
            insert_in_database("ban", None)
            await handle_log_ban(user, staff, entry.reason)

        elif entry.action == AuditLogAction.unban:
            insert_in_database("unban", None)
            await handle_log_unban(user, staff)

        # Doit être étrangement avant la condition de TO sinon ne s'applique pas
        elif entry.action == AuditLogAction.member_update and (
            hasattr(entry.before, "timed_out_until") and
            hasattr(entry.after, "timed_out_until") and
            entry.before.timed_out_until and not entry.after.timed_out_until
        ):
            insert_in_database("unto", None)
            await handle_log_unto(user, staff)

        elif entry.action == AuditLogAction.member_update and (
            hasattr(entry.before, "timed_out_until") and
            hasattr(entry.after, "timed_out_until") and
            not entry.before.timed_out_until
            and entry.after.timed_out_until
            or entry.before.timed_out_until
            and entry.before.timed_out_until < entry.after.timed_out_until
        ):
            end_of_sanction = entry.after.timed_out_until.timestamp()
            insert_in_database("to", int(ceil(end_of_sanction - datetime.now().timestamp())))
            # +60 indique la minute qui suit, mieux vaut large que pas assez
            await handle_log_to(user, staff, entry.reason, int(end_of_sanction + 60))

    class WarnModal(Modal, title="Avertir un member"):
        def __init__(self, sanction, member):
            super().__init__()
            self.sanction = sanction
            self.member = member
            self.add_item(
                TextInput(
                    label = 'Raison',
                    placeholder = "Votre comportement ne sied guère à l'esprit du serveur...",
                    max_length = 3096,
                    style = TextStyle.paragraph,
                    required = True
                )
            )
            self.add_item(
                TextInput(
                    label = "Envoi d'un message privé",
                    placeholder = 'oui/non',
                    max_length = 10,
                    required = False
                )
            )

        async def on_submit(self, interaction: discord.Interaction):
            await interaction.response.defer()
            reason = self.children[0].value
            send_dm = self.children[1].value.strip().lower() != "non"
            await self.sanction.warn(
                ctx=interaction.followup,
                guild=interaction.guild,
                member=self.member,
                staff=interaction.user,
                send_dm=send_dm,
                reason=reason
            )

        async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
            logger.error(error)
            await interaction.followup.send("Quelque chose s'est mal passé lors de la réception !", ephemeral=True)

async def setup(bot) -> None:
    await bot.add_cog(Sanction(bot))
