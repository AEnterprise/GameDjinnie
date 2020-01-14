from datetime import datetime

from discord.ext import commands
from discord.ext.commands import BadArgument
from gspread import SpreadsheetNotFound
from tortoise.exceptions import DoesNotExist

from parser import ParserError

from dateutil.parser import parse
from tortoise.query_utils import Q

from Utils import SheetUtils
from Utils.Models import Game, GameTest


class GameConverter(commands.Converter):
    async def convert(self, ctx, arg):
        try:
            return await Game.get(Q(name=arg, id=int(arg) if arg.isnumeric() else 0, join_type="OR"))
        except DoesNotExist:
            raise BadArgument("Unknown game")


def dateConverter(arg) -> datetime:
    try:
        date = parse(arg.strip('"'))
    except ParserError:
        raise BadArgument("Unable to parse that date, suggested format: '<year>/<month>/<day> <hour>:<minutes>'")
    else:
        if date.toordinal() < datetime.now().toordinal():
            raise BadArgument("Dates can not be in the past!")
        return date


class TestConverter(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            return await GameTest.get(Q(id=argument, message=int(argument) if argument.isnumeric() else 0, join_type="OR"))
        except DoesNotExist:
            raise BadArgument("Unknown test")


class Sheetconverter(commands.Converter):
    async def convert(self, ctx, argument):
        # make sure it wasn't used already
        if await GameTest.get_or_none(feedback=argument) is not None:
            raise BadArgument("This sheet was already used for a previous test!")
        try:
            SheetUtils.get_sheet(argument)
        except SpreadsheetNotFound:
            raise BadArgument("Invalid link, please make sure it is shared with the bot email")
        else:
            return argument
