import asyncio
import inspect
import re
from collections import namedtuple
from discord import Embed, Reaction
from Utils import Emoji, Utils, Configuration

Option = namedtuple("Option", "emoji text handler args", defaults=(None, None, None, None))


def timeout_format(total_seconds: int) -> str:
    seconds = total_seconds % 60
    minutes = int((total_seconds - seconds) / 60)
    output = []
    if minutes:
        output.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
    if seconds:
        output.append(f"{seconds} second{'s' if seconds > 1 else ''}")
    return ", ".join(output)


async def ask(bot, channel, author, text, options, timeout=60, show_embed=False, delete_after=False):
    embed = Embed(color=0x68a910,
                  description='\n'.join(f"{Emoji.get_chat_emoji(option.emoji)} {option.text}" for option in options))
    message = await channel.send(text, embed=embed if show_embed else None)
    handlers = dict()
    for option in options:
        emoji = Emoji.get_emoji(option.emoji)
        await message.add_reaction(emoji)
        handlers[str(emoji)] = {'handler': option.handler, 'args': option.args}

    def check(reaction: Reaction, user):
        return user == author and str(reaction.emoji) in handlers.keys() and reaction.message.id == message.id

    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=timeout, check=check)
    except asyncio.TimeoutError as ex:
        if delete_after:
            await message.delete()
        await channel.send(f'{Emoji.get_emoji("WARNING")} Waited too long for a response, aborting',
                           delete_after=10 if delete_after else None)
        raise ex
    else:
        if delete_after:
            await message.delete()
        h = handlers[str(reaction.emoji)]['handler']
        a = handlers[str(reaction.emoji)]['args']
        if h is None:
            return
        if inspect.iscoroutinefunction(h):
            await h(*a) if a is not None else await h()
        else:
            h(*a) if a is not None else h()


async def ask_text(
        bot,
        channel,
        user,
        text,
        validator=None,
        timeout=300,
        confirm=False,
        escape=True):
    def check(message):
        return user == message.author and message.channel == channel

    ask_again = True

    def confirmed():
        nonlocal ask_again
        ask_again = False

    while ask_again:
        await channel.send(text)
        try:
            while True:
                message = await bot.wait_for('message', timeout=timeout, check=check)
                if message.content is None or message.content == "":
                    result = "Please enter some text for the message"
                else:
                    result = await validator(message.content) if validator is not None else True
                if result is True:
                    break
                else:
                    await channel.send(result)
        except asyncio.TimeoutError as ex:
            await channel.send(
                f'{Emoji.get_emoji("WARNING")} Waited too long for a response, aborting'
            )
            raise ex
        else:
            content = Utils.escape_markdown(message.content) if escape else message.content
            if confirm:
                backticks = "``" if len(message.content.splitlines()) is 1 else "```"
                message = f"Are you sure {backticks}{message.content}{backticks} is correct?"
                await ask(bot, channel, user, message, [
                    Option("YES", handler=confirmed),
                    Option("NO")
                ])
            else:
                confirmed()

    return content


async def ask_attachement(bot, channel, user, text, timeout=3000):
    def check(message):
        return user == message.author and message.channel == channel

    ask_again = True

    def confirmed():
        nonlocal ask_again
        ask_again = False

    while ask_again:
        await channel.send(text)
        try:
            while True:
                message = await bot.wait_for('message', timeout=timeout, check=check)
                if len(message.attachments) is not 1:
                    await channel.send("Please provide a single attachment containing all the game codes")
                else:
                    break
        except asyncio.TimeoutError as ex:
            await channel.send(
                f'{Emoji.get_emoji("WARNING")} Waited too long for a response, aborting'
            )
            raise ex
        else:
            return message.attachments[0]

