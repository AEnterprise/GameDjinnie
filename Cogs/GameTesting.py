from datetime import datetime
from parser import ParserError

from dateutil.parser import parse
from discord import Forbidden, HTTPException
from discord.ext import commands
from discord.ext.commands import Cog
from tortoise.exceptions import DoesNotExist

from Utils import Configuration, Questions
from Utils.Converters import GameConverter, dateConverter
from Utils.Models import GameCode, Game, GameTest


class GameTesting(Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def add_game(self, ctx, *, name: str):
        name = name.lower().replace(" ", "_")
        try:
            await Game.get(name=name)
            await ctx.send(f"A game named {name} already exists!")
        except DoesNotExist:
            await Game.create(name=name)
            await ctx.send(f"Added {name} to the list of games!")


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
            except Exception:
                await ctx.send(
                    "Something went wrong reading that file, please make sure the file is valid and try again")
            else:
                await GameCode.filter(code__in=codes).delete()
                await ctx.send(f"Successfully deleted those codes!")

    @commands.command()
    async def test(self, ctx, game: GameConverter, until: dateConverter, *, announcement):
        channel = self.bot.get_channel(Configuration.get_var("announcement_channel"))
        role = channel.guild.get_role(Configuration.get_var("tester_role"))
        reaction = Configuration.get_var("reaction_emoji")
        await role.edit(mentionable=True)
        # wrap everything so we always make the role unmentionable in all cases
        try:
            message = await channel.send(f"{announcement}\n{role.mention}")
            await message.add_reaction(reaction)
            gt = await GameTest.create(game=game, message=message.id, end=until)
            print(gt)
        except Exception as ex:
            await role.edit(mentionable=False)
            raise ex






def setup(bot):
    bot.add_cog(GameTesting(bot))