#!/usr/bin/env python3
from datetime import datetime as dt
from asyncio import create_subprocess_exec, gather
from os import execl as osexecl
from signal import SIGINT, signal
from sys import executable
from time import time, monotonic
from uuid import uuid4
from httpx import AsyncClient as xclient

from aiofiles import open as aiopen
from aiofiles.os import path as aiopath
from aiofiles.os import remove as aioremove
from psutil import (boot_time, cpu_count, cpu_percent, cpu_freq, disk_usage,
                    net_io_counters, swap_memory, virtual_memory)
from pyrogram.filters import command, regex
from pyrogram.handlers import CallbackQueryHandler, MessageHandler

from bot import (DATABASE_URL, INCOMPLETE_TASK_NOTIFIER, LOGGER,
                 STOP_DUPLICATE_TASKS, Interval, QbInterval, bot, botStartTime,
                 config_dict, scheduler, user_data)
from bot.helper.listeners.aria2_listener import start_aria2_listener

from .helper.ext_utils.bot_utils import (cmd_exec, get_readable_file_size,
                                         get_readable_time, new_thread, set_commands,
                                         sync_to_async, get_progress_bar_string)
from .helper.ext_utils.db_handler import DbManager
from .helper.ext_utils.fs_utils import clean_all, exit_clean_up, start_cleanup
from .helper.telegram_helper.button_build import ButtonMaker
from .helper.telegram_helper.bot_commands import BotCommands
from .helper.telegram_helper.filters import CustomFilters
from .helper.telegram_helper.message_utils import (editMessage, sendFile,
                                                   sendMessage, auto_delete_message)
from .modules import (anonymous, authorize, bot_settings, cancel_mirror,
                      category_select, clone, eval, gd_count, gd_delete,
                      gd_search, leech_del, mirror_leech, rmdb, rss,
                      shell, status, torrent_search,
                      torrent_select, users_settings, ytdlp)


async def stats(_, message, edit_mode=False):
    buttons = ButtonMaker()
    sysTime     = get_readable_time(time() - boot_time())
    botTime     = get_readable_time(time() - botStartTime)
    remaining_time = 86400 - (time() - botStartTime)
    res_time = '⚠️ Soon ⚠️' if remaining_time <= 0 else get_readable_time(remaining_time)
    total, used, free, disk = disk_usage('/')
    total       = get_readable_file_size(total)
    used        = get_readable_file_size(used)
    free        = get_readable_file_size(free)
    sent        = get_readable_file_size(net_io_counters().bytes_sent)
    recv        = get_readable_file_size(net_io_counters().bytes_recv)
    tb          = get_readable_file_size(net_io_counters().bytes_sent + net_io_counters().bytes_recv)
    cpuUsage    = cpu_percent(interval=0.1)
    v_core      = cpu_count(logical=True) - cpu_count(logical=False)
    memory      = virtual_memory()
    mem_p       = memory.percent
    swap        = swap_memory()

    bot_stats = f'<b>🔰 <u>SYSTEM STATISTICS</u></b>\n\n'\
                f'<code>CPU  :</code> <b>{get_progress_bar_string(cpuUsage)} {cpuUsage}%</b>\n' \
                f'<code>RAM  :</code> <b>{get_progress_bar_string(mem_p)} {mem_p}%</b>\n' \
                f'<code>SWAP :</code> <b>{get_progress_bar_string(swap.percent)} {swap.percent}%</b>\n' \
                f'<code>DISK :</code> <b>{get_progress_bar_string(disk)} {disk}%</b>\n\n' \
                f'<code>Bot Uptime  :</code> <b>{botTime}</b>\n' \
                f'<code>BOT Restart :</code> <b>{res_time}</b>\n\n' \
                f'<code>Uploaded    :</code> <b>{sent}</b>\n' \
                f'<code>Downloaded  :</code> <b>{recv}</b>\n' \
                f'<code>T-Bandwidth :</code> <b>{tb}</b>'

    sys_stats = f'<b>🔰 <u>SYSTEM STATISTICS</u></b>\n\n'\
                f'<code>Sys Uptime :</code> <b>{sysTime}</b>\n' \
                f'<code>CPU        :</code> <b>{get_progress_bar_string(cpuUsage)} {cpuUsage}%</b>\n' \
                f'<code>T-Core(s)  :</code> <b>{cpu_count(logical=True)}</b>\n' \
                f'<code>P-Core(s)  :</code> <b>{cpu_count(logical=False)}</b>\n' \
                f'<code>V-Core(s)  :</code> <b>{v_core}</b>\n' \
                f'<code>Frequency  :</code> <b>{cpu_freq(percpu=False).current / 1000:.2f} GHz</b>\n\n' \
                f'<code>RAM   :</code> <b>{get_progress_bar_string(mem_p)} {mem_p}%</b>\n' \
                f'<code>Total :</code> <b>{get_readable_file_size(memory.total)}</b>\n' \
                f'<code>Free  :</code> <b>{get_readable_file_size(memory.available)}</b>\n\n' \
                f'<code>SWAP  :</code> <b>{get_progress_bar_string(swap.percent)} {swap.percent}%</b>\n' \
                f'<code>Total :</code> <b>{get_readable_file_size(swap.total)}</b>\n' \
                f'<code>Free  :</code> <b>{get_readable_file_size(swap.free)}</b>\n\n' \
                f'<code>DISK  :</code> <b>{get_progress_bar_string(disk)} {disk}%</b>\n' \
                f'<code>Total :</code> <b>{total}</b>\n' \
                f'<code>Free  :</code> <b>{free}</b>'

    buttons.ibutton("Sys Stats",  "show_sys_stats")
    buttons.ibutton("Repo Stats", "show_repo_stats")
    buttons.ibutton("Bot Limits", "show_bot_limits")
    buttons.ibutton("Close", "close_signal")
    sbtns = buttons.build_menu(2)
    if not edit_mode:
        await message.reply(bot_stats, reply_markup=sbtns)
    return bot_stats, sys_stats


