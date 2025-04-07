import logging
from functools import wraps
from typing import List
from datetime import datetime

import discord
from discord.ext.commands.errors import NoPrivateMessage, MissingAnyRole
from discord.ext.commands import check

from mp2i.wrappers.guild import GuildWrapper

logger = logging.getLogger(__name__)


def defer(ephemeral: bool = False):
    """
    Decorator that defers the response of a command.
    """

    def decorator(func):
        @wraps(func)
        async def command_wrapper(self, ctx, *args, **kwargs):
            if type(ctx) is discord.Interaction:
                await ctx.response.defer(ephemeral=ephemeral)
            else:
                await ctx.defer(ephemeral=ephemeral)
            await func(self, ctx, *args, **kwargs)

        return command_wrapper

    return decorator

def has_any_role(*items: str):
    """
    Decorator that check if the user has any of the specified roles.
    """

    def predicate(ctx):
        if ctx.guild is None:
            raise NoPrivateMessage()

        # ctx.guild is None doesn't narrow ctx.author to Member
        guild = GuildWrapper(ctx.guild)
        member = ctx.user if isinstance(ctx, discord.Interaction) else ctx.author
        if not isinstance(member, discord.Member):
            raise NoPrivateMessage()
        roles_id = {role.id for role in member.roles}
        for item in items:
            if (role := guild.get_role_by_qualifier(item)) is None:
                logger.error(f"{item} role is not defined in the configuration file")
            elif role.id in roles_id:
                return True

        raise MissingAnyRole(list(items))

    return check(predicate)

class EmbedPaginator(discord.ui.View):
    """
    Class to create an embed paginator.
    """

    def __init__(self, title: str, colour: str, content_header: str, content_body: List[str], nb_by_pages: int, footer: str, author_id: int, timestamp: datetime = datetime.now(), timeout: int = 60):
        super().__init__(timeout=timeout)
        self.current_page = 0
        self.pages = []
        self.author_id = author_id
        total_pages = len(content_body) // nb_by_pages + (1 if len(content_body) % nb_by_pages != 0 else 0)
        if total_pages == 0:
            total_pages = 1
        for index, i in enumerate(range(0, total_pages * nb_by_pages, nb_by_pages)):
            embed = discord.Embed(
                title=title,
                colour=colour,
                timestamp=timestamp,
                description=content_header + "".join(content_body[i:i + nb_by_pages])
            )
            if total_pages > 1:
                embed.set_footer(text=f"{footer} - Page {index + 1} sur {total_pages}")
            else:
                embed.set_footer(text=footer)
            self.pages.append(embed)
        if total_pages == 1:
            self.remove_item(self.previous)
            self.remove_item(self.next)

        self.total_pages = total_pages

    def update_buttons(self):
        self.previous.disabled = self.current_page == 0
        self.next.disabled = self.current_page == self.total_pages - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        Ensures only the command author can interact with the buttons.
        """
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Vous ne pouvez pas interagir avec cette pagination.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, custom_id="prev")
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    async def send(self, ctx):
        """
        Sends the paginated embed to the given context.
        """
        self.update_buttons()
        if isinstance(ctx, discord.Interaction):
            await ctx.response.send_message(embed=self.pages[self.current_page], view=self)
        else:
            await ctx.reply(embed=self.pages[self.current_page], view=self)
