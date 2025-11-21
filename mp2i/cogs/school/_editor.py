import logging
from typing import List, Optional

import discord
import discord.ui as ui
from sqlalchemy import Result, select, update

import mp2i.database.executor as database_executor
from mp2i.database.models.school import SchoolModel, SchoolType
from mp2i.wrappers.guild import GuildWrapper
from mp2i.wrappers.member import MemberWrapper

logger: logging.Logger = logging.getLogger(__name__)


async def _remove_old_referent(
    interaction: discord.Interaction, guild: GuildWrapper, school: SchoolModel
) -> Optional[discord.Role]:
    """
    Remove referent from a school

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction leading to the call of this function

    guild : GuildWrapper
        Wrapper of the guild

    school : SchoolModel
        The concerned school

    Returns
    -------
    Optional[discord.Role]
        The role of the referent if found and all went well
    """
    role_name: str = "Référent " + (
        "CPGE" if school.school_type == SchoolType.CPGE else "École"
    )
    roles: List[discord.Role] = guild.mapping_roles([role_name])

    if len(roles) == 0:
        logger.error("Référent %s is not defined for guild %d", role_name, guild.id)
        await interaction.response.send_message(
            "Le rôle de référent n'est pas défini pour ce type d'école.",
            ephemeral=True,
        )
        return None
    role: discord.Role = roles[0]

    if school.referent:
        old_referent: Optional[discord.Member] = guild.get_member(
            school.referent.user_id
        )
        if old_referent:
            try:
                await old_referent.remove_roles(role)
            except Exception:
                logger.error(
                    "Could not remove %s role from user %d.",
                    role.name,
                    old_referent.id,
                )
    return role


class SchoolNameModal(ui.Modal, title="Entrez un nouveau nom"):
    """
    Modal to get school's new name
    """

    name: ui.TextInput = ui.TextInput(
        label="Nom", style=discord.TextStyle.short, required=True, max_length=255
    )

    def __init__(self, settings: "SchoolSettings", school: SchoolModel) -> None:
        """
        Initialize parent classes and variables

        Parameters
        ----------
        settings : SchoolSettings
            The LayoutView to refresh

        school : SchoolModel
            The school to be updated
        """
        super().__init__()
        self._settings: "SchoolSettings" = settings
        self._school: SchoolModel = school

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """
        Check if the new name is not already taken and apply modification

        Parameters
        ----------
        interaction : discord.Interaction
            The submit of the modal
        """
        result: Optional[Result[SchoolModel]] = database_executor.execute(
            select(SchoolModel).where(
                SchoolModel.guild_id == self._school.guild_id,
                SchoolModel.school_name == self.name.value,
            )
        )

        if not result:
            await interaction.response.send_message(
                "Impossible de contacter la base de données.", ephemeral=True
            )
            return
        if result.scalar_one_or_none():
            await interaction.response.send_message(
                "Un établissement avec ce nom existe déjà.", ephemeral=True
            )
            return
        database_executor.execute(
            update(SchoolModel)
            .where(
                SchoolModel.school_id == self._school.school_id,
            )
            .values(school_name=self.name.value)
        )
        self._school.school_name = self.name.value
        self._settings._refresh_settings()
        logger.info(
            "User %d has changed name of school %d to user %s.",
            interaction.user.id,
            self._school.school_id,
            self.name.value,
        )
        await interaction.response.edit_message(
            view=self._settings, allowed_mentions=discord.AllowedMentions.none()
        )


class SchoolNameButton(ui.Button["SchoolSettings"]):
    """
    Button to trigger a modal to get user's input
    """

    def __init__(self, school: SchoolModel) -> None:
        """
        Initialize parent classes and variables

        Parameters
        ----------
        settings : SchoolSettings
            The LayoutView to refresh

        school : SchoolModel
            The school to be updated
        """
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="Changer le nom",
            custom_id="school::settings::name",
            emoji="✏️",
        )
        self._school: SchoolModel = school

    async def callback(self, interaction: discord.Interaction) -> None:
        """
        Send modal when user want to modify school's name

        Parameters
        ----------
        interaction : discord.Interaction
            The button interaction
        """
        if not self._view:
            return
        await interaction.response.send_modal(SchoolNameModal(self._view, self._school))


