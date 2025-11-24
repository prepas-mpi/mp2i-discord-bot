import datetime
import logging
from math import ceil
from typing import List, Optional, Sequence

import discord
from discord.app_commands import (
    ContextMenu,
    command,
    describe,
    guild_only,
    rename,
)
from discord.ext.commands import Bot, Cog, GroupCog
from sqlalchemy import Executable, Result, delete, select

import mp2i.database.executor as database_executor
from mp2i.cogs.sanctions._editor import SanctionEditorModal
from mp2i.cogs.sanctions._logs import log_sanction
from mp2i.database.models.member import MemberModel
from mp2i.database.models.sanction import SanctionModel, SanctionType
from mp2i.utils.discord import has_any_role, has_any_roles_predicate
from mp2i.utils.paginator import EmbedPaginator
from mp2i.wrappers.guild import GuildWrapper

from ._warn import WarnModal

logger: logging.Logger = logging.getLogger(__name__)


@guild_only()
class Sanction(GroupCog, name="sanction", description="Gestion des sanctions"):
    def __init__(self, bot: Bot) -> None:
        """
        Add context menu to command tree

        Parameters
        ----------
        bot : Bot
            The bot instance
        """
        self._bot = bot
        ctx_menu: ContextMenu = ContextMenu(
            name="Avertir l'utilisateur",
            callback=self.warn_context,
            type=discord.AppCommandType.user,
        )
        ctx_menu.guild_only = True
        ctx_menu.add_check(
            lambda interaction: has_any_roles_predicate(
                interaction, "Administrateur", "Modérateur"
            )
        )
        bot.tree.add_command(ctx_menu)

    async def _warn_user(
        self, interaction: discord.Interaction, member: discord.Member, ephemeral: bool
    ) -> None:
        """
        Send a modal to fill a warning

        Parameters
        ----------
        discord : discord.Interaction
            The interaction that lead to the warning

        member : discord.Member
            The member to warn

        ephemeral : bool
            Should output be ephemeral
        """
        if member.bot:
            await interaction.response.send_message(
                "Il n'est pas possible d'avertir un bot.", ephemeral=True
            )
            return
        await interaction.response.send_modal(WarnModal(member, ephemeral))

    async def warn_context(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """
        Context to warn a user

        Parameters
        ----------
        interaction : discord.Interaction
            The context menu

        member : discord.Member
            The member to warn
        """
        await self._warn_user(interaction, member, True)

    @command(name="warn", description="Avertir un membre")
    @describe(member="Membre à avertir")
    @rename(member="membre")
    @has_any_role("Administrateur", "Modérateur")
    async def warn_command(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """
        Command to warn a user

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command

        member : discord.Membr
            The member to warn
        """
        await self._warn_user(interaction, member, False)

    @command(name="list", description="Liste les sanctions")
    @describe(user="Utilisateur concerné", type="Type de sanctions")
    @rename(user="utilisateur")
    @has_any_role("Administrateur", "Modérateur")
    async def list_command(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.User],
        type: Optional[SanctionType],
    ):
        if not interaction.guild:
            return
        await interaction.response.defer()
        statement: Executable = select(SanctionModel).where(
            SanctionModel.guild_id == interaction.guild.id
        )
        if user:
            # Join the related MemberModel (victim) and filter on the member's user_id
            statement = statement.join(SanctionModel.victim).where(
                MemberModel.user_id == user.id
            )
        if type:
            statement = statement.where(SanctionModel.sanction_type == type)
        result: Optional[Result[SanctionModel]] = database_executor.execute(statement)
        if not result:
            await interaction.edit_original_response(
                content="Aucune réponse de la base de données."
            )
            return
        sanctions: Sequence[SanctionModel] = result.scalars().all()
        entries: List[str] = []
        content: str = ""
        for sanction in sanctions:
            content = f"**{sanction.sanction_id}** ━ Le {sanction.sanction_date:%d/%m/%Y à %H:%M}\n\n"
            content += f"**Type :** {sanction.sanction_type.value[0]}\n"

            victim: Optional[discord.Member] = interaction.guild.get_member(
                sanction.victim.user_id
            )
            content += f"**Membre :** {victim.mention if victim else sanction.victim.user_id}\n"
            if sanction.sanction_duration:
                content += f"**Temps :** {sanction.sanction_duration}\n"

            if sanction.staff:
                staff: Optional[discord.Member] = interaction.guild.get_member(
                    sanction.staff.user_id
                )
                content += f"**Modérateur :** {staff.mention if staff else sanction.staff.user_id}\n"
            if sanction.sanction_reason:
                content += f"**Raison :** ```yml\n{sanction.sanction_reason}```\n"
            content += "\n"
            entries.append(content)

        await EmbedPaginator(
            author=interaction.user.id,
            title="Liste des sanctions",
            header=f"Nombre de sanctions {len(sanctions)}",
            entries=entries,
            colour=0xFF00FF,
        ).send(interaction)

    @command(name="edit", description="Édite une sanction")
    @describe(id="Sanction concernée")
    @rename(id="identifiant")
    @has_any_role("Administrateur", "Modérateur")
    async def edit_command(
        self,
        interaction: discord.Interaction,
        id: int,
    ):
        if not interaction.guild:
            return
        result: Optional[Result[SanctionModel]] = database_executor.execute(
            select(SanctionModel).where(SanctionModel.sanction_id == id)
        )
        if not result or not (sanction := result.scalar_one_or_none()):
            await interaction.response.send_message(
                "Aucune sanction n'a été trouvé avec cet identifiant."
            )
            return
        await interaction.response.send_modal(SanctionEditorModal(sanction))

    @command(name="remove", description="Retire une sanction")
    @describe(id="Identifiant de la sanction")
    @rename(id="identifiant")
    @has_any_role("Administrateur", "Modérateur")
    async def remove_command(
        self,
        interaction: discord.Interaction,
        id: int,
    ):
        """
        Remove a sanction from database

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command

        id : int
            The id of the concerned sanction
        """
        if not interaction.guild:
            return
        guild: GuildWrapper = GuildWrapper(interaction.guild, fetch=False)
        sanction_channel: Optional[discord.TextChannel] = guild.sanctions_channel
        if not sanction_channel:
            await interaction.response.send_message(
                "Aucun salon de journal de sanctions n'a été trouvé.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        result: Optional[Result[SanctionModel]] = database_executor.execute(
            select(SanctionModel).where(SanctionModel.sanction_id == id)
        )
        if not result or not result.scalar_one_or_none():
            await interaction.edit_original_response(
                content="Aucune sanction n'a été trouvé avec cet identifiant."
            )
            return
        database_executor.execute(
            delete(SanctionModel).where(SanctionModel.sanction_id == id)
        )
        await sanction_channel.send(
            f"La sanction #{id} a été supprimée par {interaction.user.mention}",
            allowed_mentions=discord.AllowedMentions.none(),
        )
        await interaction.edit_original_response(content=f"Sanction #{id} supprimée.")

    @Cog.listener("on_audit_log_entry_create")
    async def on_new_log(self, entry: discord.AuditLogEntry):
        if not (
            entry.action == discord.AuditLogAction.ban
            or entry.action == discord.AuditLogAction.unban
            or entry.action == discord.AuditLogAction.member_update
            or entry.action == discord.AuditLogAction.kick
        ):
            return

        target = entry.target
        if not target or not isinstance(target.id, int):
            return

        victim: discord.User
        try:
            victim = await self._bot.fetch_user(target.id)
        except discord.NotFound:
            logger.error(
                f"Failed to fetch user {target.id} ! Cannot log their sanction."
            )
            return
        staff: Optional[discord.Member | discord.User] = entry.user
        if not staff or not isinstance(staff, discord.Member):
            return

        if entry.action == discord.AuditLogAction.ban:
            await log_sanction(
                entry.guild, victim, staff, SanctionType.BAN, True, entry.reason
            )
        elif entry.action == discord.AuditLogAction.unban:
            await log_sanction(entry.guild, victim, staff, SanctionType.UNBAN, True)
        elif entry.action == discord.AuditLogAction.kick:
            await log_sanction(
                entry.guild, victim, staff, SanctionType.KICK, True, entry.reason
            )
        elif entry.action == discord.AuditLogAction.member_update and (
            hasattr(entry.before, "timed_out_until")
            and hasattr(entry.after, "timed_out_until")
            and entry.before.timed_out_until
            and not entry.after.timed_out_until
        ):
            await log_sanction(
                entry.guild, victim, staff, SanctionType.UNTIMEOUT, True, entry.reason
            )
        elif entry.action == discord.AuditLogAction.member_update and (
            hasattr(entry.before, "timed_out_until")
            and hasattr(entry.after, "timed_out_until")
            and (
                not entry.before.timed_out_until
                and entry.after.timed_out_until
                or entry.before.timed_out_until
                and entry.before.timed_out_until < entry.after.timed_out_until
            )
        ):
            end_of_sanction: int = entry.after.timed_out_until.timestamp()
            duration: int = int(
                ceil(end_of_sanction - datetime.datetime.now().timestamp())
            )
            await log_sanction(
                entry.guild,
                victim,
                staff,
                SanctionType.TIMEOUT,
                True,
                entry.reason,
                duration,
            )


async def setup(bot: Bot) -> None:
    """
    Setting up Sanction

    Parameters
    ----------
    bot : Bot
        The bot instance
    """
    await bot.add_cog(Sanction(bot))
