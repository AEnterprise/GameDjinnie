import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler

LOGGER = logging.getLogger('gamedjinnie')
DISCORD_LOGGER = logging.getLogger('discord')
BOT_LOG_CHANNEL = None


def init():
    LOGGER.setLevel(logging.DEBUG)

    DISCORD_LOGGER.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(logging.INFO)
    handler.setFormatter(formatter)
    LOGGER.addHandler(handler)
    DISCORD_LOGGER.addHandler(handler)

    if not os.path.isdir("logs"):
        os.mkdir("logs")
    handler = TimedRotatingFileHandler(filename='logs/GameDjinnie.log', encoding='utf-8', when="midnight",
                                       backupCount=30)
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    DISCORD_LOGGER.addHandler(handler)
    LOGGER.addHandler(handler)


async def bot_log(message=None, embed=None):
    return await BOT_LOG_CHANNEL.send(content=message, embed=embed)


def debug(message):
    LOGGER.debug(message)


def info(message):
    LOGGER.info(message)


def warn(message):
    LOGGER.warning(message)


def error(message):
    LOGGER.error(message)
