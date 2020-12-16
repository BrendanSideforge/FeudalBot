import contextlib
import inspect
import pprint
import re
import textwrap
from io import StringIO, BytesIO
import os
import psutil
import datetime
import asyncio
import traceback

import discord
from discord.ext import commands
from discord.ext.commands import command, Cog

from detection import AI
from .utils import time # pylint: disable=relative-beyond-top-level

class Developer(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.env = {}
        self.ln = 0
        self.stdout = StringIO()

    def _format(self, inp, out):  # (str, Any) -> (str, discord.Embed)
        self._ = out

        res = ""

        # Erase temp input we made
        if inp.startswith("_ = "):
            inp = inp[4:]

        # Get all non-empty lines
        lines = [line for line in inp.split("\n") if line.strip()]
        if len(lines) != 1:
            lines += [""]

        # Create the input dialog
        for i, line in enumerate(lines):
            if i == 0:
                # Start dialog
                start = f"In [{self.ln}]: "

            else:
                # Indent the 3 dots correctly;
                # Normally, it's something like
                # In [X]:
                #    ...:
                #
                # But if it's
                # In [XX]:
                #    ...:
                #
                # You can see it doesn't look right.
                # This code simply indents the dots
                # far enough to align them.
                # we first `str()` the line number
                # then we get the length
                # and use `str.rjust()`
                # to indent it.
                start = "...: ".rjust(len(str(self.ln)) + 7)

            if i == len(lines) - 2:
                if line.startswith("return"):
                    line = line[6:].strip()

            # Combine everything
            res += (start + line + "\n")

        self.stdout.seek(0)
        text = self.stdout.read()
        self.stdout.close()
        self.stdout = StringIO()

        if text:
            res += (text + "\n")

        if out is None:
            # No output, return the input statement
            return (res, None)

        res += f"Out[{self.ln}]: "

        if isinstance(out, discord.Embed):
            # We made an embed? Send that as embed
            res += "<Embed>"
            res = (res, out)

        else:
            if (isinstance(out, str) and out.startswith("Traceback (most recent call last):\n")):
                # Leave out the traceback message
                out = "\n" + "\n".join(out.split("\n")[1:])

            if isinstance(out, str):
                pretty = out
            else:
                pretty = pprint.pformat(out, compact=True, width=60)

            if pretty != str(out):
                # We're using the pretty version, start on the next line
                res += "\n"

            if pretty.count("\n") > 20:
                # Text too long, shorten
                li = pretty.split("\n")

                pretty = ("\n".join(li[:3])  # First 3 lines
                          + "\n ...\n"  # Ellipsis to indicate removed lines
                          + "\n".join(li[-3:]))  # last 3 lines

            # Add the output
            res += pretty
            res = (res, None)

        return res  # Return (text, embed)

    async def _eval(self, ctx, code):  # (discord.Context, str) -> None

        self.ln += 1

        if code.startswith("exit"):
            self.ln = 0
            self.env = {}
            return await ctx.send("```Reset history!```")

        env = {
            "message": ctx.message,
            "author": ctx.message.author,
            "channel": ctx.channel,
            "server": ctx.guild,
            "ctx": ctx,
            "self": self,
            "bot": self.bot,
            "inspect": inspect,
            "discord": discord,
            "contextlib": contextlib,
            "datetime": datetime.datetime,
            "timedelta": datetime.timedelta
        }

        self.env.update(env)

        # Ignore this code, it works
        _code = """
async def func():  # (None,) -> Any
    try:
        with contextlib.redirect_stdout(self.stdout):
{0}
        if '_' in locals():
            if inspect.isawaitable(_):
                _ = await _
            return _
    finally:
        self.env.update(locals())
""".format(textwrap.indent(code, '            '))

        try:
            exec(_code, self.env)  # noqa: B102,S102
            func = self.env['func']
            res = await func()

        except Exception:
            res = traceback.format_exc()

        out, embed = self._format(code, res) # pylint: disable=unused-variable
        await ctx.send(f"```py\n{out}```")

    @commands.command(aliases=['e'])
    @commands.is_owner()
    async def eval(self, ctx, *, code: str):
        """ Run eval in a REPL-like format. """
        code = code.strip("`")
        if re.match('py(thon)?\n', code):
            code = "\n".join(code.split("\n")[1:])

        if not re.search(  # Check if it's an expression
                r"^(return|import|for|while|def|class|"
                r"from|exit|[a-zA-Z0-9]+\s*=)", code, re.M) and len(
                    code.split("\n")) == 1:
            code = "_ = " + code

        await self._eval(ctx, code)

    @command(name="reload", aliases=['r'], hidden=True)
    @commands.is_owner()
    async def reload(self, ctx, cog: str = None):

        cog_formatter = ""
        if cog is None:

            for cog in self.bot.unloaded_cogs:
                try:
                    self.bot.reload_extension(cog)
                    cog_formatter += f":repeat: `{cog}`\n\n"
                except Exception as e:
                    exc = ''.join(traceback.format_exception(type(e), e, e.__traceback__, chain=False))
                    cog_formatter += f":repeat: :warning: `{cog}`\n```py\n{exc}\n```\n\n"

        else:

            try:
                self.bot.reload_extension(cog)
                cog_formatter += f":repeat: `{cog}`\n\n"
            except Exception as e:
                exc = ''.join(traceback.format_exception(type(e), e, e.__traceback__, chain=False))
                cog_formatter += f":repeat: :warning: `{cog}`\n```py\n{exc}\n```\n\n" 

        await ctx.send(cog_formatter)

    @command(name="logout", hidden=True)
    @commands.is_owner()
    async def logout(self, ctx):

        # this is a custom function defined in the cogs/utils/context.py file
        confirm = await ctx.prompt(f":octagonal_sign: Hold up! Are you sure you want to logout?")
        if confirm is False:
            await ctx.send(f":call_me: Restart aborted...")
        else:
            await ctx.send(":outbox_tray: Logging out now...")

    # @command(name="info", hidden=True)
    # @commands.is_owner()
    # async def info(self, ctx, directory):

    #     line_count = 0
    #     comments = 0
    #     functions = []
    #     classes = []
    #     variables = []

    #     with open(directory, 'r') as f:

    #         for line in f:
    #             line = line.strip()

    #             line_count += 1

    #             if len(line) == 0:
    #                 continue

    #             if line[0] == "#":
    #                 comments += 1

    #             # variables
    #             elif "=" in line and "==" not in line:
    #                 variables = line.split("=")
    #                 variable_name = variables[0].strip()
    #                 variables.append(f"`{variable_name}`")

    #             # functions
    #             elif "async def" in line or "def" in line:
    #                 function_fm = line.replace("async def", "").replace("def", "").strip()
    #                 function_name = function_fm.split("(")[0::][0]
    #                 function_params = function_fm.replace(function_name, "").replace("(", "").replace(")", "").replace(":", "").split(",")[0::]
    #                 functions.append(f"`{function_name}`: {', '.join(function_params)}")

    #             # classes
    #             elif "class " in line:
    #                 class_fm = line.replace("class", "").strip()
    #                 class_name = class_fm.split("(")[0::][0]
    #                 class_params = class_fm.replace(class_name, "").replace("(", "").replace(")", "").replace(":", "").split()[0::]
    #                 classes.append(f"`{class_name}:` {', '.join(class_params)}")


    #     embed = discord.Embed()
    #     embed.set_author(name=f"Info on the file: {directory}")
    #     embed.description = f"This file consists of **{line_count:,} lines** of code and **{comments:,}** comments."
    #     embed.add_field(name=f":comet: Functions ({len(functions)})", value="\n".join(functions) if functions else "No functions.", inline=False)
    #     embed.add_field(name=f":asterisk: Classes ({len(classes)})", value="\n".join(classes) if classes else "No classes.", inline=False)
    #     embed.add_field(name=f":watermelon: Variables ({len(variables)})", value="\n".join(variables) if variables else "No variables.", inline=False)
    #     await ctx.send(embed=embed)

    def get_bot_uptime(self, *, brief=False):
        return time.human_timedelta(self.bot.uptime, accuracy=None, brief=brief, suffix=False)

    @command()
    @commands.is_owner()
    async def classify(self, ctx):

        if not ctx.message.attachments:
            return await ctx.send("send attachment")

        old_time = datetime.datetime.utcnow()
        old_msg = await ctx.send(f"{self.bot.cooldown} Working on it..")
        await ctx.message.attachments[0].save(fp=f"downloaded/{ctx.message.id}.png")

        AI_Class = AI(self.bot.model)
        prediction = AI_Class.predict(f"downloaded/{ctx.message.id}.png")
        await old_msg.edit(content=f"{self.bot.check} I have classified this image as a: **{prediction}**! (*Executed in: `{time.human_timedelta(old_time, accuracy=None, brief=True, suffix=False)}`*)")

        os.remove(f"downloaded/{ctx.message.id}.png")

def setup(bot):
    bot.add_cog(Developer(bot))