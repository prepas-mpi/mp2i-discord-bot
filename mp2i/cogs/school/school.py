import logging
from typing import List, Optional

import discord
from discord.app_commands import (
    Choice,
    ContextMenu,
    autocomplete,
    command,
    describe,
    rename,
)
from discord.app_commands.errors import MissingAnyRole
from discord.ext.commands import Bot, GroupCog, guild_only
from sqlalchemy import Result, delete, insert, select, update
from sqlalchemy.dialects.postgresql import insert as insert_psql

import mp2i.database.executor as database_executor
from mp2i.database.models.promotion import PromotionModel
from mp2i.database.models.school import SchoolModel, SchoolType
from mp2i.utils.discord import has_any_role, has_any_roles_predicate
from mp2i.wrappers.guild import GuildWrapper
from mp2i.wrappers.member import MemberWrapper

from ._editor import SchoolSettings, _remove_old_referent

logger: logging.Logger = logging.getLogger(__name__)


async def _find_school(
    interaction: discord.Interaction, name: str, invert: bool = False
) -> Optional[SchoolModel]:
    """
    Get school from database if exists and answer to interaction

    Parameters
    ----------
    interaction : discord.Interaction
        The slash command interaction

    name : str
        The school name

    invert : bool
        Answer if found (True) or if not found (False)

    Returns
    -------
    Optional[SchoolModel]
        SchoolModel if found in database, None otherwise
    """
    if not interaction.guild:
        return None
    result: Optional[Result[SchoolModel]] = database_executor.execute(
        select(SchoolModel).where(
            SchoolModel.guild_id == interaction.guild.id,
            SchoolModel.school_name == name,
        )
    )

    if not result:
        await interaction.edit_original_response(
            content="Impossible de contacter la base de données."
        )
        return None
    if (school := result.scalar_one_or_none()) and invert:
        await interaction.edit_original_response(
            content="Une établissement avec ce nom existe déjà."
        )
        return school
    elif not school and not invert:
        await interaction.edit_original_response(
            content="Aucun établissement avec ce nom n'a été trouvé."
        )
        return None
    return school


async def add_member_to_school(
    interaction: discord.Interaction,
    member: MemberWrapper,
    school: SchoolModel,
    year: Optional[int],
) -> Optional[PromotionModel]:
    """
    Add a member to a school with the year

    Parameters
    ----------
    interaction : discord.Interaction
        The initial interaction that lead to this remove

    member : MemberWrapper
        The concerned member

    school : SchoolModel
        The concerned school
    """
    if not interaction.guild:
        return
    guild: GuildWrapper = GuildWrapper(interaction.guild, fetch=False)
    if len(member.promotions) >= guild.max_promotions:
        await interaction.edit_original_response(
            content=f"Pas plus de {guild.max_promotions} promotions."
        )
        return

    result: Optional[Result[PromotionModel]] = database_executor.execute(
        insert_psql(PromotionModel)
        .values(
            school_id=school.school_id,
            member_id=member.member_id,
            promotion_year=year,
        )
        .on_conflict_do_update(
            index_elements=["promotion_id"], set_={"promotion_year": year}
        )
        .returning(PromotionModel)
    )
    if not result:
        return None
    if school.thread_id:
        channel: Optional[discord.Thread] = guild.get_any_channel(
            school.thread_id, discord.Thread
        )
        if channel:
            await channel.add_user(member._boxed)
    return result.scalar()


async def remove_member_from_school(
    interaction: discord.Interaction, member: MemberWrapper, promotion: PromotionModel
) -> None:
    """
    Remove a member from a school with its promotion

    Parameters
    ----------
    interaction : discord.Interaction
        The initial interaction that lead to this remove

    member : MemberWrapper
        The concerned member

    promotion : PromotionModel
        The concerned promotion
    """
    if not interaction.guild:
        return
    if (
        promotion.school.referent
        and promotion.school.referent.member_id == member.member_id
    ):
        logger.info(
            "User %d is no longer referent of school %d",
            member.id,
            promotion.school_id,
        )
        if await _remove_old_referent(
            interaction, GuildWrapper(interaction.guild, fetch=False), promotion.school
        ):
            database_executor.execute(
                update(SchoolModel)
                .values(referent_id=None)
                .where(SchoolModel.school_id == promotion.school_id)
            )

    database_executor.execute(
        delete(PromotionModel).where(
            PromotionModel.promotion_id == promotion.promotion_id
        )
    )


