import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Generic, List, Optional, Tuple, TypeVar

import discord
import discord.ui as ui

logger: logging.Logger = logging.getLogger(__name__)

T = TypeVar("T")


class Paginator(ABC, Generic[T]):
    """
    Abastract paginator
    """

    def __init__(
        self,
        author: int,
        title: str,
        entries: List[T],
        colour: Optional[int] = None,
        entries_per_page: int = 10,
        page: int = 1,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Initialize variables and give timeout to superclass
        """
        super().__init__()
        self.author: int = author
        self.title: str = title
        self.entries: List[T] = entries
        self.colour: Optional[int] = colour
        self.entries_per_page: int = entries_per_page
        self.page: int = page
        self.timestamp: datetime = timestamp or datetime.now()

    @abstractmethod
    def create_embeds_and_view(
        self,
    ) -> Tuple[Optional[discord.Embed], Optional[ui.LayoutView | ui.View]]:
        """
        Create every needed embeds or view for paginator

        Returns
        -------
        Tuple[Optional[discord.Embed], Optional[ui.View]]
            Tuple of a optional embed followed by an optional view
        """
        return (None, None)

    def _create_buttons(self) -> List[ui.Button]:
        """
        Create pagination buttons

        Returns
        -------
        List[ui.Button]
            List of pagination buttons (previous, current page, next)
        """
        prev_button: ui.Button = ui.Button(
            label="◀",
            style=discord.ButtonStyle.secondary,
            custom_id="paginator::prev",
            disabled=self.page == 1,
        )
        indicator: ui.Button = ui.Button(
            label=f"Page {self.page}/{self.max_page_number}",
            style=discord.ButtonStyle.primary,
            custom_id="paginator::indicator",
            disabled=True,
        )
        next_button: ui.Button = ui.Button(
            label="▶",
            style=discord.ButtonStyle.secondary,
            custom_id="paginator::next",
            disabled=self.page == self.max_page_number,
        )

        prev_button.callback = self._on_prev
        next_button.callback = self._on_next

        return [prev_button, indicator, next_button]

    @property
    def max_page_number(self) -> int:
        """
        Get the number of pages

        Returns
        -------
        int
            the number of pages
        """
        if len(self.entries) == 0:
            return 1
        # trick to ceil result of an integer division
        return -(len(self.entries) // -self.entries_per_page)

    async def _update(self, interaction: discord.Interaction) -> None:
        """
        Called by the view when a button is pressed. The `view` argument is the
        instance of the view that triggered this update. This method updates the
        embed contents and updates the view buttons' states/labels before editing
        the message.
        """
        (embed, view) = self.create_embeds_and_view()

        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception:
            try:
                await interaction.edit_original_response(embed=embed, view=view)
            except Exception:
                logger.warning("Could not update paginator")
                pass

    async def _on_prev(self, interaction: discord.Interaction) -> None:
        """
        Action when user click on previous button

        Parameters
        ----------
        interaction : discord.Interaction
            Interaction with the button
        """
        if self.page > 1:
            self.page -= 1
            await self._update(interaction)

    async def _on_next(self, interaction: discord.Interaction) -> None:
        """
        Action when user click on next button

        Parameters
        ----------
        interaction : discord.Interaction
            Interaction with the button
        """
        if self.page < self.max_page_number:
            self.page += 1
            await self._update(interaction)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        Check if the interact user is the author of the pagination

        Parameters
        ----------
        interaction : discord.Interaction
            Interaction with the button

        Returns
        -------
        bool
            True if the user can interact with the pagination, False otherwise
        """
        if interaction.user.id != self.author:
            await interaction.response.send_message(
                "Vous ne pouvez pas interagir avec une pagination qui ne vous appartient pas.",
                ephemeral=True,
            )
            return False
        return True

    async def send(self, interaction: discord.Interaction) -> None:
        """
        Send message for the first time

        Parameters
        ----------
        interaction : discord.Interaction
            The first interaction by the author, eventually a slashcommand
        """
        (embed, view) = self.create_embeds_and_view()
        if self.max_page_number <= 1:
            await interaction.edit_original_response(embed=embed, view=view)
            return

        await interaction.edit_original_response(embed=embed, view=view)
        self._message = await interaction.original_response()


class EmbedPaginator(Paginator[str], ui.View):
    """
    Paginator for embeds
    """

    def __init__(
        self,
        author: int,
        title: str,
        header: str,
        entries: List[str],
        colour: Optional[int] = None,
        entries_per_page: int = 10,
        page: int = 1,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Setting up variables for parent classes
        Add button to view
        """
        super().__init__(
            author,
            title,
            entries,
            colour,
            entries_per_page,
            page,
            timestamp,
        )
        self.header: str = header

    def _create_embed(self) -> discord.Embed:
        """
        Create an embed for the current page

        Returns
        -------
        discord.Embed
            Created embed
        """
        start: int = (self.page - 1) * self.entries_per_page
        end: int = min(start + self.entries_per_page, len(self.entries))

        description: str = self.header + "\n"
        for entry in self.entries[start:end]:
            description += entry + "\n"

        return discord.Embed(
            title=self.title,
            description=description,
            timestamp=self.timestamp,
            colour=self.colour,
        )

    def create_embeds_and_view(
        self,
    ) -> Tuple[Optional[discord.Embed], Optional[ui.LayoutView | ui.View]]:
        """
        Implement parent's abstract function

        Returns
        -------
        Tuple[Optional[discord.Embed], Optional[ui.View]]
            Embed of the current page and the current view
        """
        if self.max_page_number > 1:
            for child in self.children:
                self.remove_item(child)
            for button in self._create_buttons():
                self.add_item(button)
        return (self._create_embed(), self)


class ComponentsPaginator(Paginator[ui.Item[Any]], ui.LayoutView):
    def __init__(
        self,
        author: int,
        title: str,
        entries: List[ui.Item[Any]],
        colour: Optional[int] = None,
        entries_per_page: int = 10,
        page: int = 1,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Setting up variables for parent classes
        Add button to view
        """
        super().__init__(
            author,
            title,
            entries,
            colour,
            entries_per_page,
            page,
            timestamp,
        )

    def create_embeds_and_view(
        self,
    ) -> Tuple[Optional[discord.Embed], Optional[ui.LayoutView]]:
        """
        Implement parent's abstract function

        Returns
        -------
        Tuple[Optional[discord.Embed], Optional[ui.View]]
            Embed of the current page and the current view
        """
        for child in self.children:
            self.remove_item(child)
        container: ui.Container = ui.Container()
        container.add_item(ui.TextDisplay(self.title))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        start: int = (self.page - 1) * self.entries_per_page
        end: int = min(start + self.entries_per_page, len(self.entries))
        for entry in self.entries[start:end]:
            container.add_item(entry)

        if self.max_page_number > 1:
            container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
            container.add_item(ui.ActionRow(*self._create_buttons()))

        if self.colour:
            container.accent_colour = self.colour

        self.add_item(container)

        return (None, self)
