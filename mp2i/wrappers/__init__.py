from typing import Any, Generic, TypeVar

T = TypeVar("T")


class ObjectWrapper(Generic[T]):
    """
    Wrap an object
    """

    def __init__(self, boxed: T) -> None:
        """
        Save boxed object in variable

        Parameters
        ----------
        boxed : T
            Generic object
        """
        self._boxed: T = boxed

    def __getattr__(self, name: str) -> Any:
        """
        Getting attribute of the boxed object

        Parameters
        ----------
        name : str
            Attribute's name

        Returns
        -------
        Any
            The corresponding attribute

        Raises
        ------
        AttributeError
            If no attribute with the given name has been found in boxed object
        """
        if hasattr(self._boxed, name):
            return getattr(self._boxed, name)

        raise AttributeError(
            f"Attribute {name} not found in {type(self._boxed).__name__}."
        )
