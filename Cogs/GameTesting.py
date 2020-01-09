import asyncio
import csv
from collections import Counter
from datetime import datetime, timedelta
from io import StringIO

import discord
from discord import Forbidden, RawReactionActionEvent, Object, Embed
from discord.ext import commands, tasks
from discord.ext.commands import Cog
from tortoise.exceptions import DoesNotExist
from tortoise.transactions import atomic

import humanize

from Utils import Configuration, Logging, SheetUtils
from Utils.Converters import GameConverter, dateConverter, TestConverter, Sheetconverter
from Utils.Models import GameCode, Game, GameTest, TestStatus, Completion
from Utils.Utils import with_role_ping


class GameTesting(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scheduler_loop.start()

    async def cog_check(self, ctx):
        return ctx.author.id == Configuration.get_var("admin_id")

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

    @commands.command()
    @with_role_ping()
    async def test(self, ctx, game: GameConverter, until: dateConverter, sheet_url: Sheetconverter, *, announcement):
        channel = self.bot.get_channel(Configuration.get_var("announcement_channel"))
        role = channel.guild.get_role(Configuration.get_var("tester_role"))
        reaction = Configuration.get_var("reaction_emoji")
        message = await channel.send(f"{announcement}\n{role.mention}")
        await message.add_reaction(reaction)
        gt = await GameTest.create(game=game, message=message.id, end=until, feedback=sheet_url)
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
                    updated = await GameCode.filter(code=code.code, claimed_by=None, claimed_in=test).update(
                        claimed_by=payload.user_id)
                    # make sure we updated that row
                    if updated is 1:

                        try:
                            await user.send(f"Your code for {test.game} is {code}!")
                        except Forbidden:
                            # failed to send, free up the code again
                            await GameCode.filter(code=code.code).update(clamied_by=None)

                        # code claimed, make sure we have more codes left
                        available = await GameCode.filter(game=test.game, claimed_by=None, claimed_in=None).count()
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

    @commands.command()
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
        for t in await GameTest.filter(status=TestStatus.STARTED, end__lt=datetime.now() + timedelta(days=1)):
            self.bot.loop.create_task(self.delayer((t.end - datetime.now()).total_seconds(), self.reminder(t)))

        # schedule ending of the tests
        for t in await GameTest.filter(status__not=TestStatus.STARTED, end__lt=datetime.now() + timedelta(hours=1)):
            self.bot.loop.create_task(self.delayer((t.end - datetime.now()).total_seconds(), self.ender(t)))

    async def delayer(self, delay, todo):
        await asyncio.sleep(delay)
        await todo

    @with_role_ping()
    async def reminder(self, test):
        channel = self.bot.get_channel(Configuration.get_var("announcement_channel"))
        await channel.send(
            f"<@&{Configuration.get_var('tester_role')}> Only 24 hours remaining before this test ends. Please make sure to get your feedback before then if you have not already! https://canary.discordapp.com/channels/{channel.guild.id}/{channel.id}/{test.message}")
        test.status = TestStatus.ENDING
        await test.save()

    @atomic()
    async def ender(self, test):
        # edit message to say this test is completed
        channel = self.bot.get_channel(Configuration.get_var("announcement_channel"))
        message = await channel.fetch_message(test.message)
        await message.edit(content=f"~~{message.content}~~\n**This test has ended**")
        # mark as completed in the database
        test.status = TestStatus.ENDED
        await test.save()
        # find all users who filled in the feedback
        sheet = SheetUtils.get_sheet(test.feedback)
        user_ids = sheet.col_values(2)[1:]
        await Completion.bulk_create([Completion(test=test, user=u) for u in user_ids])
        await self._test_report(self.bot.get_user(Configuration.get_var("admin_id")), test)

    @commands.command()
    async def test_report(self, ctx, test: TestConverter):
        await self._test_report(ctx, test)

    async def _test_report(self, channel, test):
        await test.fetch_related("completions")
        # sort by amount submitted
        counts = {k: v for k, v in
                  sorted(Counter([c.user for c in test.completions]).items(), key=lambda item: item[1])}

        # fetch their keys
        keys = dict()
        for code in await GameCode.filter(claimed_in=test):
            keys[code.claimed_by] = code.code

        # report codes and feedback counts for all users
        buffer = StringIO()
        writer = csv.writer(buffer, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["User id", "username", "Code", "Submitted feedback x times"])

        for user_id, key in keys.items():
            writer.writerow([f"\t{user_id}", str(self.bot.get_user(user_id)), key, counts.get(user_id, 0)])

        buffer.seek(0)
        file = discord.File(buffer, "Test report.csv")
        await channel.send(file=file)

    @commands.command()
    async def game_codes(self, ctx, game: GameConverter):
        # fetch used codes
        codes = await GameCode.filter(game=game).prefetch_related("claimed_in")
        # create buffer, don't bother saving to disk
        buffer = StringIO()
        writer = csv.writer(buffer, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        # write codes to the writer
        writer.writerow(["Code", "claimed by", "claimed by username", "claimed in test"])
        for c in codes:
            writer.writerow(
                [c.code, f"\t{c.claimed_by}", str(self.bot.get_user(c.claimed_by)) if c.claimed_by is not None else "",
                 (str(c.claimed_in.id) if c.claimed_in is not None else "")])
        buffer.seek(0)
        file = discord.File(buffer, f"codes for {game.name}.csv")
        await ctx.send(file=file)

    @commands.command()
    async def inactive_report(self, ctx, count: int = 3):
        await self._report(ctx, count)

    async def _report(self, channel, count):
        announcement_channel = self.bot.get_channel(Configuration.get_var("announcement_channel"))
        # everyone who filled in feedback for the last 3 tests
        feedback_providers = set(
            c.user for test in await GameTest.filter().order_by("-end").limit(count).prefetch_related("completions") for
            c in test.completions)
        # all testers
        testers = set(
            m.id for m in announcement_channel.guild.get_role(Configuration.get_var("tester_role")).members)
        # report those who didn't contribute
        slackers = testers - feedback_providers

        buffer = StringIO()
        writer = csv.writer(buffer, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["User id", "Username"])
        # write codes to the writer
        for s in slackers:
            writer.writerow([f"\t{s}", str(self.bot.get_user(s))])
        buffer.seek(0)
        file = discord.File(buffer, f"did not participate in last {count} tests.csv")
        await channel.send(file=file)


def setup(bot):
    bot.add_cog(GameTesting(bot))