async def send_bot_stats(_, query):
    buttons = ButtonMaker()
    bot_stats, _ = await stats(_, query.message, edit_mode=True)
    buttons.ibutton("Sys Stats",  "show_sys_stats")
    buttons.ibutton("Repo Stats", "show_repo_stats")
    buttons.ibutton("Bot Limits", "show_bot_limits")
    buttons.ibutton("Close",      "close_signal")
    sbtns = buttons.build_menu(2)
    await query.answer()
    await query.message.edit_text(bot_stats, reply_markup=sbtns)


async def send_sys_stats(_, query):
    buttons = ButtonMaker()
    _, sys_stats = await stats(_, query.message, edit_mode=True)
    buttons.ibutton("Bot Stats",  "show_bot_stats")
    buttons.ibutton("Repo Stats", "show_repo_stats")
    buttons.ibutton("Bot Limits", "show_bot_limits")
    buttons.ibutton("Close",      "close_signal")
    sbtns = buttons.build_menu(2)
    await query.answer()
    await query.message.edit_text(sys_stats, reply_markup=sbtns)


async def send_repo_stats(_, query):
    buttons = ButtonMaker()
    commit_date = 'Official Repo not available'
    last_commit = 'No UPSTREAM_REPO'
    c_log       = 'N/A'
    d_log       = 'N/A'
    vtag        = 'N/A'
    version     = 'N/A'
    change_log  = 'N/A'
    update_info = ''
    s_id        = ''
    async with xclient() as client:
        if await aiopath.exists('.git'):
            last_commit = (await cmd_exec("git log -1   --date=short --pretty=format:'%cr'", True))[0]
            version     = (await cmd_exec("git describe --abbrev=0   --tags",                True))[0]
            change_log  = (await cmd_exec("git log -1   --pretty=format:'%s'",               True))[0]
            if version == '':
                version = 'N/A'
        if version != 'N/A':
            if version != vtag:
                update_info =  f'⚠️ New Version Update Available ⚠️\n'
                update_info += f'Update ASAP and experience new features and bug-fixes.'
        
    repo_stats = f'<b>🔰 <u>Repository Info</u></b> \n\n' \
                 f'<code>- Updated   : </code> {last_commit}\n'   \
                 f'<code>- Version   : </code> {version}    \n'   \
                 f'<code>- Changelog : </code> {change_log} \n\n' \
                 f'<b>{update_info}\n\n@Server0x01</b>'

    buttons.ibutton("Bot Stats",  "show_bot_stats")
    buttons.ibutton("Sys Stats",  "show_sys_stats")
    buttons.ibutton("Bot Limits", "show_bot_limits")
    buttons.ibutton("Close", "close_signal")
    sbtns = buttons.build_menu(2)
    await query.answer()
    await query.message.edit_text(repo_stats, reply_markup=sbtns)


