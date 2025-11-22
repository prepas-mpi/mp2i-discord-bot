from typing import Optional

import discord
from discord.app_commands import (
    ContextMenu,
    MissingAnyRole,
    command,
    describe,
    guild_only,
    rename,
)
from discord.ext.commands import Bot, Cog

from mp2i.cogs.profile._display import ProfileView
from mp2i.utils.discord import has_any_roles_predicate


class Profile(Cog):
    """
    Manage profile
    """

    def __init__(self, bot: Bot) -> None:
        """
        Add context menu to command tree

        Parameters
        ----------
        bot : Bot
            The bot instance
        """
        ctx_menu = ContextMenu(
            name="Voir le profil",
            callback=self.view_profile_menu,
            type=discord.AppCommandType.user,
        )
        ctx_menu.guild_only = True
        bot.tree.add_command(ctx_menu)

    async def _generate_profile(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        if member.bot:
            await interaction.edit_original_response(
                content="Vous ne pouvez pas voir le profil d'un bot."
            )
            return
        is_mod: bool = False
        try:
            is_mod = await has_any_roles_predicate(
                interaction, "Administrateur", "Modérateur"
            )
        except MissingAnyRole:
            pass
        await interaction.edit_original_response(
            view=ProfileView(
                member,
                interaction.user.id == member.id or is_mod,
            ),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def view_profile_menu(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """
        Context menu on members to display their profile

        Parameters
        ----------
        interaction : discord.Interaction
            The context menu

        member : discord.Member
            The concerned member
        """
        await interaction.response.defer(ephemeral=True)
        await self._generate_profile(interaction, member)

    @command(name="profile", description="Voir le profil d'un membre")
    @describe(member="Nom du membre")
    @rename(member="membre")
    @guild_only()
    async def profile_command(
        self, interaction: discord.Interaction, member: Optional[discord.Member]
    ) -> None:
        """
        Command to display member's profile

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command

        member : Optional[discord.Member]
            The target member if someone else
        """
        if not isinstance(interaction.user, discord.Member):
            return
        await interaction.response.defer()
        await self._generate_profile(interaction, member or interaction.user)


async def setup(bot: Bot) -> None:
    """
    Setting up Profile

    Parameters
    ----------
    bot : Bot
        The bot instance
    """
    await bot.add_cog(Profile(bot))
