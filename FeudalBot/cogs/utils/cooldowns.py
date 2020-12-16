import datetime

import discord
from discord.ext import commands

def cooldown(rate: int, per: int):
    async def predicate(ctx):
        if not isinstance(ctx.channel, discord.abc.GuildChannel):
            return commands.NoPrivateMessage()

        user = ctx.author

        members = await ctx.bot.redis.smembers(f"{ctx.command.name}:{user.id}")
        ttl = await ctx.bot.redis.ttl(f"{ctx.command.name}:{user.id}")

        if members is None or ttl < 0:
            await ctx.bot.redis.sadd(f"{ctx.command.name}:{user.id}", datetime.datetime.utcnow().timestamp())
            await ctx.bot.redis.expire(f"{ctx.command.name}:{user.id}", per)
            return True

        await ctx.bot.redis.sadd(f"{ctx.command.name}:{user.id}", datetime.datetime.utcnow().timestamp())

        if len(members) > rate and ttl > 0:
            raise commands.CommandOnCooldown(rate, ttl)
        
    return commands.check(predicate)

