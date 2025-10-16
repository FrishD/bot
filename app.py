import discord
from discord.ext import commands
import json
import datetime
import fivem_client
import os
import sqlite3
import asyncio
from discord.ext import commands, tasks
from discord.utils import get
intents = discord.Intents.all()
intents.typing = False
intents.presences = False
ip = "181.214.214.251"
client = fivem_client.Client(ip)
servername = "Hydra DM"
bot = commands.Bot(command_prefix='!', intents=intents)
bot.playerlisttimes: int = 0
bot.playerlist = []
bot.database = sqlite3.connect("database.db")
bot.db = bot.database.cursor()


@bot.event
async def setup_hook():
    for file in os.listdir("./cogs"):
        if file.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{file.replace('.py', '')}")
                print(f"Loaded cog: {file}")
            except Exception as e:
                print(f"Failed to load cog {file}: {e}")

# The on_message event listener for suggestions is being moved to a dedicated cog
# for better organization, though it could remain here. For now, we leave it.
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    suggestions_channel_id = 1236927913648062505
    if message.channel.id == suggestions_channel_id:
        excluded_role_id = 1109826341127331892
        if hasattr(message.author, 'roles') and message.guild.get_role(excluded_role_id) not in message.author.roles:
            await message.add_reaction("👍")
            await message.add_reaction("👎")


# on_member_join is now handled entirely by the blacklist cog.

# Website

@bot.command()
async def website(ctx):
    embed = discord.Embed(
        title="💳 תרומות HydraDM",
        description="",
        color=0x9932cc
    )
    embed.add_field(
        name="🏪 חדר תרומות Hydra DM : <#1116027990053228625>", 
        value="**החזר כספי = רשימה שחורה.**", 
        inline=False
    )
    embed.set_footer(text='כל הזכויות שמורות ל-HydraDM')
    embed.set_image(url="https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExYmY0aG05YnBxMzUxdnRsbzNpMmhzdGxoZ2piOTB3ODYwZm1pajV1MSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/84NhEQpMPMM3BM9DCa/giphy.gif")
    link_button = discord.ui.Button(
        style=discord.ButtonStyle.link, 
        label="🛒 קישור Tebex", 
        url="https://hydrarp.tebex.io/",
        emoji="💰"
    )
    view = discord.ui.View()
    view.add_item(link_button)
    await ctx.send(embed=embed, view=view)

#website finish

@bot.command()
@commands.has_permissions(administrator=True)
async def clear(ctx, amount=5):
    try:
        await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f'הודעות נמחקו!', delete_after=5)
    except commands.MissingPermissions:
        await ctx.send("אין לך הרשאה להשתמש בפקודה זו.", delete_after=5)
    except discord.HTTPException as e:
        await ctx.send(f"נכשל במחיקת הודעות: {e}", delete_after=5)

# IP

with open("./config.json", encoding="utf-8-sig") as f:
    data = json.load(f)
    
