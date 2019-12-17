from datetime import datetime

from discord.ext import commands
from discord.ext.commands import BadArgument
from tortoise.exceptions import DoesNotExist

from parser import ParserError

from dateutil.parser import parse

from Utils.Models import Game


class GameConverter(commands.Converter):
    async def convert(self, ctx, arg):
        try:
            return await Game.get(name=arg)
        except DoesNotExist:
            raise BadArgument("Unknown game")


def dateConverter(arg) -> datetime:
    try:
        date = parse(arg)
    except ParserError:
        raise BadArgument("Unable to parse that date, suggested format: '<day>/<month>/<year> <hour>:<minutes>'")
    else:
        if date.toordinal() < datetime.now().toordinal():
            raise BadArgument("Dates can not be in the past!")
        return date
