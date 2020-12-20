from discord.ext import commands
from discord.ext.commands import Bot
from tortoise import Tortoise

from Utils import Logging, Configuration, Utils, Emoji
from Utils.Models import NewGameTest, GameTest


class GameJinnie(Bot):
    loaded = False

    async def on_ready(self):
        if not self.loaded:
            Logging.BOT_LOG_CHANNEL = self.get_channel(Configuration.get_var("log_channel"))
            Emoji.initialize(self)

            Logging.info("Connected to discord!")

            Logging.info("Establishing database connections")
            await Tortoise.init(
                db_url="sqlite://db.sqlite3",
                modules={"models": ["Utils.Models"]}
            )
            await Tortoise.generate_schemas()
            Logging.info("Database connected")
            if await NewGameTest.filter().first() is None:
                to_insert = list()
                for test in await GameTest.all().prefetch_related("game"):
                    to_insert.append(NewGameTest(game=test.game, message=test.message, end=test.end, status=test.status, feedback=test.feedback))
                await NewGameTest.bulk_create(to_insert)
            Logging.info("Loading cogs")
            for cog in ["GameTesting"]:
                try:
                    self.load_extension("Cogs." + cog)
                except Exception as e:
                    await Utils.handle_exception(f"Failed to load cog {cog}", self, e)
            Logging.info("Cogs loaded")

            await Logging.bot_log("GameDjinnie ready to go!")
            self.loaded = True

    async def on_command_error(bot, ctx: commands.Context, error):
        if isinstance(error, commands.BotMissingPermissions):
            await ctx.send(error)
        elif isinstance(error, commands.CheckFailure):
            pass
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(error)
        elif isinstance(error, commands.MissingRequiredArgument):
            param = list(ctx.command.params.values())[min(len(ctx.args) + len(ctx.kwargs), len(ctx.command.params))]
            bot.help_command.context = ctx
            await ctx.send(
                f"{Emoji.get_chat_emoji('NO')} You are missing a required command argument: `{param._name}`\n{Emoji.get_chat_emoji('WRENCH')} Command usage: `{bot.help_command.get_command_signature(ctx.command)}`")
        elif isinstance(error, commands.BadArgument):
            param = list(ctx.command.params.values())[min(len(ctx.args) + len(ctx.kwargs), len(ctx.command.params))]
            bot.help_command.context = ctx
            await ctx.send(
                f"{Emoji.get_chat_emoji('NO')} Failed to parse the ``{param._name}`` param: ``{error}``\n{Emoji.get_chat_emoji('WRENCH')} Command usage: `{bot.help_command.get_command_signature(ctx.command)}`")
        elif isinstance(error, commands.CommandNotFound):
            return

        else:
            await Utils.handle_exception("Command execution failed", bot,
                                         error.original if hasattr(error, "original") else error, ctx=ctx)
            # notify caller
            e = Emoji.get_chat_emoji('BUG')
            if ctx.channel.permissions_for(ctx.me).send_messages:
                await ctx.send(f"{e} Something went wrong while executing that command {e}")


if __name__ == '__main__':
    Logging.init()
    Configuration.load()
    Logging.info("Did someone summon the GameDjinnie?")

    bot = GameJinnie(command_prefix=Configuration.get_var("prefix"), case_insensitive=True)
    bot.run(Configuration.get_var("token"))

    Logging.info("GameDjinnie shutdown")
