import datetime
import asyncio
import json
import traceback

import discord
from discord.ext import commands
from discord.ext.commands import Cog, command, CooldownMapping, BucketType
from fuzzywuzzy import process
import functools

from .utils.cooldowns import cooldown # pylint: disable=relative-beyond-top-level
from .utils import time # pylint: disable=relative-beyond-top-level
from .utils import arg # pylint: disable=relative-beyond-top-level

class SupportChat(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mem_update = CooldownMapping.from_cooldown(1, 1, BucketType.member)

    def split_nickname(self, user):
        nickname = user.nick
        if "]" in nickname:
            _, nickname = nickname.split("]")
        else:
            nickname = user.display_name
        return nickname

    async def wait_for_response(self, ctx, user, owner_rep, clan):
        server = ctx.guild

        # get the clan owner
        try:
            owner = [member for member in clan.members if member._roles.has(self.bot.clan_owner)][0]
        except IndexError:
            return await ctx.send(f"{self.bot.x} For some odd reason, there isn't a clan owner for this clan.")

        # format a confirmation message
        if owner_rep.lower() == "owner":
            message = f":wave: Hey there! {user.mention} is requesting to become the owner of your clan, `{clan.name}`.\nPlease respond with a `y` or `n`, you have 24 hours to reply."
        else:
            message = f":wave: Hey there! {user.mention} is requesting to become a clan rep for your clan, `{clan.name}`.\nPlease respond with a `y` or `n`, you have 24 hours to reply."

        def dm_check(m):
            return m.author.id == owner.id and type(m.channel) == discord.DMChannel

        action = owner_rep.lower()

        offline = discord.Status.offline
        if owner.status != offline:
            try:
                clanless = server.get_role(self.bot.clanless)
                clan_member = server.get_role(self.bot.clan_member)
                clan_owner = server.get_role(self.bot.clan_owner)
                clan_rep = server.get_role(self.bot.clan_rep)

                await owner.send(message)
                await ctx.send(f"{self.bot.check} Just sent the clan owner, `{owner.display_name}`, a confirmation message.")

                confirmation = await self.bot.wait_for('message', check=dm_check, timeout=86400.0)
                if confirmation.content.lower() == "y" or confirmation.content.lower() == "yes":
                    await owner.send(f"{self.bot.check} Sweet! I will notify the user right away and get to business.")
                    nickname = self.split_nickname(user)
                    if action == "rep":
                        await user.remove_roles(clanless, clan_member, clan_owner)
                        await user.add_roles(clan_rep, clan)
                        try:
                            await user.edit(nick=f"[{clan.name}/Rep] {nickname}")
                        except:
                            await user.edit(nick=f"[{clan.name}/Rep] Support Chat")
                        await user.send(f":wave: Hey! The clan owner of the clan, `{clan.name}`, has accepted your rep request.")
                    else:
                        await user.remove_roles(clanless, clan_member, clan_rep)
                        await user.add_roles(clan_owner, clan)
                        try:
                            await user.edit(nick=f"[{clan.name}/Owner] {nickname}")
                        except:
                            await user.edit(nick=f"[{clan.name}/Owner] Support Chat")
                        await user.send(f":wave: Hey! The clan owner of the clan, `{clan.name}`, has accepted your owner request.")
                elif confirmation.content.lower() == "n" or confirmation.content.lower() == "no":
                    await owner.send(f"{self.bot.check} Aborted this process.")
            except discord.Forbidden:
                return await ctx.send(f"{self.bot.x} Unfortuantely, this user has either blocked me or has disabled their DMs.")
            except asyncio.TimeoutError:
                return await owner.send(f"{self.bot.cooldown} You took too long to reply!")

        else:
            # oh no the user is offline rip, lets add that to the redis cache xd
            await ctx.send(f"{self.bot.check} When the clan owner comes online, I will send them a confirmation message.")
            data = json.dumps({
                "clan": clan.id,
                "action": owner_rep,
                "user": user.id,
                "message": message
            })
            await self.bot.redis.setnx(f"offline:{server.id}:{owner.id}", data)

    @Cog.listener(name="on_member_update")
    async def member_update(self, before, after):
        # limit discord from sending 3 events at once
        # they're an asshole for that
        obj = discord.Object(1)
        obj.author = after
        obj.guild = after.guild
        discord_bug_cooldown = self.mem_update.update_rate_limit(obj)
        if discord_bug_cooldown is not None and discord_bug_cooldown != 0:
            return

        server = after.guild
        key = await self.bot.redis.get(f"offline:{server.id}:{after.id}")
        offline = discord.Status.offline
        if before.status == offline and before.status != after.status and key is not None:
            data = json.loads(key)
            user = server.get_member(data['user'])
            clan = server.get_role(data['clan'])
            message = data['message']
            action = data['action']
            await self.bot.redis.delete(f"offline:{server.id}:{after.id}")

            def dm_check(m):
                return m.author.id == after.id and type(m.channel) == discord.DMChannel

            try:
                await after.send(message)
                confirmation = await self.bot.wait_for('message', check=dm_check, timeout=86400.0)
                nickname = self.split_nickname(user)
                if confirmation.content.lower() == "y" or confirmation.content.lower() == "yes":

                    await after.send(f"{self.bot.check} Sweet! I will notify the user right away and get to business.")
                    clanless = server.get_role(self.bot.clanless)
                    clan_member = server.get_role(self.bot.clan_member)
                    clan_owner = server.get_role(self.bot.clan_owner)
                    clan_rep = server.get_role(self.bot.clan_rep)
                    if action == "rep":
                        await user.remove_roles(clanless, clan_member, clan_owner)
                        await user.add_roles(clan_rep, clan)
                        try:
                            await user.edit(nick=f"[{clan.name}/Rep] {nickname}")
                        except:
                            await user.edit(nick=f"[{clan.name}/Rep] Support Chat")
                        await user.send(f":wave: Hey! The clan owner of the clan, `{clan.name}`, has accepted your rep request.")
                    else:
                        await user.remove_roles(clanless, clan_member, clan_rep)
                        await user.add_roles(clan_owner, clan)
                        try:
                            await user.edit(nick=f"[{clan.name}/Owner] {nickname}")
                        except:
                            await user.edit(nick=f"[{clan.name}/Owner] Support Chat")
                        await user.send(f":wave: Hey! The clan owner of the clan, `{clan.name}`, has accepted your owner request.")

                elif confirmation.content.lower() == "n" or confirmation.content.lower() == "no":
                    await after.send(f"{self.bot.check} Aborted this process.")
            except Exception as e:
                print(e)

    @command(name="iam", usage="<words here>", brief="Add a clan to yourself.")
    @cooldown(3, 10)
    async def iam(self, ctx, *, query = None):
        """Add a clan to yourself.

        You must include member, rep, or owner arguments.

        If you are trying to become a rep, the bot will automatically
        send a request to the clan owner so that you can become
        a rep."""

        # await ctx.message.delete()

        if not query:
            return

        server = ctx.guild
        user = ctx.author

        settings = await ctx.fetchrow("SELECT * FROM settings WHERE guild_id=$1", server.id)
        mapped_clans = settings['mapped_clans']
        clanhop_key = await self.bot.redis.get("clanhop")
        clanhop_ttl = await self.bot.redis.ttl("clanhop")
        getter = functools.partial(discord.utils.get, user.roles)
        if clanhop_key is None or clanhop_ttl < 0:
            clanhop = False
        else:
            clanhop = True

        clan_owner = server.get_role(self.bot.clan_owner)
        clan_rep = server.get_role(self.bot.clan_rep)
        clan_member = server.get_role(self.bot.clan_member)
        clanless = server.get_role(self.bot.clanless)
        top_header = server.get_role(self.bot.clan_header) 
        bottom_header = server.get_role(self.bot.clan_bottom_header)

        if 'rep' in query.lower() or 'owner' in query.lower():
            # failed = 0
            action = 'rep' if 'rep' in query.lower() else 'owner'
            try:
                for word in query.split(" "):
                    clan_def = [
                        role for role in server.roles
                        if role.position < top_header.position
                        and role.position > bottom_header.position
                        and role.name.lower() == word.lower()
                    ]
                    if not clan_def:
                        if word.lower() == "rep" or word.lower() == "owner":
                            continue
                        else:
                            continue

                    clan = server.get_role(clan_def[0].id)
                    if (
                        clan.permissions.administrator is True
                        or clan.permissions.ban_members is True
                        or clan.permissions.kick_members is True
                        or clan.permissions.manage_channels is True
                        or clan.permissions.manage_roles is True
                        or clan.permissions.mention_everyone is True
                    ):
                        return await ctx.send(f"{self.bot.x} The role, `{clan.name}`, has dangerous permissions.")
                    if not clanhop and any(getter(name=item) is not None for item in mapped_clans):
                        return await ctx.send(f"{self.bot.x} You cannot switch to the clan, `{clan.name}`, because your current clan is on the map.")
                    elif not clanhop and clan.name in mapped_clans:
                        return await ctx.send(f"{self.bot.x} You cannot switch to the clan, `{clan.name}`, because that clan is currently on the map.")
                    else:
                        await self.wait_for_response(ctx, user, action, clan)
            except Exception as e:
                exc = ''.join(traceback.format_exception(type(e), e, e.__traceback__, chain=False))
                await ctx.send(f"```py\n{exc}```")
                return

        elif (
            'clanless' in query.lower() 
            or 'clan less' in query.lower()
            or 'clan-less' in query.lower()
        ):
            if not clanhop and any(getter(name=item) is not None for item in mapped_clans):
                return await ctx.send(f"{self.bot.x} You cannot become clanless because your current clan is on the map.")
            
            confirmation = await ctx.prompt(f":octagonal_sign: Are you sure you want to become clanless?")
            if confirmation:
                # remove all the clans from the user
                user_clans = [
                    role for role in user.roles 
                    if role.position < top_header.position
                    and role.position > bottom_header.position
                ]
                user_clans.extend([clan_member, clan_rep, clan_owner])
                await user.remove_roles(*user_clans)
                await user.add_roles(clanless)

                # when a nickname gets too long it returns a status code of 
                # HTTPException, so we just catch that error
                nickname = self.split_nickname(user)
                try:
                    await user.edit(nick=f"[Clanless] {nickname}")
                except discord.HTTPException:
                    await user.edit(nick=f"[Clanless] Support Chat")

                await ctx.send(f"{self.bot.check} Done!")

        else:
            try:
                clan_def = [
                    role for role in server.roles
                    if role.position < top_header.position
                    and role.position > bottom_header.position
                    and role.name.lower() in query.lower().split(' ')
                ]
                if not clan_def:
                    support_chat = server.get_channel(self.bot.support_chat)
                    embed = discord.Embed(timestamp=datetime.datetime.utcnow())
                    embed.description = f"**{ctx.author.mention} is requesting:** {query}"
                    await support_chat.send(embed=embed)
                    await ctx.send(f"{self.bot.check} I have sent a support chat request.")
                    return

                clan = clan_def[0]
                # see if this role has dangerous permissions
                if (
                    clan.permissions.administrator is True
                    or clan.permissions.ban_members is True
                    or clan.permissions.kick_members is True
                    or clan.permissions.manage_channels is True
                    or clan.permissions.manage_roles is True
                    or clan.permissions.mention_everyone is True
                ):
                    return await ctx.send(f"{self.bot.x} The role, `{clan.name}`, has dangerous permissions.")

                if not clanhop and any(getter(name=item) is not None for item in mapped_clans):
                    return await ctx.send(f"{self.bot.x} You cannot join the clan, `{clan.name}`, because your current clan is on the map.")
                elif not clanhop and clan.name in mapped_clans:
                    return await ctx.send(f"{self.bot.x} You cannot join the clan, `{clan.name}`, because that clan is on the map.")
                else:
                    user_clans = [
                        role for role in user.roles 
                        if role.position < top_header.position
                        and role.position > bottom_header.position
                    ]
                    user_clans.extend([clanless, clan_rep, clan_owner])
                    await user.remove_roles(*user_clans)
                    await user.add_roles(clan_member, clan)
                    nickname = self.split_nickname(user)
                    try:
                        await user.edit(nick=f"[{clan.name}/Member] {nickname}")
                    except discord.HTTPException:
                        await user.edit(nick=f"[{clan.name}/Member] Support Chat")

                    await ctx.send(f"{self.bot.check} I have added you to the clan, `{clan.name}`, as a clan member.")

            except Exception as e:
                exc = ''.join(traceback.format_exception(type(e), e, e.__traceback__, chain=False))
                await ctx.send(f"```py\n{exc}```")
                return

    @command(name="ask", usage="<words here>", brief="Request something that the moderators can do.")
    @cooldown(3, 10)
    async def ask(self, ctx, *, query = None):
        """Request something that the moderators can do."""
        if not query:
            return

        server = ctx.guild

        await ctx.message.delete()

        if not query:
            return
        
        support_chat = server.get_channel(self.bot.support_chat)
        embed = discord.Embed(timestamp=datetime.datetime.utcnow())
        embed.description = f"**{ctx.author.mention} is asking:** {query}"
        await support_chat.send(embed=embed)
        await ctx.send(f"{self.bot.check} I have sent a support chat request.")
        return

    @iam.error
    async def iam_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            secs = error.retry_after

            dt_object = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp() + secs)
            tm_str = time.human_timedelta(dt_object, brief=True)

            await ctx.send(f"{self.bot.cooldown} You are on cooldown! Try again in `{tm_str}`")

    @ask.error
    async def ask_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            secs = error.retry_after

            dt_object = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp() + secs)
            tm_str = time.human_timedelta(dt_object, brief=True)

            await ctx.send(f"{self.bot.cooldown} You are on cooldown! Try again in `{tm_str}`")

def setup(bot):
    bot.add_cog(SupportChat(bot))
