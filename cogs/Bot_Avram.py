import discord
from discord.ext import commands
import json
import datetime

with open("./config.json", encoding="utf-8-sig") as f:
    data = json.load(f)

class VerifyButton(discord.ui.View):
    def __init__(self, rolesids, bot):
        self.rolesids = rolesids
        self.bot = bot
        super().__init__(timeout=None)

    @discord.ui.button(label="אמת אותי", custom_id='verify:veri', style=discord.ButtonStyle.primary, emoji='✅')
    async def veri(self, inter: discord.Interaction, button: discord.ui.Button):
        user_role_ids = [role.id for role in inter.user.roles]
        if all(roleid in user_role_ids for roleid in self.rolesids):
            embed = discord.Embed(
                timestamp=datetime.datetime.now(),
                title='אימות נכשל',
                description='שגיאה! אתה כבר מאומת.',
                color=0xFF6B6B
            )
            embed.set_footer(text=f"{inter.guild.name} •", icon_url=inter.guild.icon.url if inter.guild.icon else None)
            return await inter.response.send_message(embed=embed, ephemeral=True)
        
        try:
            for roleid in self.rolesids:
                role = inter.guild.get_role(roleid)
                if role not in inter.user.roles:
                    await inter.user.add_roles(role)

            embed = discord.Embed(
                timestamp=datetime.datetime.now(),
                title='אימות הושלם בהצלחה!',
                description='אומתת בהצלחה!',
                color=0x4ECDC4
            )
            
            await inter.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                timestamp=datetime.datetime.now(),
                title='שגיאה במערכת האימות',
                description='שגיאה! לא הצלחתי לאמת אותך. אנא פנה לאחד המנהלים.',
                color=0xFF4757
            )
            embed.set_footer(text=f"{inter.guild.name} • ", icon_url=inter.guild.icon.url if inter.guild.icon else None)
            await inter.response.send_message(embed=embed, ephemeral=True)
            print(f"Error during verification for {inter.user}: {e}")


class Verify(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ready = False

    async def verifyload(self):
        guild = self.bot.get_guild(self.bot.guilds[0].id)
        verify_channel = self.bot.get_channel(data['server']['verifychannel'])
        if not verify_channel:
            print(f"ERROR: Verify channel with ID {data['server']['verifychannel']} not found.")
            return

        verifyembed = discord.Embed(
            title='מערכת אימות Hydra "DM"',
            description='**כדי לאמת את עצמך ולהיכנס לשרת, לחץ על הכפתור מטה.**\n\nשימו לב: האימות הכרחי לכניסה לשרת ה-FiveM שלנו!',
            color=0x5865F2
        )
        verifyembed.set_author(
            name=f"מערכת אימות  • {guild.name}",
            icon_url=guild.icon.url if guild.icon else None
        )

        verifyembed.set_thumbnail(url=data['ui']['thumbnail'])
        # Remove the extra fields section
        verifyembed.set_image(url="https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExYmY0aG05YnBxMzUxdnRsbzNpMmhzdGxoZ2piOTB3ODYwZm1pajV1MSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/84NhEQpMPMM3BM9DCa/giphy.gif")

        try:
            history = [message async for message in verify_channel.history(limit=100)]
        except discord.errors.DiscordServerError as e:
            print(f"Could not fetch history for verify channel due to a Discord API error: {e}")
            return

        bot_message_exists = False
        for message in history:
            if message.author.id == self.bot.user.id and message.embeds:
                # To prevent re-sending, we can check if the embed title matches.
                if "מערכת אימות Hydra" in message.embeds[0].title:
                    v = VerifyButton(data['server']['member'], self.bot)
                    self.bot.add_view(view=v, message_id=message.id)
                    bot_message_exists = True
                    break

        if not bot_message_exists:
            try:
                # Before sending a new one, let's delete old messages from the bot.
                for message in history:
                    if message.author.id == self.bot.user.id:
                        await message.delete()
                await verify_channel.send(embed=verifyembed, view=VerifyButton(data['server']['member'], self.bot))
            except discord.errors.DiscordServerError as e:
                print(f"Could not send message to verify channel due to a Discord API error: {e}")
            except discord.errors.Forbidden:
                print(f"Lacking permissions to send/delete messages in verify channel.")


    @commands.Cog.listener(name="on_ready")
    async def f(self):
        if self.ready:
            return
        self.ready = True
        await self.verifyload()
        print("Verify Loaded")

async def setup(bot: commands.Bot):
    await bot.add_cog(Verify(bot))