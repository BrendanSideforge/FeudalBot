import datetime
import asyncio

import discord
from discord.ext import commands
from discord.ext.commands import Cog, command, Context

from .utils.cooldowns import cooldown # pylint: disable=relative-beyond-top-level
from .utils import time # pylint: disable=relative-beyond-top-level

class Clan_Apps(Cog):
    def __init__(self, bot):
        self.bot = bot

    async def delete_cooldown(self, command, user):
        await self.bot.redis.delete(f"{command}:{user.id}")

    async def send_application(self, server, user, invite, name, tag, icon):
        apps = await self.bot.db.fetch("SELECT * FROM clanapps WHERE guild_id=$1", server.id)
        embed = discord.Embed(color=discord.Color.blue(), timestamp=datetime.datetime.utcnow())
        embed.set_author(name=f"Clan Application | App #{len(apps)+1:,} | Pending", icon_url=user.avatar_url)
        embed.add_field(name=":innocent: User", value=f"""
The applicant is `{user}` ({user.mention}) with an ID of `{user.id}`
        """, inline=False)
        embed.add_field(name=":newspaper: Clan Name", value=name, inline=False)
        embed.add_field(name=":scroll: Clan Tag", value=tag, inline=False)
        embed.add_field(name=":inbox_tray: Clan Invite", value=f"[`{invite.code}`]({invite}) with **{invite.approximate_member_count:,} members**.")
        embed.add_field(name=":frame_photo: Clan Icon", value=f"[`URL`]({icon})", inline=False)
        embed.set_image(url=icon)
        message = await server.get_channel(self.bot.app_logs).send(embed=embed)

        await self.bot.db.execute("""
            INSERT INTO clanapps(
                app_id,
                guild_id,
                user_id,
                clan_name,
                clan_tag,
                invite_code,
                clan_logo,
                message_id,
                applied_at,
                status
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10
            )
        """, len(apps) + 1, server.id, user.id, name, tag, invite.code, icon, message.id, datetime.datetime.utcnow(), "Pending")

    @command(name="apply", brief="Clan applications for the server, Feudal. You will recieve a DM asking questions.")
    @cooldown(1, 604800)
    async def apply(self, ctx: Context):
        """Clan applications for the server, Feudal. You will recieve a DM asking questions.

        Make sure to answer these questions correctly.
        You also have to have DMs enabled.
        """

        server = ctx.guild
        user = ctx.author

        open_applications = await ctx.fetch("SELECT * FROM clanapps WHERE guild_id=$1 AND user_id=$2 AND status=$3", server.id, user.id, "Pending")
        settings = await ctx.fetchrow("SELECT * FROM settings WHERe guild_id=$1", server.id)
        ignored_users = settings['ignored_users']
        ignored_servers = settings['ignored_servers']

        if user.id in ignored_users:
            return await ctx.send(f"{self.bot.x} Unfortunately, your ID has been blocked from using this command.")

        if len(open_applications) >= 1:
            application = open_applications[0]
            
            name = application['clan_name']
            app_id = application['app_id']

            await ctx.send(f"{self.bot.x} {user.mention}, you have a clan application that is pending. The application ID is `{app_id}` with the name of `{name}`.")
            return

        try:
            await user.send(f":wave: Hey there! I will be asking you questions about your clan application, take as long as you need.")
            await ctx.send(f":email: I have sent you a dm!")
        except discord.Forbidden:
            await ctx.send(f"{self.bot.x} {user.mention}, your DMs seem to be closed, please allow FeudalBot access to your DMs.")
            await self.delete_cooldown(ctx.command.name, user)
            return

        def dm_check(m):
            return m.author == ctx.author and type(m.channel) == discord.DMChannel

        def attach_check(m):
            if not m.attachments:
                return False
            elif not m.attachments[0].width:
                return False
            else:
                return m.author == ctx.author and type(m.channel) == discord.DMChannel

        try:
            # Clan invite
            await user.send(f"{self.bot.check} What is your clan invite? (Must have at least 25 members in your server)")
            inv = await self.bot.wait_for('message', check=dm_check, timeout=60.0)
            try:
                invite = await self.bot.fetch_invite(inv.content.strip())
                if invite.guild.id in ignored_servers:
                    return await user.send(f"{self.bot.x} Unfortunately, this server ID has been blocked from applying.")
            except discord.Forbidden:
                await user.send(f"{self.bot.x} I am banned from this guild, please redo this application.")
                await self.delete_cooldown(ctx.command.name, user)
                return
            except discord.NotFound:
                await user.send(f"{self.bot.x} That is not a correct invite, please redos this application.")
                await self.delete_cooldown(ctx.command.name, user)
                return
            except discord.HTTPException:
                await user.send(f"{self.bot.x} That is not a correct invite, please redos this application.")
                await self.delete_cooldown(ctx.command.name, user)
                return

            if invite.approximate_member_count < 25:
                mems = invite.approximate_member_count
                await user.send(f"{self.bot.x} You need at least 25 members in your server to register a clan, you need {25-mems} more members!")
                await self.delete_cooldown(ctx.command.name, user)
                return

            # clan name
            await user.send(f"{self.bot.check} What is your clan name? (Must be 25 characters or less)")
            name = await self.bot.wait_for('message', check=dm_check, timeout=60.0)
            if len(name.content) > 25:
                return await user.send(f"{self.bot.x} Your clan name can only be 25 characters or less, please redo this application.")
            
            # clan tag
            await user.send(f"{self.bot.check} What is your clan tag? (Must be 7 characters or less)")
            tag = await self.bot.wait_for('message', check=dm_check, timeout=60.0)
            if len(tag.content) > 7:
                return await user.send(f"{self.bot.x} Your clan tage can only be 7 characters or less, please redo this application.") 

            # clan icon
            await user.send(f"{self.bot.check} What is your clan icon? (Must be in a file format, not a link)")
            logo = await self.bot.wait_for('message', check=attach_check)
            if not logo:
                return await user.send(f"{self.bot.x} That is not an image, please redo this application.")

            # preview embed
            apps = await ctx.fetch("SELECT * FROM clanapps WHERE guild_id=$1", server.id)
            embed = discord.Embed(color=discord.Color.blue(), timestamp=datetime.datetime.utcnow())
            embed.set_author(name=f"Clan Application | App #{len(apps)+1:,} | Pending", icon_url=user.avatar_url)
            embed.add_field(name=":innocent: User", value=f"""
The applicant is `{user}` ({user.mention}) with an ID of `{user.id}`
            """, inline=False)
            embed.add_field(name=":newspaper: Clan Name", value=name.content, inline=False)
            embed.add_field(name=":scroll: Clan Tag", value=tag.content, inline=False)
            embed.add_field(name=":inbox_tray: Clan Invite", value=f"[`{invite.code}`]({invite}) with **{invite.approximate_member_count:,} members**.")
            embed.add_field(name=":frame_photo: Clan Icon", value=f"[`URL`]({logo.attachments[0].proxy_url})", inline=False)
            embed.set_image(url=logo.attachments[0].proxy_url.replace(".jpeg", ".png").replace(".wepb", ".png").replace(".jpg", "png"))
            await user.send(embed=embed)
            await user.send(f"{self.bot.cooldown} Are you ready to send the clan application? Respond with `y` or `n`.")
            confirm = await self.bot.wait_for('message', check=dm_check, timeout=60.0)
            if confirm.content.lower() == "y" or confirm.content.lower() == "yes":
                await self.send_application(server, user, invite, name.content, tag.content, logo.attachments[0].proxy_url)
                await user.send(f"{self.bot.check} Sent the clan application! Please be patient as this review process can take up to a few days.")
            elif confirm.content.lower() == "n" or confirm.content.lower() == "no":
                await user.send(f"{self.bot.check} Clan application process has been aborted.")
            else:
                await user.send(f"{self.bot.x} I could not understand that response, clan application process aborted.")

        except asyncio.TimeoutError:
            return await user.send(f"{self.bot.x} You took too long to respond.")

    @apply.error
    async def test_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            secs = error.retry_after

            dt_object = datetime.datetime.fromtimestamp(datetime.datetime.utcnow().timestamp() + secs)
            tm_str = time.human_timedelta(dt_object, brief=True)

            await ctx.send(f"{self.bot.cooldown} You are on cooldown! Try again in `{tm_str}`")

    @command(name="accept", usage="<clan_app> [note]", brief="Accept a clan application, you can leave a note if you want.")
    @commands.has_permissions(administrator=True)
    async def accept(self, ctx: Context, app_id: int, *, note: str = None):
        """Accept a clan application, you can leave a note if you want."""
        server = ctx.guild
        app = await ctx.fetchrow("SELECT * FROM clanapps WHERE guild_id=$1 AND app_id=$2", server.id, app_id)
        
        if not app:
            return await ctx.send(f"{self.bot.x} I could not find a clan app with the ID of `{app_id}`.")
        
        await ctx.execute("UPDATE clanapps SET status=$3 WHERE guild_id=$1 AND app_id=$2", server.id, app_id, "Accepted")
        
        channel = server.get_channel(self.bot.app_logs)
        try:
            message = await channel.fetch_message(app['message_id'])
            found = True
        except:
            found = False

        if found:

            embed = message.embeds[0]
            embed.set_author(name=f"Clan Application | App #{app['app_id']:,} | Accepted", icon_url=embed.author.icon_url)
            embed.color = discord.Color.green()
            embed.add_field(name=":label: Note", value=note if note is not None else "No note was added to this application.")
            
            await message.edit(embed=embed)
        
        await ctx.send(f"{self.bot.check} I have changed that application's status to `accepted`!")
        
        user = server.get_member(app['user_id'])

        if not user:
            await ctx.send(f"{self.bot.x} {ctx.author.mention}, `{user}` is not in the server anymore.")
        else:
            top_header = server.get_role(self.bot.clan_header)
            clan_owner = server.get_role(self.bot.clan_owner)
            clan_role = await server.create_role(name=app['clan_tag'], color=discord.Color(self.bot.default_clan_color))
            await clan_role.edit(position=top_header.position-1)

            try:
                await user.add_roles(clan_role, reason=f"Application accepted for the clan, {app['clan_name']}.")
                await user.add_roles(clan_owner, reason=f"Application accepted for the clan, {app['clan_name']}.")
                await user.edit(nickname=f"[{app['clan_tag']}/Owner] {user.name}")
            except discord.Forbidden:
                return await ctx.send(f"{self.bot.x} I am requiring the manage_roles permission to do my duty.")
            note = f'\n:label: **Note:** {note}' if note is not None else ''
            await user.send(f":tada: Your clan, `{app['clan_name']}`, has been accepted in Feudal! {note}")
        

    @command(name="reject", usage="<app_id> [reason]", brief="Reject a clan application, with a reason.")
    @commands.has_permissions(administrator=True)
    async def reject(self, ctx: Context, app_id: int, *, reason: str = None):
        """Reject a clan application, with a reason."""

        server = ctx.guild
        app = await ctx.fetchrow("SELECT * FROM clanapps WHERE guild_id=$1 AND app_id=$2", server.id, app_id)
        
        if not app:
            return await ctx.send(f"{self.bot.x} I could not find a clan app with the ID of `{app_id}`.")
        
        await ctx.execute("UPDATE clanapps SET status=$3 WHERE guild_id=$1 AND app_id=$2", server.id, app_id, "Rejected")

        channel = server.get_channel(self.bot.app_logs)
        try:
            message = await channel.fetch_message(app['message_id'])
            found = True
        except:
            found = False

        if found:

            embed = message.embeds[0]
            embed.set_author(name=f"Clan Application | App #{app['app_id']:,} | Rejected", icon_url=embed.author.icon_url)
            embed.color = discord.Color.red()
            embed.add_field(name=":label: Rejection Reason", value=reason if reason is not None else "No reason was added to this rejection.")
            
            await message.edit(embed=embed)

        await ctx.send(f"{self.bot.check} I have changed that application's status to `rejected`!")
        
        user = server.get_member(app['user_id'])
        if not user:
            await ctx.send(f"{self.bot.x} {ctx.author.mention}, I have failed to contact `{user}` about this.")
        else:
            note = f'\n:label: **Reason:** {reason}' if reason is not None else ''
            await user.send(f":thumbsdown: Your clan, `{app['clan_name']}`, has been rejected in Feudal.{note}")

    @command(name='stats', usage="<clan>", brief="View the statistics for a certain clan.")
    async def stats(self, ctx: Context, *, clan: str):
        """View the statistics for a certain clan."""
        server = ctx.guild
        clan = [
            role for role in server.roles 
            if role.position <= server.get_role(self.bot.clan_header).position
            and role.position >= server.get_role(self.bot.clan_bottom_header).position
            and role is not server.get_role(self.bot.clan_bottom_header)
            and role is not server.get_role(self.bot.clan_header)
            and role.name.lower() == clan.lower()
        ]
        
        if len(clan) == 0:
            return await ctx.send(f"{self.bot.x} I could not find that clan.")
        
        role = server.get_role(clan[0].id)
        delta = datetime.datetime.utcnow() - role.created_at
        week = delta.total_seconds() / 604800

        total_members = len(role.members)
        reps = len([member for member in role.members if member._roles.has(self.bot.clan_rep)])
        members = len([member for member in role.members if member._roles.has(self.bot.clan_member)])

        await ctx.send(
            f"The clan role, `{role.name}`, has `{total_members} members`."
            f"On average, this clan gets around `{total_members/week:.2f} clan members` weekly."
            f"There are `{reps} reps` and `{members} clan members`."
        )

def setup(bot):
    bot.add_cog(Clan_Apps(bot))