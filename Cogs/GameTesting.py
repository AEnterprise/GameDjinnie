from datetime import datetime
from parser import ParserError

from dateutil.parser import parse
from discord import Forbidden, HTTPException
from discord.ext import commands
from discord.ext.commands import Cog
from tortoise.exceptions import DoesNotExist

from Utils import Configuration, Questions
from Utils.Models import GameCode, GameTest, TestStatus


class GameTesting(Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def start_test(self, ctx):
        member = self.bot.get_guild(Configuration.get_var("guild_id")).get_member(ctx.author.id)
        if member is None:
            return
        role_id = Configuration.get_var("dev_role")
        if not member.roles or not any(r.id == role_id for r in member.roles):
            return

        try:
            m = await ctx.author.send("Starting a new game test!")

            async def date_checker(d):
                try:
                    parsed = parse(d)
                except ParserError as ex:
                    return f"Unable to parse that as a valid end datetime. Please try something like <day>/<month>/<year> <hour>:<minutes> ?"
                if datetime.now().toordinal() > parsed.toordinal():
                    "End times can not be in the past"

                return True

            until = await Questions.ask_text(self.bot, ctx.author.dm_channel, ctx.author,
                                             "Until when should this test run? Please provide a timestamp", validator=date_checker)

            until = parse(until)


            async def reaction_checker(v):
                try:
                    await m.add_reaction(v)
                except HTTPException:
                    return "Not a valid reaction"
                return True



            reaction = await Questions.ask_text(self.bot, ctx.author.dm_channel, ctx.author, "Please send the emoji to use as reaction for testers", validator=reaction_checker)

            announcement = await Questions.ask_text(self.bot, ctx.author.dm_channel, ctx.author, "What text should be used as announcement?",)
            codes = []
            while len(codes) is 0:
                attachment = await Questions.ask_attachement(self.bot, ctx.author.dm_channel, ctx.author, "Please upload the game codes in a txt file, 1 code per line")
                try:
                    codes = (await attachment.read()).decode().splitlines()
                except Exception:
                    await ctx.author.send("Something went wrong reading that file, please make sure the file is valid and try again")

                for code in codes.copy():
                    if len(code) > 50:
                        codes.remove(code)
                    try:
                        await GameCode.get(code=code)
                        codes.remove(code)
                    except DoesNotExist:
                        pass # code is good
                if len(codes) is 0:
                    await ctx.author.send("No valid codes found in that file, please try again")


            await ctx.author.send("Processing...")

            message = await self.bot.get_channel(Configuration.get_var("announcement_channel")).send(announcement)
            await message.add_reaction(reaction)

            game_test = await GameTest.create(announcement=message.id, reaction=reaction, ends_at=until)
            for code in codes:
                await GameCode.create(game_test=game_test,code=code)


        except Forbidden:
            await ctx.send("🚫 Unable to DM you, please allow DMs from this server and try again. You can close them again after")



def setup(bot):
    bot.add_cog(GameTesting(bot))