import discord
from discord.ext import commands

TARGET_ROLE_ID = 1418509991685521498
ALLOWED_ROLE_ID = 1052668934307975198
TARGET_CHANNEL_ID = 1418510177275084800

class ConfirmationView(discord.ui.View):
    def __init__(self, user_to_remove_from):
        super().__init__(timeout=60)
        self.user_to_remove_from = user_to_remove_from
        self.confirmed = None

    @discord.ui.button(label="אשר", style=discord.ButtonStyle.success, custom_id="confirm_remove")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_to_remove_from.id:
            await interaction.response.send_message("This is not for you!", ephemeral=True)
            return

        self.confirmed = True
        self.stop()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="בטל", style=discord.ButtonStyle.danger, custom_id="cancel_remove")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_to_remove_from.id:
            await interaction.response.send_message("This is not for you!", ephemeral=True)
            return

        self.confirmed = False
        self.stop()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

class RoleButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Removed custom_id parameter

    @discord.ui.button(label="🏷️ קבל תיוגים", style=discord.ButtonStyle.success, custom_id="role_button")
    async def role_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_roles = [role.id for role in interaction.user.roles]

        if ALLOWED_ROLE_ID not in user_roles:
            return await interaction.response.send_message("אין לך הרשאה להשתמש בכפתור זה.", ephemeral=True)

        target_role = interaction.guild.get_role(TARGET_ROLE_ID)
        if not target_role:
            return await interaction.response.send_message("שגיאה: רול המטרה לא נמצא.", ephemeral=True)

        if target_role in interaction.user.roles:
            confirmation_view = ConfirmationView(interaction.user)
            await interaction.response.send_message(
                "האם אתה בטוח שברצונך להסיר את הרול?",
                view=confirmation_view,
                ephemeral=True
            )
            await confirmation_view.wait()
            if confirmation_view.confirmed:
                await interaction.user.remove_roles(target_role)
                await interaction.followup.send("הרול הוסר בהצלחה.", ephemeral=True)
            else:
                await interaction.followup.send("הפעולה בוטלה.", ephemeral=True)
        else:
            await interaction.user.add_roles(target_role)
            await interaction.response.send_message("הרול נוסף בהצלחה.", ephemeral=True)

class RoleManagement(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(RoleButtonView())

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(TARGET_CHANNEL_ID)
        if not channel:
            print(f"ERROR: Role button channel with ID {TARGET_CHANNEL_ID} not found.")
            return

        # Check if a message with our view already exists
        async for message in channel.history(limit=100):
            if message.author == self.bot.user and message.components:
                try:
                    if message.components[0].children[0].custom_id == "role_button":
                        print("Role button message already exists.")
                        return
                except (IndexError, AttributeError):
                    continue

        # Send new message
        print("Role button message not found, sending new one.")
        embed = discord.Embed(
            title="🏷️ תיוגים בדיסקורד",
            description="כדי לקבל תיוגים בדיסקורד, לחץ על הכפתור: **קבל**\n\nניתן גם להסיר :)",
            color=0x5865F2
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/852881450667081728.png")
        embed.set_footer(text="לחץ על הכפתור למטה", icon_url="https://cdn.discordapp.com/emojis/741614680652218469.gif")
        try:
            await channel.send(embed=embed, view=RoleButtonView())
        except discord.Forbidden:
            print(f"ERROR: Missing permissions to send message in channel {TARGET_CHANNEL_ID}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleManagement(bot))