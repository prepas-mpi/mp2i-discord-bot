class InsertException(Exception):
    """
    Insertion exception
    """

    def __init__(self, type: str):
        super().__init__("Could not insert %s in database.", type)


class ReturningElementException(Exception):
    """
    Exception when a query didn't returned any expected object
    """

    def __init__(self, type: str):
        super().__init__(
            "An expected object from a query was expected but none have been found for %s.",
            type,
        )
