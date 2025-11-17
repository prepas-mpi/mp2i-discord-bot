import logging
import time
from typing import Optional

import discord
from discord import ui
from discord.ext.commands import Bot, Cog

logger: logging.Logger = logging.getLogger(__name__)


class Welcome(Cog):
    """
    Define bot's behaviour when a member join a guild
    """

    def __init__(self):
        """
        Initialize parent classes
        """
        super().__init__()

    @Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """
        Send a welcome message in guild's system channel

        Parameters
        ----------
        member : discord.Member
            the member that has just joined the guild
        """
        channel: Optional[discord.TextChannel] = member.guild.system_channel
        if not channel:
            return

        container: ui.Container = ui.Container()
        container.add_item(
            ui.Section(
                ui.TextDisplay(f"### {member.display_name}"),
                ui.TextDisplay("## Arrivée d'un membre"),
                ui.TextDisplay(
                    f"{member.mention} a rejoint le serveur MP2I/MPI !\nN'hésitez pas à lui souhaiter la bienvenue !"
                ),
                accessory=ui.Thumbnail(member.display_avatar.url),
            )
        )
        container.add_item(ui.Separator())
        container.add_item(ui.TextDisplay(f"-# <t:{round(time.time())}:F>"))

        view: ui.LayoutView = ui.LayoutView()
        view.add_item(container)

        await channel.send(view=view, allowed_mentions=discord.AllowedMentions.none())


async def setup(bot: Bot) -> None:
    """
    Setting up welcome behavious

    Parameters
    ----------
    bot : Bot
        instance of the discord bot
    """
    await bot.add_cog(Welcome())
