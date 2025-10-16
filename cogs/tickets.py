from collections import Counter
from typing import Any
import discord
from discord.ext import commands
import json
import logging

from discord.interactions import Interaction
import utils
import asyncio
import datetime
from datetime import timedelta

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Set the desired logging level

# Create a console handler and set level to debug
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create a console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# Create a formatter and add it to the handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(ch)


with open("./config.json", encoding="utf-8-sig") as f:
    data = json.load(f)

class ResponseTimerModal(discord.ui.Modal):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(timeout=None, title="⏱️ הצבת מענה", custom_id="response_timer_modal")
    
    user_mention = discord.ui.TextInput(
        min_length=1,
        max_length=100,
        label="מי צריך לענות",
        placeholder="@user או ID של המשתמש",
        custom_id="user_mention",
        style=discord.TextStyle.short
    )
    
    minutes = discord.ui.TextInput(
        min_length=1,
        max_length=4,
        label="כמה דקות להמתין (1-1440)",
        placeholder="מספר דקות (מקסימום 24 שעות)",
        custom_id="minutes",
        style=discord.TextStyle.short
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Get user from mention or ID
        user_input = self.user_mention.value
        user = None
        
        try:
            user_id = int(''.join(filter(str.isdigit, user_input)))
            user = interaction.guild.get_member(user_id)
        except:
            pass
        
        if not user:
            return await interaction.followup.send("❌ **לא נמצא משתמש.** נסה שוב.", ephemeral=True)
        
        # Validate minutes
        try:
            minutes = int(self.minutes.value)
            if not 1 <= minutes <= 1440:
                return await interaction.followup.send("❌ **זמן ההמתנה חייב להיות בין 1 ל-1440 דקות.**", ephemeral=True)
        except:
            return await interaction.followup.send("❌ **אנא הזן מספר תקין של דקות.**", ephemeral=True)
        
        # Calculate end time
        end_time = datetime.datetime.now() + timedelta(minutes=minutes)
        
        # Format time display
        if minutes < 60:
            time_display = f"{minutes} דקות"
        else:
            hours = minutes // 60
            remaining_minutes = minutes % 60
            if remaining_minutes == 0:
                time_display = f"{hours} שעות"
            else:
                time_display = f"{hours} שעות ו-{remaining_minutes} דקות"
        
        # Store timer data in the database
        self.bot.db.execute(
            "INSERT OR REPLACE INTO response_timers (channel_id, user_id, end_time, set_by, reminder_sent) VALUES (?, ?, ?, ?, ?)",
            (interaction.channel.id, user.id, end_time.timestamp(), interaction.user.id, 0)
        )
        self.bot.database.commit()
        
        # Create button view for cancellation
        class CancelTimerView(discord.ui.View):
            def __init__(self, bot, channel_id, user_id):
                super().__init__(timeout=None)
                self.bot = bot
                self.channel_id = channel_id
                self.user_id = user_id
            
        
        # Create cancel view
        cancel_view = CancelTimerView(self.bot, interaction.channel.id, user.id)
        
        # Send confirmation message
        embed = discord.Embed(
            timestamp=utils.now(),
            color=data['ui']['embedcolor'],
            title="⏱️ דרישת מענה הוגדרה",
            description=f"### {user.mention} נדרש לענות בטיקט זה\n\n**⏰ זמן למענה:** {time_display}\n**🕒 מועד סיום:** {discord.utils.format_dt(end_time)}\n\n**הוגדר על ידי:** {interaction.user.mention}"
        )
        
        embed.add_field(name="מידע", value="• תזכורות ישלחו באופן אוטומטי\n• ללא מענה הטיקט ייסגר אוטומטית")
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"{interaction.guild.name} | הטיימר יסתיים בשעה {end_time.strftime('%H:%M:%S')}", icon_url=data["ui"]["thumbnail"])
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        await interaction.channel.send(embed=embed, view=cancel_view)
        
        # Send initial DM to the user
        try:
            user_embed = discord.Embed(
                timestamp=utils.now(),
                color=discord.Color.from_rgb(0, 123, 255),
                title="⏰ תזכורת: נדרשת תגובה",
                description=f"### שלום {user.mention}!\n\nאתה נדרש לענות בטיקט {interaction.channel.mention}\n\n**⏰ זמן למענה:** {time_display}\n**🕒 מועד סיום:** {discord.utils.format_dt(end_time)}\n\n**אם לא תענה במסגרת הזמן, הטיקט ייסגר אוטומטית.**"
            )
            user_embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
            user_embed.set_footer(text=interaction.guild.name, icon_url=data["ui"]["thumbnail"])
            
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="🔗 מעבר לטיקט", style=discord.ButtonStyle.url, url=f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}"))
            
            await user.send(embed=user_embed, view=view)
        except:
            # Send regular message if DM fails
            await interaction.channel.send(f"⚠️ **לא הצלחתי לשלוח הודעה פרטית ל-{user.mention}**\nוודא שהודעות פרטיות מופעלות אצלו.")
        
        # Start the timer
        self.bot.loop.create_task(self.run_timer(interaction.channel, user, minutes, interaction.guild))
    
    async def run_timer(self, channel, user, minutes, guild):
        end_time = datetime.datetime.now() + timedelta(minutes=minutes)
        channel_id = channel.id
        user_id = user.id
        
        # Track reminder states
        first_reminder_sent = False
        second_reminder_sent = False
        
        try:
            while datetime.datetime.now() < end_time:
                # Calculate remaining time
                remaining = end_time - datetime.datetime.now()
                remaining_minutes = remaining.total_seconds() / 60
                
                # Check if user has responded
                responded = False
                async for message in channel.history(limit=50, after=datetime.datetime.now() - timedelta(minutes=minutes)):
                    if message.author.id == user_id:
                        # User responded, cancel the timer
                        self.bot.db.execute("DELETE FROM response_timers WHERE channel_id = ? AND user_id = ?", 
                                          (channel_id, user_id))
                        self.bot.database.commit()
                        
                        response_embed = discord.Embed(
                            timestamp=utils.now(),
                            color=discord.Color.from_rgb(40, 167, 69),
                            title="✅ מענה התקבל",
                            description=f"### {user.mention} ענה לטיקט בזמן\n\nהטיימר בוטל אוטומטית."
                        )
                        response_embed.set_thumbnail(url=user.display_avatar.url)
                        response_embed.set_footer(text=guild.name, icon_url=data["ui"]["thumbnail"])
                        
                        await channel.send(embed=response_embed)
                        return
                
                # Send reminders based on remaining time and original duration
                if minutes >= 30:  # For timers longer than 30 minutes
                    half_time = minutes / 2
                    quarter_time = minutes / 4
                    
                    if remaining_minutes <= half_time and not first_reminder_sent:
                        first_reminder_sent = True
                        
                        # Format remaining time nicely
                        if remaining_minutes < 60:
                            remaining_time_display = f"{int(remaining_minutes)} דקות"
                        else:
                            remaining_hours = int(remaining_minutes // 60)
                            remaining_mins = int(remaining_minutes % 60)
                            if remaining_mins == 0:
                                remaining_time_display = f"{remaining_hours} שעות"
                            else:
                                remaining_time_display = f"{remaining_hours} שעות ו-{remaining_mins} דקות"
                        
                        # Channel reminder
                        reminder_embed = discord.Embed(
                            timestamp=utils.now(),
                            color=discord.Color.from_rgb(255, 193, 7),
                            title="⏰ תזכורת למענה",
                            description=f"### {user.mention}, נותרו {remaining_time_display} למענה\n\n**אם לא תענה בזמן, הטיקט ייסגר אוטומטית.**"
                        )
                        reminder_embed.set_thumbnail(url=user.display_avatar.url)
                        reminder_embed.set_footer(text=f"{guild.name} | הטיימר יסתיים בשעה {end_time.strftime('%H:%M:%S')}", icon_url=data["ui"]["thumbnail"])
                        await channel.send(content=user.mention, embed=reminder_embed)
                        
                        # DM reminder
                        try:
                            dm_embed = discord.Embed(
                                timestamp=utils.now(),
                                color=discord.Color.from_rgb(255, 193, 7),
                                title="⏰ תזכורת: זמן למענה מתקצר",
                                description=f"### שלום {user.mention}!\n\nנותרו {remaining_time_display} למענה בטיקט {channel.mention}\n\n**אם לא תענה בזמן, הטיקט ייסגר אוטומטית.**"
                            )
                            dm_embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
                            dm_embed.set_footer(text=guild.name, icon_url=data["ui"]["thumbnail"])
                            
                            view = discord.ui.View()
                            view.add_item(discord.ui.Button(label="🔗 מעבר לטיקט", style=discord.ButtonStyle.url, url=f"https://discord.com/channels/{guild.id}/{channel.id}"))
                            
                            await user.send(embed=dm_embed, view=view)
                        except:
                            pass
                    
                    if remaining_minutes <= quarter_time and not second_reminder_sent:
                        second_reminder_sent = True
                        
                        # Channel reminder
                        reminder_embed = discord.Embed(
                            timestamp=utils.now(),
                            color=discord.Color.from_rgb(220, 53, 69),
                            title="⚠️ תזכורת אחרונה",
                            description=f"### {user.mention}, נותרו {int(remaining_minutes)} דקות בלבד למענה\n\n**אם לא תענה בזמן, הטיקט ייסגר אוטומטית.**"
                        )
                        reminder_embed.set_thumbnail(url=user.display_avatar.url)
                        reminder_embed.set_footer(text=f"{guild.name} | הטיימר יסתיים בשעה {end_time.strftime('%H:%M:%S')}", icon_url=data["ui"]["thumbnail"])
                        await channel.send(content=user.mention, embed=reminder_embed)
                        
                        # DM reminder
                        try:
                            dm_embed = discord.Embed(
                                timestamp=utils.now(),
                                color=discord.Color.from_rgb(220, 53, 69),
                                title="⚠️ תזכורת אחרונה: הטיקט עומד להיסגר",
                                description=f"### {user.mention}!\n\nנותרו {int(remaining_minutes)} דקות בלבד למענה בטיקט {channel.mention}\n\n**אם לא תענה בזמן הקרוב, הטיקט ייסגר אוטומטית.**"
                            )
                            dm_embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
                            dm_embed.set_footer(text=guild.name, icon_url=data["ui"]["thumbnail"])
                            
                            view = discord.ui.View()
                            view.add_item(discord.ui.Button(label="🔗 מעבר לטיקט", style=discord.ButtonStyle.url, url=f"https://discord.com/channels/{guild.id}/{channel.id}"))
                            
                            await user.send(embed=dm_embed, view=view)
                        except:
                            pass
                
                # Wait before checking again (adjust based on timer length)
                await asyncio.sleep(60 if minutes > 10 else 30)  # Check more frequently for shorter timers
            
            # Time's up, check one final time if the user responded
            responded = False
            async for message in channel.history(limit=50, after=end_time - timedelta(minutes=minutes)):
                if message.author.id == user_id:
                    responded = True
                    break
            
            if not responded:
                # User didn't respond, close the ticket
                timeout_embed = discord.Embed(
                    timestamp=utils.now(),
                    color=discord.Color.from_rgb(220, 53, 69),
                    title="⏰ זמן המענה הסתיים",
                    description=f"### {user.mention} לא ענה לטיקט תוך {minutes} דקות\n\n**הטיקט ייסגר אוטומטית.**"
                )
                timeout_embed.set_thumbnail(url=user.display_avatar.url)
                timeout_embed.set_footer(text=guild.name, icon_url=data["ui"]["thumbnail"])
                await channel.send(embed=timeout_embed)
                
                # Delete timer from database
                self.bot.db.execute("DELETE FROM response_timers WHERE channel_id = ? AND user_id = ?", 
                                  (channel_id, user_id))
                self.bot.database.commit()
                
                # Close the ticket with "אין מענה" reason
                close_reason = "אין מענה"
                
                # Create transcript
                file = True
                transcript_path = f"./tickets/{channel.id}.txt"
                with open(transcript_path, "w", encoding="utf-8-sig") as f:
                    async for message in channel.history(oldest_first=True):
                        try:
                            f.write(f"{message.created_at.strftime('%m/%d/%Y, %H:%M:%S')}   {message.author.name}#{message.author.discriminator}   {message.content}\n")
                        except Exception as e:
                            print(f"Transcript error: {str(e)}")
                            file = None
                
                # Close embed for user notification
                close_embed = discord.Embed(
                    timestamp=utils.now(),
                    color=data['ui']['embedcolor'],
                    description=f"**📝 שם הטיקט:** `{channel.name}`\n**📅 נפתח ב:** `{channel.created_at.strftime('%m/%d/%Y, %H:%M:%S')}`\n**🔒 נסגר ב:** `{utils.now().strftime('%m/%d/%Y, %H:%M:%S')}`\n**❓ סיבה:** ||`{close_reason}`||\n**👤 נסגר על ידי:** מערכת - `סגירה אוטומטית`"
                )
                close_embed.set_author(name=f"{guild.name} - טיקט נסגר", icon_url=guild.icon.url if guild.icon else None)
                
                # Try to notify ticket opener
                try:
                    ticket_opener = guild.get_member(int(channel.topic))
                    if ticket_opener:
                        await ticket_opener.send(embed=close_embed)
                except Exception as e:
                    print(f"Could not notify ticket opener: {str(e)}")
                
                # Create log embed
                log_embed = discord.Embed(
                    timestamp=utils.now(),
                    color=data['ui']['embedcolor'],
                    description=f"**מידע על הטיקט שנסגר:** __{channel.name}__"
                )
                log_embed.set_image(url=data['ui']['img'])
                log_embed.set_footer(text=guild.name, icon_url=data["ui"]["thumbnail"])
                log_embed.set_thumbnail(url=data['ui']['thumbnail'])
                log_embed.add_field(name="🔖 ערוץ", value=f"__שם:__ **{channel.name}**\n__מזהה:__ **{channel.id}**")
                
                # Add ticket opener info
                ticket_opener = guild.get_member(int(channel.topic))
                opener_info = ""
                if ticket_opener:
                    opener_info = f"__נפתח על ידי:__ **{ticket_opener.mention} - {ticket_opener.name}#{ticket_opener.discriminator}**\n"
                
                # Add claimed by info
                try:
                    claimed_by_id = self.bot.db.execute(f"SELECT userid from CLAIM where channelid = {channel.id}").fetchone()[0]
                    claimed_by_member = guild.get_member(claimed_by_id)
                    claim_info = f"\n**__נתבע על ידי:__ {claimed_by_member.mention}**\n" if claimed_by_member else ""
                except:
                    claim_info = ""
                
                log_embed.add_field(
                    name="📋 כללי",
                    value=f"{opener_info}__נפתח ב:__ **{discord.utils.format_dt(channel.created_at)}**\n__נסגר על ידי:__ **מערכת** - **סגירה אוטומטית** {claim_info}\n**סיבה:** {close_reason}"
                )
                
                # Add message count per user
                result = self.bot.db.execute(f"SELECT messagecount, userid FROM ticketsmessage WHERE channelid = {channel.id} ORDER BY messagecount DESC").fetchall()
                user_messages = ""
                for message_count, user_id in result:
                    user_messages += f"**<@{user_id}>**: `{message_count}`\n"
                
                if user_messages:
                    log_embed.add_field(name="👥 משתמשים", value=user_messages)
                else:
                    log_embed.add_field(name="👥 משתמשים", value="לא נרשמו הודעות")
                
                # Send transcript to log channel
                if file:
                    transcript_channel = guild.get_channel(data["logs"]["ticket"]["trans"])
                    try:
                        transcript_message = await transcript_channel.send(file=discord.File(transcript_path))
                        log_embed.add_field(name="📄 תמליל ישיר", value=f"[לחץ כאן]({transcript_message.jump_url})")
                    except Exception as e:
                        print(f"Failed to send transcript: {str(e)}")
                
                # Send log and delete channel
                log_channel = guild.get_channel(data['logs']['ticket']['close'])
                await log_channel.send(embed=log_embed)
                
                try:
                    await channel.delete(reason="טיקט נסגר - אין מענה")
                except Exception as e:
                    print(f"Failed to delete channel: {str(e)}")
                    await channel.send("❌ **שגיאה במחיקת הערוץ.** אנא צור קשר עם מנהל המערכת.")
            else:
                # User responded within time frame, cancel timer
                self.bot.db.execute("DELETE FROM response_timers WHERE channel_id = ? AND user_id = ?", 
                                  (channel_id, user_id))
                self.bot.database.commit()
                
                response_embed = discord.Embed(
                    timestamp=utils.now(),
                    color=discord.Color.from_rgb(40, 167, 69),
                    title="✅ מענה התקבל",
                    description=f"### {user.mention} ענה לטיקט בזמן\n\nהטיימר בוטל אוטומטית."
                )
                response_embed.set_thumbnail(url=user.display_avatar.url)
                response_embed.set_footer(text=guild.name, icon_url=data["ui"]["thumbnail"])
                await channel.send(embed=response_embed)
        except Exception as e:
            print(f"Error in response timer: {e}")
            # Try to log error and notify staff
            try:
                error_embed = discord.Embed(
                    timestamp=utils.now(),
                    color=discord.Color.from_rgb(220, 53, 69),
                    title="⚠️ שגיאה במערכת המענה",
                    description=f"אירעה שגיאה בטיימר המענה בטיקט {channel.mention}.\n\n**שגיאה:** ```{str(e)}```"
                )
                error_embed.set_footer(text=guild.name, icon_url=data["ui"]["thumbnail"])
                await channel.send(embed=error_embed)
            except:
                pass

class BanAppealModal(discord.ui.Modal, title="ערעור על באן"):
    def __init__(self, bot, utils_obj):
        super().__init__()
        self.bot = bot
        self.utils = utils_obj

    username = discord.ui.TextInput(
        label="שם המשתמש בשרת",
        placeholder="הקלד את שם המשתמש שלך",
        required=True,
        style=discord.TextStyle.short
    )

    ban_id = discord.ui.TextInput(
        label="מזהה הבאן (Ban ID)",
        placeholder="הקלד את מזהה הבאן שקיבלת",
        required=True,
        style=discord.TextStyle.short
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)

        useravatar = await self.utils.avatar(interaction.user)
        file = None
        useravatarurl = useravatar
        if type(useravatar) is discord.File:
            useravatarurl = "attachment://1.png"
            file = useravatar

        category_name = "DM - ערעור על באן"
        categoryid = data["categories"][category_name]
        cat = interaction.guild.get_channel(categoryid)

        if not cat:
            return await interaction.followup.send("קטגוריית ערעור על באן לא נמצאה. אנא פנה לצוות.", ephemeral=True)

        staffrole = interaction.guild.get_role(data["server"]["staff"])
        overwrites: dict[discord.Role | discord.Member | discord.User, discord.PermissionOverwrite] = {
            staffrole: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.user: discord.PermissionOverwrite(view_channel=True, attach_files=True, add_reactions=True, send_messages=True),
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False)
        }

        channel = await interaction.guild.create_text_channel(name=f"{category_name}-{interaction.user.name}",
                                                              category=cat,
                                                              topic=str(interaction.user.id),
                                                              slowmode_delay=2,
                                                              reason=f"{interaction.user.name} opened a ticket",
                                                              overwrites=overwrites)

        self.bot.db.execute("INSERT INTO claim VALUES (?, ?)", (channel.id, 0))
        self.bot.database.commit()

        await interaction.followup.send(f"{data['tickets']['opened']['messageopen']}{channel.mention}", ephemeral=True)

        embed = discord.Embed(timestamp=utils.Options.now(),
                              description=f"{interaction.user.mention}{data['tickets']['opened']['description']}",
                              color=discord.Color.from_rgb(0, 123, 255))
        embed.set_author(name=interaction.guild.name)
        embed.set_footer(text=data['tickets']['opened']['footertext'], icon_url=data['ui']['thumbnail'])
        embed.add_field(name="קטגורית הטיקט", value=f'`{category_name}`', inline=False)
        embed.add_field(name="שם המשתמש", value=self.username.value, inline=False)
        embed.add_field(name="מזהה הבאן", value=self.ban_id.value, inline=False)
        embed.set_image(url="https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExYmY0aG05YnBxMzUxdnRsbzNpMmhzdGxoZ2piOTB3ODYwZm1pajV1MSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/84NhEQpMPMM3BM9DCa/giphy.gif")
        embed.set_thumbnail(url=useravatarurl)

        await channel.send(embed=embed, file=file, view=StaffOptions(self.bot, self.utils), content=f"<@&1418509991685521498> {interaction.user.mention}")

        logembed = discord.Embed(timestamp=utils.now(),
                                 description=f"**__🎫 טיקט נפתח__!**",
                                 color=discord.Color.from_rgb(0, 123, 255))
        logembed.add_field(name="Channel", value=f"**{channel.mention}** | `{channel.name} ({channel.id})`", inline=False)
        logembed.add_field(name="User", value=f"**{interaction.user.mention}** - `{interaction.user.name}#{interaction.user.discriminator} | {interaction.user.id}`", inline=False)
        logembed.add_field(name="Opened at", value=f"**{str(utils.now())[:19]}** - {discord.utils.format_dt(utils.now(), 'd')} ({discord.utils.format_dt(utils.now(), 'R')})", inline=False)
        logembed.set_author(name=interaction.guild.name)
        logembed.set_footer(text=interaction.guild.name, icon_url=data['ui']['thumbnail'])
        logembed.set_thumbnail(url=data['ui']['thumbnail'])
        logchannel = interaction.guild.get_channel(data["logs"]["ticket"]["open"])
        await logchannel.send(embed=logembed)

