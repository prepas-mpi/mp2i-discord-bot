import discord
import discord.ui as ui

from mp2i.database.models.sanction import SanctionType

from ._logs import log_sanction


class WarnModal(ui.Modal):
    """
    Modal to fill the warning
    """

    def __init__(self, member: discord.Member, ephemeral: bool) -> None:
        super().__init__(title=f"Avertir {member.name}")
        self._member = member
        self._ephemeral = ephemeral
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
        await log_sanction(
            interaction.guild,
            self._member._user,
            interaction.user,
            SanctionType.WARN,
            bool(self._dm.values[0] == "True"),
            self._reason.value,
        )
        await interaction.response.send_message(
            f"{self._member.mention} a été averti.",
            ephemeral=self._ephemeral,
            allowed_mentions=discord.AllowedMentions.none(),
        )
