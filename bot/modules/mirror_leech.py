from base64 import b64encode
from re import match as re_match, split as re_split
from time import sleep
from os import path as ospath
from threading import Thread
from telegram.ext import CallbackQueryHandler, CommandHandler

from bot import *
from bot.helper.ext_utils.bot_utils import is_url, is_magnet, is_mega_link, is_gdrive_link, get_content_type
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException
from bot.helper.mirror_utils.download_utils.aria2_download import add_aria2c_download
from bot.helper.mirror_utils.download_utils.gd_downloader import add_gd_download
from bot.helper.mirror_utils.download_utils.qbit_downloader import QbDownloader
from bot.helper.mirror_utils.download_utils.mega_downloader import MegaDownloader
from bot.helper.mirror_utils.download_utils.direct_link_generator import direct_link_generator
from bot.helper.mirror_utils.download_utils.telegram_downloader import TelegramDownloadHelper
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage
from .listener import MirrorLeechListener
from bot.helper.telegram_helper.button_build import ButtonMaker


def _mirror_leech(
        bot,
        message,
        isZip=False,
        extract=False,
        isQbit=False,
        isLeech=False,
        multi=0):
    buttons = ButtonMaker()
    if FSUB:
        try:
            uname = message.from_user.mention_html(
                message.from_user.first_name)
            user = bot.get_chat_member(FSUB_CHANNEL_ID, message.from_user.id)
            if user.status not in ['member', 'creator', 'administrator']:
                buttons.buildbutton(
                    f"{CHANNEL_USERNAME}",
                    f"https://t.me/{CHANNEL_USERNAME}")
                reply_markup = InlineKeyboardMarkup(buttons.build_menu(1))
                return sendMarkup(
                    f"<b>Dear {uname}️,\n\nI found that you haven't joined our Updates Channel yet.\n\nJoin and Use Bots Without Restrictions.</b>",
                    bot,
                    message,
                    reply_markup)
        except Exception as e:
            LOGGER.info(str(e))
    if BOT_PM and message.chat.type != 'private':
        try:
            msg1 = f'Added your Requested link to Download\n'
            send = bot.sendMessage(message.from_user.id, text=msg1)
            send.delete()
        except Exception as e:
            LOGGER.warning(e)
            bot_d = bot.get_me()
            b_uname = bot_d.username
            uname = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>'
            botstart = f"http://t.me/{b_uname}"
            buttons.buildbutton("Click Here to Start Me", f"{botstart}")
            startwarn = f"Dear {uname},\n\n<b>I found that you haven't started me in PM (Private Chat) yet.</b>\n\n" \
                        f"From now on i will give link and leeched files in PM and log channel only"
            message = sendMarkup(
                startwarn, bot, message, InlineKeyboardMarkup(
                    buttons.build_menu(2)))
            return
    if message.chat.type == 'private' and len(
            LEECH_LOG) == 0 and isLeech and MAX_LEECH_SIZE == 4194304000:
        text = f"Leech Log is Empty you Can't use bot in PM,\nYou Can use <i>/{BotCommands.AddleechlogCommand} chat_id </i> to add leech log."
        sendMessage(text, bot, message)
        return
    mesg = message.text.split('\n')
    message_args = mesg[0].split(maxsplit=1)
    name_args = mesg[0].split('|', maxsplit=1)
    index = 1
    ratio = None
    seed_time = None
    select = False
    seed = False

    if len(message_args) > 1:
        args = mesg[0].split(maxsplit=3)
        for x in args:
            x = x.strip()
            if x == 's':
                select = True
                index += 1
            elif x == 'd':
                seed = True
                index += 1
            elif x.startswith('d:'):
                seed = True
                index += 1
                dargs = x.split(':')
                ratio = dargs[1] if dargs[1] else None
                if len(dargs) == 3:
                    seed_time = dargs[2] if dargs[2] else None
        message_args = mesg[0].split(maxsplit=index)
        if len(message_args) > index:
            link = message_args[index].strip()
            if link.isdigit():
                if multi == 0:
                    multi = int(link)
                link = ''
            elif link.startswith(("|", "pswd:")):
                link = ''
        else:
            link = ''
    else:
        link = ''

    if len(name_args) > 1:
        name = name_args[1]
        name = name.split(' pswd:')[0]
        name = name.strip()
    else:
        name = ''

    link = re_split(r"pswd:|\|", link)[0]
    link = link.strip()

    pswd_arg = mesg[0].split(' pswd: ')
    if len(pswd_arg) > 1:
        pswd = pswd_arg[1]
    else:
        pswd = None

    if message.from_user.username:
        tag = f"@{message.from_user.username}"
    else:
        tag = message.from_user.mention_html(message.from_user.first_name)

    reply_to = message.reply_to_message
    if reply_to is not None:
        file_ = next(
            (i for i in [
                reply_to.document,
                reply_to.video,
                reply_to.audio,
                reply_to.photo] if i),
            None)
        if not reply_to.from_user.is_bot:
            if reply_to.from_user.username:
                tag = f"@{reply_to.from_user.username}"
            else:
                tag = reply_to.from_user.mention_html(
                    reply_to.from_user.first_name)
        if len(link) == 0 or not is_url(link) and not is_magnet(link):
            if file_ is None:
                reply_text = reply_to.text.split(maxsplit=1)[0].strip()
                if is_url(reply_text) or is_magnet(reply_text):
                    link = reply_to.text.strip()
            elif isinstance(file_, list):
                link = file_[-1].get_file().file_path
            elif not isQbit and file_.mime_type != "application/x-bittorrent":
                listener = MirrorLeechListener(
                    bot, message, isZip, extract, isQbit, isLeech, pswd, tag)
                Thread(target=TelegramDownloadHelper(listener).add_download, args=(
                    message, f'{DOWNLOAD_DIR}{listener.uid}/', name)).start()
                if multi > 1:
                    sleep(4)
                    nextmsg = type(
                        'nextmsg', (object, ), {
                            'chat_id': message.chat_id, 'message_id': message.reply_to_message.message_id + 1})
                    nextmsg = sendMessage(message.text, bot, nextmsg)
                    nextmsg.from_user.id = message.from_user.id
                    multi -= 1
                    sleep(4)
                    Thread(
                        target=_mirror_leech,
                        args=(
                            bot,
                            nextmsg,
                            isZip,
                            extract,
                            isQbit,
                            isLeech,
                            multi)).start()
                return
            else:
                link = file_.get_file().file_path

    if not is_url(link) and not is_magnet(link) and not ospath.exists(link):
        help_msg = "<b>Send link along with command line:</b>"
        if isQbit:
            help_msg += "\n<code>/qbcmd</code> {link} pswd: xx [zip/unzip]"
            help_msg += "\n\n<b>By replying to link/file:</b>"
            help_msg += "\n<code>/qbcmd</code> pswd: xx [zip/unzip]"
            help_msg += "\n\n<b>Bittorrent selection:</b>"
            help_msg += "\n<code>/cmd</code> <b>s</b> {link} or by replying to {file/link}"
            help_msg += "\n\n<b>Qbittorrent seed</b>:"
            help_msg += "\n<code>/qbcmd</code> <b>d</b> {link} or by replying to {file/link}.\n"
            help_msg += "To specify ratio and seed time. Ex: d:0.7:10 (ratio and time) or d:0.7 "
            help_msg += "(only ratio) or d::10 (only time) where time in minutes"
            help_msg += "\n\n<b>Multi links only by replying to first link/file:</b>"
            help_msg += "\n<code>/command</code> 10(number of links/files)\n\n<b>⚠⁉ If You Don't Know How To Use Bots, Check Others Message. Don't Play With Commands</b>"
        else:
            help_msg += "\n<code>/cmd</code> {link} |newname pswd: xx [zip/unzip]"
            help_msg += "\n\n<b>By replying to link/file:</b>"
            help_msg += "\n<code>/cmd</code> |newname pswd: xx [zip/unzip]"
            help_msg += "\n\n<b>Direct link authorization:</b>"
            help_msg += "\n<code>/cmd</code> {link} |newname pswd: xx\nusername\npassword"
            help_msg += "\n\n<b>Bittorrent selection:</b>"
            help_msg += "\n<code>/cmd</code> <b>s</b> {link} or by replying to {file/link}"
            help_msg += "\n\n<b>Bittorrent seed</b>:"
            help_msg += "\n<code>/cmd</code> <b>d</b> {link} or by replying to {file/link}.\n"
            help_msg += "To specify ratio and seed time. Ex: d:0.7:10 (ratio and time) or d:0.7 "
            help_msg += "(only ratio) or d::10 (only time) where time in minutes"
            help_msg += "\n\n<b>Multi links only by replying to first link/file:</b>"
            help_msg += "\n<code>/command</code> 10(number of links/files)\n\n<b>⚠⁉ If You Don't Know How To Use Bots, Check Others Message. Don't Play With Commands</b>"
        return sendMessage(help_msg, bot, message)

    LOGGER.info(link)

    if not is_mega_link(link) and not isQbit and not is_magnet(link) \
            and not is_gdrive_link(link) and not link.endswith('.torrent'):
        content_type = get_content_type(link)
        if content_type is None or re_match(
                r'text/html|text/plain', content_type):
            try:
                link = direct_link_generator(link)
                LOGGER.info(f"Generated link: {link}")
            except DirectDownloadLinkException as e:
                LOGGER.info(str(e))
                if str(e).startswith('ERROR:'):
                    return sendMessage(str(e), bot, message)

    listener = MirrorLeechListener(
        bot,
        message,
        isZip,
        extract,
        isQbit,
        isLeech,
        pswd,
        tag,
        select,
        seed)

    if is_gdrive_link(link):
        if not isZip and not extract and not isLeech:
            gmsg = f"Use /{BotCommands.CloneCommand} to clone Google Drive file/folder\n\n"
            gmsg += f"Use /{BotCommands.ZipMirrorCommand[0]} to make zip of Google Drive folder\n\n"
            gmsg += f"Use /{BotCommands.UnzipMirrorCommand[0]} to extracts Google Drive archive folder/file"
            sendMessage(gmsg, bot, message)
        else:
            Thread(
                target=add_gd_download,
                args=(
                    link,
                    f'{DOWNLOAD_DIR}{listener.uid}',
                    listener,
                    name)).start()
    elif is_mega_link(link):
        if MEGA_KEY is not None:
            Thread(target=MegaDownloader(listener).add_download, args=(
                link, f'{DOWNLOAD_DIR}{listener.uid}/')).start()
        else:
            sendMessage('MEGA_API_KEY not Provided!', bot, message)
    elif isQbit:
        Thread(
            target=QbDownloader(listener).add_qb_torrent,
            args=(
                link,
                f'{DOWNLOAD_DIR}{listener.uid}',
                select,
                ratio,
                seed_time)).start()
    else:
        if len(mesg) > 1:
            ussr = mesg[1]
            if len(mesg) > 2:
                pssw = mesg[2]
            else:
                pssw = ''
            auth = f"{ussr}:{pssw}"
            auth = "Basic " + b64encode(auth.encode()).decode('ascii')
        else:
            auth = ''
        Thread(
            target=add_aria2c_download,
            args=(
                link,
                f'{DOWNLOAD_DIR}{listener.uid}',
                listener,
                name,
                auth,
                select,
                ratio,
                seed_time)).start()

    if multi > 1:
        sleep(4)
        nextmsg = type(
            'nextmsg', (object, ), {
                'chat_id': message.chat_id, 'message_id': message.reply_to_message.message_id + 1})
        nextmsg = sendMessage(message.text, bot, nextmsg)
        nextmsg.from_user.id = message.from_user.id
        multi -= 1
        sleep(4)
        Thread(
            target=_mirror_leech,
            args=(
                bot,
                nextmsg,
                isZip,
                extract,
                isQbit,
                isLeech,
                multi)).start()