async def send_bot_limits(_, query):
    buttons = ButtonMaker()
    DIR = 'Unlimited' if config_dict['DIRECT_LIMIT']    == '' else config_dict['DIRECT_LIMIT']
    YTD = 'Unlimited' if config_dict['YTDLP_LIMIT']     == '' else config_dict['YTDLP_LIMIT']
    GDL = 'Unlimited' if config_dict['GDRIVE_LIMIT']    == '' else config_dict['GDRIVE_LIMIT']
    TOR = 'Unlimited' if config_dict['TORRENT_LIMIT']   == '' else config_dict['TORRENT_LIMIT']
    CLL = 'Unlimited' if config_dict['CLONE_LIMIT']     == '' else config_dict['CLONE_LIMIT']
    MGA = 'Unlimited' if config_dict['MEGA_LIMIT']      == '' else config_dict['MEGA_LIMIT']
    TGL = 'Unlimited' if config_dict['LEECH_LIMIT']     == '' else config_dict['LEECH_LIMIT']
    UMT = 'Unlimited' if config_dict['USER_MAX_TASKS']  == '' else config_dict['USER_MAX_TASKS']
    BMT = 'Unlimited' if config_dict['QUEUE_ALL']       == '' else config_dict['QUEUE_ALL']

    bot_limit = f'<b>@Serverv0x01 <u>Bot Limitations</u></b>\n' \
                f'<code>Torrent :</code> <b>{TOR} GB</b>\n' \
                f'<code>G-Drive :</code> <b>{GDL} GB</b>\n' \
                f'<code>Yt-Dlp  :</code> <b>{YTD} GB</b>\n' \
                f'<code>Direct  :</code> <b>{DIR} GB</b>\n' \
                f'<code>Clone   :</code> <b>{CLL} GB</b>\n' \
                f'<code>Leech   :</code> <b>{TGL} GB</b>\n' \
                f'<code>MEGA    :</code> <b>{MGA} GB</b>\n\n' \
                f'<code>User-T  :</code> <b>{UMT}</b>\n' \
                f'<code>Bot-T   :</code> <b>{BMT}</b>'

    buttons.ibutton("Bot Stats",  "show_bot_stats")
    buttons.ibutton("Sys Stats",  "show_sys_stats")
    buttons.ibutton("Repo Stats", "show_repo_stats")
    buttons.ibutton("Close", "close_signal")
    sbtns = buttons.build_menu(2)
    await query.answer()
    await query.message.edit_text(bot_limit, reply_markup=sbtns)


async def send_close_signal(_, query):
    await query.answer()
    try:
        await query.message.reply_to_message.delete()
    except Exception as e:
        LOGGER.error(e)
    await query.message.delete()


async def start(_, message):
    if len(message.command) > 1 and len(message.command[1]) == 36:
        userid = message.from_user.id
        input_token = message.command[1]
        if DATABASE_URL:
            stored_token = await DbManager().get_user_token(userid)
            if stored_token is None:
                return await sendMessage(message, 'This token is not associated with your account.\n\nPlease generate your own token.')
            if input_token != stored_token:
                return await sendMessage(message, 'Invalid token.\n\nPlease generate a new one.')
        if userid not in user_data:
            return await sendMessage(message, 'This token is not yours!\n\nKindly generate your own.')
        data = user_data[userid]
        if 'token' not in data or data['token'] != input_token:
            return await sendMessage(message, 'Token already used!\n\nKindly generate a new one.')
        token = str(uuid4())
        ttime = time()
        data['token'] = token
        data['time'] = ttime
        user_data[userid].update(data)
        if DATABASE_URL:
            await DbManager().update_user_tdata(userid, token, ttime)
        msg = 'Token refreshed successfully!\n\n'
        msg += f'Validity: {get_readable_time(int(config_dict["TOKEN_TIMEOUT"]))}'
        return await sendMessage(message, msg)
    elif config_dict['DM_MODE'] and message.chat.type != message.chat.type.SUPERGROUP:
        start_string = 'Bot Started.\n' \
                       'Now I will send all of your stuffs here.\n' \
                       'Use me at: @Server0x01'
    elif not config_dict['DM_MODE'] and message.chat.type != message.chat.type.SUPERGROUP:
        start_string = 'Sorry, you cannot use me here!\n' \
                       'Join: @Server0x01 Groups to use me.\n' \
                       'Thank You'
    else:
        tag = message.from_user.mention
        start_string = 'Start me in DM, not in the group.\n' \
                       f'cc: {tag}'
    await sendMessage(message, start_string)


