import datetime
import logging
import re
from pathlib import Path
from typing import Any, List, Optional

import discord
import discord.ui as ui
from discord.app_commands import (
    Choice,
    autocomplete,
    command,
    describe,
    guild_only,
    rename,
)
from discord.enums import SeparatorSpacing
from discord.ext.commands import Bot, Cog, GroupCog
from sqlalchemy import Executable, Result, insert, select, update

import mp2i.database.executor as database_executor
from mp2i.database.models.member import MemberModel
from mp2i.database.models.suggestion import SuggestionModel, SuggestionStatus
from mp2i.utils.config import get_static_file_path, get_text_from_static_file
from mp2i.utils.discord import has_any_role
from mp2i.utils.paginator import ComponentsPaginator
from mp2i.wrappers.guild import GuildWrapper
from mp2i.wrappers.member import MemberWrapper

from ._modals import SuggestionCloseModal, SuggestionCreateModal

logger: logging.Logger = logging.getLogger(__name__)


@guild_only
class Suggestions(GroupCog, name="suggestions", description="Gestion des suggestions"):
    """
    Manage suggestions
    """

    def __init__(self) -> None:
        """
        Initialize common strings
        """
        self._process: str = get_text_from_static_file("text/suggestion/process.md")
        self._answer: str = get_text_from_static_file("text/suggestion/answer.md")
        self._image: Path = get_static_file_path("img/logo.png")

    async def _send_process(self, guild: discord.Guild) -> None:
        """
        Send the main message for suggestions

        Parameters
        ----------
        guild : discord.Guild
            The concerned guild
        """
        guild_wrapper: GuildWrapper = GuildWrapper(guild)
        channel: Optional[discord.TextChannel] = guild_wrapper.suggestions_channel
        if not channel:
            return
        past_message: Optional[
            discord.Message
        ] = await guild_wrapper.suggestions_message
        if past_message:
            await past_message.delete()
        container: ui.Container = ui.Container()

        filename = self._image.name
        section = ui.Section(
            ui.TextDisplay(self._process),
            accessory=ui.Thumbnail(media=f"attachment://{filename}"),
        )
        container.add_item(section)
        container.add_item(ui.Separator())
        container.add_item(
            ui.ActionRow(
                ui.Button(
                    style=discord.ButtonStyle.green,
                    label="Proposer une suggestion",
                    custom_id="suggestion::create",
                )
            )
        )
        view: ui.LayoutView = ui.LayoutView()
        view.add_item(container)

        file = discord.File(self._image, filename=filename)
        new_message: discord.Message = await channel.send(view=view, files=[file])
        guild_wrapper.suggestions_message = new_message

    def _get_components_for_default_container(
        self,
        author: Optional[discord.User | discord.Member],
        title: str,
        description: str,
        guild: Optional[discord.Guild] = None,
    ) -> List[ui.Item[Any]]:
        """
        Get components to create the suggestion message

        Parameters
        ----------
        author: Optional[discord.User | discord.Member]
            Author of the suggestion can be None if not found

        title : str
            The title of the suggestion

        description : str
            The description of the suggestion

        guild : Optional[discord.Guild]
            The guild use to fallback author's asset if None

        Returns
        -------
        List[ui.Item[Any]]
            The list of components
        """
        if not author and not guild:
            return []
        return [
            ui.Section(
                ui.TextDisplay(
                    "### " + author.name if author else (guild.name if guild else "")
                ),
                ui.TextDisplay("## " + title),
                accessory=ui.Thumbnail(
                    media=author.display_avatar.url
                    if author
                    else (guild.icon.url if guild and guild.icon else "")
                ),
            ),
            ui.Separator(),
            ui.TextDisplay(description),
            ui.Separator(),
        ]

    async def _create_suggestion(
        self, author: discord.Member, title: str, description: str
    ) -> None:
        """
        Create a suggestion

        Parameters
        ----------
        author : discord.Member
            The member author of the suggestion

        title : str
            The title of the suggestion

        description : str
            The description of the suggestion
        """
        guild: GuildWrapper = GuildWrapper(author.guild)
        if not (channel := guild.suggestions_channel):
            return
        container: ui.Container = ui.Container()
        for item in self._get_components_for_default_container(
            author, title, description
        ):
            container.add_item(item)
        now: datetime.datetime = datetime.datetime.now()
        container.add_item(
            ui.TextDisplay(
                f"-# {SuggestionStatus.OPEN.emote} Suggestion non-traitée • <t:{round(now.timestamp())}:F>"
            )
        )
        container.accent_colour = SuggestionStatus.OPEN.colour
        view: ui.LayoutView = ui.LayoutView()
        view.add_item(container)
        message: discord.Message = await channel.send(view=view)
        try:
            await message.add_reaction("✅")
            await message.add_reaction("❌")
        except discord.errors.NotFound:
            pass
        thread: discord.Thread = await channel.create_thread(
            name=title, message=message, auto_archive_duration=10080
        )
        await thread.add_user(author)
        author_wrapper: MemberWrapper = MemberWrapper(author)
        database_executor.execute(
            insert(SuggestionModel).values(
                guild_id=guild.id,
                author_id=author_wrapper.member_id,
                suggestion_title=title,
                suggestion_description=description,
                suggestion_status=SuggestionStatus.OPEN,
                suggestion_date=now,
                suggestion_message=message.id,
            )
        )
        await self._send_process(guild._boxed)

    async def _close_suggestion(
        self,
        suggestion: SuggestionModel,
        staff: discord.Member,
        status: SuggestionStatus,
        reason: Optional[str] = None,
    ) -> None:
        """
        Close a suggestion

        Parameters
        ----------
        suggestion : SuggestionModel
            The concerned suggestion

        staff : discord.Member
            The staff that close the suggestion

        status : SuggestionStatus
            The new status

        reason : Optional[str]
            The reason of the closing, can be None
        """
        guild: GuildWrapper = GuildWrapper(staff.guild, fetch=False)
        thread: Optional[discord.Thread] = guild.get_any_channel(
            suggestion.suggestion_message, discord.Thread
        )
        if not thread or not isinstance(thread.parent, discord.TextChannel):
            return
        message: discord.Message = await thread.parent.fetch_message(thread.id)
        author_res: Optional[Result[MemberModel]] = database_executor.execute(
            select(MemberModel).where(MemberModel.member_id == suggestion.author_id)
        )
        author_member: Optional[discord.Member] = None
        if author_res and (author := author_res.scalar_one_or_none()):
            author_member = await staff.guild.fetch_member(author.user_id)
            answer: str = self._answer
            answer = re.sub(
                f"<reason>{'[^<]*' if not reason else '|'}</reason>", "", answer
            )

            await thread.send(
                answer.format(
                    author=f"<@{author.user_id}>",
                    status=status.result,
                    message=message.jump_url,
                )
            )
        accept: int = getattr(
            discord.utils.get(message.reactions, emoji="✅"), "count", 0
        )
        decline: int = getattr(
            discord.utils.get(message.reactions, emoji="❌"), "count", 0
        )

        now: datetime.datetime = datetime.datetime.now()

        container: ui.Container = ui.Container()
        for item in self._get_components_for_default_container(
            author_member,
            suggestion.suggestion_title,
            suggestion.suggestion_description,
            staff.guild,
        ):
            container.add_item(item)
        container.add_item(ui.TextDisplay(f"**Votes**\n{accept} ✅ • {decline} ❌"))
        container.add_item(ui.Separator(spacing=SeparatorSpacing.large))
        container.add_item(
            ui.TextDisplay(f"\ud83d\udcdd **Réponse de l'équipe**\n{reason}")
        )
        container.add_item(ui.Separator())
        container.add_item(
            ui.TextDisplay(
                f"-# {status.emote} Suggestion {status.result} • <t:{round(now.timestamp())}:F>"
            )
        )
        container.accent_colour = status.colour
        view: ui.LayoutView = ui.LayoutView()
        view.add_item(container)
        await message.edit(view=view)
        await message.clear_reactions()

        database_executor.execute(
            update(SuggestionModel)
            .values(
                suggestion_status=status,
                staff_id=MemberWrapper(staff).member_id,
                staff_description=reason,
                suggestion_handled_date=datetime.datetime.now(),
            )
            .where(
                SuggestionModel.guild_id == guild.id,
                SuggestionModel.suggestion_id == suggestion.suggestion_id,
            )
        )

        await thread.edit(locked=True, archived=True)

    async def _autocomplete_suggestions_titles(
        self, interaction: discord.Interaction, current: str
    ) -> List[Choice[str]]:
        """
        Autocomplete for suggestions titles

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

        result: Optional[Result[SuggestionModel]] = database_executor.execute(
            select(SuggestionModel)
            .where(
                SuggestionModel.guild_id == interaction.guild.id,
                SuggestionModel.suggestion_title.istartswith(current),
                SuggestionModel.suggestion_status == SuggestionStatus.OPEN,
            )
            .order_by(SuggestionModel.suggestion_title)
            .limit(20)
        )

        if not result:
            return []

        return [
            Choice(
                name=suggestion.suggestion_title + f"(#{suggestion.suggestion_id})",
                value=f"{suggestion.suggestion_id}",
            )
            for suggestion in result.scalars()
        ]

    @command(name="list", description="List les suggestions")
    @describe(status="État de la suggestion")
    @rename(status="statut")
    async def list_command(
        self, interaction: discord.Interaction, status: Optional[SuggestionStatus]
    ) -> None:
        """
        List all suggestions

        Parameters
        ----------
        intraction : discord.Interaction
            The slash command

        status : Optional[SuggestionStatus]
            The desired status of listed suggestions
        """
        if not interaction.guild:
            return
        guild: GuildWrapper = GuildWrapper(interaction.guild, fetch=False)
        if not (channel := guild.suggestions_channel):
            return
        statement: Executable = select(SuggestionModel).where(
            SuggestionModel.guild_id == guild.id
        )
        if status:
            statement = statement.where(
                SuggestionModel.guild_id == interaction.guild.id,
                SuggestionModel.suggestion_status == status,
            )

        result: Optional[Result[SuggestionModel]] = database_executor.execute(statement)

        if not result:
            await interaction.response.send_message(
                "Aucune réponse de la base de données."
            )
            return
        await interaction.response.defer()

        entries: List[ui.Item[Any]] = []
        for suggestion in result.scalars():
            title: ui.TextDisplay = ui.TextDisplay(
                f"**{suggestion.suggestion_title}** ({suggestion.suggestion_status.result})"
            )
            try:
                message: discord.Message = await channel.fetch_message(
                    suggestion.suggestion_message
                )
                entries.append(
                    ui.Section(
                        title,
                        accessory=ui.Button(
                            style=discord.ButtonStyle.link,
                            label="Voir",
                            url=message.jump_url,
                        ),
                    )
                )
            except discord.NotFound:
                entries.append(title)

        await ComponentsPaginator(
            author=interaction.user.id,
            title="## Liste des suggestions",
            entries=entries,
            colour=status.colour if status else None,
        ).send(interaction)

    @command(name="message", description="Envoie du message de suggestions")
    @has_any_role("Administrateur")
    async def message_command(self, interaction: discord.Interaction) -> None:
        """
        Send the main message of suggestions

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command
        """
        if not interaction.guild:
            return
        await self._send_process(interaction.guild)
        await interaction.response.send_message(
            "Message envoyé dans le salon de suggestions."
        )

    @command(name="close", description="Ferme une suggestion ouverte")
    @describe(suggestion_id="Titre de la suggestion")
    @autocomplete(suggestion_id=_autocomplete_suggestions_titles)
    @rename(suggestion_id="suggestion")
    @has_any_role("Administrateur")
    async def close_command(
        self, interaction: discord.Interaction, suggestion_id: Optional[str]
    ) -> None:
        """
        Send the main message of suggestions

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command

        suggestion_id : Optional[str]
            The suggestion's id to close can be None to use the current thread
        """
        if not interaction.channel_id or not interaction.guild:
            return
        result: Optional[Result[SuggestionModel]] = None
        suggestion: Optional[SuggestionModel] = None
        if suggestion_id:
            try:
                result = database_executor.execute(
                    select(SuggestionModel).where(
                        SuggestionModel.guild_id == interaction.guild.id,
                        SuggestionModel.suggestion_id == int(suggestion_id),
                        SuggestionModel.suggestion_status == SuggestionStatus.OPEN,
                    )
                )
                if result:
                    suggestion = result.scalar_one_or_none()
                else:
                    await interaction.response.send_message(
                        "Aucune réponse de la base de données."
                    )
                    return
            except Exception:
                pass
        if not result:
            result = database_executor.execute(
                select(SuggestionModel).where(
                    SuggestionModel.suggestion_message == interaction.channel_id,
                    SuggestionModel.suggestion_status == SuggestionStatus.OPEN,
                )
            )
            if result:
                suggestion = result.scalar_one_or_none()
            else:
                await interaction.response.send_message(
                    "Aucune réponse de la base de données."
                )
                return
        if not suggestion:
            await interaction.response.send_message("Aucune suggestion trouvée.")
            return
        await interaction.response.send_modal(
            SuggestionCloseModal(suggestion, self._close_suggestion)
        )

    @Cog.listener("on_interaction")
    async def other_open_ticket(self, interaction: discord.Interaction) -> None:
        """
        Let a user create a suggestion

        Parameters
        ----------
        interaction : discord.Interaction
            The button interaction
        """
        if (
            not interaction.message
            or not interaction.data
            or interaction.data.get("custom_id") != "suggestion::create"
        ):
            return
        await interaction.response.send_modal(
            SuggestionCreateModal(self._create_suggestion)
        )


async def setup(bot: Bot) -> None:
    """
    Setting up Suggestions

    Parameters
    ----------
    bot : Bot
        The bot
    """
    await bot.add_cog(Suggestions())
