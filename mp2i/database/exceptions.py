class InsertException(Exception):
    """
    Insertion exception
    """

    def __init__(self, type: str):
        super().__init__(f"Could not insert {type} in database.")


class ReturningElementException(Exception):
    """
    Exception when a query didn't returned any expected object
    """

    def __init__(self, type: str):
        super().__init__(
            f"An expected object from a query was expected but none have been found for {type}."
        )
