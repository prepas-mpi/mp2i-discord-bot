import logging
from typing import List

import discord
from discord import ui
from discord.ext.commands import Bot, Cog

logger: logging.Logger = logging.getLogger(__name__)


class MessageLogger(Cog):
    """
    Class to listen to edited and deleted messages
    in order to log them in a separate channel
    """

    def __init__(self) -> None:
        """
        Initialize constant values used in the logger
        """
        super().__init__()
        self.__MAX_MESSAGE_LENGTH: int = 3096
        self.__EDITED_COLOR: int = 0x6DD7FF
        self.__DELETED_COLOR: int = 0xFF6D6D

    async def __send_notification(self, message: discord.Message, edited: bool) -> None:
        """
        Send message in log channel

        Parameters
        ----------
        message : discord.Message
            The original message to log
        edited : bool
            True when logging an edit, False when logging a deletion
        """
        parts: List[ui.TextDisplay] = list(
            map(
                lambda text: ui.TextDisplay(f"```yml\n{text}```"),
                message.content.split(f"(?<=\\G.{self.__MAX_MESSAGE_LENGTH})"),
            )
        )
        for i in range(len(parts)):
            part_number: str = f"({i}/{len(parts)})"
            container: ui.Container = ui.Container()
            container.add_item(
                ui.Section(
                    ui.TextDisplay(
                        f"## Message {'modifié' if edited else 'supprimé'} {part_number if len(parts) > 1 else ''}"
                    ),
                    ui.TextDisplay(
                        f"**Auteur :** {message.author.mention} @ <t:{round(message.created_at.timestamp())}:T>"
                    ),
                    accessory=ui.Button(
                        style=discord.ButtonStyle.link,
                        url=(message.jump_url if edited else message.channel.jump_url),
                        label=f"Voir le {'message' if edited else 'salon'}",
                    ),
                )
            )
            container.add_item(ui.Separator(visible=False))
            container.add_item(parts[i])
            container.accent_colour = (
                self.__EDITED_COLOR if edited else self.__DELETED_COLOR
            )

            view: ui.LayoutView = ui.LayoutView()
            view.add_item(container)
            await message.channel.send(
                view=view, allowed_mentions=discord.AllowedMentions.none()
            )

    @Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        """
        Log deleted message in channels

        Parameters
        ----------
        message : discord.Message
            the deleted message
        """
        if not message.guild or message.author.bot:
            return
        await self.__send_notification(message, False)

    @Cog.listener()
    async def on_message_edit(
        self, previous_message: discord.Message, _: discord.Message
    ) -> None:
        """
        Log edited message in channels

        Parameters
        ----------
        previous_message : discord.Message
            the previous version of the message
        _: discord.Message
            the new version of the message, not used in this function
        """
        if not previous_message.guild or previous_message.author.bot:
            return
        await self.__send_notification(previous_message, True)


async def setup(bot: Bot) -> None:
    """
    Setting up the message logger

    Parameters
    ----------
    bot : Bot
        instance of the discord bot
    """
    await bot.add_cog(MessageLogger())
