import logging
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
from discord.ext.commands import Bot, GroupCog
from sqlalchemy import Result, delete, insert, select

import mp2i.database.executor as database_executor
from mp2i.database.models.academy import AcademyModel
from mp2i.utils.discord import has_any_role
from mp2i.utils.paginator import ComponentsPaginator

logger: logging.Logger = logging.getLogger(__name__)


@guild_only()
class Academies(GroupCog, name="academies", description="Gestion des academies"):
    """
    Manage academies
    """

    async def _autocomplete_academies_names(
        self, interaction: discord.Interaction, current: str
    ) -> List[Choice[str]]:
        """
        Autocomplete for academies names

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

        result: Optional[Result[AcademyModel]] = database_executor.execute(
            select(AcademyModel)
            .where(
                AcademyModel.guild_id == interaction.guild.id,
                AcademyModel.academy_name.istartswith(current),
            )
            .order_by(AcademyModel.academy_name)
            .limit(20)
        )

        if not result:
            return []

        return [
            Choice(
                name=academy.academy_name + f"(#{academy.academy_id})",
                value=f"{academy.academy_id}",
            )
            for academy in result.scalars()
        ]

    @command(name="add", description="Ajouter une académie")
    @describe(
        name="Nom de la nouvelle académie",
        domain="Domaine utilisé pour les adresses mails",
    )
    @rename(name="nom", domain="domaine")
    @has_any_role("Administrateur")
    async def add_command(
        self, interaction: discord.Interaction, name: str, domain: str
    ) -> None:
        """
        Add an academy to the database

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command

        name : str
            The academy's name

        domain : str
            The academy's domain name
        """
        if not interaction.guild:
            return

        try:
            database_executor.execute(
                insert(AcademyModel).values(
                    guild_id=interaction.guild.id, academy_name=name, domain_name=domain
                )
            )
            await interaction.response.send_message("Académie créée.")
        except Exception as err:
            logger.fatal("Can not insert a new academy.", err, exc_info=True)
            await interaction.response.send_message("Impossible de créer l'académie.")
            return

    @command(name="remove", description="Retirer une académie")
    @describe(
        academy_id="Nom de la nouvelle académie",
    )
    @rename(academy_id="nom")
    @autocomplete(academy_id=_autocomplete_academies_names)
    @has_any_role("Administrateur")
    async def remove_command(
        self, interaction: discord.Interaction, academy_id: str
    ) -> None:
        """
        Remove an academy from the database

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command

        academy_id : str
            The string representation of the academy's id
        """
        if not interaction.guild:
            return

        try:
            database_executor.execute(
                delete(AcademyModel).where(
                    AcademyModel.guild_id == interaction.guild.id,
                    AcademyModel.academy_id == int(academy_id),
                )
            )
            await interaction.response.send_message("Académie supprimée.")
        except Exception as err:
            logger.fatal("Can not delete an academy.", err, exc_info=True)
            await interaction.response.send_message(
                "Impossible de supprimer l'académie."
            )
            return

    @command(name="list", description="Liste les académies")
    @has_any_role("Administrateur")
    async def list_command(self, interaction: discord.Interaction) -> None:
        """
        List all academies

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command
        """
        if not interaction.guild:
            return

        await interaction.response.defer()
        result: Optional[Result[AcademyModel]] = database_executor.execute(
            select(AcademyModel).where(AcademyModel.guild_id == interaction.guild.id)
        )
        if not result:
            await interaction.response.send_message(
                "Aucune réponse de la base de données."
            )
            return

        entries: List[ui.Item[Any]] = list(
            map(
                lambda academy: ui.TextDisplay(
                    f"**{academy.academy_name}** `{academy.domain_name}`"
                ),
                result.scalars(),
            )
        )

        await ComponentsPaginator(
            author=interaction.user.id, title="## Liste des académies", entries=entries
        ).send(interaction)


async def setup(bot: Bot) -> None:
    """
    Setting up Academies

    Parameters
    ----------
    bot : Bot
        The bot
    """
    await bot.add_cog(Academies())
