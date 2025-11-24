from typing import Optional

import discord
import discord.ui as ui
from sqlalchemy import update

import mp2i.database.executor as database_executor
from mp2i.database.models.sanction import SanctionModel
from mp2i.wrappers.guild import GuildWrapper


class SanctionEdited(ui.LayoutView):
    def __init__(
        self,
        sanction: SanctionModel,
        new_reason: str,
        staff: Optional[discord.Member] = None,
        dm_sent: bool = True,
    ):
        container: ui.Container = ui.Container()
        container.add_item(ui.TextDisplay("## Modification de sanction"))
        container.add_item(
            ui.TextDisplay(
                f"La sanction d'identifiant `{sanction.sanction_id}` créée le <t:{round(sanction.sanction_date.timestamp())}"
                + "a vu sa sanction être modifiée"
                + (
                    (
                        f"par {staff.mention}"
                        + (" et l'utilisateur a été averti." if dm_sent else ".")
                    )
                    if staff
                    else "."
                )
            )
        )
        container.add_item(
            ui.TextDisplay(f"Ancienne raison :\n```yml{sanction.reason}\n```")
        )
        container.add_item(
            ui.TextDisplay(f"Nouvelle raison :\n```yml{new_reason}\n```")
        )

        container.accent_colour = sanction.sanction_type.get_colour
        self.add_item(container)


class SanctionEditorModal(ui.Modal):
    """
    Modal to edit the reason of a sanction
    """

    def __init__(self, sanction: SanctionModel) -> None:
        super().__init__(title=f"Éditer sanction #{sanction.sanction_id}")
        self._sanction = sanction
        self._reason = ui.TextInput(
            label="Raison", required=True, style=discord.TextStyle.long, max_length=1024
        )
        self._dm = ui.Select(
            placeholder="Avertir en message privé",
            options=[
                discord.SelectOption(label="Oui", value="True", default=True),
                discord.SelectOption(label="Non", value="False"),
            ],
        )
        self.add_item(self._reason)
        self.add_item(ui.Label(text="Avertir en message privé", component=self._dm))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        dm_sent: bool = bool(self._dm.values[0])
        member: Optional[discord.Member] = interaction.guild.get_member(
            self._sanction.victim.user_id
        )
        if not member:
            dm_sent = False
        else:
            try:
                await member.send(
                    view=SanctionEdited(self._sanction, self._reason.value)
                )
            except discord.Forbidden:
                dm_sent = False
        guild: GuildWrapper = GuildWrapper(interaction.guild, fetch=False)
        channel: Optional[discord.TextChannel] = guild.sanctions_channel
        if channel:
            await channel.send(
                view=SanctionEdited(
                    self._sanction, self._reason.value, interaction.user, dm_sent
                )
            )
        database_executor.execute(
            update(SanctionModel)
            .values(sanction_reason=self._reason.value)
            .where(SanctionModel.sanction_id == self._sanction.sanction_id)
        )
        await interaction.response.send_message(
            "Sanction modifiée.",
            allowed_mentions=discord.AllowedMentions.none(),
        )
