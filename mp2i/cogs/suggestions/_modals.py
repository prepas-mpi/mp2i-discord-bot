from typing import Any, Callable, Optional

import discord
import discord.ui as ui

from mp2i.database.models.suggestion import SuggestionModel, SuggestionStatus


class SuggestionCreateModal(ui.Modal):
    """
    Modal to fill the suggestion
    """

    def __init__(
        self,
        callback: Callable[[discord.Member, str, str], Any],
    ) -> None:
        """
        Initialize the modal

        Parameters
        ----------
        callback : Callable[[discord.Member, str, str], Any]
            Function to call for creating a suggestion
        """
        super().__init__(title="Proposer une suggestion")
        self._callback = callback
        self._title = ui.TextInput(
            label="Donnez un titre",
            required=True,
            style=discord.TextStyle.short,
            max_length=255,
        )
        self._description = ui.TextInput(
            label="Développez votre idée",
            required=True,
            style=discord.TextStyle.long,
            min_length=30,
            max_length=3072,
        )
        self.add_item(self._title)
        self.add_item(self._description)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """
        Modal is filled

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction with the modal
        """
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        await interaction.response.send_message(
            "Suggestion en cours de création.", ephemeral=True
        )
        await self._callback(
            interaction.user, self._title.value, self._description.value
        )
        await interaction.edit_original_response(content="Suggestion créée.")


class SuggestionCloseModal(ui.Modal):
    """
    Modal to fill the suggestion
    """

    def __init__(
        self,
        suggestion: SuggestionModel,
        callback: Callable[
            [SuggestionModel, discord.Member, SuggestionStatus, Optional[str]], Any
        ],
    ) -> None:
        """
        Initialize the modal

        Parameters
        ----------
        suggestion : SuggestionModel
            The concerned suggestion

        callback : Callable[[SuggestionModel, discord.Member, SuggestionStatus, Optional[str]], Any]
            Function to call for closing a suggestion
        """
        super().__init__(title="Clôturer une suggestion")
        self._suggestion = suggestion
        self._callback = callback
        self._status = ui.Select(
            placeholder="Choisir un nouveau statut",
            options=[
                discord.SelectOption(label=status.name, value=status.name)
                for status in [
                    SuggestionStatus.CLOSED,
                    SuggestionStatus.ACCEPTED,
                    SuggestionStatus.REJECTED,
                ]
            ],
        )
        self._reason = ui.TextInput(
            label="Donnez une raison",
            required=False,
            style=discord.TextStyle.long,
            max_length=500,
        )
        self.add_item(ui.Label(text="Nouveau statut", component=self._status))
        self.add_item(self._reason)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """
        Modal is filled

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction with the modal
        """
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return
        await interaction.response.send_message(
            "Suggestion en cours de fermeture.", ephemeral=True
        )
        await self._callback(
            self._suggestion,
            interaction.user,
            SuggestionStatus[self._status.values[0]],
            self._reason.value,
        )
        await interaction.edit_original_response(content="Suggestion fermée.")