async def _autocomplete_schools_name(
    interaction: discord.Interaction, current: str
) -> List[Choice[str]]:
    """
    Autocomplete for school names

    Parameters
    ----------
    interaction : discord.Interaction
        The slash command concerned

    current : str
        The name written by the member at that time

    Returns
    -------
    List[Choice[str]]
        List of choices
    """
    if not interaction.guild:
        return []
    await interaction.response.defer()

    result: Optional[Result[SchoolModel]] = database_executor.execute(
        select(SchoolModel)
        .where(
            SchoolModel.guild_id == interaction.guild.id,
            SchoolModel.school_name.istartswith(current),
        )
        .order_by(SchoolModel.school_name)
        .limit(20)
    )

    if not result:
        return []

    return [
        Choice(name=school.school_name, value=school.school_name)
        for school in map(lambda row: row.tuple()[0], result.all())
    ]


@guild_only()
class School(GroupCog, name="school", description="Gestion des établissements"):
    """
    Manage schools
    """

    def __init__(self, bot: Bot) -> None:
        """
        Add context menu to command tree

        Parameters
        ----------
        bot : Bot
            The bot instance
        """
        ctx_menu = ContextMenu(
            name="(Dés)épingler un message",
            callback=self.attach_message,
            type=discord.AppCommandType.message,
        )
        ctx_menu.guild_only = True
        bot.tree.add_command(ctx_menu)

    @command(name="create", description="Créer un établissement")
    @describe(
        name="Nom de l'établissement",
        type="Type de l'établissement (CPGE ou ECOLE)",
        thread="Fil de discussion relié à l'établissement",
    )
    @rename(name="nom", thread="fil")
    @has_any_role("Administrateur", "Modérateur")
    async def create_school(
        self,
        interaction: discord.Interaction,
        name: str,
        type: SchoolType,
        thread: Optional[discord.Thread],
    ) -> None:
        """
        Register a new school in database

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command

        name : str
            The name of the future registered school

        thread : Optional[discord.Thread]
            The thread to talk about the school
        """
        if not interaction.guild:
            return

        await interaction.response.defer()

        if await _find_school(interaction, name, True):
            return

        database_executor.execute(
            insert(SchoolModel).values(
                guild_id=interaction.guild.id,
                school_name=name,
                school_type=type,
                thread_id=thread.id if thread else None,
            )
        )

        await interaction.edit_original_response(content=f"Établissement {name} créé.")

    @command(name="delete", description="Supprime un établissement")
    @describe(name="Nom de l'établissement concerné")
    @rename(name="nom")
    @autocomplete(name=_autocomplete_schools_name)
    @has_any_role("Administrateur")
    async def delete_school(self, interaction: discord.Interaction, name: str) -> None:
        """
        Delete a registered school

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command

        name : str
            The name of the school
        """
        if not interaction.guild:
            return

        await interaction.response.defer()

        if not (school := await _find_school(interaction, name)):
            return

        database_executor.execute(
            delete(SchoolModel).where(
                SchoolModel.guild_id == interaction.guild.id,
                SchoolModel.school_id == school.school_id,
            )
        )

        await interaction.edit_original_response(
            content=f"Établissement {school.school_name} supprimé."
        )

    @command(name="edit", description="Modifie un établissement")
    @describe(name="Nom de l'établissement concerné")
    @rename(name="nom")
    @autocomplete(name=_autocomplete_schools_name)
    @has_any_role("Administrateur", "Modérateur")
    async def edit_school(self, interaction: discord.Interaction, name: str) -> None:
        """
        Delete a registered school

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command

        name : str
            The name of the school
        """
        if not interaction.guild:
            return

        await interaction.response.defer(ephemeral=True)

        guild: GuildWrapper = GuildWrapper(interaction.guild, fetch=False)

        if not (school := await _find_school(interaction, name)):
            return
        await interaction.edit_original_response(
            view=SchoolSettings(guild, school),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @command(name="join", description="Rejoindre un établissement")
    @describe(
        name="Nom de l'établissement",
        year="Année de promotion dans l'établissement",
        member="Membre cible",
    )
    @rename(name="nom", year="année", member="membre")
    @autocomplete(name=_autocomplete_schools_name)
    async def join_school(
        self,
        interaction: discord.Interaction,
        name: str,
        year: Optional[int],
        member: Optional[discord.Member],
    ) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if not member:
            member = interaction.user
        await interaction.response.defer()
        if interaction.user.id != member.id:
            try:
                await has_any_roles_predicate(
                    interaction, "Administrateur", "Modérateur"
                )
            except MissingAnyRole:
                await interaction.edit_original_response(
                    content="Vous ne pouvez pas assigner un autre membre que vous à un établissement."
                )
                return

        if not (school := await _find_school(interaction, name)):
            return

        prom: Optional[PromotionModel] = await add_member_to_school(
            interaction, MemberWrapper(member), school, year
        )
        if not prom:
            return

        if interaction.user.id == member.id:
            logger.info("User %d is now part of school %d", member.id, school.school_id)
            await interaction.edit_original_response(
                content=(
                    f"Vous indiquez être ou avoir été élève de {school.school_name}"
                    + (f" promotion {year}." if year else ".")
                )
            )
        else:
            logger.info(
                "User %d declare that user %d now part of school %d",
                interaction.user.id,
                member.id,
                school.school_id,
            )
            await interaction.edit_original_response(
                content=(
                    f"Vous indiquez que {member.mention} est ou a été élève de {school.school_name}"
                    + (f" promotion {year}." if year else ".")
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )

    @command(name="leave", description="Quitter un établissement")
    @describe(
        name="Nom de l'établissement",
        member="Membre cible",
    )
    @rename(name="nom", member="membre")
    @autocomplete(name=_autocomplete_schools_name)
    async def leave_school(
        self,
        interaction: discord.Interaction,
        name: str,
        member: Optional[discord.Member],
    ) -> None:
        """
        Make a member quit a school

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command interaction

        name : str
            The school's name

        member : Optional[discord.Member]
            Member to perform action on if not the author
        """
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        if not member:
            member = interaction.user
        await interaction.response.defer()
        if interaction.user.id != member.id:
            try:
                await has_any_roles_predicate(
                    interaction, "Administrateur", "Modérateur"
                )
            except MissingAnyRole:
                await interaction.edit_original_response(
                    content="Vous ne pouvez pas assigner un autre membre que vous à un établissement."
                )
                return

        if not (school := await _find_school(interaction, name)):
            return

        member_wrapper: MemberWrapper = MemberWrapper(member)
        promotions: List[PromotionModel] = list(
            filter(
                lambda prom: prom.school_id == school.school_id,
                member_wrapper.promotions,
            )
        )
        if len(promotions) == 0:
            await interaction.edit_original_response(
                content="Ne fait pas partie de l'établissement."
            )
            return

        await remove_member_from_school(interaction, member_wrapper, promotions[0])

        if interaction.user.id == member.id:
            logger.info(
                "User %d is no longer part of school %d",
                member.id,
                school.school_id,
            )
            await interaction.edit_original_response(
                content=(
                    f"Vous n'indiquez plus être ou avoir été élève de {school.school_name}"
                )
            )
        else:
            logger.info(
                "User %d declare that user %d is no longer part of school %d",
                interaction.user.id,
                member.id,
                school.school_id,
            )
            await interaction.edit_original_response(
                content=(
                    f"Vous n'indiquez plus que {member.mention} est ou a été élève de {school.school_name}"
                ),
                allowed_mentions=discord.AllowedMentions.none(),
            )

    async def attach_message(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """
        Context menu to attach or detach a message

        Parameters
        ----------
        interaction : discord.Interaction
            Interaction on a message

        message : discord.Message
            Message to perform an action on
        """
        if not interaction.guild:
            return
        await interaction.response.defer(ephemeral=True)
        result: Optional[Result[SchoolModel]] = database_executor.execute(
            select(SchoolModel).where(
                SchoolModel.guild_id == interaction.guild.id,
                SchoolModel.thread_id == message.channel.id,
            )
        )

        if not result:
            logger.error("Could not contact database.")
            await interaction.edit_original_response(
                content="Impossible de vérifier que vous êtes apte à faire cette action"
            )
            return

        matching_school: List[SchoolModel] = list(
            filter(
                lambda school: school.referent
                and school.referent.user_id == interaction.user.id,
                map(lambda row: row.tuple()[0], result.all()),
            )
        )
        if len(matching_school) == 0:
            await interaction.edit_original_response(
                content="Vous ne pouvez pas (dés)épingler un message dans ce salon"
            )
            return
        if message.pinned:
            await message.unpin()
            await interaction.edit_original_response(
                content="Le message a été désépinglé."
            )
        else:
            await message.pin()
            await interaction.edit_original_response(
                content="Le message a été épinglé."
            )


async def setup(bot: Bot) -> None:
    """
    Setting up School

    Parameters
    ----------
    bot : Bot
        The bot instance
    """
    await bot.add_cog(School(bot))
