import datetime

import discord
from discord.ext import commands
import aioredis
import asyncpg
import yaml
import tensorflow as tf

from cogs.utils.context import Context # pylint: disable=bad-option-value

# Load the FeudalBot configurations such as the bot TOKEN, CLIENT_ID, CLIENT_SECRET, etc
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

async def prefix(bot, message):
    
    if not message.guild:
        return

    server = message.guild
    settings = await bot.db.fetchrow("SELECT * FROM settings WHERE guild_id=$1", server.id)

    if not settings:
        await bot.db.execute("""
            insert into settings (
                guild_id,
                prefix,
                mapped_clans,
                ignored_users,
                ignored_servers
            ) values (
                $1, $2, $3, $4, $5
            )
        """, server.id, ".", [], [], [])
        prefix = "."
    else:
        prefix = settings['prefix']
    return prefix

class Feudal_Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=prefix, case_insensitive=True)

        # Init the bot emojis
        self.check = ":white_check_mark:"
        self.x = ":x:"
        self.cooldown = ":stopwatch:"

        self.unloaded_cogs = [
            "cogs.developer",
            "cogs.settings",
            "cogs.clan_apps",
            "cogs.support_chat",
            "cogs.cc"
        ]

        self.redis = None
        self.db = None

        self.app_logs = 722976081812127797
        self.default_clan_color = 0xbeeed5
        self.clan_header = 427136480906051585
        self.clan_owner = 416334933649260544
        self.clan_bottom_header = 428297234820497426
        self.clan_rep = 428568031204081666
        self.clan_member = 416334972857876480
        self.clanless = 416335327633080322
        self.support_chat = 450448803745628161

        self.model = tf.keras.models.load_model("image_classifier.model")

    async def on_ready(self):
        self.uptime = datetime.datetime.utcnow()

        print(f"{self.user} has logged onto Discord with the ID of {self.user.id}")

    async def get_context(self, message, cls=None):
        # get_context uses the "process_commands" function
        # which sees if a message starts with a certain command
        # so we should just make it return if the message doesn't belong to a guild
        # this just prevents annoying errors
        if not message.guild:
            return

        return await super().get_context(message, cls=cls)
    
    async def process_commands(self, message):
        ctx = await self.get_context(message, cls=Context)

        # if the ctx var returns none return
        # if there isn't a command attribute return
        if not ctx or ctx.command is None:
            return

        # this just runs the command
        await self.invoke(ctx)

    async def _load_cogs(self):
        for cog in self.unloaded_cogs:
            try:
                self.load_extension(cog)
                print(f"Loaded the cog: {cog}")
            except Exception as e:
                print(f"Failed to load the cog {cog} with the error: {e}")

    async def _create_redis_session(self):
        
        # pylint: disable=no-member
        self.redis = await aioredis.create_redis_pool(
            address=(config['redis']['host'], config['redis']['port'])
        )
        print("Redis connection has been established.")
    
    async def _create_postgres_session(self):
        self.db = await asyncpg.create_pool(
            host=config['postgres']['host'],
            port=config['postgres']['port'],
            database=config['postgres']['database'],
            user=config['postgres']['user'],
            password=config['postgres']['password']
        )
        print("PostgreSQL connection has been established.")
        await self.db.execute("""
            create table if not exists settings (
                guild_id bigint primary key,
                prefix varchar(20),
                mapped_clans text[],
                ignored_users bigint[],
                ignored_servers bigint[]
            )
        """)

        await self.db.execute("""
            create table if not exists clanapps (
                app_id smallint,
                guild_id bigint,
                user_id bigint,
                clan_name varchar(25),
                clan_tag varchar(7),
                invite_code text,
                clan_logo text,
                message_id bigint,
                applied_at timestamp,
                status text
            )
        """)

        await self.db.execute("""
            create table if not exists custom_commands (
                cc_id serial,
                guild_id bigint,
                user_id bigint,
                cc_name varchar(20),
                cc_code text,
                created_at timestamp,
                uses integer,
                executed smallint[]
            )
        """)
    
    async def login(self, *args, **kwargs):

        await self._load_cogs()
        await self._create_redis_session()
        await self._create_postgres_session()

        await super().login(*args, **kwargs)

bot = Feudal_Bot()

# this module allows you to use bot utils
# refer to readme.md to see how to install it
bot.load_extension("jishaku")

bot.run(config['token'])