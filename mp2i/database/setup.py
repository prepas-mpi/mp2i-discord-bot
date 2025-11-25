import logging

from sqlalchemy import Inspector, inspect

from . import engine
from .models import Base

# Import so that models are registered in Base's metadata
from .models.academy import AcademyModel as AcademyModel
from .models.guild import GuildModel as GuildModel
from .models.member import MemberModel as MemberModel
from .models.pin import PinModel as PinModel
from .models.promotion import PromotionModel as PromotionModel
from .models.sanction import SanctionModel as SanctionModel
from .models.school import SchoolModel as SchoolModel
from .models.suggestion import SuggestionModel as SuggestionModel
from .models.ticket import TicketModel as TicketModel
from .models.user import UserModel as UserModel

logger: logging.Logger = logging.getLogger(__name__)


def test_connection() -> bool:
    """
    Test that a connection with the database can be done

    Returns
    -------
    bool
        True if the test is a succes, False otherwise
    """
    if not engine:
        logger.warning("Attempt to connect to database but no engine was setup.")
        return False
    try:
        engine.connect()
    except Exception as err:
        logger.fatal(f"Could not connect to database: {err}")
        return False
    return True


def initialize_database() -> bool:
    """
    Initialize database if needed

    Returns
    -------
    bool
        True if database is initialized, False otherwise
    """
    if not engine:
        logger.warning("Engine is not setup.")
        return False
    try:
        inspector: Inspector = inspect(engine)
        if not inspector.has_table("guilds"):
            logger.info("Creating tables...")
            Base.metadata.create_all(engine)
            inspector = inspect(engine)
        else:
            logger.info("Tables already created.")
        return inspector.has_table("guilds")
    except Exception as err:
        logger.fatal(f"Could not connect or create tables: {err}")
        return False
