import logging
from typing import List, Optional

import discord
import discord.ui as ui
from discord.app_commands import MissingAnyRole, command, describe, guild_only
from discord.ext.commands import Bot, Cog, GroupCog
from sqlalchemy import Result, insert, select, update

import mp2i.database.executor as database_executor
from mp2i.database.models.ticket import TicketLevel, TicketModel
from mp2i.utils.config import get_text_from_static_file
from mp2i.utils.discord import has_any_role, has_any_roles_predicate
from mp2i.wrappers.guild import GuildWrapper
from mp2i.wrappers.member import MemberWrapper

logger: logging.Logger = logging.getLogger(__name__)


@guild_only()
class Ticket(GroupCog, name="ticket", description="Gestion des tickets"):
    """
    Manage tickets
    """

    def __init__(self) -> None:
        """
        Read files that contain plain text
        """
        self._global_message: str = get_text_from_static_file(
            "text/ticket/global_message.md"
        )
        if self._global_message == "":
            logger.warning(
                "It seems that file `text/ticket/global_message.md` is empty."
            )
        self._open_staff: str = get_text_from_static_file("text/ticket/open_staff.md")
        if self._open_staff == "":
            logger.warning("It seems that file `text/ticket/open_staff.md` is empty.")
        self._open_other: str = get_text_from_static_file("text/ticket/open_other.md")
        if self._open_other == "":
            logger.warning("It seems that file `text/ticket/open_other.md` is empty.")

    async def _open_ticket(
        self,
        interaction: discord.Interaction,
        target: MemberWrapper,
        level: TicketLevel,
        request: Optional[discord.Member] = None,
    ) -> None:
        """
        Open a ticket for a member, may be initiated by a staff

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command or button interaction

        target : MemberWrapper
            The member concerned by the ticket

        level : TicketLevel
            The level of the ticket (ADMINISTRATOR or MODERATOR)

        request : Optional[discord.Member]
            The member that initiated the ticket, if None they are the target
        """
        if not interaction.guild:
            return

        guild: GuildWrapper = GuildWrapper(interaction.guild, fetch=False)
        channel: Optional[discord.TextChannel] = guild.get_ticket_channel
        if not channel:
            await interaction.response.send_message(
                "Le canal de tickets n'a pas été configuré correctement.",
                ephemeral=True,
            )
            return

        thread: discord.Thread = await channel.create_thread(
            name=f"[Ouvert] Ticket de {target.name}", invitable=False
        )
        container: ui.Container = ui.Container()
        container.add_item(
            ui.TextDisplay(
                (self._open_staff if request else self._open_other).format(
                    mention=target.mention
                )
            )
        )
        container.add_item(ui.Separator(visible=False))
        container.add_item(
            ui.ActionRow(
                ui.Button(label="Clôturer le ticket", custom_id="ticket:close")
            )
        )
        view: ui.LayoutView = ui.LayoutView()
        view.add_item(container)

        message: discord.Message = await thread.send(view=view)
        await message.pin()

        database_executor.execute(
            insert(TicketModel).values(
                member_id=target.member_id, thread_id=thread.id, level=level
            )
        )

        role_to_mention: List[discord.Role] = guild.mapping_roles(
            ["Administrateur", "Modérateur"]
            if level == TicketLevel.MODERATOR
            else ["Administrateur"]
        )

        mention_message: discord.Message = await thread.send("(╯°□°)╯︵ ┻━┻")
        await mention_message.edit(
            content=" ".join(map(lambda role: role.mention, role_to_mention))
        )
        await mention_message.delete()

        if request:
            await interaction.response.send_message(
                f"Un ticket a été ouvert pour {target.mention} dans le fil {thread.jump_url}."
            )
        else:
            await interaction.response.send_message(
                f"Vous avez demandé l'ouverture d'un ticket disponible au lien {thread.jump_url}.",
                ephemeral=True,
            )

    @command(name="message", description="Envoie le message de tickets")
    @has_any_role("Administrateur")
    async def ticket_message(self, interaction: discord.Interaction) -> None:
        """
        Send a message to let members create tickets

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command
        """
        await interaction.response.defer()
        if not interaction.guild:
            await interaction.edit_original_response(
                content="Vous n'êtes pas dans une guilde."
            )
            return

        guild: GuildWrapper = GuildWrapper(interaction.guild, fetch=False)
        channel: Optional[discord.TextChannel] = guild.get_ticket_channel
        if not channel:
            await interaction.edit_original_response(
                content="Le canal de tickets n'a pas été configuré correctement."
            )
            return

        container: ui.Container = ui.Container()
        container.add_item(
            ui.TextDisplay(self._global_message),
        )
        container.add_item(ui.Separator(visible=False))

        container.add_item(
            ui.ActionRow(
                ui.Button(
                    custom_id="ticket:open",
                    style=discord.ButtonStyle.danger,
                    label="Ouvrir un ticket",
                    emoji="🎫",
                )
            )
        )
        container.accent_colour = 0xFF6B60

        view: ui.LayoutView = ui.LayoutView()
        view.add_item(container)

        await channel.send(view=view)
        await interaction.edit_original_response(
            content=f"Un message a été envoyé dans le salon {channel.jump_url}."
        )

    @command(name="open", description="Ouvre un ticket pour un membre")
    @describe(
        member="Membre concerné par le ticket", level="Niveau d'incidence du ticket"
    )
    @has_any_role("Administrateur", "Modérateur")
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        level: TicketLevel,
    ) -> None:
        """
        Open a ticket for a member

        Parameters
        ----------
        interaction : discord.Interaction
            The slash command interaction

        member : discord.Member
            The member concerned by the ticket

        level : TicketLevel
            The level of the ticker (ADMINISTRATOR or MODERATOR)
        """
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Il semblerait que vous ne puissez créer de ticket ici.", ephemeral=True
            )
            return

        if member.bot:
            await interaction.response.send_message(
                "Vous ne pouvez pas créer un ticket pour un bot.", ephemeral=True
            )
            return

        await interaction.response.defer()
        member_wrapper: MemberWrapper = MemberWrapper(member)
        logger.info(
            "User %d open a ticket for user %d with level %d",
            interaction.user.id,
            member.id,
            level,
        )

        await self._open_ticket(interaction, member_wrapper, level, interaction.user)

    @Cog.listener("on_interaction")
    async def other_get_level_ticket(self, interaction: discord.Interaction) -> None:
        """
        Let a user select the level of a ticket

        Parameters
        ----------
        interaction : discord.Interaction
            The button interaction
        """
        if not interaction.data or interaction.data.get("custom_id") != "ticket:open":
            return
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Il semblerait que vous ne puissez créer de ticket ici.", ephemeral=True
            )
            return

        view: ui.LayoutView = ui.LayoutView()
        view.add_item(
            ui.ActionRow(
                ui.Select(
                    custom_id="ticket:level",
                    placeholder="Choisissez le niveau de votre ticket",
                    options=[
                        discord.SelectOption(
                            label="Administration",
                            value=str(TicketLevel.ADMINISTRATOR.value),
                        ),
                        discord.SelectOption(
                            label="Modération", value=str(TicketLevel.MODERATOR.value)
                        ),
                    ],
                )
            )
        )
        await interaction.response.send_message(view=view, ephemeral=True)

    @Cog.listener("on_interaction")
    async def other_open_ticket(self, interaction: discord.Interaction) -> None:
        """
        Let a user create a ticket of the desired level

        Parameters
        ----------
        interaction : discord.Interaction
            The button interaction
        """
        if (
            not interaction.message
            or not interaction.data
            or interaction.data.get("custom_id") != "ticket:level"
        ):
            return
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Il semblerait que vous ne puissez créer de ticket ici.", ephemeral=True
            )
            return
        guild: GuildWrapper = GuildWrapper(interaction.guild, fetch=False)
        member_wrapper: MemberWrapper = MemberWrapper(interaction.user)
        if (
            len(list(filter(lambda t: not t.closed, member_wrapper.tickets)))
            >= guild.get_max_ticket
        ):
            logger.warning(
                "User %d tried to open more tickets than the guild %d limit",
                member_wrapper.id,
                guild.id,
            )
            await interaction.response.send_message(
                "Vous avez trop de tickets en activité.", ephemeral=True
            )
            return
        values: Optional[List[str]] = interaction.data.get("values")
        if not values:
            await interaction.response.send_message(
                "Vous n'avez sélectionné aucun niveau.", ephemeral=True
            )
            return
        await self._open_ticket(
            interaction, member_wrapper, TicketLevel(int(values[0]))
        )

    @Cog.listener("on_interaction")
    async def close_ticket(self, interaction: discord.Interaction) -> None:
        """
        Let staff close a ticket

        Parameters
        ----------
        interaction : discord.Interaction
            The button interaction
        """
        if (
            not interaction.message
            or not interaction.data
            or interaction.data.get("custom_id") != "ticket:close"
        ):
            return
        if (
            not interaction.guild
            or not isinstance(interaction.user, discord.Member)
            or not isinstance(interaction.channel, discord.Thread)
        ):
            await interaction.response.send_message(
                "Il semblerait que vous ne puissez interagir ici.", ephemeral=True
            )
            return
        thread: discord.Thread = interaction.channel

        try:
            await has_any_roles_predicate(interaction, "Administrateur", "Modérateur")
        except MissingAnyRole:
            await interaction.response.send_message(
                "Vous ne pouvez pas clôturer vous-même le ticket.", ephemeral=True
            )
            return

        result: Optional[Result[TicketModel]] = database_executor.execute(
            select(TicketModel).where(TicketModel.thread_id == thread.id).limit(1)
        )
        if not result:
            logger.fatal(
                "No answer from database for ticket with thread %d.", thread.id
            )
            await interaction.response.send_message(
                "Aucune réponse reçue de la base de données."
            )
            return
        ticket: Optional[TicketModel] = result.scalar_one_or_none()
        if not ticket:
            logger.error("Ticket with thread %d was not found in database.", thread.id)
            await interaction.response.send_message(
                "Le ticket n'a pas été trouvée dans la base de données."
            )
            return
        if ticket.closed:
            await interaction.response.send_message("Ce ticket a déjà été fermé.")
            return

        await interaction.response.send_message("Fermeture du ticket en cours...")
        await thread.edit(
            archived=True, locked=True, name=thread.name.replace("Ouvert", "Fermé")
        )

        database_executor.execute(
            update(TicketModel)
            .where(TicketModel.ticket_id == ticket.ticket_id)
            .values(closed=True)
        )
        await interaction.edit_original_response(content="Ticket fermé et archivé.")


async def setup(bot: Bot) -> None:
    """
    Register ready Cog
    """
    await bot.add_cog(Ticket())
