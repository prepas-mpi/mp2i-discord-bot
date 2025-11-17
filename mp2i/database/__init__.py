import os
from logging import Logger, getLogger
from typing import Optional

from sqlalchemy import Connection, create_engine
from sqlalchemy.engine import Engine

logger: Logger = getLogger(__name__)
engine: Optional[Engine] = None

if __database_url := os.getenv("MP2I__DATABASE_URL"):
    try:
        engine = create_engine(__database_url.strip())
    except ImportError as err:
        logger.fatal(
            f"Could not create a database engine due to an import error: {err}"
        )
    except Exception as ex:
        logger.fatal(f"Unknown error has occurred when creating database engine: {ex}")
else:
    logger.fatal("Currently not supporting database system without a server.")


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
        conn: Connection = engine.connect()
        conn.close()
    except Exception as err:
        logger.fatal(f"Could not connect to database: {err}")
        return False
    return True