@bot.command()
async def ip(ctx: commands.Context):
    status = None
    async for m in ctx.guild.get_channel(data['server']['playerlist']).history(limit=2
                                                                                      , oldest_first=True):
        if m.embeds and m.author.id == bot.user.id:
            if not m.embeds[0].fields and not m.embeds[0].title:
                if "🟢" in m.embeds[0].footer.text:
                    playersin2 = await client.get_players_count()
                    slots2 = await client.get_current_slot()
                    description = f"**📊 סטטוס:** **` דלוק 🟢`**\n\n**📈 שחקנים:** **` {playersin2}/{slots2} `**\n\n**` connect 181.214.214.251 `**\n\n**📖 חוקים:** **` אל תשכחו לקרוא: ` <#1109910338352185367>**"
                    status = True
    if not status:
        description = "**📊 סטטוס:** `כבוי 🔴`"
    embed = discord.Embed(
        timestamp=datetime.datetime.now(),
        description=description,
        color=0x00ff00 if status else 0xff0000
    )            
    if status:
        slots = await client.get_current_slot()
        playersin = await client.get_players_count()
        embed.set_footer(
            text=f"שחקנים: {playersin}/{slots}",
            icon_url=data['ui']['thumbnail']
        )
    embed.set_author(
        name=f"🎮 {ctx.guild.name}",
        icon_url="https://images-ext-1.discordapp.net/external/tfv1_fxTzLNo4urcfGWShfgXBdcox3vwl-1CXqo29CA/%3Fsize%3D1024/https/cdn.discordapp.com/icons/1052668757044105266/a_94e369beeee517744c46f8f28e6ae708.gif"
    )
    embed.set_thumbnail(url="https://images-ext-1.discordapp.net/external/tfv1_fxTzLNo4urcfGWShfgXBdcox3vwl-1CXqo29CA/%3Fsize%3D1024/https/cdn.discordapp.com/icons/1052668757044105266/a_94e369beeee517744c46f8f28e6ae708.gif")
    embed.set_image(url='https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExYmY0aG05YnBxMzUxdnRsbzNpMmhzdGxoZ2piOTB3ODYwZm1pajV1MSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/84NhEQpMPMM3BM9DCa/giphy.gif')
    button = discord.ui.Button(
        style=discord.ButtonStyle.link, 
        label="התחבר", 
        url="https://cfx.re/join/qg4kj9"
    )
    
    view = discord.ui.View()
    view.add_item(button)
    await ctx.send(embed=embed, view=view)


@bot.command()
async def IP(ctx: commands.Context):
    status = None
    async for m in ctx.guild.get_channel(data['server']['playerlist']).history(limit=2
                                                                                      , oldest_first=True):
        if m.embeds and m.author.id == bot.user.id:
            if not m.embeds[0].fields and not m.embeds[0].title:
                if "🟢" in m.embeds[0].footer.text:
                    playersin2 = await client.get_players_count()
                    slots2 = await client.get_current_slot()
                    description = f"**📊 סטטוס:** **` דלוק 🟢`**\n\n**📈 שחקנים:** **` {playersin2}/{slots2} `**\n\n**` connect 181.214.214.251 `**\n\n**📖 חוקים:** **` אל תשכחו לקרוא: ` <#1109910338352185367>**"
                    status = True
    if not status:
        description = "**📊 סטטוס:** `כבוי 🔴`"
    embed = discord.Embed(
        timestamp=datetime.datetime.now(),
        description=description,
        color=0x00ff00 if status else 0xff0000
    )            
    if status:
        slots = await client.get_current_slot()
        playersin = await client.get_players_count()
        embed.set_footer(
            text=f"שחקנים: {playersin}/{slots}",
            icon_url=data['ui']['thumbnail']
        )
    embed.set_author(
        name=f"🎮 {ctx.guild.name}",
        icon_url="https://images-ext-1.discordapp.net/external/tfv1_fxTzLNo4urcfGWShfgXBdcox3vwl-1CXqo29CA/%3Fsize%3D1024/https/cdn.discordapp.com/icons/1052668757044105266/a_94e369beeee517744c46f8f28e6ae708.gif"
    )
    embed.set_thumbnail(url="https://images-ext-1.discordapp.net/external/tfv1_fxTzLNo4urcfGWShfgXBdcox3vwl-1CXqo29CA/%3Fsize%3D1024/https/cdn.discordapp.com/icons/1052668757044105266/a_94e369beeee517744c46f8f28e6ae708.gif")
    embed.set_image(url='https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExYmY0aG05YnBxMzUxdnRsbzNpMmhzdGxoZ2piOTB3ODYwZm1pajV1MSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/84NhEQpMPMM3BM9DCa/giphy.gif')
    button = discord.ui.Button(
        style=discord.ButtonStyle.link, 
        label="התחבר", 
        url="https://cfx.re/join/qg4kj9"
    )
    
    view = discord.ui.View()
    view.add_item(button)
    await ctx.send(embed=embed, view=view)

# Finish IP

@tasks.loop(seconds=18)
async def botstatus():
    guild = bot.get_guild(bot.guilds[0].id)
    status = await client.serveronline
    if status:
        s = f"{await client.get_players_count()}/{await client.get_current_slot()}"
    else:
        s = f"OFF"
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"[{s}] ({len(guild.members)})"))


