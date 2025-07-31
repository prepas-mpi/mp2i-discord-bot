from typing import List, Optional

import re
import logging

from datetime import datetime

import discord
from discord import app_commands, AppCommandType
from discord.client import Client
from discord.ext.commands import Cog, hybrid_command, guild_only, Range
from discord.app_commands import autocomplete, Choice, choices
from discord.guild import Guild
from discord.member import Member
from discord.message import Message
from discord.role import Role
from sqlalchemy import func, select, update

from mp2i.wrappers.member import MemberWrapper
from mp2i.wrappers.guild import GuildWrapper
from mp2i.models import MemberModel, SchoolModel, CPGEModel, PostCPGEModel
from mp2i.utils import database
from mp2i.utils.school_manager import SchoolManager
from mp2i.utils.discord import defer, has_any_role, EmbedPaginator
import random

logger = logging.getLogger(__name__)

class School(Cog):
    """
    Interface to manage schools.
    """

    def __init__(self, bot):
        self.bot: Client = bot
        self.manager = SchoolManager()
        ctx_menu = app_commands.ContextMenu(
            name="Profil",
            callback=self.get_profile,
            type=AppCommandType.user
        )
        ctx_menu.guild_only = True
        self.bot.tree.add_command(ctx_menu)

        # Interactions to promote someone to referent

        ctx_menu = app_commands.ContextMenu(
            name="Passer référent cpge",
            callback=self.make_referent_cpge,
            type=AppCommandType.user
        )
        ctx_menu.guild_only = True
        ctx_menu.checks.append(has_any_role("Modérateur", "Administrateur").predicate)
        self.bot.tree.add_command(ctx_menu)

        ctx_menu = app_commands.ContextMenu(
            name="Passer référent école",
            callback=self.make_referent_postcpge,
            type=AppCommandType.user
        )
        ctx_menu.guild_only = True
        ctx_menu.checks.append(has_any_role("Modérateur", "Administrateur").predicate)
        self.bot.tree.add_command(ctx_menu)

        # Let referent pin messages in their school's thread

        ctx_menu = app_commands.ContextMenu(
            name="(Dés)épingler le message",
            callback=self.un_pin_message,
            type=AppCommandType.message
        )
        ctx_menu.guild_only = True
        ctx_menu.checks.append(has_any_role("Référent CPGE", "Référent École").predicate)
        self.bot.tree.add_command(ctx_menu)

    async def make_referent(self, type: str, interaction: discord.Interaction, guild_member: discord.Member):
        """
        Promote a member to referent of their school

        Parameters
        ----------
        type: type of the school cpge or postcpge
        interaction: discord event when someone trigger the interaction
        guild_member: future referent
        """
        guild: Optional[Guild] = interaction.guild
        if not guild:
            await interaction.followup.send("Guilde non trouvée.")
            return
        guild_wrapper: GuildWrapper = GuildWrapper(guild)
        member: MemberWrapper = MemberWrapper(guild_member)
        school_id: int = member.cpge if type == "cpge" else member.postcpge
        school: Optional[SchoolModel] = self.manager.get_guild_school(guild.id, school_id)

        if not school:
            await interaction.followup.send(f"Cet utilisateur n'est dans aucune école de type {type}.")
            return

        role: Optional[discord.Role] = guild_wrapper.get_role_by_qualifier("Référent CPGE" if type == "cpge" else "Référent École")
        if not role:
            await interaction.followup.send("Aucun rôle référent n'a été trouvé.")
            return

        logger.info(f"{interaction.user.id} has attempted to make {guild_member.id} referent of {school.name}.")

        await interaction.response.send_message(f"Attribution d'un référent à {school.name}...")

        referent_symbol: str = "@" if type == "cpge" else "#"

        if school.referent:
            await interaction.edit_original_response(content="Suppression de l'ancien référent...")
            old_referent: Optional[Member] = guild.get_member(school.referent)
            if old_referent:
                await interaction.edit_original_response(content="Suppression du rôle")
                await old_referent.remove_roles(role)
                nick: Optional[str] = old_referent.nick
                if nick:
                    await interaction.edit_original_response(content="Mise à jour du pseudonyme...")
                    old_referent.nick = nick.replace(referent_symbol, "|")

        await interaction.edit_original_response(content="Changement dans la base de donnée...")
        school.referent = member.id
        database.execute(
            update(SchoolModel)
            .where(SchoolModel.id == school.id)
            .values(referent=school.referent)
        )

        await interaction.edit_original_response(content="Mise à jour des rôles...")
        await guild_member.add_roles(role)
        await interaction.edit_original_response(content="Mise à jour du pseudonyme...")
        nick: Optional[str] = guild_member.nick
        if nick:
            guild_member.nick = nick.replace("|", referent_symbol)
        else:
            guild_member.nick = f"{guild_member.name} {referent_symbol} {school.name}"

        await interaction.edit_original_response(content=f"{guild_member.mention} est maintenant référent de {school.name}")

    async def make_referent_cpge(self, interaction: discord.Interaction, guild_member: discord.Member):
        """
        Promote someone as referent of CPGE school

        Parameters
        ----------
        interaction: discord event when someone trigger the interaction
        guild_member: future referent
        """
        await self.make_referent("cpge", interaction, guild_member)

    async def make_referent_postcpge(self, interaction: discord.Interaction, guild_member: discord.Member):
        """
        Promote someone as referent of CPGE school

        Parameters
        ----------
        interaction: discord event when someone trigger the interaction
        guild_member: future referent
        """
        await self.make_referent("postcpge", interaction, guild_member)

    @defer(ephemeral=True)
    async def un_pin_message(self, interaction: discord.Interaction, message: discord.Message):
        """
        Let referents pin or unpin messages in their school's thread

        Parameters
        ----------
        interaction: discord event when someone trigger the interaction
        message: message to be (un)pinned
        """
        if not isinstance(message.channel, discord.Thread):
            await interaction.followup.send("Vous devez être dans le canal de discussion d'un établissement.")
            return

        thread: discord.Thread = message.channel
        matching_thread: List[SchoolModel] = [
            school for school in self.manager.get_guild_all_schools(interaction.guild.id)
            if school.channel == thread.id
        ]
        if len(matching_thread) == 0:
            await interaction.followup.send("Ce canal n'est relié à aucun établissement.")
            return

        if matching_thread[0].referent != interaction.user.id:
            await interaction.followup.send("Vous n'êtes pas référent de cet établissement.")
            return

        if message.id == thread.id:
            await interaction.followup.send("Vous ne pouvez pas interagir avec ce message.")
            return

        if message.pinned:
            await message.unpin()
            await interaction.followup.send("Message désépinglé.")
        else:
            await message.pin()
            await interaction.followup.send("Message épinglé.")
        pass

    @Cog.listener()
    async def on_ready(self):
        """
        Register schools by guilds
        """
        for guild_raw in self.bot.guilds:
            guild: GuildWrapper = GuildWrapper(guild_raw)
            self.manager.cpge[guild.guild.id] = database.execute(
                select(CPGEModel)
                .where(CPGEModel.guild == guild.id)
                .order_by(CPGEModel.name)
            ).scalars().all()
            self.manager.postcpge[guild.guild.id] = database.execute(
                select(PostCPGEModel)
                .where(PostCPGEModel.guild == guild.id)
                .order_by(PostCPGEModel.name)
            ).scalars().all()

    @Cog.listener()
    async def on_raw_member_remove(self, raw_event: discord.RawMemberRemoveEvent):
        """
        Remove member as referent if it was

        Parameters
        ----------
        member: leaving member
        """
        schools: List[SchoolModel] = self.manager.get_guild_all_schools(raw_event.guild_id)
        matching_school = [school for school in schools if school.referent == raw_event.user.id]
        if len(matching_school) == 0:
            return
        matching_school[0].referent = None
        database.execute(
            update(SchoolModel)
            .where(SchoolModel.id == matching_school[0].id)
            .values(referent=school.referent)
        )

    async def autocomplete_school(
        self, interaction: discord.Interaction, current: str
    ) -> List[Choice[str]]:
        """
        Return a list of school corresponding to current text.
        """
        await interaction.response.defer()  # Defer the response to avoid timeout
        if not interaction.guild:
            return []

        type = interaction.namespace.type
        if type == "cpge":
            schools = self.manager.get_guild_cpge(interaction.guild.id)
        elif type == "postcpge":
            schools = self.manager.get_guild_postcpge(interaction.guild.id)
        else:
            schools = self.manager.get_guild_all_schools(interaction.guild.id)

        filtered_schools = [s for s in schools if current.lower().strip() in s.name.lower()]
        return [Choice(name=s.name, value=s.name) for s in filtered_schools[:20]]

    @hybrid_command(name="create_school")
    @guild_only()
    @has_any_role("Administrateur")
    @choices(
        type=[
            Choice(name="CPGE", value="cpge"),
            Choice(name="Poursuite d'études", value="postcpge"),
        ]
    )
    @defer(ephemeral=True)
    async def create_school(self, ctx, type: str, school_name: str, thread: discord.Thread):
        """
        Register a school in database
        """
        guild: GuildWrapper = GuildWrapper(ctx.guild)
        # check if school does not already exist
        matching_names = [
            school for school in self.manager.get_guild_all_schools(guild.guild.id)
            if school_name.lower() == school.name.lower()
        ]
        if len(matching_names) > 0:
            await ctx.reply("Un établissement avec ce nom existe déjà.")
            return

        await thread.join()

        # register school
        reply = await ctx.reply(content="Enregistrement de l'école dans la base de données.")
        school = None
        if type == "cpge":
            school = CPGEModel(
                name=school_name,
                guild=guild.id,
                channel=thread.id,
            )
            self.manager.cpge[guild.guild.id].append(school)
        else:
            school = PostCPGEModel(
                name=school_name,
                guild=guild.id,
                channel=thread.id,
            )
            self.manager.postcpge[guild.guild.id].append(school)
        # register preivously created object into database
        with database.Session(database.engine, expire_on_commit=False) as session:
            session.add(school)
            session.commit()
        await reply.edit(
            content=f"Établissement `{school_name}` enregistré et " + \
            f"le channel de discussion est disponible ici : {thread.jump_url}."
        )

    @hybrid_command(name="school")
    @guild_only()
    @has_any_role("MP2I", "MPI", "Ex MPI", "Intégré", "Modérateur", "Administrateur")
    @autocomplete(school=autocomplete_school)
    @choices(
        type=[
            Choice(name="CPGE", value="cpge"),
            Choice(name="Poursuite d'études", value="postcpge"),
        ]
    )
    async def school_selection(
        self, ctx, type: str, school: str, user: Optional[discord.Member] = None
    ):
        """
        Associe une CPGE ou une école à un membre (Aucun pour supprimer l'association)

        Parameters
        ----------
        type : CPGE ou Poursuite d'études
        school: Le nom de l'école à associer.
        user: Réservé aux Administrateurs et Modérateurs
            L'utilisateur à qui on associe l'école (par défaut, l'auteur de la commande)
        """
        guild: GuildWrapper = GuildWrapper(ctx.guild)
        if user is None or user == ctx.author:
            member = MemberWrapper(ctx.author)
        elif ctx.author.guild_permissions.manage_roles:
            member = MemberWrapper(user)
        else:
            await ctx.reply("Vous n'avez pas les droits suffisants.", ephemeral=True)
            return

        response = f"L'école {school} n'existe pas"
        list_of_schools = []

        if type == "cpge":
            if school == "Aucun":
                response = f"{member.name} ne fait plus partie d'une CPGE."
                member.cpge = None
            else:
                list_of_schools = self.manager.get_guild_cpge(guild.guild.id)
        elif type == "postcpge":
            if school == "Aucun":
                response = f"{member.name} ne fait plus partie d'aucune école."
                member.postcpge = None
            else:
                list_of_schools = self.manager.get_guild_postcpge(guild.guild.id)
        else:
            response = "Veuillez choisir un type entre `cpge` et `postcpge`."
            return

        print(list_of_schools)
        matches = [s for s in list_of_schools if school in s.name]
        if len(matches) > 0: 
            response = f"{member.name} fait maintenant partie de {matches[0].name}."
            if type == "cpge":
                member.cpge = matches[0].id
            else:
                member.postcpge = matches[0].id

        await ctx.reply(response, ephemeral=True)

    @hybrid_command(name="generation")
    @has_any_role("MP2I", "MPI", "Ex MPI", "Intégré", "Modérateur", "Administrateur")
    @guild_only()
    async def generation(
        self,
        ctx,
        year: Range[int, 2021, datetime.now().year],
        user: Optional[discord.Member] = None,
    ):
        """
        Définit l'année d'arrivée en sup

        Parameters
        ----------
        year: L'année d'arrivée en sup
        user: Réservé aux modérateurs
            L'utilisateur à qui on associe la date (par défaut, l'auteur de la commande)
        """
        member = MemberWrapper(ctx.author)
        if user is None or user == ctx.author:
            member.generation = year
            await ctx.reply(
                f"Vous faites maintenant partie de la génération {year} !",
                ephemeral=True,
            )
        elif member.guild_permissions.manage_roles:
            MemberWrapper(user).generation = year
            await ctx.reply(
                f"{user.mention} fait maintenant partie de la génération {year} !",
                ephemeral=True,
            )
        else:
            await ctx.reply("Vous n'avez pas les droits suffisants.", ephemeral=True)

    @hybrid_command(name="members")
    @guild_only()
    @autocomplete(school_name=autocomplete_school)
    @defer(ephemeral=False)
    async def members(self, ctx, school_name: str):
        """
        Affiche les étudiants d'une école donnée.
        """
        guild: GuildWrapper = GuildWrapper(ctx.guild)

        # get list of potential schools
        school_list: List[SchoolModel] = [
            school for school in self.manager.get_guild_all_schools(guild.guild.id)
            if school_name in school.name
        ]
        if len(school_list) < 0:
            ctx.reply(f"L'établissement `{school_name}` n'est pas enregistré.")
            return
        # get the first one
        school: SchoolModel = sorted(school_list, key=lambda s: s.name)[0]

        # retrieve members that belong to the school 
        students: List[MemberModel] = database.execute(
            select(MemberModel)
            .where((MemberModel.cpge if school.type == "CPGE" else MemberModel.postcpge) == school.id
                   and MemberModel.guild_id == guild.id)
        ).scalars().all()

        if not students:
            await ctx.reply(f"`{school.name}` n'a aucun étudiant enregistré.")
            return

        # fetch discord members from students' id
        discord_members = [await guild.guild.fetch_member(s.id) for s in students]

        # find referent if exists
        referents: List[Member] = [student for student in discord_members if student.id == school.referent]
        referent: Optional[Member] = None
        if len(referents) > 0:
            referent = referents[0]

        content_header: str = f"Nombre d'étudiants : {len(students)}\n"
        if referent:
            status = guild.get_emoji_by_name(f"{referent.status}")
            content_header += f"Référent : `{referent.name}`・{referent.mention} {status}\n\n"
        else:
            content_header += "Cet établissement n'a pas encore de référent\n\n"
        content_body: List[str] = []
        for member in discord_members:
            # Do not display referent twice
            if member == referent:
                continue
            content_body.append(f"- `{member.name}`・{member.mention}\n")

        content_body = random.sample(content_body, len(content_body))
        embed = EmbedPaginator(
            title=f"Liste des étudiants à {school.name}",
            colour=0xFF66FF,
            content_header=content_header,
            content_body=content_body,
            nb_by_pages=15,
            footer=self.bot.user.name,
            author_id=ctx.author.id,
            timeout=300,
        )
        await embed.send(ctx)

    @hybrid_command(name="referents")
    @guild_only()
    @choices(
        type=[
            Choice(name="CPGE", value="cpge"),
            Choice(name="Poursuite d'études", value="postcpge"),
        ]
    )
    @defer()
    async def referents(self, ctx, type: Optional[str] = "cpge") -> None:
        """
        Liste les étudiants référents du serveur.
        """
        guild = GuildWrapper(ctx.guild)
        referent_role: Optional[Role] = None
        schools = []

        if type == "cpge":
            referent_role = guild.get_role_by_qualifier("Référent CPGE")
            schools = self.manager.get_guild_cpge(guild.guild.id)
        elif type == "postcpge":
            referent_role = guild.get_role_by_qualifier("Référent École")
            schools = self.manager.get_guild_postcpge(guild.guild.id)
        else:
            await ctx.reply("Type d'établissement non reconnu.")
            return

        if referent_role is None:
            raise ValueError("Corresponding referent role is not in bot config file.")

        schools = [school for school in schools if school.referent]
        referents = [(await guild.guild.fetch_member(school.referent), school) for school in schools]

        content = ""
        for member, school in sorted(referents, key=lambda k: k[1].name):
            status = guild.get_emoji_by_name(f"{member.status}")
            content += f"- **{school.name}** : `{member.name}`・{member.mention} {status}\n"

        embed = discord.Embed(
            title=f"Liste des {referent_role.name} du serveur {guild.name}",
            colour=0xFF66FF,
            description=content,
            timestamp=datetime.now(),
        )
        embed.set_footer(text=self.bot.user.name)
        await ctx.send(embed=embed)

    # PROFILE COMMANDS

    async def generate_profile(self, ctx, user: discord.Member, member: Optional[discord.Member] = None) -> None:
        """
        Consulte les infos d'un membre.

        Parameters
        ----------
        user : discord.Member
            Membre qui exécute la commande.
        member : discord.Member
            Membre à consulter.
        ephemeral : bool
            Message personnel.
        """
        member: MemberWrapper = MemberWrapper(member or user)
        embed = discord.Embed(title="Profil", colour=int(member.profile_color, 16))
        embed.set_author(name=member.name)
        if member.avatar is None:
            embed.set_thumbnail(url=member.default_avatar.url)
        else:
            embed.set_thumbnail(url=member.avatar.url)
        embed.add_field(name="Pseudo", value=member.mention)
        embed.add_field(name="Membre depuis", value=f"{member.joined_at:%d/%m/%Y}")
        embed.add_field(name="Messages", value=member.messages_count)
        embed.add_field(
            name="Rôles",
            value=" ".join(r.mention for r in reversed(member.roles) if r.name != "@everyone"),
        )
        if member.cpge:
            cpge: Optional[CPGEModel] = self.manager.get_cpge(ctx.guild.id, member.cpge)
            if cpge:
                embed.add_field(name="CPGE", value=cpge.name)
        if member.generation > 0:
            embed.add_field(name="Génération", value=member.generation)
        if member.postcpge:
            postcpge: Optional[PostCPGEModel] = self.manager.get_postcpge(ctx.guild.id, member.postcpge)
            if postcpge:
                embed.add_field(name="Poursuite d'études", value=postcpge.name)

        await ctx.send(embed=embed)

    @defer(ephemeral=True)
    async def get_profile(self, interaction: discord.Interaction, member: discord.Member):
        """
        Consulte les infos d'un membre.

        Parameters
        ----------
        interaction : discord.Interaction
            Interaction du contexte.
        member : discord.Member
            Membre à consulter.
        """
        await self.generate_profile(interaction.followup, interaction.user, member)

    @hybrid_command(name="profile")
    @guild_only()
    async def profile(self, ctx, member: Optional[discord.Member] = None) -> None:
        """
        Consulte les infos d'un membre.

        Parameters
        ----------
        member : discord.Member
            Membre à consulter.
        """
        await self.generate_profile(ctx, ctx.author, member)

async def setup(bot) -> None:
    await bot.add_cog(School(bot))
