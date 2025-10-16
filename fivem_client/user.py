class User:
    def __init__(self
                 , name: str
                 , id: int
                 , discordid: int
                 , ping: int):
        self.__name = name
        self.__id = id
        self.__discordid = discordid
        self.__ping = ping
        
    @property
    def name(self):
        return self.__name
    
    @property
    def discordid(self) -> int:
        """Returns the user discord id"""
        return self.__discordid

    @property
    def ping(self) -> int:
        """Returns the user ping """
        return self.__ping

    @property
    def id(self) -> int:
        return self.__id    
    