@tasks.loop(seconds=18)
async def botstatus():
    guild = bot.get_guild(bot.guilds[0].id)
    status = await client.serveronline
    if status:
        s = f"{await client.get_players_count()}/{await client.get_current_slot()}"
    else:
        s = f"OFF"
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"[{s}] ({len(guild.members)})"))

# Finish Bot Status


channel_ids = [1109825363078549564, 1112286613217755216]

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

    for guild in bot.guilds:
        print(f"{guild.name} - {guild.id}") 
        
    # The functionality to clear channels on ready seems to be for development/testing.
    # I will leave it for now, but this could be removed for production.
    for channel_id in channel_ids:
        channel = bot.get_channel(channel_id)
        if channel:
            try:
                await channel.purge()
            except discord.errors.Forbidden:
                print(f"Lacking permissions to purge channel {channel_id}")
            except discord.errors.HTTPException as e:
                print(f"Failed to purge channel {channel_id}: {e}")

    if not playerlist.is_running():
        playerlist.start()
    if not botstatus.is_running():
        botstatus.start()

@commands.Cog.listener()
async def on_ready(self):
    print("Role Management cog on_ready triggered")
    await self.bot.wait_until_ready()
    
    channel = 'self.bot.get_channel(TARGET_CHANNEL_ID)'
    if not channel:
        print(f"ERROR: Role button channel with ID {TARGET_CHANNEL_ID} not found.")
        print(f"Available channels: {[c.id for c in self.bot.get_all_channels()]}")
        return
    
    print(f"Found channel: {channel.name}")

    # Check if a message with our view already exists
    message_found = False
    async for message in channel.history(limit=100):
        if message.author == self.bot.user and message.components:
            print(f"Found bot message with components: {message.id}")
            try:
                if message.components[0].children[0].custom_id == "role_button":
                    print("Role button message already exists.")
                    message_found = True
                    break
            except (IndexError, AttributeError) as e:
                print(f"Error checking message components: {e}")
                continue

    if not message_found:
        print("Role button message not found, sending new one.")
        embed = discord.Embed(
            title="🔧 ניהול תפקידים",
            description="לחץ על הכפתור כדי לקבל או להסיר את התפקיד.",
            color=0x5865f2
        )
        embed.set_image(url="https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExYmY0aG05YnBxMzUxdnRsbzNpMmhzdGxoZ2piOTB3ODYwZm1pajV1MSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/84NhEQpMPMM3BM9DCa/giphy.gif")
        try:
            sent_message = await channel.send(embed=embed, view=RoleButtonView())
            print(f"Successfully sent role management message: {sent_message.id}")
        except discord.Forbidden:
            print(f"ERROR: Missing permissions to send message in channel {TARGET_CHANNEL_ID}.")
        except Exception as e:
            print(f"ERROR: Failed to send message: {e}")


