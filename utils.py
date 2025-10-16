import datetime
import discord
from discord.ext import commands
from io import BytesIO
import json


with open("./info.json", encoding="utf-8") as f:
    data = json.load(f)

def now() -> datetime.datetime:
    return datetime.datetime.now()

class Options:
    def __init__(self, bot):
        self.bot = bot
        
    def now() -> datetime.datetime:
        return datetime.datetime.now()
        
    async def avatar(self, user: discord.Member | discord.User):
        try:
            inbytes = await user.display_avatar.read()
        except:
            pass
        if user.avatar:
            return user.avatar.url
        with open(f"./1.png", 'wb') as f:
            f.write(inbytes)
        return discord.File("./1.png", filename="./1.png")
            


class Getguildinfo:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def get_user_avatar(self, user: discord.Member) -> str:
        try:
            d = user.avatar
            del d
            msgauurl = user.avatar.url
        except:
            r = BytesIO(await user.display_avatar.read())
            file = discord.File(fp=r, filename="whatever.png")
            v = self.bot.get_guild(self.bot.guilds[0].id).get_channel(data["cache"])
            g: discord.Message = await v.send(file=file)
            sttt = str(g.attachments).split('url=')[1]
            sttt = sttt.replace("'", "")
            sttt = sttt.replace(">", "")
            sttt = sttt.replace("]", "")
            msgauurl = sttt
        return msgauurl