class TicketsSelect(discord.ui.Select):
    def __init__(self, utils, bot, reasons_list):
        self.bot = bot
        self.utils = utils
        options: list[discord.SelectOption] = []
        for option in reasons_list:
            description = data["tickets"]["descriptions"].get(option)
            emoji = data["tickets"]["emojis"].get(option)
            options.append(
                discord.SelectOption(label=option
                                     , description=description
                                     , emoji=emoji)
                           )
        super().__init__(placeholder=data["tickets"]["placeholder"]
                         , min_values=1
                         , max_values=1
                         , options=options
                         , custom_id="ticketselectreasons")
    
    async def callback(self, interaction: discord.Interaction):
        selected_reason = self.values[0]

        if selected_reason == "DM - בירור":
            inquiry_role_id = data["tickets"].get("inquiry_role_id")
            if not inquiry_role_id or inquiry_role_id not in [r.id for r in interaction.user.roles]:
                return await interaction.response.send_message("אין לך הרשאה לפתוח טיקט מסוג זה.", ephemeral=True)

        if selected_reason == "DM - ערעור על באן":
            modal = BanAppealModal(self.bot, self.utils)
            return await interaction.response.send_modal(modal)

        await interaction.response.defer(thinking=True, ephemeral=True)

        category_id = data["categories"].get(selected_reason)
        if not category_id:
            return await interaction.followup.send(f"שגיאת הגדרה: לא נמצאה קטגוריה עבור הסיבה '{selected_reason}'.", ephemeral=True)

        category = interaction.guild.get_channel(category_id)
        if not category or not isinstance(category, discord.CategoryChannel):
            return await interaction.followup.send(f"שגיאה: קטגוריית הטיקטים (ID: {category_id}) לא נמצאה או אינה קטגוריה. אנא פנה לצוות.", ephemeral=True)

        useravatar = await self.utils.avatar(interaction.user)
        file = None
        useravatarurl = useravatar
        if type(useravatar) is discord.File:
            useravatarurl = "attachment://1.png"
            file = useravatar

        staffrole = interaction.guild.get_role(data["server"]["staff"])
        overwrites: dict[discord.Role | discord.Member | discord.User, discord.PermissionOverwrite] = {
            staffrole: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.user: discord.PermissionOverwrite(view_channel=True, attach_files=True, add_reactions=True, send_messages=True),
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False)
        }

        try:
            channel = await interaction.guild.create_text_channel(name=f"{selected_reason}-{interaction.user.name}",
                                                                  category=category,
                                                                  topic=str(interaction.user.id),
                                                                  slowmode_delay=2,
                                                                  reason=f"{interaction.user.name} opened a ticket",
                                                                  overwrites=overwrites)
        except discord.Forbidden:
            return await interaction.followup.send("שגיאה: אין לי הרשאות ליצור ערוצים בקטגוריה זו.", ephemeral=True)
        except discord.HTTPException as e:
            return await interaction.followup.send(f"שגיאה ביצירת הערוץ: {e}", ephemeral=True)

        self.bot.db.execute("INSERT INTO claim VALUES (?, ?)", (channel.id, 0))
        self.bot.database.commit()

        await interaction.followup.send(f"{data['tickets']['opened']['messageopen']}{channel.mention}", ephemeral=True)

        embed = discord.Embed(timestamp=utils.Options.now(),
                              description=f"{interaction.user.mention}{data['tickets']['opened']['description']}",
                              color=discord.Color.from_rgb(0, 123, 255))
        embed.set_author(name=interaction.guild.name)
        embed.set_footer(text=data['tickets']['opened']['footertext'], icon_url=data['ui']['thumbnail'])
        embed.add_field(name="קטגורית הטיקט", value=f'`{selected_reason}`', inline=False)
        embed.set_image(url="https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExYmY0aG05YnBxMzUxdnRsbzNpMmhzdGxoZ2piOTB3ODYwZm1pajV1MSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/84NhEQpMPMM3BM9DCa/giphy.gif")
        embed.set_thumbnail(url=useravatarurl)

        if data['tickets']['opened']['format']:
            ticketformat = data['tickets']['opened']['formats'].get(selected_reason)
            if ticketformat:
                embed.add_field(name="פורמט הטיקט", value=f"```{ticketformat}```")

        await channel.send(embed=embed, file=file, view=StaffOptions(self.bot, self.utils), content=f"<@&1418509991685521498> {interaction.user.mention}")

        logembed = discord.Embed(timestamp=utils.now(),
                                 description=f"**__🎫 טיקט נפתח__!**",
                                 color=discord.Color.from_rgb(0, 123, 255))
        logembed.add_field(name="Channel", value=f"**{channel.mention}** | `{channel.name} ({channel.id})`", inline=False)
        logembed.add_field(name="User", value=f"**{interaction.user.mention}** - `{interaction.user.name}#{interaction.user.discriminator} | {interaction.user.id}`", inline=False)
        logembed.add_field(name="Opened at", value=f"**{str(utils.now())[:19]}** - {discord.utils.format_dt(utils.now(), 'd')} ({discord.utils.format_dt(utils.now(), 'R')})", inline=False)
        logembed.set_author(name=interaction.guild.name)
        logembed.set_footer(text=interaction.guild.name, icon_url=data['ui']['thumbnail'])
        logembed.set_thumbnail(url=data['ui']['thumbnail'])
        logchannel = interaction.guild.get_channel(data["logs"]["ticket"]["open"])
        await logchannel.send(embed=logembed)