@tasks.loop(seconds=60)
async def playerlist():
    # if bot.playerlisttimes % 12 == 0:
        # await asyncio.sleep(20)
    bot.playerlisttimes += 1
    status = await client.serveronline
    playerlistchannel = bot.get_channel(1112286613217755216)
    guild = playerlistchannel.guild
    description1: str = ""
    description2: str = ""
    if status:
        players: list[fivem_client.User] = await client.get_players_info()
        count = await client.get_players_count()
        maxslots = await client.get_current_slot()
        try:
            space = int(count / maxslots * 180)
        except:
            space = 0
        if players:
            description1 += f"`📊` **סטטוס: מחובר**\n`👨` **שחקנים: [{count}/{maxslots}]**\n\n\n"
        else:
            description1 += f"`📊` **סטטוס: מחובר**\n`👨` **שחקנים: [{count}/{maxslots}]**\n\n\n"
        label1 = f"שחקנים: [{count}/{maxslots}]"
        label2 = "שחקנים (המשך)"
        footer = f'{servername} • מחובר 🟢'
        if players:
            half_count = len(players) // 2
            players1 = players[:half_count]
            players2 = players[half_count:]

        else:
            description1 += "**אין שחקנים בשרת!**\n"
        is1 = "מחובר"
    else:
        description1 += "`📊` **סטטוס: לא מחובר**"
        description2 += "`📊` **סטטוס: לא מחובר**"
        footer = f'{servername} • לא מחובר 🔴'
        label1 = "לא מחובר"
        label2 = "לא מחובר"
        is1 = "לא מחובר"
    color = 0x00ff00 if status else 0xff0000
    embed1 = discord.Embed(
        timestamp=datetime.datetime.now(),
        description=description1,
        color=color
    )
    embed1.set_author(
        name=f'🎮 {servername} - השרת {is1}',
        icon_url=guild.icon.url
    )
    embed1.set_footer(
        text=footer,
        icon_url=guild.icon.url
    )
    embed1.set_thumbnail(url=guild.icon.url)
    embed1.set_image(url="https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExYmY0aG05YnBxMzUxdnRsbzNpMmhzdGxoZ2piOTB3ODYwZm1pajV1MSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/84NhEQpMPMM3BM9DCa/giphy.gif")

    max_description_length = 2048

    if len(description1) > max_description_length:
        description1 = description1[:max_description_length - 3] + "..."

    embed2 = discord.Embed(
        timestamp=datetime.datetime.now(),
        description=description2,
        color=color
    )
    embed2.set_author(
        name=f'🎮 {servername} - השרת {is1}',
        icon_url=guild.icon.url
    )
    embed2.set_footer(
        text=footer,
        icon_url=guild.icon.url
    )
    embed2.set_thumbnail(url=guild.icon.url)
    embed2.set_image(url="https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExYmY0aG05YnBxMzUxdnRsbzNpMmhzdGxoZ2piOTB3ODYwZm1pajV1MSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/84NhEQpMPMM3BM9DCa/giphy.gif")

    if len(description2) > max_description_length:
        description2 = description2[:max_description_length - 3] + "..."

    st = discord.ButtonStyle.success if status else discord.ButtonStyle.danger
    if is1 == "מחובר":
        inq = await client.inq

    class Thebutton2(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label=f"📊 {label1}", disabled=True, style=st, emoji="👥")
        async def f(self, inter, bu):
            pass

        if is1 == "מחובר":
            if inq is not None:
                @discord.ui.button(
                    label=f"⏳ {inq} שחקנים בתור",
                    disabled=True,
                    style=discord.ButtonStyle.primary,
                    emoji="🕐"
                )
                async def fnt(self, igwwg, by6):
                    pass

    class Thebutton(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label=f"📊 {label2}", disabled=True, style=st, emoji="👥")
        async def f(self, inter, bu):
            pass

    status = False
    async for m in playerlistchannel.history():
        if m.author.id == bot.user.id and m.embeds:
            bot.playerlist.append(m)
            bot.playerlist.append(m.embeds[0])
            status = True
            break
    if not status:
        m1 = await playerlistchannel.send(embed=embed1, view=Thebutton())
        m2 = await playerlistchannel.send(embed=embed2, view=Thebutton2())
        bot.playerlist.append(m1)
        bot.playerlist.append(embed1)
        bot.playerlist.append(m2)
        bot.playerlist.append(embed2)
    if bot.playerlist:
        max_embed_description_length = 2048
        if len(embed1.description) > max_embed_description_length:
            embed1.description = embed1.description[:max_embed_description_length - 3] + "..."
        if len(embed2.description) > max_embed_description_length:
            embed2.description = embed2.description[:max_embed_description_length - 3] + "..."

        embed1.timestamp = datetime.datetime.now()
        embed2.timestamp = datetime.datetime.now()

        if len(bot.playerlist) >= 4:
            g1 = bot.playerlist[1].copy()
            g1.timestamp = embed1.timestamp
            g2 = bot.playerlist[3].copy()
            g2.timestamp = embed2.timestamp
            if g1 != embed1:
                m1 = await bot.playerlist[0].edit(embed=embed1, view=Thebutton())
                bot.playerlist[0] = m1
                bot.playerlist[1] = embed1
            if g2 != embed2:
                m2 = await bot.playerlist[2].edit(embed=embed2, view=Thebutton2())
                bot.playerlist[2] = m2
                bot.playerlist[3] = embed2
        else:

            print("Error: bot.playerlist does not have enough elements.")

bot.run('TOKEn')