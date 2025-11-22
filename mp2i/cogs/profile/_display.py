from typing import Iterator, List

import discord
import discord.ui as ui

from mp2i.database.models.promotion import PromotionModel
from mp2i.database.models.school import SchoolType
from mp2i.utils.discord import has_any_roles_predicate
from mp2i.wrappers.guild import GuildWrapper
from mp2i.wrappers.member import MemberWrapper

from ._editor import ProfileEditorView


class ProfileModifyButton(ui.Button["ProfileView"]):
    """
    Button to begin modification on profile
    """

    def __init__(self, member: discord.Member):
        """
        Initialize parent classes and variables

        Parameters
        ----------
        member : discord.Member
            Concerned member
        """
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="Modifier le profil",
            emoji="🔧",
            custom_id="profile::editor",
        )
        self._member = member

    async def callback(self, interaction: discord.Interaction) -> None:
        """
        Send editor view when clicking on the button

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction with the button
        """
        if not interaction.guild:
            return
        if interaction.user.id != self._member.id and not has_any_roles_predicate(
            interaction, "Administrateur", "Modérateur"
        ):
            await interaction.response.send_message(
                "Vous ne pouvez pas interagir avec ce profil.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            view=ProfileEditorView(
                GuildWrapper(interaction.guild, fetch=False),
                MemberWrapper(self._member),
            ),
            ephemeral=True,
        )


class ProfileView(ui.LayoutView):
    """
    View of a profile
    """

    def __init__(self, member: discord.Member, editable: bool) -> None:
        """
        Initialize parent classes and create container of the view

        Parameters
        ----------
        member : discord.Member
            Concerned member

        editable : bool
            Rather or not showing the modification button
        """
        super().__init__()
        member_wrapper: MemberWrapper = MemberWrapper(member)
        container: ui.Container = ui.Container()
        container.add_item(
            ui.Section(
                ui.TextDisplay(f"# {member.name}"),
                ui.TextDisplay("### Pseudo"),
                ui.TextDisplay(f"{member.mention}"),
                accessory=ui.Thumbnail(member.display_avatar.url),
            )
        )
        container.add_item(ui.Separator())
        container.add_item(
            ui.TextDisplay(
                "### Membre depuis\n<t:"
                + f"{round(member.joined_at.timestamp()) if member.joined_at else 0}:F>"
            )
        )
        container.add_item(
            ui.TextDisplay(f"### Messages\n{member_wrapper.message_count}")
        )
        roles: Iterator[discord.Role] = reversed(member.roles[1:])
        container.add_item(
            ui.TextDisplay(
                f"### Rôles\n{' '.join(map(lambda role: role.mention, roles))}"
            )
        )

        if len(member_wrapper.promotions) > 0:
            container.add_item(ui.Separator())

            cpge: List[PromotionModel] = sorted(
                filter(
                    lambda prom: prom.school.school_type == SchoolType.CPGE,
                    member_wrapper.promotions,
                ),
                key=lambda prom: (prom.promotion_year, prom.school.school_name),
            )

            if len(list(cpge)) > 0:
                container.add_item(ui.TextDisplay("### CPGE"))
                for promotion in cpge:
                    container.add_item(
                        ui.TextDisplay(
                            f"{promotion.school.school_name}"
                            + (
                                f" ({promotion.promotion_year})"
                                if promotion.promotion_year
                                else ""
                            )
                        )
                    )

            ecole: List[PromotionModel] = sorted(
                filter(
                    lambda prom: prom.school.school_type == SchoolType.ECOLE,
                    member_wrapper.promotions,
                ),
                key=lambda prom: (prom.promotion_year, prom.school.school_name),
            )
            if len(list(ecole)) > 0:
                container.add_item(ui.TextDisplay("### Post-CPGE"))
                for promotion in ecole:
                    container.add_item(
                        ui.TextDisplay(
                            f"{promotion.school.school_name}"
                            + (
                                f" ({promotion.promotion_year})"
                                if promotion.promotion_year
                                else ""
                            )
                        )
                    )

        if editable:
            container.add_item(ui.Separator(visible=False))
            container.add_item(ui.Separator())
            container.add_item(ui.Separator(visible=False))
            container.add_item(ui.ActionRow(ProfileModifyButton(member)))

        container.accent_colour = member_wrapper.profile_colour or member.colour

        self.add_item(container)