class ClearTickets(discord.ui.View):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Clear Tickets"
                       , emoji="🗑️"
                       , custom_id="clarrr")
    async def clear(self, inter: discord.Interaction, button: discord.ui.Button):
        await inter.response.defer(thinking=True
                                   , ephemeral=True)
        categories = list(data["categories"].values())
        res = "Clearing tickets"
        embeds: list[discord.Embed] = [
            discord.Embed(timestamp=utils.now()
                          , description=f"There is no open tickets!"
                          , color=discord.Color.from_rgb(220, 53, 69)
                          , title="Clear tickets")
        ]
        for category in inter.guild.categories:
            if category.id in categories:
                for channel in category.channels:
                    mbed = discord.Embed(timestamp=utils.now()
                                        , description=f"Clearing all the channels in the category: **{category.name}**"
                                        , color=discord.Color.yellow())
                    member = inter.guild.get_member(int(channel.topic))
                    first = ""
                    if member is not None:
                        first = f" | __Opened By:__ **{member.mention} - {member.name}#{member.discriminator}**\n"
                    mbed.add_field(name=f"{channel.name}"
                                   , value=f"**{channel.name}** - `{channel.id}`{first}")
                    embed = discord.Embed(timestamp=utils.now()
                                        , color=data['ui']['embedcolor']
                                        , description=f"**Ticket Channel:** `{channel.name}`\n**Opened At:** `{channel.created_at.strftime('%m/%d/%Y, %H:%M:%S')}`\n**Closed At:** `{utils.now().strftime('%m/%d/%Y, %H:%M:%S')}`\n**Reason:** ||`{res}`||\n**Closed By:** {inter.user.mention} - `{inter.user.name}#{inter.user.discriminator}`")
                    embed.set_author(name=f"{inter.guild.name} - טיקט נסגר")
                    try:
                        await inter.guild.get_member(int(channel.topic)).send(embed=embed)
                    except:
                        pass
                    logembed = discord.Embed(timestamp=utils.now()
                                            , color=data['ui']['embedcolor']
                                            , description=f"**All info about the closed ticket:** __{channel.name}__")
                    logembed.set_image(url=data['ui']['img'])
                    logembed.set_footer(text=inter.guild.name
                                        , icon_url=data["ui"]["thumbnail"])
                    logembed.set_thumbnail(url=data['ui']['thumbnail'])
                    logembed.add_field(name="Channel"
                                    , value=f"__Name:__ **{channel.name}**\n__ID:__ **{channel.id}**")
                    try:
                        claimedbyid = self.bot.db.execute(f"SELECT userid from claims where channelid = {channel.id}").fetchone()[0]
                    except:
                        claimedbyid = 0
                    claimedbymember = inter.guild.get_member(claimedbyid)
                    claim = ""
                    if claimedbymember is not None:
                        claim = f"\n**__Claimd By:__ {claimedbymember.mention}**\n"
                    logembed.add_field(name="General"
                                       , value=f"{first}__Opened At:__ **{discord.utils.format_dt(channel.created_at)}**\n__Closed By:__ **{inter.user.mention}** - **{inter.user.name}#{inter.user.discriminator}** {claim}\n**Reason:** {res}")
                    result: list[int, int] = self.bot.db.execute(f"SELECT messagecount, userid FROM ticketsmessage WHERE channelid = {channel.id} ORDER BY messagecount DESC").fetchall()
                    val = ""
                    for usermessages, userid in result:
                        val += f"**<@{userid}>**: `{usermessages}`\n"
                    logembed.add_field(name="Users"
                                    , value=val)
                    file = True
                    with open(f"./tickets/{channel.id}.txt", "w", encoding="utf-8-sig") as f:
                        async for message in channel.history(oldest_first=True):
                            try:
                                f.write(f"{message.created_at.strftime('%m/%d/%Y, %H:%M:%S')}   {message.author.name}#{message.author.discriminator}   {message.content}\n")
                            except Exception as e:
                                print(str(e))        
                                file = None
                        f.close()
                    chanid = channel.id    
                    chan = channel
                    if file:
                        channel = inter.guild.get_channel(data["logs"]["ticket"]["trans"]) 
                        m = await channel.send(file=discord.File(f"./tickets/{chanid}.txt"))
                        logembed.add_field(name="Direct Transcripit"
                                        , value=f"[Click Here]({m.jump_url})")
                    logchannel = inter.guild.get_channel(data['logs']['ticket']['close'])
                    await logchannel.send(embed=logembed)
                    await chan.delete(reason="טיקט נסגר")      
                    embeds.append(mbed)   
        if len(embeds) > 1:
            del embeds[0]
        await inter.followup.send(embeds=embeds)
            


