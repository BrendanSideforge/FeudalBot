import datetime

import discord
from discord.ext import commands
from discord.ext.commands import command, Cog, Context, group

from .utils import time # pylint: disable=relative-beyond-top-level

class Settings(Cog):
    def __init__(self, bot):
        self.bot = bot

    @command(name="prefix", usage="<prefix>", brief='Set the server prefix.')
    @commands.has_permissions(manage_guild=True)
    async def prefix(self, ctx: Context, prefix: str = None):
        """Set the server prefix."""
        server = ctx.guild

        if not prefix:
            settings = await ctx.fetchrow("SELECT * FROM settings WHERE guild_id=$1", server.id)
            prefix = settings['prefix']
            await ctx.send(f"The current server prefix is: `{prefix}`")
            return

        # a prefix larger than 5 characters will trigger an error
        if len(prefix) > 4:
            return await ctx.send(f"{self.bot.x} Please shorten the prefix.")

        await ctx.execute("UPDATE settings SET prefix=$2 WHERE guild_id=$1", server.id, prefix)

        await ctx.send(f"{self.bot.check} The server prefix has been set to: `{prefix}`")

    @group(name="map", brief="View the current map settings and contents.")
    @commands.has_permissions(administrator=True)
    async def map(self, ctx: Context):
        """View the current map settings and contents."""
        if not ctx.invoked_subcommand:
            server = ctx.guild
            settings = await ctx.fetchrow("SELECT * FROM settings WHERE guild_id=$1", server.id)

            mapped_clans = ", ".join(settings['mapped_clans'])
            if len(mapped_clans) == 0:
                mapped_clans = "No clans have been added to the map."

            # get the last message in the channel: #map
            channel = server.get_channel(547718591638798386)
            history = await channel.history().flatten()
            message = history[0]

            embed = discord.Embed()
            embed.set_author(name="Mapped Clans", icon_url=server.icon_url)
            embed.add_field(name=f":map: Clans on the map ({len(settings['mapped_clans'])})", value=mapped_clans, inline=False)
            embed.add_field(name=f"{self.bot.cooldown} Last updated", value=message.created_at.strftime("%A, %B %d, %I:%M %p"))
            if len(message.attachments) >= 1:
                attachment = message.attachments[0].proxy_url
                embed.set_image(url=attachment)
            
            await ctx.send(embed=embed)

    @map.command(name="add", usage="<clans>", brief="Add clans to the mapped database.")
    @commands.has_permissions(administrator=True)
    async def map_add(self, ctx: Context, *, maps: str):
        """Add clans to the mapped database.

        You can add multiple maps by separating them with a comma.
        """
        server = ctx.guild
        settings = await ctx.fetchrow("SELECT * FROM settings WHERE guild_id=$1", server.id)
        mapped_clans = settings['mapped_clans']

        wanted_clans = await ctx.sep(maps)

        for clan in wanted_clans:
            clan = clan.strip()
            # postgres doesn't have a check to see if there is a dup
            # so we must return if there already is an item in there that matches this clan
            if clan in mapped_clans:
                continue

            mapped_clans.append(clan)

        await ctx.execute("UPDATE settings SET mapped_clans=$2 WHERE guild_id=$1", server.id, mapped_clans)
        
        clans_format = ", ".join([f"`{x}`" for x in wanted_clans])
        await ctx.send(f"{self.bot.check} You have added the clans {clans_format} to the map!")

    @map.command(name="remove", usage="<clans>", brief="Remove clans from the mapped database.")
    @commands.has_permissions(administrator=True)
    async def map_remove(self, ctx: Context, *, maps: str):
        """Remove clans from the mapped database.

        You can remove multiple databases by separating them with a comma.
        """
        server = ctx.guild
        settings = await ctx.fetchrow("SELECT * FROM settings WHERE guild_id=$1", server.id)
        mapped_clans = settings['mapped_clans']

        wanted_clans = await ctx.sep(maps)

        for clan in wanted_clans:
            clan = clan.strip()

            # We would get an error if we didn't have this 
            # you can't remove an item from a list when it doesn't even exist
            if not clan in mapped_clans:
                continue

            mapped_clans.remove(clan)

        await ctx.execute("UPDATE settings SET mapped_clans=$2 WHERE guild_id=$1", server.id, mapped_clans)

        clans_format = ", ".join([f"`{x}`" for x in wanted_clans])
        await ctx.send(f"{self.bot.check} You have removed the clans {clans_format} from the map.")

    @command(name="clanhop", aliases=['clan-hop'], usage="<on/off>", brief="Set the clanhop rule to be on or off.")
    @commands.has_permissions(administrator=True)
    async def clanhop(self, ctx: Context, action: str = None):
        """Set the clanhop rule to be on or off.

        When the clanhop rule is on they are allowed to switch clans and go clanless.
        When the clanhop rule is off they are not allowed to switch clans and go clanless, unless they are clanless or
        their clan is not on the map.

        When you turn the clanhop rule on, there will be a timer for 24 hours and once that timer expires,
        people will not be able to switch clans and go clanless, unless they are clanless or their clan is not on the map.
        """

        if not action:
            key = await self.bot.redis.get("clanhop")
            ttl = await self.bot.redis.ttl('clanhop')
            # usually a negative number is below 0....
            if not key or ttl <= 0:
                await ctx.send(f"{self.bot.check} Clan hopping is `disabled`.")
            else:
                # create a datetime object by adding 86400 seconds to the current datetime timestamp
                dt_object = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp() + ttl)
                expires_at = time.human_timedelta(dt_object, accuracy=None, brief=True, suffix=False)
                await ctx.send(f"{self.bot.check} Clan hopping is `enabled` and it will disable in `{expires_at}`.")
            return

        actions = ['on', 'off']
        if not action.lower() in actions:
            return await ctx.send(f"{self.bot.x} You can only turn clan hopping on or off.")
        
        if action.lower() == "on":
            await self.bot.redis.setex("clanhop", 86400, "on")

            dt_object = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp() + 86400)
            expires_at = time.human_timedelta(dt_object, accuracy=None, brief=True, suffix=False)
            await ctx.send(f"{self.bot.check} Clan hopping has been `enabled` and it will be disabled in `{expires_at}`.")
        
        else:
            await self.bot.redis.delete("clanhop")

            await ctx.send(f"{self.bot.check} Clan hopping has been `disabled`.")

    @command(name="ignore-server", aliases=['ignoreserver'], usage="<server_id>", brief="Ignore a server ID from clan applications.")
    @commands.has_permissions(administrator=True)
    async def ignore_server(self, ctx, server_id):
        """Ignore a server ID from clan applications.

        Once a user submits a clan application with an invite, it will automatically detect the server ID.
        If the server ID is matched with any of the ignored ones in the database, it will stop the application process.
        """
        server = ctx.guild
        settings = await ctx.fetchrow("SELECT * FROM settings WHERE guild_id=$1", server.id)

        if len(server_id) < 18 or len(server_id) > 18 or int(server_id) in settings['ignored_users']:
            return await ctx.send(f"{self.bot.x} That is not a correct server ID.")
            
        ignored_servers = settings['ignored_servers']
        ignored_servers.append(int(server_id))
        await ctx.execute("UPDATE settings SET ignored_servers=$2 WHERE guild_id=$1", server.id, ignored_servers)
        await ctx.send(f"{self.bot.check} Added the server ID `{server_id}` to the ignored servers list.")
    
    @command(name="ignore-user", aliases=['ignoreuser'], usage="<user>", brief="Ignore a user ID from clan applications.")
    @commands.has_permissions(administrator=True)
    async def ignore_user(self, ctx, user_id):
        """Ignore a user ID from clan applications.

        This will block that certain user from using clan applications.
        """
        server = ctx.guild
        settings = await ctx.fetchrow("SELECT * FROM settings WHERE guild_id=$1", server.id)

        if len(user_id) < 18 or len(user_id) > 18 or int(user_id) in settings['ignored_servers']:
            return await ctx.send(f"{self.bot.x} That is not a correct user ID.")

        ignored_users = settings['ignored_users']
        ignored_users.append(int(user_id))
        await ctx.execute("UPDATE settings SET ignored_users=$2 WHERE guild_id=$1", server.id, ignored_users)
        await ctx.send(f"{self.bot.check} Added the user ID `{user_id}` to the ignored users list.")

    @command(name="unignore-server", aliases=['unignoreserver'], usage="<server_id>", brief="Unignore a server ID allowing them to apply.")
    @commands.has_permissions(administrator=True)
    async def unignore_server(self, ctx, server_id):
        """Unignore a server ID allowing that server to apply.
        """
        server = ctx.guild
        settings = await ctx.fetchrow("SELECT * FROM settings WHERE guild_id=$1", server.id)

        if len(server_id) < 18 or len(server_id) > 18 or int(server_id) not in settings['ignored_servers']:
            return await ctx.send(f"{self.bot.x} That is not a correct server ID.")
            
        ignored_servers = settings['ignored_servers']
        ignored_servers.remove(int(server_id))
        await ctx.execute("UPDATE settings SET ignored_servers=$2 WHERE guild_id=$1", server.id, ignored_servers)
        await ctx.send(f"{self.bot.check} Removed the server ID `{server_id}` from the ignored servers list.")
    
    @command(name="unignore-user", aliases=['unignoreuser'], usage="<user>", brief="Unignore a user ID, allowing them to apply.")
    @commands.has_permissions(administrator=True)
    async def unignore_user(self, ctx, user_id):
        """Unigore a user ID allowing them to apply.
        """
        server = ctx.guild
        settings = await ctx.fetchrow("SELECT * FROM settings WHERE guild_id=$1", server.id)

        if len(user_id) < 18 or len(user_id) > 18 or int(user_id) not in settings['ignored_users']:
            return await ctx.send(f"{self.bot.x} That is not a correct user ID.")

        ignored_users = settings['ignored_users']
        ignored_users.remove(int(user_id))
        await ctx.execute("UPDATE settings SET ignored_users=$2 WHERE guild_id=$1", server.id, ignored_users)
        await ctx.send(f"{self.bot.check} Removed the user ID `{user_id}` from the ignored users list.")

    @command(name="ignored", brief="See all of the ignored users and servers.")
    @commands.has_permissions(administrator=True)
    async def ignored(self, ctx):
        """See all of the ignored users and servers."""
        server = ctx.guild
        settings = await ctx.fetchrow("SELECT * FROM settings WHERE guild_id=$1", server.id)

        ignored_users = "\n".join([str(x) for x in settings['ignored_users']]) if settings['ignored_users'] else "No users have been ignored."
        ignored_servers = "\n".join([str(x) for x in settings['ignored_servers']]) if settings['ignored_servers'] else "No servers have been ignored."

        embed = discord.Embed()
        embed.set_author(name="Ignored users/servers", icon_url=server.icon_url)
        embed.add_field(name=f"Servers ({len(settings['ignored_servers'])})", value=ignored_servers, inline=False)
        embed.add_field(name=f"Users ({len(settings['ignored_users'])})", value=ignored_users)
        await ctx.send(embed=embed)
    
def setup(bot):
    bot.add_cog(Settings(bot))