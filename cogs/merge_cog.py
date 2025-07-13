# cogs/merge_cog.py

import os
import discord
import asqlite
import asyncio
import io
from discord import app_commands, ui
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

class ConfirmView(ui.View):
    def __init__(self, author: discord.User):
        super().__init__(timeout=60.0)
        self.value = None; self.author = author; self.interaction = None
    async def interaction_check(self, i: discord.Interaction):
        if i.user.id != self.author.id:
            await i.response.send_message("You cannot interact with this.", ephemeral=True)
            return False
        return True
    @ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, i: discord.Interaction, button: ui.Button):
        self.value = True; self.interaction = i
        for item in self.children: item.disabled = True
        await i.response.edit_message(view=self)
        self.stop()
    @ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, i: discord.Interaction, button: ui.Button):
        self.value = False; self.interaction = i
        for item in self.children: item.disabled = True
        await i.response.edit_message(view=self)
        self.stop()

class MergeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _execute_merge(self, interaction: discord.Interaction, source: discord.TextChannel, target: discord.TextChannel, delete_source: bool):
        source_channel_name = source.name
        try:
            all_messages = [message async for message in source.history(limit=None, oldest_first=True)]
            if not all_messages:
                await interaction.followup.send("Source channel is empty.", ephemeral=True)
                return
            
            webhooks = await target.webhooks()
            webhook = discord.utils.get(webhooks, name="MoveIt") or await target.create_webhook(name="MoveIt")
            moved_count = 0
            
            for i, message in enumerate(all_messages):
                try:
                    # Define the message state as a tuple for pattern matching
                    message_state = (bool(message.content), bool(message.attachments), bool(message.embeds), bool(message.webhook_id))

                    match message_state:
                        # Case 1: Any message from a webhook
                        case (_, _, _, True):
                            quote_embed = discord.Embed(description=message.content, timestamp=message.created_at)
                            quote_embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
                            quote_embed.set_footer(text=f"Original message from #{source_channel_name}")
                            await target.send(embeds=[quote_embed] + message.embeds)
                            moved_count += 1

                        # Case 2: A regular user message with any combination of content, embeds, or attachments
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
                            
                            await webhook.send(
                                content=content_with_links,
                                username=message.author.display_name,
                                avatar_url=message.author.display_avatar.url,
                                embeds=message.embeds,
                                files=files_to_send
                            )
                            moved_count += 1
                        
                        # Case 3 (Default): An unsendable message (e.g., sticker).
                        case _:
                            print(f"Skipping unsendable message (ID: {message.id}).")
                            pass # Do nothing, just proceed to delete it

                    await message.delete()
                    await asyncio.sleep(1)

                except Exception as e:
                    error_message = f"❌ A critical error occurred while moving message #{i+1}. **The merge has been aborted.**\n\n**Error:** `{e}`\n\nThe source channel has NOT been deleted."
                    await interaction.followup.send(error_message, ephemeral=True)
                    return
            
            # This part is only reached if the loop completes without any errors.
            if delete_source:
                await source.delete(reason=f"Merged into #{target.name} by {interaction.user}")
            
            final_message = f"✅ Successfully merged **{moved_count}** message(s) from `#{source_channel_name}` into {target.mention}."
            if delete_source: final_message += f"\n\nThe `#{source_channel_name}` channel has been deleted."
            await target.send(f"✅ This channel has been successfully merged with `#{source_channel_name}` by {interaction.user.mention}.")
            
            log_embed = discord.Embed(title="Channel Merge Complete", color=discord.Color.orange(), description=f"**Moderator:** {interaction.user.mention}\n**Source:** `#{source_channel_name}`\n**Target:** {target.mention}\n**Messages Moved:** {moved_count}", timestamp=discord.utils.utcnow())
            log_embed.set_footer(text="MoveIt Audit Log")
            await log_to_audit_channel(self.bot, interaction.guild.id, log_embed)
        except Exception as e:
            await interaction.followup.send(f"An unexpected error occurred during merge setup: `{e}`", ephemeral=True)

    @app_commands.command(name="merge", description="[ADMIN ONLY] Moves all messages from a source channel to a target channel.")
    @app_commands.describe(source_channel="The channel to move messages FROM.", target_channel="The channel to move messages TO.", delete_source_channel="[DANGEROUS] Delete the source channel after the merge? (Default: False)")
    @app_commands.checks.has_permissions(administrator=True)
    async def merge_command(self, interaction: discord.Interaction, source_channel: discord.TextChannel, target_channel: discord.TextChannel, delete_source_channel: bool = False):
        if source_channel.id == target_channel.id:
            await interaction.response.send_message("❌ Source and target channels cannot be the same.", ephemeral=True)
            return
        view = ConfirmView(interaction.user)
        confirmation_message = f"**⚠️ You are about to merge all messages from `#{source_channel.name}` into `#{target_channel.name}`.**\n\nThis action is **irreversible**.\n\n"
        if delete_source_channel: confirmation_message += f"**DANGER:** You have also chosen to **DELETE** the `#{source_channel.name}` channel after the merge."
        await interaction.response.send_message(confirmation_message, view=view, ephemeral=True)
        await view.wait()
        if view.value is True:
            await view.interaction.followup.send("Merge confirmed. This may take a long time for large channels. Please be patient.", ephemeral=True)
            await self._execute_merge(interaction, source_channel, target_channel, delete_source_channel)
        elif view.value is False:
            await interaction.followup.send("Merge cancelled.", ephemeral=True)
        else:
            await interaction.edit_original_response(content="Confirmation timed out.", view=None)

async def setup(bot: commands.Bot):
    await bot.add_cog(MergeCog(bot))