async def restart(_, message):
    restart_message = await sendMessage(message, "Restarting...")
    if scheduler.running:
        scheduler.shutdown(wait=False)
    for interval in [QbInterval, Interval]:
        if interval:
            interval[0].cancel()
    await sync_to_async(clean_all)
    proc1 = await create_subprocess_exec('pkill', '-9', '-f', '-e', 'gunicorn|buffet|openstack|render|zcl')
    proc2 = await create_subprocess_exec('python3', 'update.py')
    await gather(proc1.wait(), proc2.wait())
    async with aiopen(".restartmsg", "w") as f:
        await f.write(f"{restart_message.chat.id}\n{restart_message.id}\n")
    osexecl(executable, executable, "-m", "bot")

@new_thread
async def ping(_, message):
    start_time = monotonic()
    reply = await sendMessage(message, "Starting Ping")
    end_time = monotonic()
    ping_time = int((end_time - start_time) * 1000)
    await editMessage(reply, f'{ping_time} ms')

async def log(_, message):
    await sendFile(message, 'Logs.txt')

help_string = f'''
<b>NOTE: Click on any CMD to see more detalis.</b>

/{BotCommands.MirrorCommand[0]} or /{BotCommands.MirrorCommand[1]}: Upload to Cloud Drive.

<b>Use qBit commands for torrents only:</b>
/{BotCommands.QbMirrorCommand[0]} or /{BotCommands.QbMirrorCommand[1]}: Download using qBittorrent and Upload to Cloud Drive.

/{BotCommands.BtSelectCommand}: Select files from torrents by gid or reply.
/{BotCommands.CategorySelect}: Change upload category for Google Drive.

<b>Use Yt-Dlp commands for YouTube or any videos:</b>
/{BotCommands.YtdlCommand[0]} or /{BotCommands.YtdlCommand[1]}: Mirror yt-dlp supported link.

<b>Use Leech commands for upload to Telegram:</b>
/{BotCommands.LeechCommand[0]} or /{BotCommands.LeechCommand[1]}: Upload to Telegram.
/{BotCommands.QbLeechCommand[0]} or /{BotCommands.QbLeechCommand[1]}: Download using qBittorrent and upload to Telegram(For torrents only).
/{BotCommands.YtdlLeechCommand[0]} or /{BotCommands.YtdlLeechCommand[1]}: Download using Yt-Dlp(supported link) and upload to telegram.

/leech{BotCommands.DeleteCommand} [telegram_link]: Delete replies from telegram (Only Owner & Sudo).

<b>G-Drive commands:</b>
/{BotCommands.CloneCommand}: Copy file/folder to Cloud Drive.
/{BotCommands.CountCommand} [drive_url]: Count file/folder of Google Drive.
/{BotCommands.DeleteCommand} [drive_url]: Delete file/folder from Google Drive (Only Owner & Sudo).

<b>Cancel Tasks:</b>
/{BotCommands.CancelMirror}: Cancel task by gid or reply.
/{BotCommands.CancelAllCommand[0]} : Cancel all tasks which added by you /{BotCommands.CancelAllCommand[1]} to in bots.

<b>Torrent/Drive Search:</b>
/{BotCommands.ListCommand} [query]: Search in Google Drive(s).
/{BotCommands.SearchCommand} [query]: Search for torrents with API.

<b>Bot Settings:</b>
/{BotCommands.UserSetCommand}: Open User settings.
/{BotCommands.UsersCommand}: show users settings (Only Owner & Sudo).
/{BotCommands.BotSetCommand}: Open Bot settings (Only Owner & Sudo).

<b>Authentication:</b>
/{BotCommands.AuthorizeCommand}: Authorize a chat or a user to use the bot (Only Owner & Sudo).
/{BotCommands.UnAuthorizeCommand}: Unauthorize a chat or a user to use the bot (Only Owner & Sudo).
/{BotCommands.AddSudoCommand}: Add sudo user (Only Owner).
/{BotCommands.RmSudoCommand}: Remove sudo users (Only Owner).

<b>Bot Stats:</b>
/{BotCommands.StatusCommand[0]} or /{BotCommands.StatusCommand[1]}: Shows a status of all active tasks.
/{BotCommands.StatsCommand[0]} or /{BotCommands.StatsCommand[1]}: Show server stats.
/{BotCommands.PingCommand[0]} or /{BotCommands.PingCommand[1]}: Check how long it takes to Ping the Bot.

<b>Maintainance:</b>
/{BotCommands.RestartCommand[0]}: Restart and update the bot (Only Owner & Sudo).
/{BotCommands.RestartCommand[1]}: Restart and update all bots (Only Owner & Sudo).
/{BotCommands.LogCommand}: Get a log file of the bot. Handy for getting crash reports (Only Owner & Sudo).

<b>Extras:</b>
/{BotCommands.ShellCommand}: Run shell commands (Only Owner).
/{BotCommands.EvalCommand}: Run Python Code Line | Lines (Only Owner).
/{BotCommands.ExecCommand}: Run Commands In Exec (Only Owner).
/{BotCommands.ClearLocalsCommand}: Clear {BotCommands.EvalCommand} or {BotCommands.ExecCommand} locals (Only Owner).

<b>RSS Feed:</b>
/{BotCommands.RssCommand}: Open RSS Menu.

<b>Attention: Read the first line again!</b>
'''

