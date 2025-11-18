import logging
from typing import Any, Optional

from sqlalchemy import Executable
from sqlalchemy.engine import Result
from sqlalchemy.orm.session import Session

from . import engine

logger: logging.Logger = logging.getLogger(__name__)


def execute(statement: Executable, *args: Any) -> Optional[Result[Any]]:
    """
    Execute SQL statement in session

    Parameters
    ----------
    statement : Executable
        statement to execute
    args : Tuple[Any]
        query's arguments

    Returns
    -------
    Optional[Result[Any]]
        Potential answer from the database
    """
    with Session(engine, expire_on_commit=False) as session:
        try:
            result: Result[Any] = session.execute(
                statement, *args, execution_options={"prebuffer_rows": True}
            )
            try:
                session.commit()
                return result
            except Exception as err:
                session.rollback()
                logger.fatal(f"Could not commit query: {err}")
                return None
        except Exception as err:
            logger.fatal(f"Could not execute statement: {err}")
    return None
