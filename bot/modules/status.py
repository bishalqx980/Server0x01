#!/usr/bin/env python3
from time import time

from psutil import cpu_percent, disk_usage, virtual_memory, net_io_counters
from pyrogram.filters import command, regex
from pyrogram.handlers import CallbackQueryHandler, MessageHandler

from bot import (Interval, bot, botStartTime, config_dict, download_dict, DOWNLOAD_DIR,
                 download_dict_lock, status_reply_dict_lock)
from bot.helper.ext_utils.bot_utils import (getAllDownload,
                                            get_readable_file_size,
                                            get_readable_time,
                                            MirrorStatus, new_task,
                                            setInterval, turn_page)
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import (auto_delete_message,
                                                      deleteMessage, isAdmin,
                                                      request_limiter,
                                                      sendMessage,
                                                      sendStatusMessage,
                                                      update_all_messages)


@new_task
async def mirror_status(_, message):
    async with download_dict_lock:
        count = len(download_dict)
    if count == 0:
        currentTime = get_readable_time(time() - botStartTime)
        free = get_readable_file_size(disk_usage(config_dict['DOWNLOAD_DIR']).free)
        msg = '<b><u>@Server0x01 - BOT IDLE</u></b>\n\n'
        msg += '<b>↺ NO ACTIVE TASK </b>\n\n'
        msg += f"<code>CPU    :</code> <b>{cpu_percent()}%</b>\n"\
               f"<code>FREE   :</code> <b>{free}</b>\n" \
               f"<code>RAM    :</code> <b>{virtual_memory().percent}%</b>\n" \
               f"<code>UPTIME :</code> <b>{currentTime}</b>"
        reply_message = await sendMessage(message, msg)
        await auto_delete_message(message, reply_message)
    else:
        await sendStatusMessage(message)
        await deleteMessage(message)
        async with status_reply_dict_lock:
            if Interval:
                Interval[0].cancel()
                Interval.clear()
                Interval.append(setInterval(config_dict['STATUS_UPDATE_INTERVAL'], update_all_messages))


@new_task
async def status_pages(_, query):
    user_id = query.from_user.id
    spam = not await isAdmin(query.message, user_id) and await request_limiter(query=query)
    if spam:
        return
    if not await isAdmin(query.message, user_id) and user_id and not await getAllDownload('all', user_id):
        await query.answer("You don't have any active tasks", show_alert=True)
        return
    data = query.data.split()
    action = data[1]
    if action == "stats":
        bstats = bot_sys_stats()
        await query.answer(bstats, show_alert=True)
    else:
        await turn_page(data)
        await update_all_messages(True)


def bot_sys_stats():
    cpup = cpu_percent(interval=0.1)
    ramp = virtual_memory().percent
    disk = disk_usage(config_dict["DOWNLOAD_DIR"]).percent
    totl = len(download_dict)
    traf = get_readable_file_size(net_io_counters().bytes_sent + net_io_counters().bytes_recv)
    free = max(config_dict['QUEUE_ALL'] - totl, 0) if config_dict['QUEUE_ALL'] else '∞'
    inqu, dwld, upld, splt, arch, extr, seed = [0] * 7
    for download in download_dict.values():
        status = download.status()
        if status in MirrorStatus.STATUS_QUEUEDL or status in MirrorStatus.STATUS_QUEUEUP:
            inqu += 1
        elif status == MirrorStatus.STATUS_DOWNLOADING:
            dwld += 1
        elif status == MirrorStatus.STATUS_UPLOADING:
            upld += 1
        elif status == MirrorStatus.STATUS_SPLITTING:
            splt += 1
        elif status == MirrorStatus.STATUS_ARCHIVING:
            arch += 1
        elif status == MirrorStatus.STATUS_EXTRACTING:
            extr += 1
        elif status == MirrorStatus.STATUS_SEEDING:
            seed += 1
    bmsg = f'⚡ @Server0x01 BOT INFO ⚡\n\n'
    bmsg += f'CPU: {cpup}% | RAM: {ramp}% | DISK: {disk}%\n\n'
    bmsg += f'Total: {totl} | Free: {free} | Queued: {inqu}\n'
    bmsg += f'Download: {dwld} | Upload: {upld} | Seeding: {seed}\n'
    bmsg += f'Zip: {arch} | Unzip: {extr} | Split: {splt}\n\n'
    bmsg += f'Bandwidth Used: {traf}'
    return bmsg


bot.add_handler(MessageHandler(mirror_status, filters=command(BotCommands.StatusCommand) & CustomFilters.authorized))
bot.add_handler(CallbackQueryHandler(status_pages, filters=regex("^status")))
