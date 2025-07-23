# cogs/split_cog.py

import os
import discord
import asqlite
import asyncio
import io
from discord import app_commands, abc as discord_abc
from discord.ext import commands

DB_PATH = os.getenv('DB_PATH')
MAX_ATTACHMENT_SIZE = 7 * 1024 * 1024

async def log_to_audit_channel(bot, guild_id, log_message):
    async with asqlite.connect(DB_PATH) as conn:
        config = await conn.fetchone("SELECT audit_log_channel_id FROM guild_configs WHERE guild_id = ?", (guild_id,))
    if config and config['audit_log_channel_id']:
        try:
            log_channel = bot.get_channel(config['audit_log_channel_id']) or await bot.fetch_channel(config['audit_log_channel_id'])
            await log_channel.send(embed=log_message)
        except: pass

class SplitCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="split", description="Moves a continuous block of messages to a new location.")
    @app_commands.describe(first_message_id="The ID of the FIRST message in the block.", target_channel="The channel or thread to move the messages to.", last_message_id="[OPTIONAL] The ID of the LAST message in the block.", thread_name="[OPTIONAL] Create a new thread for these messages.")
    async def split_command(self, interaction: discord.Interaction, first_message_id: str, target_channel: discord_abc.GuildChannel, last_message_id: str = None, thread_name: str = None):
        # --- DEFER FIRST! ---
        await interaction.response.defer(ephemeral=True, thinking=True)

        # --- CHECK PERMISSIONS SECOND! ---
        async with asqlite.connect(DB_PATH) as conn:
            config = await conn.fetchone("SELECT allowed_role_ids FROM guild_configs WHERE guild_id = ?", (interaction.guild.id,))
        if not config:
            await interaction.followup.send("❌ MoveIt has not been configured.", ephemeral=True)
            return
        if not interaction.user.guild_permissions.administrator:
            allowed_ids_str = config.get('allowed_role_ids') or ""
            allowed_role_ids = allowed_ids_str.split(',') if allowed_ids_str else []
            user_role_ids = {str(role.id) for role in interaction.user.roles}
            if not user_role_ids.intersection(allowed_role_ids):
                await interaction.followup.send("❌ You do not have the required role or permissions.", ephemeral=True)
                return
        
        # --- THE REST OF THE COMMAND LOGIC ---
        if not isinstance(target_channel, (discord.TextChannel, discord.Thread, discord.ForumChannel)):
             await interaction.followup.send("❌ Invalid target channel.", ephemeral=True)
             return
        
        try:
            messages_to_move = []
            first_message = await interaction.channel.fetch_message(int(first_message_id))
            if last_message_id is None:
                messages_to_move.append(first_message)
            else:
                last_message = await interaction.channel.fetch_message(int(last_message_id))
                if first_message.channel.id != last_message.channel.id:
                    await interaction.followup.send("❌ Start and end messages must be in the same channel.", ephemeral=True)
                    return
                if first_message.created_at > last_message.created_at:
                    start_msg, end_msg = last_message, first_message
                else:
                    start_msg, end_msg = first_message, last_message
                history_between = [msg async for msg in interaction.channel.history(after=start_msg, before=end_msg, oldest_first=True)]
                messages_to_move = [start_msg] + history_between + [end_msg]
        except (ValueError, discord.NotFound, discord.HTTPException):
            await interaction.followup.send("❌ Invalid message ID.", ephemeral=True)
            return
            
        try:
            parent_channel = target_channel.parent if isinstance(target_channel, discord.Thread) else target_channel
            webhooks = await parent_channel.webhooks()
            webhook = discord.utils.get(webhooks, name="MoveIt") or await parent_channel.create_webhook(name="MoveIt")
        except:
            await interaction.followup.send("❌ I can't manage webhooks in the target channel.", ephemeral=True)
            return
            
        destination = target_channel
        if thread_name:
            if not isinstance(target_channel, (discord.TextChannel, discord.ForumChannel)):
                await interaction.followup.send("❌ You can only create threads in a normal text channel or a forum.", ephemeral=True)
                return
            try:
                destination = await target_channel.create_thread(
                    name=thread_name,
                    type=discord.ChannelType.public_thread,
                    reason=f"Split by {interaction.user}"
                )
            except discord.Forbidden:
                await interaction.followup.send("❌ I can't create threads in that channel.", ephemeral=True)
                return
        
        moved_count = 0
        for i, message in enumerate(messages_to_move):
            try:
                message_state = (bool(message.content), bool(message.attachments), bool(message.embeds), bool(message.webhook_id))
                match message_state:
                    case (_, _, _, True):
                        quote_embed = discord.Embed(description=message.content, timestamp=message.created_at)
                        quote_embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
                        quote_embed.set_footer(text=f"Original message from #{interaction.channel.name}")
                        await destination.send(embeds=[quote_embed] + message.embeds)
                        moved_count += 1
                    case (True, _, _, False) | (_, True, _, False) | (_, _, True, False):
                        files_to_send = []
                        content_with_links = message.content
                        if message.attachments:
                            for attachment in message.attachments:
                                if attachment.size > MAX_ATTACHMENT_SIZE:
                                    content_with_links += f"\n\n**(Attachment too large to move:** `{attachment.filename}`\n{attachment.url} **)**"
                                else:
                                    buffer = io.BytesIO(await attachment.read())
                                    files_to_send.append(discord.File(buffer, filename=attachment.filename))
                        send_kwargs = {'content': content_with_links, 'username': message.author.display_name, 'avatar_url': message.author.display_avatar.url, 'embeds': message.embeds, 'files': files_to_send}
                        if isinstance(destination, discord.Thread): send_kwargs['thread'] = destination
                        await webhook.send(**send_kwargs)
                        moved_count += 1
                    case _:
                        pass
                await message.delete()
                await asyncio.sleep(1)
            except Exception as e:
                error_message = f"❌ A critical error occurred while moving message #{i+1}. **The split has been aborted.**\n\n**Error:** `{e}`"
                await interaction.followup.send(error_message, ephemeral=True)
                return
        
        final_destination = f"thread **{destination.name}**" if isinstance(destination, discord.Thread) else destination.mention
        await interaction.followup.send(f"✅ Successfully split **{moved_count}** message(s) to {final_destination}.", ephemeral=True)
        source_channel_name = f"#{interaction.channel.name}"
        log_embed = discord.Embed(title="Channel Split", color=discord.Color.blue(), description=f"A block of **{moved_count}** message(s) was split.", timestamp=discord.utils.utcnow())
        log_embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="Destination", value=final_destination, inline=True)
        log_embed.add_field(name="Source", value=source_channel_name, inline=False)
        log_embed.set_footer(text="MoveIt Audit Log")
        await log_to_audit_channel(self.bot, interaction.guild.id, log_embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(SplitCog(bot))