@new_thread
async def bot_help(_, message):
    reply_message = await sendMessage(message, help_string)
    await auto_delete_message(message, reply_message)


async def restart_notification():
    if await aiopath.isfile(".restartmsg"):
        with open(".restartmsg") as f:
            chat_id, msg_id = map(int, f)
    else:
        chat_id, msg_id = 0, 0

    async def send_incompelete_task_message(cid, msg):
        try:
            if msg.startswith('Restarted Successfully!'):
                await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text='Restarted Successfully!')
                await bot.send_message(chat_id, msg, disable_web_page_preview=True, reply_to_message_id=msg_id)
                await aioremove(".restartmsg")
            else:
                await bot.send_message(chat_id=cid, text=msg, disable_web_page_preview=True,
                                       disable_notification=True)
        except Exception as e:
            LOGGER.error(e)
    if DATABASE_URL:
        if INCOMPLETE_TASK_NOTIFIER and (notifier_dict := await DbManager().get_incomplete_tasks()):
            for cid, data in notifier_dict.items():
                msg = 'Restarted Successfully!' if cid == chat_id else 'Bot Restarted!'
                for tag, links in data.items():
                    msg += f"\n\n👤 {tag} Do your tasks again. \n"
                    for index, link in enumerate(links, start=1):
                        msg += f" {index}: {link} \n"
                        if len(msg.encode()) > 4000:
                            await send_incompelete_task_message(cid, msg)
                            msg = ''
                if msg:
                    await send_incompelete_task_message(cid, msg)

        if STOP_DUPLICATE_TASKS:
            await DbManager().clear_download_links()


    if await aiopath.isfile(".restartmsg"):
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text='Restarted Successfully!')
        except:
            pass
        await aioremove(".restartmsg")


async def main():
    await gather(start_cleanup(), torrent_search.initiate_search_tools(), restart_notification(), set_commands(bot))
    await sync_to_async(start_aria2_listener, wait=False)

    bot.add_handler(MessageHandler(start,   filters=command(BotCommands.StartCommand)))
    bot.add_handler(MessageHandler(log,     filters=command(BotCommands.LogCommand)     & CustomFilters.sudo))
    bot.add_handler(MessageHandler(restart, filters=command(BotCommands.RestartCommand) & CustomFilters.sudo))
    bot.add_handler(MessageHandler(ping,    filters=command(BotCommands.PingCommand)    & CustomFilters.authorized))
    bot.add_handler(MessageHandler(bot_help,filters=command(BotCommands.HelpCommand)    & CustomFilters.authorized))
    bot.add_handler(MessageHandler(stats,   filters=command(BotCommands.StatsCommand)   & CustomFilters.authorized))
    bot.add_handler(MessageHandler(stats,   filters=command(BotCommands.StatsCommand)   & CustomFilters.authorized))
    bot.add_handler(CallbackQueryHandler(send_close_signal, filters=regex("^close_signal")))
    bot.add_handler(CallbackQueryHandler(send_bot_stats,    filters=regex("^show_bot_stats")))
    bot.add_handler(CallbackQueryHandler(send_sys_stats,    filters=regex("^show_sys_stats")))
    bot.add_handler(CallbackQueryHandler(send_repo_stats,   filters=regex("^show_repo_stats")))
    bot.add_handler(CallbackQueryHandler(send_bot_limits,   filters=regex("^show_bot_limits")))
    LOGGER.info("Congratulations, Bot Started Successfully!")
    signal(SIGINT, exit_clean_up)

bot.loop.run_until_complete(main())
bot.loop.run_forever()
