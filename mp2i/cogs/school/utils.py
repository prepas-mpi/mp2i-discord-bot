from typing import Any, List, Optional, Tuple

import discord
import discord.ui as ui
from discord.app_commands import autocomplete, command, describe, guild_only, rename
from discord.ext.commands import Bot, Cog
from discord.member import Member
from sqlalchemy import Executable, Result, select

import mp2i.database.executor as database_executor
from mp2i.database.models.member import MemberModel
from mp2i.database.models.promotion import PromotionModel
from mp2i.database.models.school import SchoolModel, SchoolType
from mp2i.utils.paginator import ComponentsPaginator

from .school import _autocomplete_schools_name, _find_school


class SchoolCmdUtils(Cog):
    """
    Some useful command for schools
    """

    def _get_emoji_by_status(self, member: discord.Member) -> Optional[discord.Emoji]:
        return discord.utils.get(member.guild.emojis, name=member.status.name)

    @command(name="members", description="Affiche la liste des membres d'une école")
    @describe(name="Nom de l'établissement")
    @autocomplete(name=_autocomplete_schools_name)
    @rename(name="nom")
    @guild_only()
    async def get_members(self, interaction: discord.Interaction, name: str) -> None:
        guild: Optional[discord.Guild] = interaction.guild
        if not guild:
            return
        await interaction.response.defer()

        if not (school := await _find_school(interaction, name)):
            return

        result: Optional[Result[MemberModel]] = database_executor.execute(
            select(MemberModel)
            .add_columns(PromotionModel.promotion_year)
            .join(PromotionModel, full=True)
            .where(PromotionModel.school_id == school.school_id)
            .distinct()
        )
        if not result:
            await interaction.response.send_message(
                "Impossible de récupérer la base de données."
            )
            return

        members: List[Tuple[MemberModel, Optional[Member], int]] = list(
            map(
                lambda model: (model[0], guild.get_member(model[0].user_id), model[1]),
                result.all(),
            )
        )
        title: str = "## Membres de l'établissement " + school.school_name
        referent: Optional[str] = None
        entries: List[ui.Item[Any]] = []
        for model, member, year in members:
            if not member:
                continue
            text: str = f" `{member.name}`・{member.mention}・{year}"
            if model.member_id == school.referent_id:
                referent = text + f" {self._get_emoji_by_status(member)}"
                continue
            entries.append(ui.TextDisplay(text))
        title += f"\n**Nombre d'étudiants** {len(entries) + (1 if referent else 0)}"
        if referent:
            title += f"\n**Référent** {referent}"
        await ComponentsPaginator(
            author=interaction.user.id,
            title=title,
            entries=entries,
        ).send(interaction)

    @command(name="referents", description="Affiche la liste des référents")
    @describe(type="Type d'établissement")
    @guild_only()
    async def get_referents(
        self, interaction: discord.Interaction, type: Optional[SchoolType]
    ) -> None:
        """
        Get a list of referents globally or for a specific kind of school

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command

        type : Optional[SchoolType]
            The kind of school to see, None if no kind desired
        """
        guild: Optional[discord.Guild] = interaction.guild
        if not guild:
            return
        await interaction.response.defer()

        statement: Executable = select(SchoolModel).where(
            SchoolModel.guild_id == guild.id, SchoolModel.referent
        )
        if type:
            statement = statement.where(SchoolModel.school_type == type)

        result: Optional[Result[SchoolModel]] = database_executor.execute(statement)

        if not result:
            await interaction.response.send_message(
                "Impossible de récupérer la base de données."
            )
            return

        schools: List[Tuple[SchoolModel, Optional[discord.Member]]] = list(
            map(
                lambda school: (school, guild.get_member(school.referent.user_id)),
                result.scalars(),
            )
        )

        entries: List[ui.Item[Any]] = []
        for school, member in schools:
            if not member:
                continue
            entries.append(
                ui.TextDisplay(
                    f" * **{school.school_name}**・{member.mention}・`{member.name}` {self._get_emoji_by_status(member)}"
                )
            )
        await ComponentsPaginator(
            author=interaction.user.id,
            title=f"## Référents {type.value if type else ''}",
            entries=entries,
        ).send(interaction)


async def setup(bot: Bot) -> None:
    await bot.add_cog(SchoolCmdUtils())