class StaffOptions(discord.ui.View):
    def __init__(self, bot, utils):
        self.utils = utils
        self.bot = bot
        super().__init__(timeout=None)                
        
        
    @discord.ui.button(label="אפשרויות צוות"
                       , emoji="🎓"
                       , custom_id="sendthestaff")
    async def staff(self, inter: discord.Interaction, button: discord.ui.Button):
        if inter.guild.get_role(data["server"]["staff"]) not in inter.user.roles:
            embed = discord.Embed(timestamp=utils.now()
                                  , description=f"**__{inter.user.mention}__ Tried to open the staff option without permissions**"
                                  , color=discord.Color.from_rgb(220, 53, 69))
            embed.add_field(name="Ticket info"
                            , value=f"__Name:__ **{inter.channel.name}**\n__ID:__ **{inter.channel.id}**\n__Opened At:__ **{inter.channel.created_at.strftime('%m/%d/%Y, %H:%M:%S')}**")
            logchannelgeneral = inter.guild.get_channel(data['logs']['ticket']['general'])
            await logchannelgeneral.send(embed=embed)
            return await inter.response.send_message(f"You dont have permission to use that!"
                                                     , ephemeral=True)
        await inter.response.send_message(view=StaffActions(self.bot)
                                          , ephemeral=True)
        
    @discord.ui.button(label="לקחת את הטיקט"
                       , custom_id="claimticketstaff"
                       , style=discord.ButtonStyle.success)
    async def claimticketstaff(self, inter: discord.Interaction, button: discord.ui.Button):
        useravatar = await self.utils.avatar(inter.user)
        file = None
        useravatarurl = useravatar
        if type(useravatar) is discord.File:
            useravatarurl = "attachment://1.png"
            file = useravatar       
        if inter.guild.get_role(data["server"]["staff"]) not in inter.user.roles:
            return await inter.response.send_message(f"You can't use this!"
                                                     , ephemeral=True)
        button.label = f"נלקח על ידי - {inter.user.name}#{inter.user.discriminator}"
        button.disabled = True
        await inter.response.edit_message(view=self)
        embed = discord.Embed(timestamp=utils.now()
                              , description=f"**קליים נלקח By {inter.user.mention} - **`{inter.user.name}#{inter.user.discriminator}`"
                              , color=discord.Color.yellow())
        embed.set_author(name=inter.guild.name)
        embed.set_thumbnail(url=useravatarurl)
        now = utils.now()
        date = f"{now.day}/{now.month}/{now.year}"
        self.bot.db.execute("UPDATE claim SET userid = ? WHERE channelid = ?"
                            , (inter.user.id, inter.channel.id))
        self.bot.db.execute("INSERT INTO claims VALUES (?, ?, ?, ?)"
                            , (inter.channel.id, inter.user.id, date, str(now.timestamp())))
        self.bot.database.commit()
        await inter.channel.send(embed=embed
                                 , file=file)
        today = self.bot.db.execute("SELECT channelid FROM claims WHERE userid = ? AND date = ?"
                                    , (inter.user.id, date)).fetchall()
        always = self.bot.db.execute(f"SELECT channelid FROM claims WHERE userid = {inter.user.id}").fetchall()
        today, always = len(today), len(always)
        channeltime = inter.channel.created_at
        logembed = discord.Embed(timestamp=now
                                 , title="Ticket Claim Logs"
                                 , description=f"**__קליים נלקח__!**"
                                 , color=discord.Color.from_rgb(40, 167, 69))
        user = inter.guild.get_member(int(inter.channel.topic))
        if user:
            openedticket = f"\n**User Ticket:** __{user.mention}__ `({user.name}#{user.discriminator})`\n**Stafff Claim:** __{inter.user.mention}__ `({inter.user.name}#{inter.user.discriminator})`"
        logembed.add_field(name="Ticket"
                           , value=f"**__{inter.channel.mention}__ | {inter.channel.name} - {inter.channel.id}**{openedticket}")
        logembed.add_field(name="Opened At"
                           , value=f"**{str(channeltime)[:19]}** - {discord.utils.format_dt(channeltime, 'd')} ({discord.utils.format_dt(channeltime, 'R')})"
                           , inline=False)
        logembed.add_field(name="Claimed at"
                           , value=f"**{str(utils.now())[:19]}** - {discord.utils.format_dt(utils.now(), 'd')} ({discord.utils.format_dt(utils.now(), 'R')})"
                           , inline=False)
        logembed.add_field(name="User Claims"
                           , value=f"**Today:** `{today}` - **Always:** - `{always}`")
        utnow = discord.utils.utcnow()
        seconds = (utnow - inter.channel.created_at).seconds
        day = int(seconds // (24 * 3600))
        dayformat = True if day >= 1 else False
        hours, seconds = divmod(seconds, 60)
        hours, hours = divmod(hours, 60)
        hourformat = False if hours == 0 else True
        hoursformat = False if hours == 0 else True
        claimafterstring: str = ""
        if dayformat:
            if day > 1:
                claimafterstring += f"{day} days"
            else:
                claimafterstring += f"{day} day"
        if hourformat:
            if dayformat:
                g = int(hours - (day * 24))
                if hours > 1:
                    claimafterstring += f", {g} hours"
                else:
                    claimafterstring += f", {g} hour"
            else:
                if hours > 1:
                    claimafterstring += f"{hours} hours"
                else:
                    claimafterstring += f"{hours} hour"
        if hoursformat:
            if hourformat:
                if hours > 1:
                    claimafterstring += f", {hours} hours"
                else:
                    claimafterstring += f", {hours} minute"
            else:
                if hours > 1:
                    claimafterstring += f"{hours} hours"
                else:
                    claimafterstring += f"{hours} minute"
        if hoursformat:
            if seconds > 1:
                claimafterstring += f", {seconds} seconds"
            else:
                claimafterstring += f", {seconds} second"
        else:
            if seconds > 1:
                claimafterstring += f"{seconds} seconds"
            else:
                claimafterstring += f"{seconds} second"
        logembed.add_field(name="Claimed After..."
                           , value=f"{claimafterstring}")
        logchannel = inter.guild.get_channel(data["logs"]["ticket"]["claim"])
        await logchannel.send(embed=logembed)




class ReasonsToClose(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.add_item(ReasonToClose(bot))


class CloseModal(discord.ui.Modal):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(timeout=None
                         , title="סגירת טיקט"
                         , custom_id="clsllslewfo")
    
    reason = discord.ui.TextInput(min_length=3
                                  , max_length=170
                                  , label="סיבת סגירה"
                                  , placeholder="הסיבה שבגללה אתה רוצה לסגור את הטיקט"
                                  , custom_id="rsmynier")
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("הטיקט ייסגר בקרוב"
                                                , ephemeral=True)
        res = self.reason.value
        embed = discord.Embed(timestamp=utils.now()
                              , color=data['ui']['embedcolor']
                              , description=f"**Ticket Channel:** `{interaction.channel.name}`\n**Opened At:** `{interaction.channel.created_at.strftime('%m/%d/%Y, %H:%M:%S')}`\n**Closed At:** `{utils.now().strftime('%m/%d/%Y, %H:%M:%S')}`\n**Reason:** ||`{res}`||\n**Closed By:** {interaction.user.mention} - `{interaction.user.name}#{interaction.user.discriminator}`")
        embed.set_author(name=f"{interaction.guild.name} - טיקט נסגר")
        try:
            await interaction.guild.get_member(int(interaction.channel.topic)).send(embed=embed)
        except:
            pass
        logembed = discord.Embed(timestamp=utils.now()
                                 , color=data['ui']['embedcolor']
                                 , description=f"**All info about the closed ticket:** __{interaction.channel.name}__")
        logembed.set_image(url=data['ui']['img'])
        logembed.set_footer(text=interaction.guild.name
                            , icon_url=data["ui"]["thumbnail"])
        logembed.set_thumbnail(url=data['ui']['thumbnail'])
        logembed.add_field(name="Channel"
                           , value=f"__Name:__ **{interaction.channel.name}**\n__ID:__ **{interaction.channel.id}**")
        member = interaction.guild.get_member(int(interaction.channel.topic))
        first = ""
        if member is not None:
            first = f"__Opened By:__ **{member.mention} - {member.name}#{member.discriminator}**\n"
        try:
            claimedbyid = self.bot.db.execute(f"SELECT userid from CLAIM where channelid = {interaction.channel.id}").fetchone()[0]
        except:
            claimedbyid = 0
        claimedbymember = interaction.guild.get_member(claimedbyid)
        claim = ""
        if claimedbymember is not None:
            claim = f"\n**__Claimd By:__ {claimedbymember.mention}**\n"
        logembed.add_field(name="General"
                           , value=f"{first}__Opened At:__ **{discord.utils.format_dt(interaction.channel.created_at)}**\n__Closed By:__ **{interaction.user.mention}** - **{interaction.user.name}#{interaction.user.discriminator}** {claim}\n**Reason:** {res}")
        result: list[int, int] = self.bot.db.execute(f"SELECT messagecount, userid FROM ticketsmessage WHERE channelid = {interaction.channel.id} ORDER BY messagecount DESC").fetchall()
        val = ""
        for usermessages, userid in result:
            val += f"**<@{userid}>**: `{usermessages}`\n"
        logembed.add_field(name="Users"
                           , value=val)
        file = True
        with open(f"./tickets/{interaction.channel.id}.txt", "w", encoding="utf-8-sig") as f:
            async for message in interaction.channel.history(oldest_first=True):
                try:
                    f.write(f"{message.created_at.strftime('%m/%d/%Y, %H:%M:%S')}   {message.author.name}#{message.author.discriminator}   {message.content}\n")
                except Exception as e:
                    print(str(e))        
                    file = None
        if file:
            channel = interaction.guild.get_channel(data["logs"]["ticket"]["trans"]) 
            m = await channel.send(file=discord.File(f"./tickets/{interaction.channel.id}.txt"))
            logembed.add_field(name="Direct Transcripit"
                               , value=f"[Click Here]({m.jump_url})")
        # --- PC Checker Timer Claim Logic ---
        try:
            timer_data = self.bot.db.execute("SELECT set_by, end_time FROM pc_check_timers WHERE channel_id = ?", (interaction.channel.id,)).fetchone()
            if timer_data:
                setter_id, end_time_stamp = timer_data
                if datetime.datetime.now().timestamp() >= end_time_stamp:
                    setter_member = interaction.guild.get_member(setter_id)
                    if setter_member:
                        now = utils.now()
                        date = f"{now.day}/{now.month}/{now.year}"
                        self.bot.db.execute("INSERT INTO pc_claims VALUES (?, ?, ?, ?)",
                                            (interaction.channel.id, setter_id, date, str(now.timestamp())))
                        self.bot.db.execute("DELETE FROM pc_check_timers WHERE channel_id = ?", (interaction.channel.id,))
                        self.bot.database.commit()
        except Exception as e:
            print(f"Error during PC checker claim processing: {e}")
        # --- End of PC Checker Logic ---

        logchannel = interaction.guild.get_channel(data['logs']['ticket']['close'])
        await logchannel.send(embed=logembed)
        await interaction.channel.delete(reason="טיקט נסגר")        


class ReasonToClose(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options: list[discord.SelectOption] = [
            discord.SelectOption(label="טופל"
                                 , emoji="✅"),
            
            discord.SelectOption(label="אין מענה"
                                 , emoji="❌"),
            
            discord.SelectOption(label="לא"
                                 , emoji="⛔"),
            
            discord.SelectOption(label="אחר")
        ]
        super().__init__(options=options
                         , min_values=1
                         , max_values=1
                         , placeholder="בחר אחת מהסיבות")
    
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "אחר":
            return await interaction.response.send_modal(CloseModal(self.bot))
        await interaction.response.send_message("הטיקט ייסגר בקרוב"
                                                , ephemeral=True)
        res = self.values[0]
        embed = discord.Embed(timestamp=utils.now()
                              , color=data['ui']['embedcolor']
                              , description=f"**Ticket Channel:** `{interaction.channel.name}`\n**Opened At:** `{interaction.channel.created_at.strftime('%m/%d/%Y, %H:%M:%S')}`\n**Closed At:** `{utils.now().strftime('%m/%d/%Y, %H:%M:%S')}`\n**Reason:** ||`{res}`||\n**Closed By:** {interaction.user.mention} - `{interaction.user.name}#{interaction.user.discriminator}`")
        embed.set_author(name=f"{interaction.guild.name} - טיקט נסגר")
        try:
            await interaction.guild.get_member(int(interaction.channel.topic)).send(embed=embed)
        except:
            pass
        logembed = discord.Embed(timestamp=utils.now()
                                 , color=data['ui']['embedcolor']
                                 , description=f"**All info about the closed ticket:** __{interaction.channel.name}__")
        logembed.set_image(url=data['ui']['img'])
        logembed.set_footer(text=interaction.guild.name
                            , icon_url=data["ui"]["thumbnail"])
        logembed.set_thumbnail(url=data['ui']['thumbnail'])
        logembed.add_field(name="Channel"
                           , value=f"__Name:__ **{interaction.channel.name}**\n__ID:__ **{interaction.channel.id}**")
        member = interaction.guild.get_member(int(interaction.channel.topic))
        first = ""
        if member is not None:
            first = f"__Opened By:__ **{member.mention} - {member.name}#{member.discriminator}**\n"
        try:
            claimedbyid = self.bot.db.execute(f"SELECT userid from CLAIM where channelid = {interaction.channel.id}").fetchone()[0]
        except:
            claimedbyid = 0
        claimedbymember = interaction.guild.get_member(claimedbyid)
        claim = ""
        if claimedbymember is not None:
            claim = f"\n**__Claimd By:__ {claimedbymember.mention}**\n"
        logembed.add_field(name="General"
                           , value=f"{first}__Opened At:__ **{discord.utils.format_dt(interaction.channel.created_at)}**\n__Closed By:__ **{interaction.user.mention}** - **{interaction.user.name}#{interaction.user.discriminator}** {claim}\n**Reason:** {res}")
        result: list[int, int] = self.bot.db.execute(f"SELECT messagecount, userid FROM ticketsmessage WHERE channelid = {interaction.channel.id} ORDER BY messagecount DESC").fetchall()
        val = ""
        for usermessages, userid in result:
            val += f"**<@{userid}>**: `{usermessages}`\n"
        logembed.add_field(name="Users"
                           , value=val)
        file = True
        with open(f"./tickets/{interaction.channel.id}.txt", "w", encoding="utf-8-sig") as f:
            async for message in interaction.channel.history(oldest_first=True):
                try:
                    f.write(f"{message.created_at.strftime('%m/%d/%Y, %H:%M:%S')}   {message.author.name}#{message.author.discriminator}   {message.content}\n")
                except Exception as e:
                    print(str(e))        
                    file = None
        if file:
            channel = interaction.guild.get_channel(data["logs"]["ticket"]["trans"]) 
            m = await channel.send(file=discord.File(f"./tickets/{interaction.channel.id}.txt"))
            logembed.add_field(name="Direct Transcripit"
                               , value=f"[Click Here]({m.jump_url})")
        logchannel = interaction.guild.get_channel(data['logs']['ticket']['close'])
        await logchannel.send(embed=logembed)
        await interaction.channel.delete(reason="טיקט נסגר")        



class CloseSelect(discord.ui.View):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(timeout=None)
        
    
    @discord.ui.button(label="🔐סגור עם סיבה"
                       , emoji='🔄'
                       , style=discord.ButtonStyle.success
                       , custom_id="clreason")
    async def closeres(self, inter: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(timestamp=utils.now()
                              , description=f"בחר את הסיבה שבגללה ברצונך לסגור את הטיקט"
                              , color=discord.Color.from_rgb(0, 123, 255))
        embed.set_author(name=inter.guild.name)
        embed.set_footer(text=inter.guild.name
                         , icon_url=data['ui']['thumbnail'])
        await inter.response.send_message(embed=embed
                                          , view=ReasonsToClose(self.bot)
                                          , ephemeral=True)
        
        
    @discord.ui.button(label="סגור ללא סיבה"
                       , style=discord.ButtonStyle.danger
                       , custom_id="closeticknor"
                       , emoji="🔐")
    async def closenores(self, interaction: discord.Interaction, button: discord.ui.Button):
        res = "לא סופקה סיבה"
        embed = discord.Embed(timestamp=utils.now()
                              , color=data['ui']['embedcolor']
                              , description=f"**Ticket Channel:** `{interaction.channel.name}`\n**Opened At:** `{interaction.channel.created_at.strftime('%m/%d/%Y, %H:%M:%S')}`\n**Closed At:** `{utils.now().strftime('%m/%d/%Y, %H:%M:%S')}`\n**Reason:** ||`{res}`||\n**Closed By:** {interaction.user.mention} - `{interaction.user.name}#{interaction.user.discriminator}`")
        embed.set_author(name=f"{interaction.guild.name} - טיקט נסגר")
        try:
            await interaction.guild.get_member(int(interaction.channel.topic)).send(embed=embed)
        except:
            pass
        logembed = discord.Embed(timestamp=utils.now()
                                 , color=data['ui']['embedcolor']
                                 , description=f"**All info about the closed ticket:** __{interaction.channel.name}__")
        logembed.set_image(url=data['ui']['img'])
        logembed.set_footer(text=interaction.guild.name
                            , icon_url=data["ui"]["thumbnail"])
        logembed.set_thumbnail(url=data['ui']['thumbnail'])
        logembed.add_field(name="Channel"
                           , value=f"__Name:__ **{interaction.channel.name}**\n__ID:__ **{interaction.channel.id}**")
        member = interaction.guild.get_member(int(interaction.channel.topic))
        first = ""
        if member is not None:
            first = f"__Opened By:__ **{member.mention} - {member.name}#{member.discriminator}**\n"
        try:
            claimedbyid = self.bot.db.execute(f"SELECT userid from CLAIM where channelid = {interaction.channel.id}").fetchone()[0]
        except:
            claimedbyid = 0
        claimedbymember = interaction.guild.get_member(claimedbyid)
        claim = ""
        if claimedbymember is not None:
            claim = f"\n**__Claimd By:__ {claimedbymember.mention}**\n"
        logembed.add_field(name="General"
                           , value=f"{first}__Opened At:__ **{discord.utils.format_dt(interaction.channel.created_at)}**\n__Closed By:__ **{interaction.user.mention}** - **{interaction.user.name}#{interaction.user.discriminator}** {claim}\n**Reason:** {res}")
        result: list[int, int] = self.bot.db.execute(f"SELECT messagecount, userid FROM ticketsmessage WHERE channelid = {interaction.channel.id} ORDER BY messagecount DESC").fetchall()
        val = ""
        for usermessages, userid in result:
            val += f"**<@{userid}>**: `{usermessages}`\n"
        logembed.add_field(name="Users"
                           , value=val)
        file = True
        with open(f"./tickets/{interaction.channel.id}.txt", "w", encoding="utf-8-sig") as f:
            async for message in interaction.channel.history(oldest_first=True):
                try:
                    f.write(f"{message.created_at.strftime('%m/%d/%Y, %H:%M:%S')}   {message.author.name}#{message.author.discriminator}   {message.content}\n")
                except Exception as e:
                    print(str(e))        
                    file = None
        if file:
            channel = interaction.guild.get_channel(data["logs"]["ticket"]["trans"]) 
            m = await channel.send(file=discord.File(f"./tickets/{interaction.channel.id}.txt"))
            logembed.add_field(name="Direct Transcripit"
                               , value=f"[Click Here]({m.jump_url})")
        logchannel = interaction.guild.get_channel(data['logs']['ticket']['close'])
        await logchannel.send(embed=logembed)
        await interaction.channel.delete(reason="טיקט נסגר")        


    
    
class PCCheckerTimerModal(discord.ui.Modal, title="הצב זמן מענה"):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    minutes = discord.ui.TextInput(
        label="כמה דקות להמתין?",
        placeholder="הזן מספר דקות (למשל, 60)",
        required=True,
        style=discord.TextStyle.short
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes_to_wait = int(self.minutes.value)
            if minutes_to_wait <= 0:
                await interaction.response.send_message("אנא הזן מספר דקות חיובי.", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("ערך לא תקין. אנא הזן מספר דקות.", ephemeral=True)
            return

        end_time = datetime.datetime.now() + timedelta(minutes=minutes_to_wait)

        self.bot.db.execute(
            "INSERT OR REPLACE INTO pc_check_timers (channel_id, set_by, end_time) VALUES (?, ?, ?)",
            (interaction.channel.id, interaction.user.id, end_time.timestamp())
        )
        self.bot.database.commit()

        embed = discord.Embed(
            title="⏰ הוגדר זמן מענה",
            description=f"זמן מענה הוגדר על ידי {interaction.user.mention}.\nהטיימר יסתיים ב: {discord.utils.format_dt(end_time, style='F')}",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class PCCheckerActions(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="הוסף משתמש", emoji="➕", style=discord.ButtonStyle.secondary, custom_id="pc_add_user")
    async def add_user(self, inter: discord.Interaction, button: discord.ui.Button):
        await inter.response.defer(thinking=True, ephemeral=True)
        embed = discord.Embed(timestamp=utils.now(),
                              description="שלח כאן את המשתמש שברצונך להוסיף לטיקט")
        embed.set_author(name=inter.guild.name)
        embed.set_footer(text=inter.guild.name, icon_url=data['ui']['thumbnail'])
        await inter.followup.send(embed=embed, ephemeral=True)
        try:
            resp: discord.Message = await self.bot.wait_for("message",
                                                            check=lambda r: r.author.id == inter.user.id and r.channel.id == inter.channel.id,
                                                            timeout=30)
        except asyncio.TimeoutError:
            failembed = discord.Embed(timestamp=utils.now(),
                                      description="הוספת המשתמש נכשלה, הזמן אזל!",
                                      color=discord.Color.from_rgb(220, 53, 69))
            return await inter.followup.send(embed=failembed, ephemeral=True)
        user = None
        try:
            user_id = int(resp.content)
            user = inter.guild.get_member(user_id)
        except: pass
        if resp.mentions:
            user = resp.mentions[0]
        if not user:
            return await inter.followup.send('משתמש לא תקין', ephemeral=True)

        await inter.channel.set_permissions(user, view_channel=True, send_messages=True)
        embed = discord.Embed(timestamp=utils.now(),
                              color=discord.Color.from_rgb(0, 123, 255),
                              description=f"המשתמש {user.mention} נוסף בהצלחה לטיקט על ידי - {inter.user.mention}")
        await inter.channel.send(embed=embed)


    @discord.ui.button(label="הסר משתמש", emoji="➖", style=discord.ButtonStyle.secondary, custom_id="pc_remove_user")
    async def remove_user(self, inter: discord.Interaction, button: discord.ui.Button):
        await inter.response.defer(thinking=True, ephemeral=True)
        embed = discord.Embed(timestamp=utils.now(),
                              description="שלח כאן את המשתמש שברצונך להסיר מהטיקט")
        await inter.followup.send(embed=embed, ephemeral=True)
        try:
            resp: discord.Message = await self.bot.wait_for("message",
                                                            check=lambda r: r.author.id == inter.user.id and r.channel.id == inter.channel.id,
                                                            timeout=30)
        except asyncio.TimeoutError:
            failembed = discord.Embed(timestamp=utils.now(),
                                      description="הסרת המשתמש נכשלה, הזמן אזל!",
                                      color=discord.Color.from_rgb(220, 53, 69))
            return await inter.followup.send(embed=failembed, ephemeral=True)
        user = None
        try:
            user_id = int(resp.content)
            user = inter.guild.get_member(user_id)
        except: pass
        if resp.mentions:
            user = resp.mentions[0]
        if not user:
            return await inter.followup.send('משתמש לא תקין', ephemeral=True)

        await inter.channel.set_permissions(user, view_channel=False)
        embed = discord.Embed(timestamp=utils.now(),
                              color=discord.Color.dark_orange(),
                              description=f"המשתמש {user.mention} הוסר בהצלחה מהטיקט על ידי - {inter.user.mention}")
        await inter.channel.send(embed=embed)

    @discord.ui.button(label="הצב זמן מענה", emoji="⏰", style=discord.ButtonStyle.primary, custom_id="pc_set_timer")
    async def set_timer(self, interaction: discord.Interaction, button: discord.ui.Button):
        pc_checker_role_id = 1125003229659406366
        if not any(role.id == pc_checker_role_id for role in interaction.user.roles):
            return await interaction.response.send_message("אין לך הרשאה להשתמש בכפתור זה.", ephemeral=True)

        await interaction.response.send_modal(PCCheckerTimerModal(self.bot))


    @discord.ui.button(label="קח קליים", emoji="✔️", style=discord.ButtonStyle.success, custom_id="pc_take_claim")
    async def take_claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        pc_checker_role_id = 1125003229659406366
        if not any(role.id == pc_checker_role_id for role in interaction.user.roles):
            return await interaction.response.send_message("אין לך הרשאה להשתמש בכפתור זה.", ephemeral=True)

        now = utils.now()
        date = f"{now.day}/{now.month}/{now.year}"

        self.bot.db.execute("INSERT INTO pc_claims VALUES (?, ?, ?, ?)",
                            (interaction.channel.id, interaction.user.id, date, str(now.timestamp())))
        self.bot.database.commit()

        button.disabled = True
        button.label = f"קליים נלקח על ידי {interaction.user.name}"
        await interaction.response.edit_message(view=self)

        embed = discord.Embed(
            title="✅ קליים נלקח",
            description=f"קליים של PC CHECKER נלקח על ידי {interaction.user.mention}.",
            color=discord.Color.green()
        )
        await interaction.channel.send(embed=embed)


class StaffActions(discord.ui.View):
    def __init__(self, bot, utils=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self._utils = utils
        
        # Initialize database table if it doesn't exist
        self.bot.db.execute('''
        CREATE TABLE IF NOT EXISTS response_timers (
            channel_id INTEGER,
            user_id INTEGER,
            end_time REAL,
            set_by INTEGER,
            reminder_sent INTEGER,
            PRIMARY KEY (channel_id, user_id)
        )''')
        self.bot.database.commit()
    
    @property
    def utils(self):
        """Get utils, creating it if needed"""
        if self._utils is None:
            import utils as utils_module
            self._utils = utils_module.Options(self.bot)
        return self._utils    
    
    
    @discord.ui.button(label="סגור טיקט"
                       , emoji="🔒"
                       , style=discord.ButtonStyle.primary
                       , custom_id="closticketbutton")    
    async def close(self, inter: discord.Interaction, button: discord.ui.Button):
        await inter.response.send_message(view=CloseSelect(self.bot)
                                          , ephemeral=True)
    
    @discord.ui.button(label="תן קליים"
                   , emoji="🎯"
                   , style=discord.ButtonStyle.primary
                   , custom_id="give_claim_button")
    async def give_claim(self, inter: discord.Interaction, button: discord.ui.Button):
        # בדיקת הרשאות
        required_role_id = 1113574262364712970
        if not any(role.id == required_role_id for role in inter.user.roles):
            return await inter.response.send_message("אין לך הרשאה לתת קליים!", ephemeral=True)
        
        await inter.response.defer(thinking=True, ephemeral=True)
        
        embed = discord.Embed(timestamp=utils.now(),
                            description="תייג את המשתמש שברצונך לתת לו קליים על הטיקט")
        embed.set_author(name=inter.guild.name)
        embed.set_footer(text=inter.guild.name, icon_url=data['ui']['thumbnail'])
        await inter.followup.send(embed=embed, ephemeral=True)
        
        try:
            resp: discord.Message = await self.bot.wait_for("message",
                                                            check=lambda r: r.author.id == inter.user.id and r.channel.id == inter.channel.id,
                                                            timeout=30)
        except asyncio.TimeoutError:
            failembed = discord.Embed(timestamp=utils.now(),
                                    description="מתן קליים נכשל, הזמן אזל!",
                                    color=discord.Color.from_rgb(220, 53, 69))
            return await inter.followup.send(embed=failembed, ephemeral=True)
        
        # זיהוי משתמש
        user = None
        try:
            user_id = int(''.join(filter(str.isdigit, resp.content)))
            user = inter.guild.get_member(user_id)
        except:
            pass
        
        if resp.mentions:
            user = resp.mentions[0]
        
        if not user:
            return await inter.followup.send('משתמש לא תקין', ephemeral=True)
        
        # עדכון בסיס נתונים
        now = utils.now()
        date = f"{now.day}/{now.month}/{now.year}"
        self.bot.db.execute("UPDATE claim SET userid = ? WHERE channelid = ?",
                            (user.id, inter.channel.id))
        self.bot.db.execute("INSERT INTO claims VALUES (?, ?, ?, ?)",
                            (inter.channel.id, user.id, date, str(now.timestamp())))
        self.bot.database.commit()
        
        # הודעה בערוץ
        useravatar = await self.utils.avatar(user)
        file = None
        useravatarurl = useravatar
        if type(useravatar) is discord.File:
            useravatarurl = "attachment://1.png"
            file = useravatar
        
        embed = discord.Embed(timestamp=utils.now(),
                            description=f"**קליים הוענק ל-{user.mention} על ידי {inter.user.mention}**",
                            color=discord.Color.yellow())
        embed.set_author(name=inter.guild.name)
        embed.set_thumbnail(url=useravatarurl)
        await inter.channel.send(embed=embed, file=file)
        
        # לוג
        today_claims = len(self.bot.db.execute("SELECT channelid FROM claims WHERE userid = ? AND date = ?",
                                            (user.id, date)).fetchall())
        always_claims = len(self.bot.db.execute("SELECT channelid FROM claims WHERE userid = ?",
                                                (user.id,)).fetchall())
        
        logembed = discord.Embed(timestamp=now,
                                title="Ticket Claim Logs",
                                description=f"**__קליים הוענק__!**",
                                color=discord.Color.from_rgb(40, 167, 69))
        ticket_opener = inter.guild.get_member(int(inter.channel.topic))
        if ticket_opener:
            openedticket = f"\n**User Ticket:** __{ticket_opener.mention}__ `({ticket_opener.name}#{ticket_opener.discriminator})`\n**Claim Given By:** __{inter.user.mention}__ `({inter.user.name}#{inter.user.discriminator})`\n**Claim Given To:** __{user.mention}__ `({user.name}#{user.discriminator})`"
        logembed.add_field(name="Ticket",
                        value=f"**__{inter.channel.mention}__ | {inter.channel.name} - {inter.channel.id}**{openedticket}")
        logembed.add_field(name="User Claims",
                        value=f"**Today:** `{today_claims}` - **Always:** `{always_claims}`")
        
        logchannel = inter.guild.get_channel(data["logs"]["ticket"]["claim"])
        await logchannel.send(embed=logembed)
        
    @discord.ui.button(label="הצבת מענה"
                       , emoji="⏰"
                       , style=discord.ButtonStyle.secondary
                       , custom_id="response_timer_button")
    async def set_response_timer(self, inter: discord.Interaction, button: discord.ui.Button):
        await inter.response.send_modal(ResponseTimerModal(self.bot))

    @discord.ui.button(label="מעבר ל PC CHECKERS", emoji="💻", style=discord.ButtonStyle.danger, custom_id="move_to_pc_checkers")
    async def move_to_pc_checkers(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Role IDs
        staff_role_id = 1128143033431511081
        pc_checker_role_id = 1125003229659406366

        # Permission Check
        if not any(role.id == staff_role_id for role in interaction.user.roles):
            return await interaction.response.send_message("אין לך הרשאה לבצע פעולה זו.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        # 1. Grant claim to the user
        now = utils.now()
        date = f"{now.day}/{now.month}/{now.year}"
        self.bot.db.execute("INSERT INTO claims VALUES (?, ?, ?, ?)",
                            (interaction.channel.id, interaction.user.id, date, str(now.timestamp())))
        self.bot.database.commit()

        # 2. Move ticket to the new category
        pc_category_id = 1428406834783322195
        category = interaction.guild.get_channel(pc_category_id)
        if category and isinstance(category, discord.CategoryChannel):
            await interaction.channel.edit(category=category)

        # 3. Remove permissions from the regular staff role
        staff_role = interaction.guild.get_role(staff_role_id)
        if staff_role:
            await interaction.channel.set_permissions(staff_role, view_channel=False)

        # 4. Send the new message with the PC Checker view
        pc_checker_role = interaction.guild.get_role(pc_checker_role_id)
        ticket_opener = interaction.guild.get_member(int(interaction.channel.topic))

        message_content = f"{pc_checker_role.mention}, {ticket_opener.mention}, מבקש בדיקת מחשב. לטיפולכם :)"

        embed = discord.Embed(
            title="אפשרויות PC CHECKERS",
            description="אנא השתמשו בכפתורים למטה לניהול הבדיקה.",
            color=discord.Color.red()
        )

        await interaction.channel.send(message_content, embed=embed, view=PCCheckerActions(self.bot))
        await interaction.followup.send("הטיקט הועבר בהצלחה ל-PC Checkers.", ephemeral=True)
    

    @discord.ui.button(label="הוסף רול", 
                   emoji="🎭", 
                   style=discord.ButtonStyle.gray, 
                   custom_id="addrolebutton")
    async def add_role(self, inter: discord.Interaction, button: discord.ui.Button):
        await inter.response.defer(thinking=True, ephemeral=True)
        embed = discord.Embed(
            timestamp=utils.now(),
            description="שלח כאן את הרול שברצונך להוסיף לטיקט (תייג את הרול או ספק את שמו)"
        )
        embed.set_author(name=inter.guild.name)
        embed.set_footer(text=inter.guild.name, icon_url=data['ui']['thumbnail'])
        await inter.followup.send(embed=embed, ephemeral=True)
        
        try:
            resp: discord.Message = await self.bot.wait_for(
                "message",
                check=lambda r: r.author.id == inter.user.id and r.channel.id == inter.channel.id,
                timeout=30
            )
        except asyncio.TimeoutError:
            failembed = discord.Embed(
                timestamp=utils.now(),
                description="הוספת הרול נכשלה, הזמן אזל!",
                color=discord.Color.from_rgb(220, 53, 69)
            )
            return await inter.followup.send(embed=failembed, ephemeral=True)

        role = None
        try:
            # אם הוא מתייג את הרול
            if resp.role_mentions:
                role = resp.role_mentions[0]
            else:
                # אם הוא כותב שם של רול
                role = discord.utils.get(inter.guild.roles, name=resp.content)
        except:
            pass

        if not role:
            return await inter.followup.send('רול לא תקין', ephemeral=True)
        
        overwrites = inter.channel.overwrites
        overwrites.update({
            role: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True
            )
        })
        await inter.channel.edit(overwrites=overwrites)

        embed = discord.Embed(
            timestamp=utils.now(),
            color=discord.Color.from_rgb(0, 123, 255),
            description=f"הרול {role.mention} נוסף בהצלחה לטיקט על ידי - {inter.user.mention}"
        )
        embed.set_author(name=inter.guild.name)
        embed.set_footer(text=inter.guild.name, icon_url=data['ui']['thumbnail'])
        await inter.channel.send(embed=embed)

        logembed = discord.Embed(
            timestamp=utils.now(),
            color=discord.Color.from_rgb(40, 167, 69),
            description=f"Role added to the ticket - {inter.channel.name}"
        )
        logembed.add_field(name="Staff added", value=f"{inter.user.mention} - `{inter.user.name}#{inter.user.discriminator}`")
        logembed.add_field(name="Role added", value=f"{role.mention} - `{role.name}`")
        user = inter.guild.get_member(int(inter.channel.topic))
        if user:
            openedticket = f"\n**User Ticket:** __{user.mention}__`({user.name}#{user.discriminator})`"
        logembed.add_field(
            name="Ticket",
            value=f"**__{inter.channel.mention}__ | {inter.channel.name} - {inter.channel.id}**{openedticket}"
        )
        logchannel = inter.guild.get_channel(data["logs"]["ticket"]["general"])
        await logchannel.send(embed=logembed)

    @discord.ui.button(label="החלף קטגוריה"
                    , custom_id="switchcategory"
                    , style=discord.ButtonStyle.primary
                    , emoji="🔄")
    async def switch_category(self, inter: discord.Interaction, button: discord.ui.Button):
        await inter.response.defer(thinking=True, ephemeral=True)
        
        # Create embed asking for category selection
        embed = discord.Embed(timestamp=utils.now()
                            , description="בחר את הקטגוריה החדשה לטיקט")
        embed.set_author(name=inter.guild.name)
        embed.set_footer(text=inter.guild.name
                        , icon_url=data['ui']['thumbnail'])
        
        # Create select menu for categories
        options = []
        for category_name, category_id in data["categories"].items():
            options.append(
                discord.SelectOption(
                    label=category_name,
                    value=str(category_id)
                )
            )
        
        # Create select menu view
        class CategorySelect(discord.ui.Select):
            def __init__(self):
                super().__init__(
                    placeholder="בחר קטגוריה",
                    min_values=1,
                    max_values=1,
                    options=options
                )
                
            async def callback(self, interaction: discord.Interaction):
                old_category = interaction.channel.category
                new_category = interaction.guild.get_channel(int(self.values[0]))
                
                # Move channel to new category
                await interaction.channel.edit(category=new_category)
                
                # Send success message
                success_embed = discord.Embed(
                    timestamp=utils.now(),
                    color=discord.Color.from_rgb(40, 167, 69),
                    description=f"הטיקט הועבר בהצלחה מ-{old_category.name} ל-{new_category.name}"
                )
                success_embed.set_author(name=interaction.guild.name)
                success_embed.set_footer(text=interaction.guild.name, icon_url=data['ui']['thumbnail'])
                await interaction.response.send_message(embed=success_embed, ephemeral=True)
                
                # Log the category change
                log_embed = discord.Embed(
                    timestamp=utils.now(),
                    color=discord.Color.from_rgb(0, 123, 255),
                    description="קטגוריית טיקט שונתה"
                )
                log_embed.add_field(
                    name="מידע",
                    value=f"שונה על ידי: {interaction.user.mention}\nמ: {old_category.name}\nל: {new_category.name}\nטיקט: {interaction.channel.mention}"
                )
                log_channel = interaction.guild.get_channel(data["logs"]["ticket"]["general"])
                await log_channel.send(embed=log_embed)
        
        # Create view with select menu
        class CategoryView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.add_item(CategorySelect())
        
        # Send message with category selection
        await inter.followup.send(embed=embed, view=CategoryView(), ephemeral=True)

    @discord.ui.button(label="הוסף שחקן"
                        , emoji="➕"
                        , custom_id="addus"
                        , style=discord.ButtonStyle.gray)
    async def add(self, inter: discord.Interaction, button: discord.ui.Button):
        await inter.response.defer(thinking=True
                                , ephemeral=True)
        embed = discord.Embed(timestamp=utils.now()
                            , description="שלח כאן את המשתמש שברצונך להוסיף לטיקט")
        embed.set_author(name=inter.guild.name)
        embed.set_footer(text=inter.guild.name
                        , icon_url=data['ui']['thumbnail'])
        await inter.followup.send(embed=embed
                                , ephemeral=True)
        try:
            resp: discord.Message = await self.bot.wait_for("message"
                                                            , check=lambda r: r.author.id == inter.user.id and r.channel.id == inter.channel.id
                                                            , timeout=30)
        except asyncio.TimeoutError:
            failembed = discord.Embed(timestamp=utils.now()
                                    , description="הוספת המשתמש נכשלה, הזמן אזל!"
                                    , color=discord.Color.from_rgb(220, 53, 69))
            return await inter.followup.send(embed=failembed, ephemeral=True)
        user = None
        try:
            user: int = int(resp.content)
            user: discord.Member = inter.guild.get_member(user)
        except: pass
        if resp.mentions:
            user = resp.mentions[0]
        try:
            for member in inter.guild.members:
                fullname = member.name + "#" + member.discriminator
                if resp.content == fullname:
                    user = member
                    break
        except: pass
        if not user:
            return await inter.followup.send('משתמש לא תקין', ephemeral=True)
        
        overwrites = inter.channel.overwrites
        overwrites.update({
            user: discord.PermissionOverwrite(view_channel=True,
                                            send_messages=True)
                                            })
        await inter.channel.edit(
            overwrites=overwrites
        )
        embed = discord.Embed(timestamp=utils.now()
                            , color=discord.Color.from_rgb(0, 123, 255)
                            , description=f"המשתמש {user.mention} נוסף בהצלחה לטיקט על ידי - {inter.user.mention}")
        embed.set_author(name=inter.guild.name)
        embed.set_footer(text=inter.guild.name
                        , icon_url=data['ui']['thumbnail'])
        await inter.channel.send(embed=embed)
        logembed = discord.Embed(timestamp=utils.now()
                                , color=discord.Color.from_rgb(40, 167, 69)
                                , description=f"משתמש נוסף לטיקט - {inter.channel.name}")
        logembed.add_field(name="נוסף על ידי"
                        , value=f"{inter.user.mention} - `{inter.user.name}#{inter.user.discriminator}`")
        logembed.add_field(name="המשתמש שנוסף"
                        , value=f"{user.mention} - `{user.name}#{user.discriminator}`")
        user = inter.guild.get_member(int(inter.channel.topic))
        if user:
            openedticket = f"\n**User Ticket:** __{user.mention}__`({user.name}#{user.discriminator})`"
        logembed.add_field(name="Ticket"
                        , value=f"**__{inter.channel.mention}__ | {inter.channel.name} - {inter.channel.id}**{openedticket}")
        logchannel = inter.guild.get_channel(data["logs"]["ticket"]["general"])
        await logchannel.send(embed=logembed)

    @discord.ui.button(label="שנה שם לטיקט"
                    , custom_id="renameti"
                    , style=discord.ButtonStyle.success)
    async def rename(self, inter: discord.Interaction, button: discord.ui.Button):
        before = inter.channel.name
        
        try:
            await inter.response.defer(ephemeral=True)
            
            embed = discord.Embed(timestamp=utils.now()
                                , description="What would be the name of the ticket ?")
            embed.set_author(name=inter.guild.name)
            embed.set_footer(text=inter.guild.name
                            , icon_url=data['ui']['thumbnail'])
            # Sending the "What would be the name of the ticket?" message
            await inter.followup.send(embed=embed, ephemeral=True)  

            name = await self.bot.wait_for("message"
                                        , check=lambda x: x.author.id == inter.user.id and x.channel.id == inter.channel.id
                                        , timeout=20)

            await inter.channel.edit(name=name.content, reason="Ticket rename")

            embed_success = discord.Embed(timestamp=utils.now()
                                        , color=discord.Color.dark_orange()
                                        , description=f"Ticket was successfully renamed to - `{name.content}`")
            embed_success.set_author(name=inter.guild.name)
            embed_success.set_footer(text=inter.guild.name
                                    , icon_url=data['ui']['thumbnail'])
            # Sending success message with ephemeral set to True
            await inter.followup.send(embed=embed_success, ephemeral=True)

            logembed = discord.Embed(timestamp=utils.now()
                                    , color=discord.Color.from_rgb(40, 167, 69)
                                    , description=f"Ticket Renamed")      
            logembed.add_field(name="Staff Renamer"
                            , value=f"{inter.user.mention} - `{inter.user.name}#{inter.user.discriminator}`")
            logembed.add_field(name="Before"
                            , value=f"`{before}`")
            logembed.add_field(name="After"
                            , value=f"`{name.content}`")
            user = inter.guild.get_member(int(inter.channel.topic))
            if user:
                openedticket = f"\n**User Ticket:** __{user.mention}__`({user.name}#{user.discriminator})`"
            logembed.add_field(name="Ticket"
                            , value=f"**__{inter.channel.mention}__ | {inter.channel.name} - {inter.channel.id}**{openedticket}")
            logchannel = inter.guild.get_channel(data["logs"]["ticket"]["general"])
            await logchannel.send(embed=logembed)
            
        except asyncio.TimeoutError:
            failembed = discord.Embed(timestamp=utils.now()
                                    , description="rename ticket failed, timeout!"
                                    , color=discord.Color.from_rgb(220, 53, 69))
            return await inter.followup.send(embed=failembed, ephemeral=True)


    @discord.ui.button(label="הסר שחקן"
                       , style=discord.ButtonStyle.primary
                       , custom_id="removeuser"
                       , emoji="➖")
    async def removeuser(self, inter: discord.Interaction, button: discord.ui.Button):
        await inter.response.defer(thinking=True
                                , ephemeral=True)
        embed = discord.Embed(timestamp=utils.now()
                            , description="שלח כאן את המשתמש שברצונך להסיר מהטיקט")
        embed.set_author(name=inter.guild.name)
        embed.set_footer(text=inter.guild.name
                        , icon_url=data['ui']['thumbnail'])
        await inter.followup.send(embed=embed
                                , ephemeral=True)
        try:
            resp: discord.Message = await self.bot.wait_for("message"
                                                            , check=lambda r: r.author.id == inter.user.id and r.channel.id == inter.channel.id
                                                            , timeout=30)
        except asyncio.TimeoutError:
            failembed = discord.Embed(timestamp=utils.now()
                                    , description="הסרת המשתמש נכשלה, הזמן אזל!"
                                    , color=discord.Color.from_rgb(220, 53, 69))
            return await inter.followup.send(embed=failembed, ephemeral=True)
        user = None
        try:
            user: int = int(resp.content)
            user: discord.Member = inter.guild.get_member(user)
        except: pass
        if resp.mentions:
            user = resp.mentions[0]
        try:
            for member in inter.guild.members:
                fullname = member.name + "#" + member.discriminator
                if resp.content == fullname:
                    user = member
                    break
        except: pass
        if not user:
            return await inter.followup.send('משתמש לא תקין', ephemeral=True)
        overwrites = inter.channel.overwrites
        overwrites.update({
            user: discord.PermissionOverwrite(
                view_channel=False,
                send_messages=False
            )
        })
        await inter.channel.edit(
            overwrites=overwrites)
        embed = discord.Embed(timestamp=utils.now()
                            , color=discord.Color.dark_orange()
                            , description=f"המשתמש {user.mention} הוסר בהצלחה מהטיקט על ידי - {inter.user.mention}")
        embed.set_author(name=inter.guild.name)
        embed.set_footer(text=inter.guild.name
                        , icon_url=data['ui']['thumbnail'])
        await inter.channel.send(embed=embed)
        logembed = discord.Embed(timestamp=utils.now()
                                , color=discord.Color.from_rgb(40, 167, 69)
                                , description=f"User removed from the ticket - {inter.channel.name}")      
        logembed.add_field(name="Staff removed"
                        , value=f"{inter.user.mention} - `{inter.user.name}#{inter.user.discriminator}`")
        logembed.add_field(name="User removed"
                        , value=f"{user.mention} - `{user.name}#{user.discriminator}`")
        user = inter.guild.get_member(int(inter.channel.topic))
        if user:
            openedticket = f"\n**User Ticket:** __{user.mention}__`({user.name}#{user.discriminator})`"
        logembed.add_field(name="Ticket"
                        , value=f"**__{inter.channel.mention}__ | {inter.channel.name} - {inter.channel.id}**{openedticket}")
        logchannel = inter.guild.get_channel(data["logs"]["ticket"]["general"])
        await logchannel.send(embed=logembed)
        
        
    @discord.ui.button(label="שנה שם מרשימה", emoji="🏷️", style=discord.ButtonStyle.secondary, custom_id="rename_from_list_button")
    async def rename_from_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(view=RenameTicketView(self.bot), ephemeral=True)

class RenameTicketSelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(label="Waiting for Head Admin"),
            discord.SelectOption(label="Waiting for Staff Manager"),
            discord.SelectOption(label="Waiting for Management"),
            discord.SelectOption(label="Waiting for Server Manager"),
            discord.SelectOption(label="Waiting for Staff Wager"),
            discord.SelectOption(label="Waiting for Head Pc Checkers"),
            discord.SelectOption(label="Waiting for PC Checker"),
            discord.SelectOption(label="Waiting for Head Of Staff"),
            discord.SelectOption(label="Waiting for Blacklists Manager"),
            discord.SelectOption(label="Waiting for Shay"),
            discord.SelectOption(label="Waiting for Daniel"),
        ]
        super().__init__(placeholder="בחר שם חדש לטיקט", options=options, custom_id="rename_ticket_select")

    async def callback(self, interaction: discord.Interaction):
        new_name = self.values[0]
        before_name = interaction.channel.name
        await interaction.channel.edit(name=new_name, reason=f"Renamed by {interaction.user}")
        
        # Log the rename
        logembed = discord.Embed(timestamp=utils.now(),
                                 color=discord.Color.from_rgb(40, 167, 69),
                                 description=f"שם טיקט שונה")
        logembed.add_field(name="שונה על ידי", value=f"{interaction.user.mention} - `{interaction.user.name}#{interaction.user.discriminator}`")
        logembed.add_field(name="לפני", value=f"`{before_name}`")
        logembed.add_field(name="אחרי", value=f"`{new_name}`")
        user = interaction.guild.get_member(int(interaction.channel.topic))
        if user:
            openedticket = f"\n**User Ticket:** __{user.mention}__`({user.name}#{user.discriminator})`"
        else:
            openedticket = ""
        logembed.add_field(name="Ticket", value=f"**__{interaction.channel.mention}__ | {interaction.channel.name} - {interaction.channel.id}**{openedticket}")
        logchannel = interaction.guild.get_channel(data["logs"]["ticket"]["general"])
        await logchannel.send(embed=logembed)

        await interaction.response.send_message(f"שם הטיקט שונה ל: `{new_name}`", ephemeral=True)

class RenameTicketView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.add_item(RenameTicketSelect(bot))
        
class SelectReset(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options: list[discord.SelectOption] = [
            discord.SelectOption(label="all"
                                 , description="Resets the claim to everyone"),
            
            discord.SelectOption(label="user"
                                 , description="Resets the claim to a specific user")
        ]
        super().__init__(custom_id="resettt"
                         , options=options
                         , min_values=1
                         , max_values=1
                         , placeholder="select option")
    
    async def callback(self, inter: discord.Interaction):
        if self.values[0] == "all":
            self.bot.db.execute("DELETE FROM claim;")
            self.bot.db.execute("DELETE FROM claims;")
            self.bot.database.commit()
            embed = discord.Embed(timestamp=utils.now()
                                  , title="Reset Claims"
                                  , description="All the claims have been reseted."
                                  , color=data['ui']['embedcolor'])
            embed.set_footer(text=inter.guild.name
                            , icon_url=data["ui"]["thumbnail"])
            embed.set_author(name=inter.guild.name)            
            return await inter.response.send_message(embed=embed)
        embed = discord.Embed(timestamp=utils.now()
                                , title="Reset Claims"
                                , description="mention the user you want to reset his claims. (20 seconds)"
                                , color=data['ui']['embedcolor'])
        embed.set_footer(text=inter.guild.name
                        , icon_url=data["ui"]["thumbnail"])
        embed.set_author(name=inter.guild.name)                    
        await inter.response.send_message(embed=embed)
        try:
            user: discord.Message = await self.bot.wait_for("message"
                                                            , check=lambda x: x.author.id == inter.user.id and x.channel.id == inter.channel.id
                                                            , timeout=20)
        except asyncio.TimeoutError:
            return await inter.channel.send("Timeout!")
        try:
            user = user.mentions[0]
        except:
            return await inter.channel.send("Invalid user!")
        self.bot.db.execute(f"DELETE FROM claim WHERE userid = '{user.id}'")
        self.bot.db.execute(f"DELETE FROM claims WHERE userid = '{user.id}'")
        self.bot.database.commit()
        embed = discord.Embed(timestamp=utils.now()
                                , title="Reset Claims"
                                , description=f"All the claims of the user: {user.mention} has been successfully reseted."
                                , color=data['ui']['embedcolor'])
        embed.set_footer(text=inter.guild.name
                        , icon_url=data["ui"]["thumbnail"])
        embed.set_author(name=inter.guild.name)        
        await inter.channel.send(embed=embed)
    
    
class SelectResetV(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.add_item(SelectReset(bot))
    
class TicketsButton(discord.ui.View):
    def __init__(self, utils, bot):
        self.bot = bot
        self.utils = utils
        super().__init__(timeout=None)
        
    @discord.ui.button(label=f"{data['tickets']['open']['button']}"
                       , custom_id="opentcietkbutt"
                       , style=discord.ButtonStyle.success)
    async def oe(self, inter: discord.Interaction, button: discord.ui.Button):
        await inter.response.defer(thinking=True, ephemeral=True)

        user_role_ids = [role.id for role in inter.user.roles]
        inquiry_role_id = data["tickets"].get("inquiry_role_id")

        reasons_to_show = []
        for reason in data["tickets"]["reasons"]:
            if reason == "DM - בירור":
                if inquiry_role_id and inquiry_role_id in user_role_ids:
                    reasons_to_show.append(reason)
            else:
                reasons_to_show.append(reason)

        view = TicketsSelectView(self.utils, self.bot, reasons_to_show)

        embed = discord.Embed(color=data["tickets"]["open"]["color"],
                              description=data["tickets"]["open"]["embedselect"]["description"])
        embed.set_footer(text=inter.guild.name, icon_url=data["ui"]["thumbnail"])
        embed.set_author(name=inter.guild.name)
        await inter.followup.send(view=view, embed=embed, ephemeral=True)

class TicketsSelectView(discord.ui.View):
    def __init__(self, utils1, bot, reasons_list):
        super().__init__(timeout=None)
        self.add_item(TicketsSelect(utils1, bot, reasons_list))
    
class TicketSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ready = False
        

    
    @commands.has_any_role(data["server"]["staff"])
    @commands.command()
    async def resetclaims(self, ctx: commands.Context):
        await ctx.send(view=SelectResetV(self.bot))
        
        
    @commands.Cog.listener('on_message')
    async def msg(self, message: discord.Message):
        categories = list(data["categories"].values())
        try:
            if not message.channel.category:
                return
        except:
            return
        if message.channel.category.id not in categories: return
        userid = message.author.id
        channelid = message.channel.id
        messagecount = 0
        try:
            messagecount: int = self.bot.db.execute("SELECT messagecount FROM ticketsmessage WHERE userid = ? AND channelid = ?"
                                                    , (userid, channelid)).fetchone()[0]
        except:
            self.bot.db.execute("INSERT INTO ticketsmessage VALUES (?, ?, ?)"
                                , (channelid, userid, 0))
            self.bot.database.commit()
        self.bot.db.execute("UPDATE ticketsmessage SET messagecount = ? WHERE channelid = ? AND userid = ?",
                            (messagecount + 1, channelid, userid))
        self.bot.database.commit()
    
    @commands.has_role(data["server"]["staff"])
    @commands.command()
    async def topclaims(self, ctx: commands.Context):
        class TodayOrAlways(discord.ui.Select):
            def __init__(self, bot):
                self.bot = bot
                options: list[discord.SelectOption] = [
                    discord.SelectOption(
                        label="Always",
                        description="All the claims"
                    ),
                    
                    discord.SelectOption(
                        label="Today",
                        description="All the claims today"
                    )
                ]
                super().__init__(custom_id="topppic",
                                 placeholder="Select option",
                                 min_values=1,
                                 max_values=1,
                                 options=options)
            async def callback(self, interaction: discord.Interaction):
                # Helper function to chunk the data
                def chunk_data(data_list, chunk_size=25):
                    for i in range(0, len(data_list), chunk_size):
                        yield data_list[i:i + chunk_size]

                if self.values[0] == "Today":
                    now = utils.now()
                    date = f"{now.day}/{now.month}/{now.year}"
                    today = self.bot.db.execute(f"SELECT userid FROM claims WHERE date = '{date}'").fetchall()
                    today = [x[0] for x in today]
                    counter = Counter(today)
                    sorted_list = [(item, today.count(item)) for item in set(today)]  # Get unique users and their counts
                    sorted_list.sort(key=lambda x: x[1], reverse=True)  # Sort by count
                    todaylen = len(today)
                    
                    # Split the data into chunks
                    chunks = list(chunk_data(sorted_list))
                    if not chunks:
                        # If no data, send a single embed
                        embed = discord.Embed(
                            timestamp=utils.now(),
                            title="Ticket Claims",
                            description=f"Today Claims - `{todaylen}`\nNo claims found.",
                            color=discord.Color.from_rgb(40, 167, 69)
                        )
                        return await interaction.response.send_message(embed=embed)
                        
                    # Send first chunk with response
                    first_embed = discord.Embed(
                        timestamp=utils.now(),
                        title="Ticket Claims",
                        description=f"Today Claims - `{todaylen}`",
                        color=discord.Color.from_rgb(40, 167, 69)
                    )
                    for userid, count in chunks[0]:
                        first_embed.add_field(
                            name=f"{count} Claims",
                            value=f"<@{userid}>",
                            inline=True
                        )
                    await interaction.response.send_message(embed=first_embed)
                    
                    # Send remaining chunks as follow-up messages
                    for i, chunk in enumerate(chunks[1:], 1):
                        embed = discord.Embed(
                            timestamp=utils.now(),
                            title=f"Ticket Claims (Page {i+1})",
                            description=f"Today Claims - `{todaylen}`",
                            color=discord.Color.from_rgb(40, 167, 69)
                        )
                        for userid, count in chunk:
                            embed.add_field(
                                name=f"{count} Claims",
                                value=f"<@{userid}>",
                                inline=True
                            )
                        await interaction.channel.send(embed=embed)
                        
                else:  # "Always" option
                    always = self.bot.db.execute(f"SELECT userid FROM claims").fetchall()
                    always = [x[0] for x in always]
                    counter = Counter(always)
                    sorted_list = [(item, counter[item]) for item in counter]
                    sorted_list.sort(key=lambda x: x[1], reverse=True)
                    alwayslen = len(always)
                    
                    # Split the data into chunks
                    chunks = list(chunk_data(sorted_list))
                    if not chunks:
                        # If no data, send a single embed
                        embed = discord.Embed(
                            timestamp=utils.now(),
                            title="Ticket Claims",
                            description=f"Always Claims - `{alwayslen}`\nNo claims found.",
                            color=discord.Color.from_rgb(40, 167, 69)
                        )
                        return await interaction.response.send_message(embed=embed)
                        
                    # Send first chunk with response
                    first_embed = discord.Embed(
                        timestamp=utils.now(),
                        title="Ticket Claims",
                        description=f"Always Claims - `{alwayslen}`",
                        color=discord.Color.from_rgb(40, 167, 69)
                    )
                    for userid, count in chunks[0]:
                        first_embed.add_field(
                            name=f"{count} Claims",
                            value=f"<@{userid}>",
                            inline=True
                        )
                    await interaction.response.send_message(embed=first_embed)
                    
                    # Send remaining chunks as follow-up messages
                    for i, chunk in enumerate(chunks[1:], 1):
                        embed = discord.Embed(
                            timestamp=utils.now(),
                            title=f"Ticket Claims (Page {i+1})",
                            description=f"Always Claims - `{alwayslen}`",
                            color=discord.Color.from_rgb(40, 167, 69)
                        )
                        for userid, count in chunk:
                            embed.add_field(
                                name=f"{count} Claims",
                                value=f"<@{userid}>",
                                inline=True
                            )
                        await interaction.channel.send(embed=embed)
                        
        class TheView(discord.ui.View):
            def __init__(self, bot):
                super().__init__(timeout=None)              
                self.add_item(TodayOrAlways(bot))
        await ctx.send(view=TheView(self.bot))

    @commands.has_role(1125003229659406366) # PC Checker Role
    @commands.command()
    async def pcclaims(self, ctx: commands.Context):
        class TodayOrAlways(discord.ui.Select):
            def __init__(self, bot):
                self.bot = bot
                options: list[discord.SelectOption] = [
                    discord.SelectOption(
                        label="Always",
                        description="All the PC claims"
                    ),

                    discord.SelectOption(
                        label="Today",
                        description="All the PC claims today"
                    )
                ]
                super().__init__(custom_id="pc_toppic",
                                 placeholder="Select option",
                                 min_values=1,
                                 max_values=1,
                                 options=options)
            async def callback(self, interaction: discord.Interaction):
                def chunk_data(data_list, chunk_size=25):
                    for i in range(0, len(data_list), chunk_size):
                        yield data_list[i:i + chunk_size]

                if self.values[0] == "Today":
                    now = utils.now()
                    date = f"{now.day}/{now.month}/{now.year}"
                    today = self.bot.db.execute(f"SELECT userid FROM pc_claims WHERE date = '{date}'").fetchall()
                    today = [x[0] for x in today]
                    counter = Counter(today)
                    sorted_list = [(item, today.count(item)) for item in set(today)]
                    sorted_list.sort(key=lambda x: x[1], reverse=True)
                    todaylen = len(today)

                    chunks = list(chunk_data(sorted_list))
                    if not chunks:
                        embed = discord.Embed(
                            timestamp=utils.now(),
                            title="PC Checker Claims",
                            description=f"Today Claims - `{todaylen}`\nNo claims found.",
                            color=discord.Color.from_rgb(40, 167, 69)
                        )
                        return await interaction.response.send_message(embed=embed)

                    first_embed = discord.Embed(
                        timestamp=utils.now(),
                        title="PC Checker Claims",
                        description=f"Today Claims - `{todaylen}`",
                        color=discord.Color.from_rgb(40, 167, 69)
                    )
                    for userid, count in chunks[0]:
                        first_embed.add_field(name=f"{count} Claims", value=f"<@{userid}>", inline=True)
                    await interaction.response.send_message(embed=first_embed)

                    for i, chunk in enumerate(chunks[1:], 1):
                        embed = discord.Embed(
                            timestamp=utils.now(),
                            title=f"PC Checker Claims (Page {i+1})",
                            description=f"Today Claims - `{todaylen}`",
                            color=discord.Color.from_rgb(40, 167, 69)
                        )
                        for userid, count in chunk:
                            embed.add_field(name=f"{count} Claims", value=f"<@{userid}>", inline=True)
                        await interaction.channel.send(embed=embed)

                else:
                    always = self.bot.db.execute(f"SELECT userid FROM pc_claims").fetchall()
                    always = [x[0] for x in always]
                    counter = Counter(always)
                    sorted_list = [(item, counter[item]) for item in counter]
                    sorted_list.sort(key=lambda x: x[1], reverse=True)
                    alwayslen = len(always)

                    chunks = list(chunk_data(sorted_list))
                    if not chunks:
                        embed = discord.Embed(
                            timestamp=utils.now(),
                            title="PC Checker Claims",
                            description=f"Always Claims - `{alwayslen}`\nNo claims found.",
                            color=discord.Color.from_rgb(40, 167, 69)
                        )
                        return await interaction.response.send_message(embed=embed)

                    first_embed = discord.Embed(
                        timestamp=utils.now(),
                        title="PC Checker Claims",
                        description=f"Always Claims - `{alwayslen}`",
                        color=discord.Color.from_rgb(40, 167, 69)
                    )
                    for userid, count in chunks[0]:
                        first_embed.add_field(name=f"{count} Claims", value=f"<@{userid}>", inline=True)
                    await interaction.response.send_message(embed=first_embed)

                    for i, chunk in enumerate(chunks[1:], 1):
                        embed = discord.Embed(
                            timestamp=utils.now(),
                            title=f"PC Checker Claims (Page {i+1})",
                            description=f"Always Claims - `{alwayslen}`",
                            color=discord.Color.from_rgb(40, 167, 69)
                        )
                        for userid, count in chunk:
                            embed.add_field(name=f"{count} Claims", value=f"<@{userid}>", inline=True)
                        await interaction.channel.send(embed=embed)

        class TheView(discord.ui.View):
            def __init__(self, bot):
                super().__init__(timeout=None)
                self.add_item(TodayOrAlways(bot))
        await ctx.send(view=TheView(self.bot))
        
    
    @commands.Cog.listener('on_ready')
    async def on_ready(self):
        if self.ready: return
        self.ready = True    
        self.bot.db.execute("CREATE TABLE IF NOT EXISTS claims (channelid BIGINT, userid BIGINT, date TEXT, correct TEXT)")
        self.bot.db.execute("CREATE TABLE IF NOT EXISTS claim (channelid BIGINT, userid BIGINT)")
        self.bot.db.execute("CREATE TABLE IF NOT EXISTS ticketsmessage (channelid BIGINT, userid BIGINT, messagecount INT)")
        # --- New tables for PC Checker feature ---
        self.bot.db.execute("CREATE TABLE IF NOT EXISTS pc_claims (channelid BIGINT, userid BIGINT, date TEXT, correct TEXT)")
        self.bot.db.execute("CREATE TABLE IF NOT EXISTS pc_check_timers (channel_id INTEGER PRIMARY KEY, set_by INTEGER, end_time REAL)")
        self.bot.database.commit()
        self.utils = utils.Options(self.bot)
        guild = self.bot.get_guild(self.bot.guilds[0].id)
        categories = list(data["categories"].values())
        for category in guild.categories:
            if category.id in categories:
                for channel in category.channels:
                    async for m in channel.history(limit=1, oldest_first=True):
                        self.bot.add_view(view=StaffOptions(self.bot, self.utils)
                                          , message_id=m.id)
        clearchannel = self.bot.get_channel(data["tickets"]["clear"])                    
        embed = discord.Embed(timestamp=utils.now()
                                , title="Clear Tickets"
                                , description='Click on the button below to clear all the tickets'
                                , color=discord.Color.from_rgb(220, 53, 69))
        embed.set_footer(text=guild.name
                            , icon_url=data["ui"]["thumbnail"])
        embed.set_thumbnail(url=data["ui"]["thumbnail"])
        embed.set_image(url="https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExYmY0aG05YnBxMzUxdnRsbzNpMmhzdGxoZ2piOTB3ODYwZm1pajV1MSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/84NhEQpMPMM3BM9DCa/giphy.gif")
        messages: list[discord.Message] = [m async for m in clearchannel.history()]
        authors: list[int] = [a.author.id async for a in clearchannel.history()]
        if not messages or self.bot.user.id not in authors:
            await clearchannel.send(view=ClearTickets(self.bot)
                                     , embed=embed)
        else:
            async for m in clearchannel.history():
                if m.author.id == self.bot.user.id and m.embeds:
                    if m.embeds[0].title == "Clear Tickets":
                        self.bot.add_view(view=ClearTickets(self.bot)
                                          , message_id=m.id)
        ticketchannel = self.bot.get_channel(data["tickets"]["openchannel"])
        embed = discord.Embed(timestamp=utils.now()
                                , title=data["tickets"]["open"]["title"]
                                , description=f'{data["tickets"]["open"]["description"]}'
                                , color=data["tickets"]["open"]["color"])
        embed.set_footer(text=data["tickets"]["open"]["footer"]
                            , icon_url=data["ui"]["thumbnail"])
        embed.set_thumbnail(url=data["ui"]["thumbnail"])
        embed.set_image(url="https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExYmY0aG05YnBxMzUxdnRsbzNpMmhzdGxoZ2piOTB3ODYwZm1pajV1MSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/84NhEQpMPMM3BM9DCa/giphy.gif")
        messages: list[discord.Message] = [m async for m in ticketchannel.history()]
        authors: list[int] = [a.author.id async for a in ticketchannel.history()]
        if not messages or self.bot.user.id not in authors:
            await ticketchannel.send(view=TicketsButton(self.utils, self.bot)
                                     , embed=embed)
        else:
            async for m in ticketchannel.history():
                if m.author.id == self.bot.user.id and m.embeds:
                    if m.embeds[0].title == data["tickets"]["open"]["title"] and m.embeds[0].description == data["tickets"]["open"]["description"]:
                        self.bot.add_view(view=TicketsButton(self.utils, self.bot)
                                          , message_id=m.id)
        
        
async def setup(bot: commands.Bot):
    await bot.add_cog(TicketSystem(bot))