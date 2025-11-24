import datetime
from typing import Any, List, Optional

import discord
import discord.ui as ui
from sqlalchemy import Result, select, update

import mp2i.database.executor as database_executor
from mp2i.cogs.school.school import add_member_to_school, remove_member_from_school
from mp2i.database.models.member import MemberModel
from mp2i.database.models.promotion import PromotionModel
from mp2i.database.models.school import SchoolModel
from mp2i.utils.paginator import ComponentsPaginator
from mp2i.wrappers.guild import GuildWrapper
from mp2i.wrappers.member import MemberWrapper


class ProfileEditorChangeColour(ui.Button["ProfileEditorView"]):
    """
    Button to change profile colour
    """

    def __init__(self, member: MemberWrapper):
        """
        Initialize all values

        Parameters
        ----------
        member : MemberWrapper
            The concerned member
        """
        super().__init__(
            label="Changer", custom_id="profile::editor::colour", emoji="🎨"
        )
        self._member: MemberWrapper = member

    async def callback(self, interaction: discord.Interaction) -> None:
        """
        User want to change colour

        Parameters
        ----------
        interaction : discord.Interaction
            The button interaction
        """
        if not self._view:
            return
        await interaction.response.send_modal(
            ProfileEditorChangeColourModal(self._view, self._member)
        )


class ProfileEditorChangeColourModal(ui.Modal, title="Entrez une couleur"):
    """
    Modal to get member's new colour
    """

    colour: ui.TextInput = ui.TextInput(
        label="Couleur (hexadécimale)",
        style=discord.TextStyle.short,
        required=False,
        max_length=8,
    )

    def __init__(self, editor: "ProfileEditorView", member: MemberWrapper) -> None:
        """
        Initialize parent classes and variables

        Parameters
        ----------
        editor : ProfileEditorView
            The LayoutView to refresh

        member : MemberWrapper
            The member to be updated
        """
        super().__init__()
        self._editor: "ProfileEditorView" = editor
        self._member: MemberWrapper = member

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """
        Apply modification if user's input is correct

        Parameters
        ----------
        interaction : discord.Interaction
            The submit of the modal
        """
        str_colour: str = self.colour.value
        try:
            self._member.profile_colour = (
                int(str_colour.removeprefix("#"), 16) if len(str_colour) > 0 else None
            )
        except ValueError:
            await interaction.response.send_message(
                "Vous devez entrer une valeur hexadécimale (ABCDEF ou #ABCDEF ou 0xABCDEF)",
                ephemeral=True,
            )
            return
        database_executor.execute(
            update(MemberModel)
            .values(profile_colour=self._member.profile_colour)
            .where(MemberModel.member_id == self._member.member_id)
        )
        self._editor._refresh_content()
        await interaction.response.edit_message(view=self._editor)


class ProfileEditorRemovePromotion(ui.Button["ProfileEditorView"]):
    """
    Button to remove a promotion (school + user + optional(year))
    """

    def __init__(self, member: MemberWrapper, promotion: PromotionModel):
        """
        Initialize all values

        Parameters
        ----------
        member : MemberWrapper
            The concerned member

        promotion : PromotionModel
            The concerned promotion
        """
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="Retirer",
            custom_id=f"profile::editor::promotion::remove::{promotion.promotion_id}",
        )
        self._member: MemberWrapper = member
        self._promotion: PromotionModel = promotion

    async def callback(self, interaction: discord.Interaction) -> None:
        """
        User want to remove a school

        Parameters
        ----------
        interaction : discord.Interaction
            The button interaction
        """
        if not self._member.as_model or not self._view:
            return
        await remove_member_from_school(interaction, self._member, self._promotion)
        self._member.as_model.promotions = list(
            filter(
                lambda prom: prom.promotion_id != self._promotion.promotion_id,
                self._member.promotions,
            )
        )
        self._view._refresh_content()
        await interaction.response.edit_message(view=self._view)


class ProfileEditorSchoolYear(ui.Select):
    """
    Let user select a year for the promotion
    """

    def __init__(
        self, editor: "ProfileEditorView", member: MemberWrapper, school: SchoolModel
    ):
        """
        Initialize all values

        Parameters
        ----------
        editor : ProfileEditorView
            The initial view to edit profile

        member : MemberWrapper
            The concerned member

        school : SchoolModel
            The concerned school
        """
        super().__init__(
            placeholder="Choisissez une année de promotion",
            options=[discord.SelectOption(label="Non déclarée", value="0")]
            + [
                discord.SelectOption(label=f"{year}", value=f"{year}")
                for year in range(2021, datetime.datetime.now().year + 4)
            ],
            custom_id=f"schools::year::{school.school_id}",
        )
        self._editor: "ProfileEditorView" = editor
        self._member: MemberWrapper = member
        self._school: SchoolModel = school

    async def callback(self, interaction: discord.Interaction) -> None:
        """
        User has selected a year

        Parameters
        ----------
        interaction : discord.Interaction
            The button interaction
        """
        if not self._member.as_model:
            return
        year: Optional[int] = int(self.values[0]) if self.values[0] != "0" else None
        prom: Optional[PromotionModel] = await add_member_to_school(
            interaction, self._member, self._school, year
        )
        self._member.as_model.promotions.append(prom)
        self._editor._refresh_content()
        await interaction.response.edit_message(view=self._editor)