class SchoolThreadSelector(ui.ChannelSelect["SchoolSettings"]):
    """
    Selector to choose a public thread as thread for a school
    """

    def __init__(self, school: SchoolModel):
        """
        Initialize parent classes and variables

        Parameters
        ----------
        settings : SchoolSettings
            The LayoutView to refresh

        school : SchoolModel
            The school to be updated
        """
        super().__init__(
            placeholder="Choisissez un fil de discussion",
            channel_types=[discord.ChannelType.public_thread],
        )
        self._school: SchoolModel = school

    async def callback(self, interaction: discord.Interaction) -> None:
        """
        Change school's thread according to the user's selection

        Parameters
        ----------
        interaction : discord.Interaction
            The selection interaction
        """
        if not self._view:
            return
        database_executor.execute(
            update(SchoolModel)
            .where(
                SchoolModel.school_id == self._school.school_id,
            )
            .values(thread_id=self.values[0].id)
        )
        self._school.thread_id = self.values[0].id
        self._view._refresh_settings()
        logger.info(
            "User %d has changed thread of school %d to thread %d.",
            interaction.user.id,
            self._school.school_id,
            self.values[0].id,
        )
        await interaction.response.edit_message(
            view=self._view, allowed_mentions=discord.AllowedMentions.none()
        )


class SchoolReferentButton(ui.Button["SchoolSettings"]):
    """
    Button to remove referent from school
    """

    def __init__(
        self, guild: GuildWrapper, settings: "SchoolSettings", school: SchoolModel
    ) -> None:
        """
        Initialize parent classes and variables

        Parameters
        ----------
        guild : GuildWrapper
            The wrapper on the guild which has the registered school

        settings : SchoolSettings
            The LayoutView to refresh

        school : SchoolModel
            The school to be updated
        """
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="Retirer référent",
            custom_id="school::settings::rmrf",
            emoji="❌",
        )
        self._guild: GuildWrapper = guild
        self._school: SchoolModel = school

    async def callback(self, interaction: discord.Interaction) -> None:
        """
        User want to remove school's referent

        Parameters
        ----------
        interaction : discord.Interaction
            The button interaction
        """
        if not self._view:
            return
        if not self._school.referent:
            await interaction.response.send_message(
                "Cet établissement n'a pas de référent.", ephemeral=True
            )
            return
        role_name: str = "Référent " + (
            "CPGE" if self._school.school_type == SchoolType.CPGE else "École"
        )
        roles: List[discord.Role] = self._guild.mapping_roles([role_name])

        if len(roles) == 0:
            logger.error(
                "Référent %s is not defined for guild %d", role_name, self._guild.id
            )
            await interaction.response.send_message(
                "Le rôle de référent n'est pas défini pour ce type d'école.",
                ephemeral=True,
            )
            return

        role: Optional[discord.Role] = await _remove_old_referent(
            interaction, self._guild, self._school
        )
        if not role:
            return
        database_executor.execute(
            update(SchoolModel)
            .where(
                SchoolModel.school_id == self._school.school_id,
            )
            .values(referent_id=None)
        )
        self._school.referent_id = None
        self._school.referent = None
        self._view._refresh_settings()
        logger.info(
            "User %d has removed referent of school %d.",
            interaction.user.id,
            self._school.school_id,
        )
        await interaction.response.edit_message(
            view=self._view, allowed_mentions=discord.AllowedMentions.none()
        )


