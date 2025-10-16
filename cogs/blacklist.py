import discord
from discord.ext import commands
import json
import utils

allowed_role_id = 1139239986454069249

class Blacklist(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.utils = utils.Options(self.bot)
        self.page_messages = []
        self.last_blacklist_message = None
        self.bot.blacklist = self.load_blacklist()

    def load_blacklist(self):
        try:
            with open('blacklist.json', 'r') as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_blacklist(self):
        with open('blacklist.json', 'w') as file:
            json.dump(self.bot.blacklist, file, indent=4)

    async def update_blacklist_message(self, channel):
        if channel:
            embed = discord.Embed(title='Blacklisted Players', color=discord.Color.from_rgb(220, 53, 69))

            if self.bot.blacklist:
                total_players = len(self.bot.blacklist)
                players_per_page = 30
                total_pages = (total_players - 1) // players_per_page + 1

                embeds = []
                for page in range(total_pages):
                    start_index = page * players_per_page
                    end_index = min(start_index + players_per_page, total_players)

                    embed = discord.Embed(title='Blacklisted Players', color=discord.Color.from_rgb(220, 53, 69))
                    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1082477526166802514/1122451779133640815/Hydra_Gang_Spray.webp")
                    embed.set_footer(text=f"Page {page + 1}/{total_pages} | Total Blacklisted Players: {total_players}")

                    description = ''
                    for user_id in self.bot.blacklist[start_index:end_index]:
                        user = channel.guild.get_member(user_id['id'])
                        reason = user_id['reason']
                        if user:
                            entry = f"{user.mention}\nReason: **{reason}**\n\n"
                            if len(description) + len(entry) <= 4096:
                                description += entry
                            else:
                                break
                        else:
                            self.bot.blacklist.remove(user_id)

                    embed.description = description
                    embeds.append(embed)

                if self.page_messages:
                    for i, embed in enumerate(embeds):
                        message = self.page_messages[i]
                        await message.edit(embed=embed)

                    if len(self.page_messages) > len(embeds):
                        for message in self.page_messages[len(embeds):]:
                            await message.delete()
                        self.page_messages = self.page_messages[:len(embeds)]

                    if len(self.page_messages) < len(embeds):
                        for embed in embeds[len(page_messages):]:
                            message = await channel.send(embed=embed)
                            self.page_messages.append(message)
                else:
                    for embed in embeds:
                        message = await channel.send(embed=embed)
                        self.page_messages.append(message)
            else:
                embed.description = '**HydraDM Blacklisted Players!**'
                embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1082477526166802514/1122451779133640815/Hydra_Gang_Spray.webp")
                embed.set_footer(text=f"Total Blacklisted Players: 0")

                if self.page_messages:
                    for message in self.page_messages:
                        await message.delete()
                    self.page_messages = []

                message = await channel.send(embed=embed)
                self.page_messages.append(message)

    @commands.command()
    @commands.has_role(allowed_role_id)
    async def blacklist(self, ctx, member: discord.Member, *, reason=None):
        blacklist_role_id = 1322656273388539924
        whitelist_role_id = 1418819921789456445

        if any(entry['id'] == member.id for entry in self.bot.blacklist):
            embed = discord.Embed(
                title="Already Blacklisted",
                description=f"{member.mention} is already blacklisted.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed, delete_after=5)
            await ctx.message.delete()
        else:
            self.bot.blacklist.append({'id': member.id, 'reason': reason})
            self.save_blacklist()

            guild = self.bot.get_guild(1052668757044105266)
            blacklist_role = guild.get_role(blacklist_role_id)
            whitelist_role = guild.get_role(whitelist_role_id)

            if blacklist_role:
                await member.add_roles(blacklist_role)
            if whitelist_role:
                await member.remove_roles(whitelist_role)

            channel = discord.utils.get(guild.text_channels, name='blacklist')
            await self.update_blacklist_message(channel)

            embed = discord.Embed(
                title="User Blacklisted",
                description=f"{member.mention} has been successfully blacklisted.\nReason: {reason or 'No reason provided'}",
                color=discord.Color.from_rgb(220, 53, 69)
            )
            await ctx.send(embed=embed, delete_after=5)
            await ctx.message.delete()

    @blacklist.error
    async def blacklist_error(self, ctx, error):
        if isinstance(error, commands.MissingRole):
            embed = discord.Embed(
                title="Access Denied",
                description="You don't have permission to use this command.",
                color=discord.Color.from_rgb(220, 53, 69)
            )
            await ctx.send(embed=embed, delete_after=5)
            await ctx.message.delete()
        else:
            await ctx.send("An error occurred while executing the command.")

    @commands.command(name="blacklistlist")
    @commands.has_role(allowed_role_id)
    async def blacklist_list(self, ctx):
        if not self.bot.blacklist:
            embed = discord.Embed(title='רשימה שחורה', description='הרשימה השחורה ריקה.', color=discord.Color.from_rgb(40, 167, 69))
            return await ctx.send(embed=embed)

        description = ""
        for entry in self.bot.blacklist:
            user = self.bot.get_user(entry['id'])
            user_mention = user.mention if user else f"ID: {entry['id']}"
            reason = entry.get('reason', 'N/A')
            description += f"- {user_mention} | סיבה: `{reason}`\n"
            if len(description) > 3800:
                description += "..."
                break

        embed = discord.Embed(title='רשימה שחורה', description=description, color=discord.Color.from_rgb(220, 53, 69))
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_role(allowed_role_id)
    async def checkblacklist(self, ctx, discord_id: int):
        blacklisted_user = None
        for entry in self.bot.blacklist:
            if entry['id'] == discord_id:
                blacklisted_user = entry
                break

        if blacklisted_user:
            user = self.bot.get_user(discord_id)
            user_mention = user.mention if user else f"משתמש עם ID `{discord_id}`"
            reason = blacklisted_user.get('reason', 'לא סופקה סיבה.')
            embed = discord.Embed(
                title="בדיקת רשימה שחורה",
                description=f"{user_mention} נמצא ברשימה השחורה.",
                color=discord.Color.from_rgb(220, 53, 69)
            )
            embed.add_field(name="סיבה", value=reason)
        else:
            embed = discord.Embed(
                title="בדיקת רשימה שחורה",
                description=f"משתמש עם ID `{discord_id}` לא נמצא ברשימה השחורה.",
                color=discord.Color.from_rgb(40, 167, 69)
            )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_role(allowed_role_id)
    async def removeblacklist(self, ctx, member: discord.Member):
        if any(entry['id'] == member.id for entry in self.bot.blacklist):
            self.bot.blacklist = [entry for entry in self.bot.blacklist if entry['id'] != member.id]
            self.save_blacklist()

            whitelist_role_id = 1418819921789456445
            blacklist_role_id = 1322656273388539924

            whitelist_role = ctx.guild.get_role(whitelist_role_id)
            blacklist_role = ctx.guild.get_role(blacklist_role_id)

            if whitelist_role and blacklist_role:
                await member.remove_roles(blacklist_role)
                await member.add_roles(whitelist_role)

            guild = self.bot.get_guild(1052668757044105266)
            channel = discord.utils.get(guild.text_channels, name='blacklist')
            await self.update_blacklist_message(channel)

            embed = discord.Embed(
                title="User Removed from Blacklist",
                description=f"{member.mention} has been successfully removed from blacklist.",
                color=discord.Color.from_rgb(40, 167, 69)
            )
            await ctx.send(embed=embed, delete_after=5)
            await ctx.message.delete()
        else:
            embed = discord.Embed(
                title="Not Blacklisted",
                description=f"{member.mention} is not blacklisted.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed, delete_after=5)
            await ctx.message.delete()

    @removeblacklist.error
    async def removeblacklist_error(self, ctx, error):
        if isinstance(error, commands.MissingRole):
            embed = discord.Embed(
                title="Access Denied",
                description="You don't have permission to use this command.",
                color=discord.Color.from_rgb(220, 53, 69)
            )
            await ctx.send(embed=embed, delete_after=5)
            await ctx.message.delete()
        else:
            await ctx.send("An error occurred while executing the command.")

    @commands.command()
    @commands.has_role(allowed_role_id)
    async def showblacklist(self, ctx):
        if self.bot.blacklist:
            total_players = len(self.bot.blacklist)
            players_per_page = 30
            total_pages = (total_players - 1) // players_per_page + 1

            embeds = []
            for page in range(total_pages):
                start_index = page * players_per_page
                end_index = min(start_index + players_per_page, total_players)

                embed = discord.Embed(title='Blacklisted Players', color=discord.Color.from_rgb(220, 53, 69))
                embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1082477526166802514/1122451779133640815/Hydra_Gang_Spray.webp")
                embed.set_footer(text=f"Page {page + 1}/{total_pages} | Total Blacklisted Players: {total_players}")

                description = ''
                for user_id in self.bot.blacklist[start_index:end_index]:
                    user = self.bot.get_user(user_id['id'])
                    reason = user_id['reason']
                    if user:
                        user_mention = user.mention
                        entry = f"{user_mention}\nReason: {reason}\n\n"
                        if len(description) + len(entry) <= 4096:
                            description += entry
                        else:
                            break
                    else:
                        self.bot.blacklist.remove(user_id)

                embed.description = description
                embeds.append(embed)

            if self.last_blacklist_message:
                await self.last_blacklist_message.delete()
                self.last_blacklist_message = None

            for embed in embeds:
                self.last_blacklist_message = await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title='Blacklisted Players', description='**Blacklist is empty!**', color=discord.Color.from_rgb(220, 53, 69))
            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1082477526166802514/1122451779133640815/Hydra_Gang_Spray.webp")
            embed.set_footer(text=f"Total Blacklisted Players: 0")

            if self.last_blacklist_message:
                await self.last_blacklist_message.delete()
                self.last_blacklist_message = None

            self.last_blacklist_message = await ctx.send(embed=embed)

    @showblacklist.error
    async def showblacklist_error(self, ctx, error):
        if isinstance(error, commands.MissingRole):
            await ctx.author.send("")
        else:
            await ctx.send("An error occurred while executing the command.")

    @commands.Cog.listener()
    async def on_disconnect(self):
        self.save_blacklist()

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        whitelist_role_id = 1418819921789456445
        blacklist_role_id = 1322656273388539924

        whitelist_role = after.guild.get_role(whitelist_role_id)
        blacklist_role = after.guild.get_role(blacklist_role_id)

        if whitelist_role not in before.roles and whitelist_role in after.roles:
            if any(entry['id'] == after.id for entry in self.bot.blacklist):
                await after.remove_roles(whitelist_role)
                await after.add_roles(blacklist_role)

                try:
                    embed = discord.Embed(
                        title="Verification Denied",
                        description="You are blacklisted from this server and cannot be verified.",
                        color=discord.Color.from_rgb(220, 53, 69)
                    )
                    await after.send(embed=embed)
                except:
                    pass

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # First, check if the user is blacklisted.
        is_blacklisted = any(entry['id'] == member.id for entry in self.bot.blacklist)
        if is_blacklisted:
            blacklist_role_id = 1322656273388539924
            blacklist_role = member.guild.get_role(blacklist_role_id)
            if blacklist_role:
                try:
                    await member.add_roles(blacklist_role)
                except discord.Forbidden:
                    print(f"Failed to add blacklist role to {member.name} due to permissions.")

            try:
                embed = discord.Embed(
                    title="הנך ברשימה השחורה",
                    description="קיבלת את הרול של הרשימה השחורה באופן אוטומטי מכיוון שנכנסת לשרת.",
                    color=discord.Color.from_rgb(220, 53, 69)
                )
                await member.send(embed=embed)
            except discord.Forbidden:
                pass  # Can't send DMs to this user

        # Then, send the welcome message, regardless of blacklist status.
        welcome_channel_id = 1052733336545660968
        channel = self.bot.get_channel(welcome_channel_id)
        if not channel:
            return

        embed = discord.Embed(
            title=f'ברוך הבא ל-{member.guild.name}',
            description=f"שלום {member.mention}, הגעת לשרת **{member.guild.name}**!\nאתה המשתמש מספר **{len(member.guild.members)}** בשרת.",
            color=discord.Color.from_rgb(0, 123, 255)
        )

        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)

        embed.set_footer(text="Hydra DM , Always On Top")
        embed.add_field(name="קרא את החוקים", value="חשוב לקרוא את <#1109910338352185367> לפני הכניסה לשרת.", inline=False)
        embed.add_field(name="אימות", value="כדי להיכנס לשרת, יש לעבור אימות בחדר <#1113566909674295336>.", inline=False)
        embed.set_image(url='https://share.creavite.co/VmqDqRVg43o52nJm.gif')

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            print(f"Failed to send welcome message to channel {welcome_channel_id} due to permissions.")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.wait_until_ready()

        guild = self.bot.get_guild(1052668757044105266)
        if guild:
            blacklist_channel = discord.utils.get(guild.text_channels, name='blacklist')
            if blacklist_channel:
                await self.update_blacklist_message(blacklist_channel)

async def setup(bot: commands.Bot):
    await bot.add_cog(Blacklist(bot))
