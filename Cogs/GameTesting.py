import asyncio
import csv
from datetime import datetime, timedelta
from io import BytesIO, StringIO
from parser import ParserError

import discord
from dateutil.parser import parse
from discord import Forbidden, HTTPException, RawReactionActionEvent, Object, Embed
from discord.ext import commands, tasks
from discord.ext.commands import Cog
from tortoise.exceptions import DoesNotExist
from tortoise.query_utils import Q
from tortoise.transactions import atomic

import humanize

from Utils import Configuration, Questions, Logging
from Utils.Converters import GameConverter, dateConverter, TestConverter
from Utils.Models import GameCode, Game, GameTest, TestStatus
from Utils.Utils import with_role_ping


class GameTesting(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scheduler_loop.start()

    @commands.command()
    async def add_game(self, ctx, *, name: str):
        name = name.lower().replace(" ", "_")
        try:
            await Game.get(name=name)
        except DoesNotExist:
            await Game.create(name=name)
            await ctx.send(f"Added {name} to the list of games!")
        else:
            await ctx.send(f"A game named {name} already exists!")

    @commands.command()
    async def add_codes(self, ctx, game: GameConverter):
        if len(ctx.message.attachments) is not 1:
            await ctx.send("Please send the txt file with codes with the command")
        else:
            try:
                codes = (await ctx.message.attachments[0].read()).decode().splitlines()
            except Exception:
                await ctx.send(
                    "Something went wrong reading that file, please make sure the file is valid and try again")
            else:
                for c in await GameCode.filter(code__in=codes):
                    codes.remove(c.code)
                await GameCode.bulk_create([GameCode(code=c, game=game) for c in codes])
                await ctx.send(f"Successfully imported {len(codes)} codes for {game}!")

    @commands.command()
    async def remove_codes(self, ctx):
        if len(ctx.message.attachments) is not 1:
            await ctx.send("Please send the txt file with codes with the command")
        else:
            try:
                codes = (await ctx.message.attachments[0].read()).decode().splitlines()
            except Exception as ex:
                await ctx.send(
                    "Something went wrong reading that file, please make sure the file is valid and try again")
                Logging.error(ex)
            else:
                await GameCode.filter(code__in=codes).delete()
                await ctx.send(f"Successfully deleted those codes!")

    @with_role_ping
    @commands.command()
    async def test(self, ctx, game: GameConverter, until: dateConverter, *, announcement):
        channel = self.bot.get_channel(Configuration.get_var("announcement_channel"))
        role = channel.guild.get_role(Configuration.get_var("tester_role"))
        reaction = Configuration.get_var("reaction_emoji")
        message = await channel.send(f"{announcement}\n{role.mention}")
        await message.add_reaction(reaction)
        gt = await GameTest.create(game=game, message=message.id, end=until)
        await ctx.send(f"Test running until {humanize.naturaldate(gt.end)} has started!")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        # ignore the bot itself
        if payload.user_id == self.bot.user.id:
            return
        await self.give_code(payload)

    @atomic()
    async def give_code(self, payload):
        user = self.bot.get_user(payload.user_id)

        async def message_user(message):
            try:
                await user.send(message)
            except Forbidden:
                # user has DMs closed, remove their reaction to indicate this
                message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
                await message.remove_reaction(payload.emoji, Object(payload.user_id))

        try:
            test = await GameTest.get(message=payload.message_id)
        except DoesNotExist:
            return  # not an announcement, nothing to do
        else:
            if test.status == TestStatus.ENDED:
                try:
                    await user.send("This test has already ended")
                except Forbidden:
                    pass
                message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
                await message.remove_reaction(payload.emoji, Object(payload.user_id))
                return
            try:
                await test.fetch_related("game")
                exising_code = await GameCode.get(game=test.game, claimed_by=payload.user_id)
            except DoesNotExist:
                # doesn't have a code, fetch one for claiming
                code = await GameCode.filter(game=test.game, claimed_by=None).first()
                if code is None:
                    # no more codes are available!
                    await message_user(
                        f"Sadly there are no more codes available for {test.game} at this time. Please try again later")
                else:
                    # try to claim that code but make sure we don't override races
                    updated = await GameCode.filter(code=code.code, claimed_by=None).update(claimed_by=payload.user_id)
                    # make sure we updated that row
                    if updated is 1:

                        try:
                            await user.send(f"Your code for {test.game} is {code}!")
                        except Forbidden:
                            # failed to send, free up the code again
                            await GameCode.filter(code=code.code).update(clamied_by=None)

                        # code claimed, make sure we have more codes left
                        available = await GameCode.filter(game=test.game, claimed_by=None).count()
                        if available is 0:
                            # this was the last one, inform admin
                            admin = self.bot.get_user(Configuration.get_var('admin_id'))
                            try:
                                await admin.send(f"Someone just claimed the last available code for {test.game}!")
                            except Forbidden:
                                # admin has DMs closed, fall back to botlog
                                await Logging.bot_log(
                                    f"{admin.mention} Someone just claimed the last available code for {test.game}!")

                    else:
                        # we didn't claim, probably someone else won the race, try again
                        await self.give_code(payload)
            else:
                # user already has a code, send it to them again
                user = self.bot.get_user(payload.user_id)
                await message_user(
                    f"You already claimed a code for {test.game} before: {exising_code}. If this code didn't work please contact <@{Configuration.get_var('admin_id')}>")

    @commands.command()
    async def running(self, ctx):
        channel = self.bot.get_channel(Configuration.get_var("announcement_channel"))
        active_tests = await GameTest.filter(status__not=TestStatus.ENDED).order_by("-end").limit(20).prefetch_related(
            "game")
        embed = Embed(description="\n".join(
            f"[{test.id} - {test.game.name}: ending in {humanize.naturaltime(datetime.now() - test.end)}](https://canary.discordapp.com/channels/{channel.guild.id}/{channel.id}/{test.message})"
            for test in active_tests))
        await ctx.send(embed=embed)

    @commands.command()
    async def update(self, ctx, test: TestConverter, *, new_content):
        channel = self.bot.get_channel(Configuration.get_var("announcement_channel"))
        message = await channel.fetch_message(test.message)
        # edit message to new content + role ping
        await message.edit(content=f"{new_content}\n<@&{Configuration.get_var('tester_role')}>")
        await ctx.send("Message updated!")

    async def update_end_time(self, ctx, test: TestConverter, *, new_time: dateConverter):
        # set new end time
        test.end = new_time
        await test.save()
        # run the scheduler so we pick up on the date being lowered
        await self.scheduler()

    @tasks.loop(minutes=10)
    async def scheduler_loop(self):
        await self.scheduler()

    async def scheduler(self):
        # schedule 24 notices
        for t in await GameTest.filter(status=TestStatus.STARTED, end__lt=datetime.now() + timedelta(days=1),
                                       end__gt=datetime.now()):
            self.bot.loop.create_task(self.delayer((t.end - datetime.now()).total_seconds(), self.reminder(t)))

        # schedule ending of the tests
        for t in await GameTest.filter(status__not=TestStatus.STARTED, end__lt=datetime.now() + timedelta(hours=1)):
            self.bot.loop.create_task(self.delayer((t.end - datetime.now()).total_seconds(), self.ender(t)))

    async def delayer(self, delay, todo):
        await asyncio.sleep(delay)
        await todo

    @with_role_ping
    async def reminder(self, test):
        channel = self.bot.get_channel(Configuration.get_var("announcement_channel"))
        await channel.send(
            f"<@&{Configuration.get_var('tester_role')}> Only 24 hours remaining before this test ends. Please make sure to get your feedback before then if you have not already! https://canary.discordapp.com/channels/{channel.guild.id}/{channel.id}/{test.message}")
        test.status = TestStatus.ENDING
        await test.save()

    async def ender(self, test):
        test.status = TestStatus.ENDED
        await test.save()

    @commands.command()
    async def used_codes(self, ctx, game: GameConverter):
        # fetch used codes
        codes = await GameCode.filter(game=game, claimed_by__not_isnull=True).prefetch_related("game")
        # create buffer, don't bother saving to disk
        buffer = StringIO()
        writer = csv.writer(buffer, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        # write codes to the writer
        for c in codes:
            writer.writerow([c.code, c.claimed_by, c.game.name])
        buffer.seek(0)
        file = discord.File(buffer, "Used codes.csv")
        await ctx.send(file=file)


def setup(bot):
    bot.add_cog(GameTesting(bot))
