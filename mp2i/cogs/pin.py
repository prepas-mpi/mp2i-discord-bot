from typing import Any, List, Optional

import discord
import discord.ui as ui
from discord.app_commands import (
    Choice,
    ContextMenu,
    autocomplete,
    command,
    describe,
    rename,
)
from discord.ext.commands import Bot, Cog, GroupCog
from sqlalchemy import Result, insert, select, update

import mp2i.database.executor as database_executor
from mp2i.database.models.pin import PinModel, PinStatus
from mp2i.utils.discord import has_any_role, has_any_roles_predicate
from mp2i.utils.paginator import ComponentsPaginator
from mp2i.wrappers.guild import GuildWrapper


class Pin(GroupCog, name="pins", description="Gestion des messages épinglés à faire"):
    """
    Manage pins
    """

    def __init__(self, bot: Bot) -> None:
        """
        Setting context menu

        Parameters
        ----------
        bot : Bot
            The bot
        """
        self._bot = bot
        ctx_menu: ContextMenu = ContextMenu(
            name="Pin à faire",
            callback=self._add_pin_menu,
            type=discord.AppCommandType.message,
        )
        ctx_menu.guild_only = True
        ctx_menu.add_check(
            lambda interaction: has_any_roles_predicate(
                interaction, "Administrateur", "Modérateur", "Gestion Association"
            )
        )
        bot.tree.add_command(ctx_menu)
        self._roles: dict[int, dict[str, tuple[discord.Role, int]]] = {}

    async def _add_pin(
        self, guild: GuildWrapper, message: discord.Message, community: bool
    ) -> bool:
        """
        Add new pin

        Parameters
        ----------
        guild : GuildWrapper
            The wrapper of the guild

        message : discord.Message
            The message to pin

        community : bool
            Is the action from community

        Returns
        -------
        bool
            True if succeed, False otherwise
        """
        result: Optional[Result[PinModel]] = database_executor.execute(
            select(PinModel).where(
                PinModel.guild_id == guild.id,
                PinModel.original_message_id == message.id,
            )
        )

        if not result or result.scalar_one_or_none():
            return False

        channel: Optional[discord.TextChannel] = guild.pin_channel
        if not channel:
            return False

        container: ui.Container = ui.Container()
        container.add_item(
            ui.Section(
                ui.TextDisplay("## Message épinglé"),
                ui.TextDisplay(f" > par {message.author.mention}"),
                accessory=ui.Thumbnail(media=message.author.display_avatar.url),
            )
        )
        if community:
            container.add_item(
                ui.TextDisplay(
                    "La communauté a retenu ce message et devrait sans doute être publié sur le site."
                )
            )
        else:
            container.add_item(
                ui.TextDisplay(
                    "Un administrateur a retenu ce message et devrait sans doute être publié sur le site."
                )
            )
        container.add_item(
            ui.TextDisplay(
                f"```yml\n{message.content[:255]}{'[...]' if len(message.content) > 255 else ''}\n```\nLe message est accessible [ici]({message.jump_url})"
            )
        )
        view: ui.LayoutView = ui.LayoutView()
        view.add_item(container)

        alert_message: discord.Message = await channel.send(
            view=view, allowed_mentions=discord.AllowedMentions.none()
        )
        await alert_message.pin()

        first_words: str = " ".join(message.content.strip().split(" ")[:6])
        if len(first_words) > 255:
            first_words = first_words[:255]
        database_executor.execute(
            insert(PinModel).values(
                guild_id=guild.id,
                original_message_id=message.id,
                alert_message_id=alert_message.id,
                first_words=first_words,
            )
        )

        return True

    async def _add_pin_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """
        Context menu to pin a message

        Parameters
        ----------
        interaction : discord.Interaction
            The context menu interaction

        message : discord.Message
            The concerned message
        """
        if not interaction.guild:
            return
        guild: GuildWrapper = GuildWrapper(interaction.guild, fetch=False)
        if not await self._add_pin(guild, message, False):
            await interaction.response.send_message("Impossible d'épingler le message.")
            return
        await interaction.response.send_message("Message épinglé.")

    async def _autocomplete_pins_words(
        self, interaction: discord.Interaction, current: str
    ) -> List[Choice[str]]:
        """
        Autocomplete for pins first words

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command concerned

        current : str
            The worlds written by the member at that time

        Returns
        -------
        List[Choice[str]]
            List of choices
        """
        if not interaction.guild:
            return []
        await interaction.response.defer()

        result: Optional[Result[PinModel]] = database_executor.execute(
            select(PinModel)
            .where(
                PinModel.guild_id == interaction.guild.id,
                PinModel.first_words.istartswith(current),
                PinModel.pin_status == PinStatus.TODO,
            )
            .order_by(PinModel.pin_id)
            .limit(20)
        )

        if not result:
            return []

        return [
            Choice(
                name=pin.first_words + f"(#{pin.pin_id})",
                value=f"{pin.pin_id}",
            )
            for pin in result.scalars()
        ]

    @command(name="list", description="Liste les pins à faire")
    async def list_command(self, interaction: discord.Interaction) -> None:
        """
        List all pins todo

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command
        """
        if not interaction.guild:
            return
        guild: GuildWrapper = GuildWrapper(interaction.guild, fetch=False)
        channel: Optional[discord.TextChannel] = guild.pin_channel
        if not channel:
            await interaction.response.send_message("Salon de pins non défini")
            return
        await interaction.response.defer()
        result: Optional[Result[PinModel]] = database_executor.execute(
            select(PinModel)
            .where(PinModel.guild_id == guild.id, PinModel.pin_status == PinStatus.TODO)
            .order_by(PinModel.pin_id)
        )
        if not result:
            await interaction.edit_original_response(
                content="Aucune réponse de la base de données"
            )
            return

        entries: List[ui.Item[Any]] = []
        for pin in result.scalars():
            message: discord.Message = await channel.fetch_message(pin.alert_message_id)
            entries.append(
                ui.Section(
                    ui.TextDisplay(pin.first_words),
                    accessory=ui.Button(
                        style=discord.ButtonStyle.link,
                        label="Voir",
                        url=message.jump_url,
                    ),
                )
            )

        await ComponentsPaginator(
            author=interaction.user.id, title="## Pins à faire", entries=entries
        ).send(interaction)

    @command(name="done", description="Termine un pin")
    @describe(id="Le pin concerné")
    @rename(id="pin")
    @autocomplete(id=_autocomplete_pins_words)
    @has_any_role("Administrateur", "Gestion Association")
    async def done_command(self, interaction: discord.Interaction, id: str) -> None:
        """
        Make a pin done

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command

        id : str
            The string representation of the pin's id
        """
        if not interaction.guild:
            return
        guild: GuildWrapper = GuildWrapper(interaction.guild, fetch=False)
        channel: Optional[discord.TextChannel] = guild.pin_channel
        if not channel:
            await interaction.response.send_message("Salon de pins non défini")
            return
        await interaction.response.defer()
        result: Optional[Result[PinModel]] = database_executor.execute(
            select(PinModel).where(
                PinModel.pin_id == int(id),
                PinModel.guild_id == guild.id,
                PinModel.pin_status == PinStatus.TODO,
            )
        )
        if not result:
            await interaction.edit_original_response(
                content="Aucune réponse de la base de données"
            )
            return
        if not (pin := result.scalar_one_or_none()):
            await interaction.edit_original_response(content="Pin non trouvé")
            return
        database_executor.execute(
            update(PinModel)
            .values(pin_status=PinStatus.DONE)
            .where(
                PinModel.pin_id == int(id),
                PinModel.guild_id == guild.id,
            )
        )
        message: discord.Message = await channel.fetch_message(pin.alert_message_id)
        await message.unpin()
        await interaction.edit_original_response(content="Pin terminé.")

    @Cog.listener("on_raw_reaction_add")
    async def action_added(self, payload: discord.RawReactionActionEvent):
        """
        Detect when a message should be pin by the community

        Parameters
        ----------
        payload: discord.RawReactionActionEvent
            The reaction event
        """
        if not payload.guild_id or not (guild := self._bot.get_guild(payload.guild_id)):
            return

        guild_wrapper: GuildWrapper = GuildWrapper(guild, fetch=False)

        if guild_wrapper.pin_emoji != str(payload.emoji):
            return

        channel: Optional[discord.TextChannel] = guild_wrapper.get_any_channel(
            payload.channel_id, discord.TextChannel
        )
        if not channel:
            return

        message: discord.Message = await channel.fetch_message(payload.message_id)
        pins_count: int = getattr(
            discord.utils.get(message.reactions, emoji=guild_wrapper.pin_emoji),
            "count",
            0,
        )
        if pins_count < guild_wrapper.pin_min_emoji:
            return

        await self._add_pin(guild_wrapper, message, True)


async def setup(bot: Bot) -> None:
    """
    Setting up Pins

    Parameters
    ----------
    bot : Bot
        The bot
    """
    await bot.add_cog(Pin(bot))
