import re
import datetime
import time

import discord
from discord.ext import commands
from discord.ext.commands import Cog, command, group
import functools
from durations_nlp import Duration

from .utils import arg # pylint: disable=relative-beyond-top-level

class CustomCommands(Cog):
    def __init__(self, bot):
        self.bot = bot

    def role_is_safe(self, ctx, fnc_role):
        server_role = [
            role for role in ctx.guild.roles 
            if role.name.lower() == fnc_role.lower()
            and role.permissions.administrator is False
            and role.permissions.ban_members is False
            and role.permissions.kick_members is False
            and role.permissions.manage_channels is False
            and role.permissions.manage_roles is False
            and role.permissions.mention_everyone is False
        ]

        if server_role:
            return True
        else:
            return False

    @group(name="cc", aliases=['custom-commands', 'custom-command', 'customcommand', 'customcommands'])
    @commands.has_permissions(administrator=True)
    async def cc(self, ctx):
        """View all the functions of custom command code."""
        if not ctx.invoked_subcommand:
            server = ctx.guild
            custom_commands = await ctx.fetch("SELECT * FROM custom_commands WHERE guild_id=$1", server.id)

            await ctx.send(f"""
There are currently `{len(custom_commands)}` custom commands added in this server.

TBA
            """)

    @cc.command(name='add', brief='Add a custom command with a piece of code attached to it.')
    @commands.has_permissions(administrator=True)
    async def add(self, ctx, name: str, *, code: str):
        """Add a custom command with a piece of code attached to it."""

        server = ctx.guild
        user = ctx.author

        if len(name) > 20:
            return await ctx.send(f"{self.bot.x} The custom command name must be less than 10 characters.")
            
        found_command = await ctx.fetchrow("SELECT * FROM custom_commands WHERE guild_id=$1 AND cc_name=$2", server.id, name.lower())
        if found_command:
            return await ctx.send(f"{self.bot.x} That custom command has already been registered in the database.")
        
        if self.bot.get_command(name.lower()):
            return await ctx.send(f"{self.bot.x} That is already a default command in FeudalBot.")
        msg = await ctx.send(f"{self.bot.cooldown} Creating the custom command...")

        code = code.strip("`")
        if re.match('py(thon)?\n', code):
            code = "\n".join(code.split("\n")[1:])

        for code_piece in code.split("\n"):
            function = code_piece.split()

            
                        
def setup(bot):
    bot.add_cog(CustomCommands(bot))