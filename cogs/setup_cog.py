# cogs/setup_cog.py

import os
import discord
import asqlite
import re
import asyncio
from discord import app_commands
from discord.ext import commands
import gdrive_handler

DB_PATH = os.getenv('DB_PATH')
GDRIVE_CREDENTIALS = os.getenv('GDRIVE_CREDENTIALS')
GDRIVE_FOLDER_ID = os.getenv('GDRIVE_FOLDER_ID')

def run_gdrive_upload():
    print("[SETUP_COG][GDRIVE_UPLOAD_BG] Starting background GDrive upload...")
    try:
        service = gdrive_handler.get_drive_service(GDRIVE_CREDENTIALS)
        if service:
            gdrive_handler.upload_db(service, GDRIVE_FOLDER_ID, DB_PATH)
            print("[SETUP_COG][GDRIVE_UPLOAD_BG] ✅ Background upload finished.")
        else:
            print("[SETUP_COG][GDRIVE_UPLOAD_BG] ❌ Could not get GDrive service to start upload.")
    except Exception as e:
        print(f"[SETUP_COG][GDRIVE_UPLOAD_BG] ❌ FAILED: {e}")

class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="[Admin Only] Configure MoveIt for this server.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction, audit_log_channel: discord.TextChannel, additional_roles: str = None):
        print("\n[SETUP_COG][SETUP] Command invoked.")
        await interaction.response.defer(ephemeral=True)
        
        print("[SETUP_COG][SETUP] Parsing roles...")
        role_ids = []
        if additional_roles:
            role_ids = re.findall(r'<@&(\d+)>', additional_roles)
        role_ids_str = ",".join(role_ids) if role_ids else ""
        print(f"[SETUP_COG][SETUP] Parsed role IDs: {role_ids_str}")
        
        print("[SETUP_COG][SETUP] Writing to local database...")
        try:
            async with asqlite.connect(DB_PATH) as connection:
                await connection.execute("INSERT OR REPLACE INTO guild_configs (guild_id, audit_log_channel_id, allowed_role_ids) VALUES (?, ?, ?)", (interaction.guild.id, audit_log_channel.id, role_ids_str))
                await connection.commit()
            print("[SETUP_COG][SETUP] Local DB write successful.")
            
            print("[SETUP_COG][SETUP] Starting background GDrive upload task...")
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, run_gdrive_upload)
            print("[SETUP_COG][SETUP] Background task created.")

        except Exception as e:
            print(f"[SETUP_COG][SETUP] ❌ FAILED during DB operation: {e}")
            await interaction.followup.send(f"❌ **Database Error!** Could not save configuration: `{e}`", ephemeral=True)
            return

        print("[SETUP_COG][SETUP] Sending confirmation messages...")
        await interaction.followup.send("✅ **MoveIt has been configured!**", ephemeral=True)
        try:
            await audit_log_channel.send("✅ **This channel has been set as the Audit Log for MoveIt.**")
        except discord.Forbidden:
            await interaction.followup.send("⚠️ **Warning:** Could not send confirmation to the audit channel. Please check my permissions.", ephemeral=True)
        print("[SETUP_COG][SETUP] Command finished successfully.")

async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))