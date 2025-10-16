"""this is a fivem moudle that you can use to see your fivem game info players slot and more"""
VERSION = 1
__name__ = 'fivem_client'
__author__ = 'idopy'
__email__ = "iddi1288@gmail.com"


import requests
from .user import User
from functools import wraps
import os
import re
import aiohttp

class Client:
    def __init__(self
                 , adderss: str
                 , port: int=30120):
        """Creates a client object for fivem server

        Args:
        -----
            adderss `str`: _the ip of the server_
            port `int`: _port of the server_
        """
        self.adderss = adderss
        self.port = port
        self.full = f'http://{adderss}:{port}'
        self.users = None   
        self.usersinfo: self.get_players_info = None 
        status = False
        if not re.findall(r'\d\d\d.\d\d\d.\d\d\d.\d\d\d', adderss):
            status = True
        if not re.findall(r'\d\d\d.\d\d.\d\d\d.\d\d\d', adderss):
            status = True
        if not status:
            raise \
                ValueError('Invalid ip adderss')
        if port not in [30120
                        , 30150
                        , 30170]:
            raise \
                ValueError('Invalid port')
            
    @property
    async def inq(self) -> int | None:
        """_Returns The players in the queue_

        Returns:
            int | None: _`None` if server is offline `int` the players in the queue_
        """
        url = f"{self.full}/dynamic.json"
        if not await self.serveronline: return None
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as data:
                re = await data.json(content_type=None)
                if int(re["clients"]) > int(re["sv_maxclients"]):
                    return int(re["clients"]) - int(re["sv_maxclients"])
                
            
    @property
    async def serveronline(self) -> bool:
        """_checks if the server is online_

        Returns:
        -------
            bool: _`True` if server is online `False` if oflline_
        """
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.full + "/info.json") as r:
                    return True
            except:
                return False


    @property
    async def discord_server(self) -> str | None:
        """_the discord server link_

        Returns:
        -------
            `str` | `None`: _`None` if server offline or unable to get the discord server link else: `str` the discord server link_
        """
        url = self.full + "/info.json"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    response = await response.json(content_type=None)
            except:        
                return None  
        vars = response["vars"]
        url = None
        try:
            url = vars["Discord"]
        except:
            pass  
        try:
            url = vars["discord"] 
        except:
            pass
        try:
            url = vars["DISCORD"]
        except:
            pass
        return url     


    @property
    async def language(self) -> str | None:
        """_return the language used in the server_

        Returns:
        --------
            `str` | `None`: _`str` is the language of the server for example: he-IL or `None` if the serever is offline_
        """
        url = self.full + "/info.json"
        async with aiohttp.ClientSession() as sess:
            try:
                async with sess.get(url) as f:
                    response = await f.json(content_type=None)
            except:
                return None  
        lang: str = response['vars']['locale']
        return lang
    
    @property
    async def resources(self) -> list[str] | None:    
        """_Return a list of resources used in server_

        Returns:
        -------
            `list[str]` | `None`: _`list[str]` list with the resources in the server `None` if the server offline_
        """
        url = self.full + "/info.json"
        async with aiohttp.ClientSession() as sess:
            try:
                async with sess.get(url) as f:
                    response = await f.json(content_type=None)
            except:
                return None  
        allused: list[str] = response['resources']
        return allused

    class loading_file:
        def __init__(selff, self):
            selff = self
            
        @property
        async def bytes(self) -> bytes | None:
            """_Returns the bytes of the loading screen_

            Returns:
                `bytes` | `None`: _`bytes` the bytes of the loading screen `None` if the server is offline_
            """
            url = self.full + "/info.json"
            async with aiohttp.ClientSession() as sess:
                try:
                    async with sess.get(url) as f:
                        response = await f.json(content_type=None)
                except:
                    return None  
            response = response.json(content_type=None)
            banner = response['vars']['banner_connecting']
            bytesobject = requests.get(banner)
            return bytesobject.content
        
        async def save(self, filename: str) -> str | None:
            """_Saves the loading screen to a file_

            Args:
            -----
                filename `str`: _the name of the file be saved_

            Returns:
            -------
                `str` | `None`: _`str` with the file location `None` if the Server offline_
            """
            url = self.full + "/info.json"
            async with aiohttp.ClientSession() as sess:
                try:
                    async with sess.get(url) as f:
                        response = await f.json(content_type=None)
                except:
                    return None 
            response = response.json(content_type=None)
            banner = response['vars']['banner_connecting']
            bytesobject = requests.get(banner)
            bytesobject = bytesobject.content
            location = f"{os.getcwd()}/{filename}"
            with open(location, 'wb') as f:
                f.write(bytesobject)
            return location

    
            
    async def get_current_slot(self) -> int | None:
        """_the slot of the players in the servers (max players)_

        Returns:
        -------
            `int` | `None`: _`int` the slot `None` if the server offline_
        """
        url = f"{self.full}/dynamic.json"
        async with aiohttp.ClientSession() as sess:
            try:
                async with sess.get(url) as f:
                    response = await f.json(content_type=None)
            except:
                return None 
        return int(response['sv_maxclients'])
        
    async def get_server_names(self) -> str | None:
        """Returns The server name"""
        url = f"{self.full}/dynamic.json"
        async with aiohttp.ClientSession() as sess:
            try:
                async with sess.get(url) as f:
                    response = await f.json(content_type=None)
            except:
                return None 
        return response['hostname']
    
    def get_map_name(self) -> str | None:
        """Returns The map name"""
        url = f"{self.full}/dynamic.json"
        try:
            response = requests.get(url)
        except:
            return None
        return response['mapname']
    
    def get_game_type(self) -> str | None:
        """Returns The type of the game"""
        url = f"{self.full}/dynamic.json"
        try:
            response = requests.get(url)
        except:
            return None
        response = response.json(content_type=None)
        return response['gametype']
    
    async def get_players_count(self) -> int | None:
        """Returns the number of players in the game"""
        url = f"{self.full}/dynamic.json"
        async with aiohttp.ClientSession() as sess:
            try:
                async with sess.get(url) as f:
                    response = await f.json(content_type=None)
            except:
                return None 
        return int(response['clients'])
    
        
    async def get_players_info(self) -> list[User] | None:
        """Get information about every connected player to the server
        Returns:
        ----------
            list[User]: _list of every user connected to the server_
        
        Raises:
        ----------
            RuntimeError: _Unable to connect server or the server is offline_
        """
        if not await self.serveronline: return None
        url = f"{self.full}/players.json"
        async with aiohttp.ClientSession() as ses:
            async with ses.get(url) as se:
                try:
                    response = await se.json(encoding='utf-8'
                                             , content_type=None)
                except:
                    return []
        list_of_players: list[User] = []
        if response is None:
            return []
        for player in response:
            playername = player['name']
            playerping = player['ping']
            playerid = player['id']
            ident = player['identifiers']
            playerdiscordid = None
            for i in ident:
                if 'discord:' in i:
                    playerdiscordid = int(i.split('discord:')[1])
            user = User(playername
                        , playerid
                        , playerdiscordid
                        , playerping)
            list_of_players.append(user)
        return list_of_players