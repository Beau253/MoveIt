# move_it.py

import os
import sys
import discord
import asyncio
import logging
import asqlite
from discord.ext import commands
from dotenv import load_dotenv
from threading import Thread
from flask import Flask
import gdrive_handler

print("[MOVEIT_PY][STARTUP] Script execution started.")

# --- Load and Validate Environment Variables ---
print("[MOVEIT_PY][STARTUP-STEP 1] Loading environment variables...")
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
DB_PATH = os.getenv('DB_PATH')
LOG_PATH = os.getenv('LOG_PATH')
GDRIVE_CREDENTIALS = os.getenv('GDRIVE_CREDENTIALS')
GDRIVE_FOLDER_ID = os.getenv('GDRIVE_FOLDER_ID')

if not all([TOKEN, DB_PATH, LOG_PATH, GDRIVE_CREDENTIALS, GDRIVE_FOLDER_ID]):
    print("CRITICAL ERROR: One or more environment variables are missing.", file=sys.stderr)
    sys.exit("Exiting due to missing environment variables.")
print("[MOVEIT_PY][STARTUP-STEP 1] Environment variables loaded successfully.")

# --- Logger Setup ---
print("[MOVEIT_PY][STARTUP-STEP 2] Initializing file logger...")
# (Logger setup remains the same)
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename=LOG_PATH, encoding='UTF-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)
print("[MOVEIT_PY][STARTUP-STEP 2] File logger initialized.")

# --- Database Initialization Function ---
async def db_init():
    print("[MOVEIT_PY][DB_INIT] Initializing local database...")
    async with asqlite.connect(DB_PATH) as connection:
        await connection.execute("CREATE TABLE IF NOT EXISTS guild_configs (guild_id INTEGER PRIMARY KEY, audit_log_channel_id INTEGER, allowed_role_ids TEXT)")
        await connection.execute("CREATE TABLE IF NOT EXISTS prefs (guild_id INTEGER PRIMARY KEY, notify_dm TEXT, embed_message TEXT, move_message TEXT, strip_ping TEXT, delete_original TEXT)")
        await connection.commit()
    print("[MOVEIT_PY][DB_INIT] Local database tables verified/created.")

# --- Bot Definition ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MoveItBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!mi", intents=intents)
        print("[MOVEIT_PY][BOT_INIT] MoveItBot class initialized.")

    async def on_ready(self):
        print("--------------------------------------------------")
        print(f"[MOVEIT_PY][ON_READY] Logged in as {self.user} (ID: {self.user.id}). Bot is fully operational.")
        print("--------------------------------------------------")

    # The setup_hook is where all async startup logic should go.
    # It is guaranteed to run before on_ready.
    async def setup_hook(self):
        print("[MOVEIT_PY][SETUP_HOOK] Starting async setup process...")
        print("[MOVEIT_PY][SETUP_HOOK] Step 1: Google Drive Sync...")
        gdrive_handler.sync_with_gdrive(GDRIVE_CREDENTIALS, GDRIVE_FOLDER_ID, DB_PATH)
        print("[MOVEIT_PY][SETUP_HOOK] Step 1 complete.")
        
        print("[MOVEIT_PY][SETUP_HOOK] Step 2: Database Init...")
        await db_init()
        print("[MOVEIT_PY][SETUP_HOOK] Step 2 complete.")

        print("[MOVEIT_PY][SETUP_HOOK] Step 3: Loading Cogs...")
        bot_dir = os.path.dirname(os.path.abspath(__file__))
        cogs_path = os.path.join(bot_dir, 'cogs')
        for filename in os.listdir(cogs_path):
            if filename.endswith('.py'):
                cog_name = f'cogs.{filename[:-3]}'
                try:
                    await self.load_extension(cog_name)
                    print(f"[MOVEIT_PY][SETUP_HOOK] ✅ Successfully loaded Cog: {cog_name}")
                except Exception as e:
                    print(f"[MOVEIT_PY][SETUP_HOOK] ❌ Failed to load cog {cog_name}: {e}", file=sys.stderr)
        print("[MOVEIT_PY][SETUP_HOOK] Step 3 complete.")

        print("[MOVEIT_PY][SETUP_HOOK] Step 4: Syncing application commands...")
        try:
            await self.tree.sync()
            print("[MOVEIT_PY][SETUP_HOOK] ✅ Command tree successfully synced!")
        except Exception as e:
            print(f"[MOVEIT_PY][SETUP_HOOK] ❌ FAILED TO SYNC COMMANDS: {e}", file=sys.stderr)
        print("[MOVEIT_PY][SETUP_HOOK] Step 4 complete.")
        print("[MOVEIT_PY][SETUP_HOOK] Setup hook finished.")

# --- Keep-Alive Server ---
app = Flask('')
@app.route('/')
def home(): return "MoveIt is alive!"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    print("[MOVEIT_PY][KEEP-ALIVE] Starting Flask server thread.")
    Thread(target=run).start()

# --- THIS IS THE CORRECTED MAIN EXECUTION BLOCK ---
if __name__ == '__main__':
    print("[MOVEIT_PY][MAIN_BLOCK] Main execution block started.")
    
    # Start the keep-alive server first
    keep_alive()
    
    # Create an instance of the bot
    bot = MoveItBot()
    
    # Run the bot directly
    # This is a more direct approach that can solve startup issues in some environments.
    try:
        print("[MOVEIT_PY][MAIN_BLOCK] Starting bot.run(TOKEN)...")
        bot.run(TOKEN)
    except Exception as e:
        print("--- [ULTIMATE CATCH-ALL ERROR] ---", file=sys.stderr)
        print(f"The bot's main run() method crashed with an unhandled exception: {e}", file=sys.stderr)
        print("--- [END OF REPORT] ---", file=sys.stderr)