def bot_pm_button_handle(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    data = data.split(" ")
    if user_id != int(data[1]):
        return query.answer(
            text="Since you didnt perform this task this file, you cant see it in your BOT PM",
            show_alert=True,
        )
    else:
        bot_d = context.bot.get_me()
        b_uname = bot_d.username
        boturl = f"https://t.me/{b_uname}?start={int(data[2])}"
        return query.answer(url=boturl)


def mirror(update, context):
    _mirror_leech(context.bot, update.message)


def unzip_mirror(update, context):
    _mirror_leech(context.bot, update.message, extract=True)


def zip_mirror(update, context):
    _mirror_leech(context.bot, update.message, True)


def qb_mirror(update, context):
    _mirror_leech(context.bot, update.message, isQbit=True)


def qb_unzip_mirror(update, context):
    _mirror_leech(context.bot, update.message, extract=True, isQbit=True)


def qb_zip_mirror(update, context):
    _mirror_leech(context.bot, update.message, True, isQbit=True)


def leech(update, context):
    _mirror_leech(context.bot, update.message, isLeech=True)


def unzip_leech(update, context):
    _mirror_leech(context.bot, update.message, extract=True, isLeech=True)


def zip_leech(update, context):
    _mirror_leech(context.bot, update.message, True, isLeech=True)


def qb_leech(update, context):
    _mirror_leech(context.bot, update.message, isQbit=True, isLeech=True)


def qb_unzip_leech(update, context):
    _mirror_leech(
        context.bot,
        update.message,
        extract=True,
        isQbit=True,
        isLeech=True)


def qb_zip_leech(update, context):
    _mirror_leech(context.bot, update.message, True, isQbit=True, isLeech=True)


if MIRROR_ENABLED:

    mirror_handler = CommandHandler(
        BotCommands.MirrorCommand,
        mirror,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True)
    unzip_mirror_handler = CommandHandler(
        BotCommands.UnzipMirrorCommand,
        unzip_mirror,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True)
    zip_mirror_handler = CommandHandler(
        BotCommands.ZipMirrorCommand,
        zip_mirror,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True)
    qb_mirror_handler = CommandHandler(
        BotCommands.QbMirrorCommand,
        qb_mirror,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True)
    qb_unzip_mirror_handler = CommandHandler(
        BotCommands.QbUnzipMirrorCommand,
        qb_unzip_mirror,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True)
    qb_zip_mirror_handler = CommandHandler(
        BotCommands.QbZipMirrorCommand,
        qb_zip_mirror,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True)

else:
    mirror_handler = CommandHandler(
        BotCommands.MirrorCommand,
        mirror,
        filters=CustomFilters.owner_filter | CustomFilters.authorized_user,
        run_async=True)
    unzip_mirror_handler = CommandHandler(
        BotCommands.UnzipMirrorCommand,
        unzip_mirror,
        filters=CustomFilters.owner_filter | CustomFilters.authorized_user,
        run_async=True)
    zip_mirror_handler = CommandHandler(
        BotCommands.ZipMirrorCommand,
        zip_mirror,
        filters=CustomFilters.owner_filter | CustomFilters.authorized_user,
        run_async=True)
    qb_mirror_handler = CommandHandler(
        BotCommands.QbMirrorCommand,
        qb_mirror,
        filters=CustomFilters.owner_filter | CustomFilters.authorized_user,
        run_async=True)
    qb_unzip_mirror_handler = CommandHandler(
        BotCommands.QbUnzipMirrorCommand,
        qb_unzip_mirror,
        filters=CustomFilters.owner_filter | CustomFilters.authorized_user,
        run_async=True)
    qb_zip_mirror_handler = CommandHandler(
        BotCommands.QbZipMirrorCommand,
        qb_zip_mirror,
        filters=CustomFilters.owner_filter | CustomFilters.authorized_user,
        run_async=True)

if LEECH_ENABLED:
    leech_handler = CommandHandler(
        BotCommands.LeechCommand,
        leech,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True)
    unzip_leech_handler = CommandHandler(
        BotCommands.UnzipLeechCommand,
        unzip_leech,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True)
    zip_leech_handler = CommandHandler(
        BotCommands.ZipLeechCommand,
        zip_leech,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True)
    qb_leech_handler = CommandHandler(
        BotCommands.QbLeechCommand,
        qb_leech,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True)
    qb_unzip_leech_handler = CommandHandler(
        BotCommands.QbUnzipLeechCommand,
        qb_unzip_leech,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True)
    qb_zip_leech_handler = CommandHandler(
        BotCommands.QbZipLeechCommand,
        qb_zip_leech,
        filters=CustomFilters.authorized_chat | CustomFilters.authorized_user,
        run_async=True)

else:
    leech_handler = CommandHandler(
        BotCommands.LeechCommand,
        leech,
        filters=CustomFilters.owner_filter | CustomFilters.authorized_user,
        run_async=True)
    unzip_leech_handler = CommandHandler(
        BotCommands.UnzipLeechCommand,
        unzip_leech,
        filters=CustomFilters.owner_filter | CustomFilters.authorized_user,
        run_async=True)
    zip_leech_handler = CommandHandler(
        BotCommands.ZipLeechCommand,
        zip_leech,
        filters=CustomFilters.owner_filter | CustomFilters.authorized_user,
        run_async=True)
    qb_leech_handler = CommandHandler(
        BotCommands.QbLeechCommand,
        qb_leech,
        filters=CustomFilters.owner_filter | CustomFilters.authorized_user,
        run_async=True)
    qb_unzip_leech_handler = CommandHandler(
        BotCommands.QbUnzipLeechCommand,
        qb_unzip_leech,
        filters=CustomFilters.owner_filter | CustomFilters.authorized_user,
        run_async=True)
    qb_zip_leech_handler = CommandHandler(
        BotCommands.QbZipLeechCommand,
        qb_zip_leech,
        filters=CustomFilters.owner_filter | CustomFilters.authorized_user,
        run_async=True)

botpmbutton = CallbackQueryHandler(
    bot_pm_button_handle, pattern="botpmfilebutton", run_async=True
)
dispatcher.add_handler(botpmbutton)
dispatcher.add_handler(mirror_handler)
dispatcher.add_handler(unzip_mirror_handler)
dispatcher.add_handler(zip_mirror_handler)
dispatcher.add_handler(qb_mirror_handler)
dispatcher.add_handler(qb_unzip_mirror_handler)
dispatcher.add_handler(qb_zip_mirror_handler)
dispatcher.add_handler(leech_handler)
dispatcher.add_handler(unzip_leech_handler)
dispatcher.add_handler(zip_leech_handler)
dispatcher.add_handler(qb_leech_handler)
dispatcher.add_handler(qb_unzip_leech_handler)
dispatcher.add_handler(qb_zip_leech_handler)
