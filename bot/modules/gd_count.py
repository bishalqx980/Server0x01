#!/usr/bin/env python3
from time import time

from pyrogram.filters import command
from pyrogram.handlers import MessageHandler

from bot import bot
from bot.helper.ext_utils.bot_utils import (get_readable_file_size,
                                            get_readable_time, is_gdrive_link,
                                            new_task, sync_to_async)
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import deleteMessage, sendMessage


@new_task
async def countNode(_, message):
    args = message.text.split()
    link = args[1] if len(args) > 1 else ''
    if len(link) == 0 and (reply_to := message.reply_to_message):
        link = reply_to.text.split(maxsplit=1)[0].strip()

    if is_gdrive_link(link):
        msg = await sendMessage(message, f"Counting: <code>{link}</code>")
        gd = GoogleDriveHelper()
        start_time = time()
        name, mime_type, size, files, folders = await sync_to_async(gd.count, link)
        elapsed = time() - start_time
        if mime_type is None:
            await sendMessage(message, name)
            return
        await deleteMessage(msg)
        msg = f'<b><i>{name}</i></b>'
        msg += f'\n\n<b>• Size: </b>{get_readable_file_size(size)}'
        msg += f'\n<b>• Type: </b>{mime_type}'
        if mime_type == 'Folder':
            msg += f'\n<b>• SubFolders: </b>{folders}'
            msg += f'\n<b>• Files: </b>{files}'
        msg += f'\n<b>• Elapsed: </b>{get_readable_time(elapsed)}'
    else:
        msg = 'Send Gdrive link along with command or by replying to the link by command'

    await sendMessage(message, msg)


bot.add_handler(MessageHandler(countNode, filters=command(
    BotCommands.CountCommand) & CustomFilters.authorized))