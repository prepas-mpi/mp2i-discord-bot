import asyncio
import logging
from typing import Optional, Tuple

import discord
import humanize
from discord.app_commands import ContextMenu, guild_only
from discord.ext.commands import Bot, Cog, GroupCog
from sqlalchemy import Result, literal, select

import mp2i.database.executor as database_executor
from mp2i.database.models.academy import AcademyModel
from mp2i.utils.config import get_text_from_static_file
from mp2i.utils.discord import has_any_roles_predicate
from mp2i.utils.email import send_email, verification_code_generator
from mp2i.wrappers.guild import GuildWrapper

logger: logging.Logger = logging.getLogger(__name__)


@guild_only()
class Roles(GroupCog, name="roles", description="Gestion des roles"):
    """
    Manage academies and role attribution
    """

    def __init__(self, bot: Bot):
        """
        Initialize common strings

        Parameters
        ----------
        bot : Bot
            The bot
        """
        self._bot = bot
        self._dm_message: str = get_text_from_static_file("text/prof/greetings.md")
        self._followup: str = get_text_from_static_file("text/prof/follow.md")
        self._mail: str = get_text_from_static_file("text/prof/mail.md")
        self._hardness: int = 6
        self._timeout: int = 5 * 60

        ctx_menu: ContextMenu = ContextMenu(
            name="Définir comme message de rôles",
            callback=self.observe_command,
            type=discord.AppCommandType.message,
        )
        ctx_menu.guild_only = True
        ctx_menu.add_check(
            lambda interaction: has_any_roles_predicate(interaction, "Administrateur")
        )
        bot.tree.add_command(ctx_menu)
        self._roles: dict[int, dict[str, tuple[discord.Role, int]]] = {}

    async def _prof_verification(
        self, member: discord.Member, role: discord.Role
    ) -> None:
        """
        Verify that the member is eligible for Professor role

        Parameters
        ----------
        member : discord.Member
            The member who wants the role

        role : discord.Role
            The prof's role
        """
        await member.send(self._dm_message)
        try:
            message: discord.Message = await self._bot.wait_for(
                "message",
                check=lambda message: message.channel == member.dm_channel,
                timeout=self._timeout,
            )
            received_message: str = message.content.strip()
            result: Optional[Result[AcademyModel]] = database_executor.execute(
                select(AcademyModel).where(
                    AcademyModel.guild_id == member.guild.id,
                    literal(received_message).endswith(AcademyModel.domain_name),
                )
            )
            if not result:
                await member.send(
                    "La connexion avec la base de donnée n'a pas pu être faite. Nous vous invitons à contacter un membre de l'administration."
                )
                return
            if len(list(result.scalars())) == 0:
                await member.send(
                    "Nous n'avons pas pu établir de correspondance entre votre adresse mail et une académie. Nous vous invitons à contacter un membre de l'administration."
                )
                return

            verification_code: str = verification_code_generator(self._hardness)

            if not send_email(
                received_message,
                "[Prépas MP2I/MPI] Vérification de votre adresse mail",
                self._mail.format(username=member.name, code=verification_code),
            ):
                await member.send(
                    "Nous n'avons pas pu vous envoyer d'email. Nous vous invitons à contacter un membre de l'administration."
                )
                return

            await member.send(
                self._followup.format(
                    nb=self._hardness, time=humanize.naturaldelta(self._timeout)
                )
            )
            message = await self._bot.wait_for(
                "message",
                check=lambda message: message.channel == member.dm_channel,
                timeout=self._timeout,
            )
            if verification_code != message.content.strip():
                await member.send(
                    "Le code entré n'est pas correct. Nous vous invitons à contacter un membre de l'administration."
                )
                return

            await member.add_roles(role)
            await member.send("Le rôle de professeur vous a été attribué.")

        except asyncio.TimeoutError:
            await member.send(
                "Le délai d'attente est passé, merci de recommencer la procédure."
            )
        except Exception as err:
            logger.fatal(
                "An error occurred when a prof was verifying their account.",
                err,
                exc_info=True,
            )
            await member.send(
                "Une erreur est survenue lors de la procédure. Nous vous invitons à contacter un membre de l'administration."
            )

    async def observe_command(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        """
        Context menu to observe a message as message role

        Parameters
        ----------
        interaction : discord.Interaction
            The context command

        message : discord.Message
            The concerned message
        """
        if not interaction.guild:
            return
        guild: GuildWrapper = GuildWrapper(interaction.guild)
        guild.roles_message_id = message.id
        await interaction.response.send_message("Message défini.", ephemeral=True)

    @Cog.listener("on_ready")
    async def populate_roles(self) -> None:
        """
        Get selectionnable roles for guilds
        """
        for guild in self._bot.guilds:
            self._roles[guild.id] = GuildWrapper(guild).selectionnable_roles

    @Cog.listener("on_raw_reaction_add")
    async def reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """
        Add role when reacting to roles' message

        Parameters
        ----------
        payload : discord.RawReactionActionEvent
            Event when adding a reaction
        """
        if not payload.member:
            return
        guild: GuildWrapper = GuildWrapper(payload.member.guild)
        if guild.roles_message_id != payload.message_id:
            return

        member: discord.Member = payload.member
        roles: dict[str, Tuple[discord.Role, int]] = self._roles[guild.id]

        was_mpi: bool = roles.get("MPI", [])[0] in member.roles
        await member.remove_roles(*map(lambda r: r[0], roles.values()))
        for role_name, (role, emoji) in roles.items():
            if emoji != payload.emoji.id:
                continue
            if role_name == "Prof":
                await self._prof_verification(member, role)
                return
            elif (
                role_name == "Intégré"
                and was_mpi
                and (ex_mpi := roles.get("Ex MPI", None))
            ):
                await member.add_roles(ex_mpi[0])
            await member.add_roles(role)
            return


async def setup(bot: Bot) -> None:
    """
    Setting up Roles

    Parameters
    ----------
    bot : Bot
        The bot
    """
    await bot.add_cog(Roles(bot))
