# cogs/move_queue_cog.py

import os
import discord
import asqlite
import asyncio
from discord import app_commands, abc as discord_abc
from discord.ext import commands

# --- Load environment variables needed ---
DB_PATH = os.getenv('DB_PATH')

# --- This dictionary stores (channel_id, message_id) tuples ---
move_queue = {}

async def log_to_audit_channel(bot, guild_id, log_message):
    """Fetches the audit log channel and sends a message."""
    async with asqlite.connect(DB_PATH) as conn:
        config = await conn.fetchone("SELECT audit_log_channel_id FROM guild_configs WHERE guild_id = ?", (guild_id,))
    
    # Use dictionary-style access, which is correct for sqlite3.Row
    if config and config['audit_log_channel_id']:
        try:
            log_channel = bot.get_channel(config['audit_log_channel_id']) or await bot.fetch_channel(config['audit_log_channel_id'])
            await log_channel.send(embed=log_message)
        except (discord.NotFound, discord.Forbidden):
            # Fail silently if the log channel has issues
            pass

# --- Main Cog Class ---
class MoveQueueCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.add_to_queue_context_menu = app_commands.ContextMenu(name='Add to Move Queue', callback=self.context_menu_callback)
        self.bot.tree.add_command(self.add_to_queue_context_menu)

    async def cog_check(self, interaction: discord.Interaction) -> bool:
        """A global check for all commands in this cog."""
        async with asqlite.connect(DB_PATH) as conn:
            config = await conn.fetchone("SELECT allowed_role_ids FROM guild_configs WHERE guild_id = ?", (interaction.guild.id,))
        
        if not config:
            await interaction.response.send_message("❌ MoveIt has not been configured. An admin must run `/setup` first.", ephemeral=True)
            return False
            
        if interaction.user.guild_permissions.administrator:
            return True
            
        allowed_ids_str = config['allowed_role_ids'] or ""
        allowed_role_ids = allowed_ids_str.split(',') if allowed_ids_str else []
        user_role_ids = {str(role.id) for role in interaction.user.roles}

        if not user_role_ids.intersection(allowed_role_ids):
            await interaction.response.send_message("❌ You do not have the required role or permissions to use this command.", ephemeral=True)
            return False

        return True

    async def context_menu_callback(self, interaction: discord.Interaction, message: discord.Message):
        """The callback for the right-click command."""
        user_id = interaction.user.id
        if user_id not in move_queue:
            move_queue[user_id] = []
        
        message_identifier = (message.channel.id, message.id)
        if message_identifier in move_queue[user_id]:
            await interaction.response.send_message("⚠️ This message is already in your queue.", ephemeral=True)
            return

        move_queue[user_id].append(message_identifier)
        queue_count = len(move_queue[user_id])
        await interaction.response.send_message(f"✅ Added message to queue. You now have **{queue_count}** message(s) queued.", ephemeral=True)


    queue_group = app_commands.Group(name="queue", description="Manage your message move queue.")

    @queue_group.command(name="view", description="View the number of messages in your queue.")
    async def view_queue(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        if user_id not in move_queue or not move_queue[user_id]:
            await interaction.followup.send("Your move queue is currently empty.")
        else:
            queue_count = len(move_queue[user_id])
            await interaction.followup.send(f"You have **{queue_count}** message(s) in your move queue.")

    @queue_group.command(name="clear", description="Clear all messages from your move queue.")
    async def clear_queue(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id
        if user_id in move_queue:
            del move_queue[user_id]
        await interaction.followup.send("✅ Your move queue has been cleared.")
        
    @queue_group.command(name="move", description="Moves all messages in your queue to a new location.")
    @app_commands.describe(target_channel="The channel or thread to move the messages to.", thread_name="Optional: Create a new thread for these messages.")
    async def move_queue_command(
        self, 
        interaction: discord.Interaction, 
        target_channel: discord_abc.GuildChannel,
        thread_name: str = None
    ):
        if not isinstance(target_channel, (discord.TextChannel, discord.Thread, discord.ForumChannel)):
             await interaction.response.send_message("❌ You can only move messages to a text channel, thread, or forum.", ephemeral=True)
             return

        await interaction.response.defer(ephemeral=True, thinking=True)
        
        user_id = interaction.user.id
        if user_id not in move_queue or not move_queue[user_id]:
            await interaction.followup.send("Your queue is empty.", ephemeral=True)
            return

        original_messages = []
        for channel_id, message_id in move_queue[user_id]:
            try:
                channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
                message = await channel.fetch_message(message_id)
                original_messages.append(message)
            except (discord.NotFound, discord.Forbidden):
                continue
        
        original_messages.sort(key=lambda m: m.created_at)
        
        if not original_messages:
            await interaction.followup.send("Could not fetch any of the queued messages. They may have been deleted.", ephemeral=True)
            return

        try:
            parent_channel = target_channel.parent if isinstance(target_channel, discord.Thread) else target_channel
            webhooks = await parent_channel.webhooks()
            webhook = discord.utils.get(webhooks, name="MoveIt") or await parent_channel.create_webhook(name="MoveIt")
        except (discord.Forbidden, AttributeError):
            await interaction.followup.send("❌ I don't have permission to manage webhooks in that channel.", ephemeral=True)
            return

        destination = target_channel
        if thread_name:
            if not isinstance(target_channel, (discord.TextChannel, discord.ForumChannel)):
                await interaction.followup.send("❌ You can only create threads in a normal text channel or a forum.", ephemeral=True)
                return
            try:
                destination = await target_channel.create_thread(name=thread_name, reason=f"Moved by {interaction.user}")
            except discord.Forbidden:
                await interaction.followup.send("❌ I don't have permission to create threads in that channel.", ephemeral=True)
                return

        for message in original_messages:
            content_with_attachments = message.content
            if message.attachments:
                urls = "\n".join([f"**Attachment:** {att.url}" for att in message.attachments])
                content_with_attachments += f"\n\n{urls}"
            
            send_kwargs = {
                'content': content_with_attachments,
                'username': message.author.display_name,
                'avatar_url': message.author.display_avatar.url,
                'embeds': message.embeds
            }
            if isinstance(destination, discord.Thread):
                send_kwargs['thread'] = destination
            
            await webhook.send(**send_kwargs)

            try:
                await message.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
            await asyncio.sleep(1.5)

        final_destination = f"thread **{destination.name}**" if isinstance(destination, discord.Thread) else destination.mention
        await interaction.followup.send(f"✅ Successfully moved **{len(original_messages)}** message(s) to {final_destination}.")
        
        # --- THIS IS THE FINAL FIX ---
        # Isolate the audit log in a try/except block.
        try:
            source_channels = ", ".join(set(f"#{msg.channel.name}" for msg in original_messages))
            log_embed = discord.Embed(
                title="Messages Moved",
                color=discord.Color.green(),
                description=f"**{len(original_messages)}** message(s) were moved.",
                timestamp=discord.utils.utcnow()
            )
            log_embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Destination", value=final_destination, inline=True)
            log_embed.add_field(name="Source(s)", value=source_channels, inline=False)
            log_embed.set_footer(text="MoveIt Audit Log")
            await log_to_audit_channel(self.bot, interaction.guild.id, log_embed)
        except Exception as e:
            # If logging fails for any reason, print to console but DO NOT stop the command.
            print(f"Failed to send audit log: {e}")

        # This will now ALWAYS be reached after a successful move.
        del move_queue[user_id]

async def setup(bot: commands.Bot):
    await bot.add_cog(MoveQueueCog(bot))