import datetime
import logging
from typing import Optional

import discord
import discord.ui as ui
import humanize
from sqlalchemy import insert

import mp2i.database.executor as database_executor
from mp2i.database.models.member import MemberModel
from mp2i.database.models.sanction import SanctionModel, SanctionType
from mp2i.wrappers.guild import GuildWrapper
from mp2i.wrappers.member import MemberWrapper
from mp2i.wrappers.user import UserWrapper

logger: logging.Logger = logging.getLogger(__name__)


async def log_sanction(
    guild: discord.Guild,
    victim: discord.User,
    staff: Optional[discord.Member],
    type: SanctionType,
    send_dm: bool,
    reason: Optional[str] = None,
    duration: Optional[int] = None,
) -> None:
    guild_wrapper: GuildWrapper = GuildWrapper(guild, fetch=False)
    sanction_channel: Optional[discord.TextChannel] = (
        guild_wrapper.get_sanctions_channel
    )
    if not sanction_channel:
        logger.fatal(f"Can not find channel to log sanction for {victim.id}.")
        return
    victim_model: Optional[MemberModel] = UserWrapper(victim).as_member_model(guild)
    if not victim_model:
        logger.fatal(f"Can not log sanction for {victim.id} no model has been found.")
        return
    staff_wrapper: Optional[MemberWrapper] = MemberWrapper(staff) if staff else None
    database_executor.execute(
        insert(SanctionModel).values(
            guild_id=guild.id,
            victim_id=victim_model.member_id,
            staff_id=staff_wrapper.member_id if staff_wrapper else None,
            sanction_type=type,
            sanction_date=datetime.datetime.now(),
            sanction_reason=reason,
            sanction_duration=duration,
        )
    )
    dm_sent: bool = False
    if send_dm:
        try:
            await victim.send(view=LogVictim(type, duration, reason))
            dm_sent = True
        except discord.Forbidden:
            pass
    await sanction_channel.send(
        view=LogStaff(
            type, victim, staff, duration, reason, send_dm=send_dm, dm_sent=dm_sent
        ),
        allowed_mentions=discord.AllowedMentions.none(),
    )


class VictimText(ui.TextDisplay):
    def __init__(self, type: SanctionType):
        text: str = ""
        if type == SanctionType.WARN:
            text = "Vous avez été averti."
        elif type == SanctionType.TIMEOUT:
            text = "Vous avez été rendu muet."
        elif type == SanctionType.UNTIMEOUT:
            text = "Vous n'êtes plus muet."
        elif type == SanctionType.KICK:
            text = "Vous été expulsé."
        elif type == SanctionType.BAN:
            text = "Vous avez été banni."
        elif type == SanctionType.UNBAN:
            text = "Vous avez été débanni."
        super().__init__(text)


class StaffText(ui.TextDisplay):
    def __init__(self, user: discord.User, type: SanctionType):
        text: str = ""
        if type == SanctionType.WARN:
            text = f"{user.name} a été averti."
        elif type == SanctionType.TIMEOUT:
            text = f"{user.name} a été rendu muet."
        elif type == SanctionType.UNTIMEOUT:
            text = f"{user.name} n'est plus muet."
        elif type == SanctionType.KICK:
            text = f"{user.name} a été expulsé."
        elif type == SanctionType.BAN:
            text = f"{user.name} a été banni."
        elif type == SanctionType.UNBAN:
            text = f"{user.name} a été débanni."
        super().__init__(text)


class LogVictim(ui.LayoutView):
    def __init__(
        self, type: SanctionType, duration: Optional[int], reason: Optional[str]
    ):
        super().__init__()

        container: ui.Container = ui.Container()
        container.add_item(ui.TextDisplay("## Sanction"))
        container.add_item(VictimText(type))
        if duration:
            container.add_item(
                ui.TextDisplay(
                    f"La durée de la sanction est de {humanize.naturaldelta(duration)}"
                )
            )
        if reason:
            container.add_item(
                ui.TextDisplay(f"La raison de la sanction est ```yml\n{reason}\n```")
            )
        container.accent_colour = type.get_colour
        self.add_item(container)


class LogStaff(ui.LayoutView):
    """
    Log view for staff
    """

    def __init__(
        self,
        type: SanctionType,
        victim: discord.User,
        staff: Optional[discord.Member],
        duration: Optional[int],
        reason: Optional[str],
        send_dm: bool,
        dm_sent: bool,
    ):
        super().__init__()

        container: ui.Container = ui.Container()
        container.add_item(ui.TextDisplay("## Sanction"))
        container.add_item(StaffText(victim, type))
        if staff:
            container.add_item(
                ui.TextDisplay(f"La sanction a été infligée par {staff.mention}")
            )
        if duration:
            container.add_item(
                ui.TextDisplay(
                    f"La durée de la sanction est de {humanize.naturaldelta(duration)}"
                )
            )
        if reason:
            container.add_item(
                ui.TextDisplay(f"La raison de la sanction est ```yml\n{reason}\n```")
            )
        if send_dm:
            if dm_sent:
                container.add_item(ui.TextDisplay("L'utilisateur a été notifié."))
            else:
                container.add_item(
                    ui.TextDisplay("L'utilisateur n'a pas pu être notifié.")
                )
        container.accent_colour = type.get_colour
        self.add_item(container)