class SchoolReferentSelector(ui.UserSelect["SchoolSettings"]):
    """
    Select a new referent
    """

    def __init__(self, guild: GuildWrapper, school: SchoolModel):
        """
        Initialize parent classes and variables

        Parameters
        ----------
        guild : GuildWrapper
            The wrapper on the guild which has the registered school

        settings : SchoolSettings
            The LayoutView to refresh

        school : SchoolModel
            The school to be updated
        """
        super().__init__(
            placeholder="Choisissez un référent",
        )
        self._guild: GuildWrapper = guild
        self._school: SchoolModel = school

    async def callback(self, interaction: discord.Interaction) -> None:
        """
        Change school's thread according to the user's selection

        Parameters
        ----------
        interaction : discord.Interaction
            The selection interaction
        """
        if not self._view:
            return
        member: discord.Member | discord.User = self.values[0]
        if member.bot:
            await interaction.response.send_message(
                "Un bot ne peut pas être référent.", ephemeral=True
            )
            return
        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "Cet utilisateur n'est pas sur le serveur.", ephemeral=True
            )
            return
        member_wrapper: MemberWrapper = MemberWrapper(member)
        if member_wrapper.member_id == self._school.referent_id:
            await interaction.response.send_message(
                "Cet utilisateur est déjà référent de cet établissement.",
                ephemeral=True,
            )
            return

        matching_schools: List[SchoolModel] = list(
            filter(
                lambda prom: prom.school_id == self._school.school_id,
                member_wrapper.promotions,
            )
        )
        if len(matching_schools) == 0:
            await interaction.response.send_message(
                "Cet utilisateur n'a jamais été dans cet établissement, il ne peut donc être référent de ce-dernier.",
                ephemeral=True,
            )
            return

        role: Optional[discord.Role] = await _remove_old_referent(
            interaction, self._guild, self._school
        )
        if not role:
            return

        database_executor.execute(
            update(SchoolModel)
            .where(
                SchoolModel.school_id == self._school.school_id,
            )
            .values(referent_id=member_wrapper.member_id)
        )
        self._school.referent_id = member_wrapper.member_id
        self._school.referent = member_wrapper.as_model
        try:
            await member_wrapper.add_roles(role)
        except Exception:
            logger.error(
                "Could not add %s role to user %d.", role.name, member_wrapper.id
            )
        self._view._refresh_settings()
        logger.info(
            "User %d has changed referent of school %d to user %d.",
            interaction.user.id,
            self._school.school_id,
            member_wrapper.id,
        )
        await interaction.response.edit_message(
            view=self._view, allowed_mentions=discord.AllowedMentions.none()
        )


class SchoolSettings(ui.LayoutView):
    """
    Layout of the settings panel for school
    """

    def __init__(self, guild: GuildWrapper, school: SchoolModel) -> None:
        """
        Initialize parent classes and variables

        Parameters
        ----------
        guild : GuildWrapper
            The wrapper on the guild which has the registered school

        school : SchoolModel
            The school to be updated
        """
        super().__init__(timeout=120)
        self._guild = guild
        self._school = school
        self._refresh_settings()

    def _refresh_settings(self) -> None:
        """
        Remove previous children and add fresh ones
        """
        for child in self.children:
            self.remove_item(child)
        channel: Optional[discord.Thread] = self._guild.get_any_channel(
            self._school.thread_id, discord.Thread
        )
        container: ui.Container = ui.Container()
        container.add_item(ui.TextDisplay("## Édition de l'établissement"))
        container.add_item(
            ui.Section(
                ui.TextDisplay(f"### Nom actuel\n{self._school.school_name}"),
                accessory=SchoolNameButton(self._school),
            )
        )
        container.add_item(ui.TextDisplay(f"### Identifiant\n{self._school.school_id}"))
        container.add_item(
            ui.TextDisplay(f"### Type\n{self._school.school_type.value}")
        )
        container.add_item(
            ui.TextDisplay(
                "### Fil associé\n"
                + (channel.jump_url if channel else "Aucun salon associé")
            )
        )
        referent: Optional[discord.Member] = None
        if self._school.referent:
            referent = self._guild.get_member(self._school.referent.user_id)

        if referent:
            container.add_item(
                ui.Section(
                    ui.TextDisplay(f"### Référent actuel\n{referent.mention}"),
                    accessory=SchoolReferentButton(self._guild, self, self._school),
                )
            )
        else:
            container.add_item(ui.TextDisplay("### Référent actuel\nAucun"))
        self.add_item(container)
        self.add_item(ui.ActionRow(SchoolThreadSelector(self._school)))
        self.add_item(ui.ActionRow(SchoolReferentSelector(self._guild, self._school)))
