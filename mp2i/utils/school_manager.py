from typing import cast, Dict, List, Optional, TypeVar

from mp2i.models import SchoolModel, CPGEModel, PostCPGEModel

S = TypeVar('S', bound='SchoolModel')

class SchoolManager:
    """
    Manage schools buffer
    """
    
    _instance = None

    def __new__(cls):
        """
        Use for a singleton pattern
        """
        if not cls._instance:
            cls._instance = super(SchoolManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """
        Initialize instance's fields
        """
        self.cpge: Dict[int, List[CPGEModel]] = {}
        self.postcpge: Dict[int, List[PostCPGEModel]] = {}

    def get_guild_schools(self, school: Dict[int, List[S]], guild_id: int) -> List[S]:
        """
        Get specific schools for a guild

        Parameters
        ----------
        school: dictionnary mapping guilds' id to list of schools
        guild_id: guild'id
        """
        if not guild_id in school:
            return []
        return school[guild_id]

    def get_guild_all_schools(self, guild_id: int) -> List[SchoolModel]:
        """
        Get list of schools for a guild

        Parameters
        ----------
        guild_id: guild's id

        Return
        ------
        list of schools
        """
        schools: List[PostCPGEModel | CPGEModel] = self.get_guild_schools(self.cpge, guild_id) + self.get_guild_schools(self.postcpge, guild_id)
        return cast(List[SchoolModel], schools)

    def get_guild_school(self, guild_id: int, school_id: int) -> Optional[SchoolModel]:
        """
        Retrieve school from its id for a guild

        Parameters
        ----------
        guild_id: guild's id
        school_id: school's id

        Return
        ------
        School if exists or None
        """
        schools: List[PostCPGEModel | CPGEModel] = self.get_guild_schools(self.cpge, guild_id) + self.get_guild_schools(self.postcpge, guild_id)
        matching = [school for school in schools if school.id == school_id]
        if len(matching) == 0:
            return None
        return matching[0]

    def get_school(self, school: Dict[int, List[S]], guild_id: int, school_id: int) -> Optional[S]:
        """
        Retrieve generic school from its id for a guild

        Parameters
        ----------
        school: dictionnary containing generic schools
        guild_id: guild's id
        school_id: school's id

        Return
        ------
        Generic school if exists or None
        """
        schools = self.get_guild_schools(school, guild_id)
        matching: List[S] = [school for school in schools if school.id == school_id]
        return None if len(matching) == 0 else matching[0]

    def get_guild_cpge(self, guild_id: int) -> List[CPGEModel]:
        """
        Retrieve all cpge schools from a guild

        Parameters
        ----------
        guild_id: guild's id

        Return
        ------
        List of cpge schools
        """
        return self.get_guild_schools(self.cpge, guild_id)

    def get_guild_postcpge(self, guild_id: int) -> List[PostCPGEModel]:
        """
        Retrieve all postcpge schools from a guild

        Parameters
        ----------
        guild_id: guild's id

        Return
        ------
        List of postcpge schools
        """
        return self.get_guild_schools(self.postcpge, guild_id)
    
    def get_cpge(self, guild_id: int, school_id: int) -> Optional[CPGEModel]:
        """
        Retrieve a cpge school from its id of a guild

        Parameters
        ----------
        guild_id: guild's id
        school_id: school's id

        Return
        ------
        Cpge school or None
        """
        return self.get_school(self.cpge, guild_id, school_id)

    def get_postcpge(self, guild_id: int, school_id: int) -> Optional[PostCPGEModel]:
        """
        Retrieve a postcpge school from its id of a guild

        Parameters
        ----------
        guild_id: guild's id
        school_id: school's id

        Return
        ------
        Postcpge school or None
        """
        return self.get_school(self.postcpge, guild_id, school_id)