class ProfileEditorAddSchool(ui.Button["ProfileEditorView"]):
    """
    Button to add a school
    """

    def __init__(
        self, editor: "ProfileEditorView", member: MemberWrapper, school: SchoolModel
    ):
        """
        Initialize all values

        Parameters
        ----------
        member : MemberWrapper
            The concerned member
        """
        super().__init__(
            style=discord.ButtonStyle.blurple,
            label="Ajouter",
            custom_id=f"schools::add::{school.school_id}",
        )
        self._editor: "ProfileEditorView" = editor
        self._member: MemberWrapper = member
        self._school: SchoolModel = school

    async def callback(self, interaction: discord.Interaction) -> None:
        """
        User want to add this school

        Parameters
        ----------
        interaction : discord.Interaction
            The button interaction
        """
        if not self._member.as_model or not self._view:
            return
        view: ui.LayoutView = ui.LayoutView()
        view.add_item(
            ui.ActionRow(
                ProfileEditorSchoolYear(self._editor, self._member, self._school)
            )
        )
        await interaction.response.edit_message(view=view)


class ProfileEditorAddPromotion(ui.Button["ProfileEditorView"]):
    """
    Button to add a new promotion
    """

    def __init__(self, member: MemberWrapper):
        """
        Initialize all values

        Parameters
        ----------
        member : MemberWrapper
            The concerned member
        """
        super().__init__(
            style=discord.ButtonStyle.success,
            label="Ajouter",
            custom_id="profile::editor::promotion::add",
            emoji="🏫",
        )
        self._member = member

    async def callback(self, interaction: discord.Interaction) -> None:
        """
        User want to add a school

        Parameters
        ----------
        interaction : discord.Interaction
            The button interaction
        """
        if not self._view:
            return
        await interaction.response.defer(ephemeral=True)
        already_in_schools: List[int] = list(
            map(lambda prom: prom.school_id, self._member.promotions)
        )
        result: Optional[Result[SchoolModel]] = database_executor.execute(
            select(SchoolModel)
            .where(~SchoolModel.school_id.in_(already_in_schools))
            .order_by(SchoolModel.school_name)
        )

        if not result:
            await interaction.response.send_message(
                "Impossible de communiquer avec la base de données"
            )
            return

        entries: List[ui.Item[Any]] = [
            ui.Section(
                ui.TextDisplay(f"{school.school_name} ({school.school_type.value})"),
                accessory=ProfileEditorAddSchool(self._view, self._member, school),
            )
            for school in result.scalars()
        ]

        await ComponentsPaginator(
            author=interaction.user.id,
            title="## Choisissez votre école",
            entries=entries,
            colour=0xFFA636,
            entries_per_page=1,
        ).send(interaction)


class ProfileEditorView(ui.LayoutView):
    """
    General view for profile editing
    """

    def __init__(self, guild: GuildWrapper, member: MemberWrapper):
        """
        Initialize all values

        Parameters
        ----------
        guild : GuildWrapper
            The concerned guild

        member : MemberWrapper
            The concerned member
        """
        super().__init__()
        self._guild: GuildWrapper = guild
        self._member: MemberWrapper = member
        self._refresh_content()

    def _refresh_content(self):
        """
        Refresh all items
        """
        for child in self.children:
            self.remove_item(child)

        container: ui.Container = ui.Container()
        container.add_item(ui.TextDisplay("## Éditeur de profil"))
        container.add_item(
            ui.Section(
                ui.TextDisplay("### Modifier la couleur"),
                accessory=ProfileEditorChangeColour(self._member),
            )
        )

        container.add_item(ui.TextDisplay("### Établissements"))

        for promotion in self._member.promotions:
            container.add_item(
                ui.Section(
                    ui.TextDisplay(promotion.school.school_name),
                    accessory=ProfileEditorRemovePromotion(self._member, promotion),
                )
            )

        if len(self._member.promotions) < self._guild.max_promotions:
            container.add_item(ui.ActionRow(ProfileEditorAddPromotion(self._member)))

        if self._member.profile_colour:
            container.accent_colour = self._member.profile_colour

        self.add_item(container)
