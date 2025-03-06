import configparser
import json
import logging
import os
import requests

from aiohttp import web

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from bs4 import BeautifulSoup

from uuid import uuid4
from urllib.parse import urlparse

from yuribot.utils import convert_gif, download_link

config = configparser.ConfigParser()
config.read('config.ini')

ADMIN = config['TELEGRAM'].getint('ADMIN')
ADMIN_CHANNEL = config['TELEGRAM'].getint('ADMIN_CHANNEL')
CHANNEL = config['TELEGRAM'].getint('CHANNEL')
TOKEN = config['TELEGRAM']['TOKEN']

BASE_WEBHOOK_URL = config['SERVER']['BASE_WEBHOOK_URL']
WEB_SERVER_HOST = config['SERVER']['HOST']
WEB_SERVER_PORT = config['SERVER'].getint('PORT')
WEBHOOK_PATH = config['SERVER']['WEBHOOK_PATH']
WEBHOOK_SECRET = str(uuid4())

media_album = {}
router = Router()


def keyboardbuilder(is_video: bool, is_admin: bool) -> InlineKeyboardMarkup:
    inline_keyboard = [
        [InlineKeyboardButton(text='✅ Send', callback_data='send_admin' if is_admin else 'send')],
        [InlineKeyboardButton(text='⚠️ Send with spoiler', callback_data='send_spoiler_admin' if is_admin else 'send_spoiler')],
        [InlineKeyboardButton(text='❌ Reject', callback_data='reject')],
    ]
    if is_video:
        inline_keyboard.append([InlineKeyboardButton(text='🔁 Convert to GIF', callback_data='gif')])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def descriptionbuilder(message: Message) -> str:
    try:
        desc = (f'Submitter: {message.from_user.full_name if message.from_user.username == None else "@" + message.from_user.username}\n'
            f'Source: {"Telegram" if message.text == None else message.text}')
    except:
        desc = 'Unable to get user'
    return desc


@router.message(F.animation)
@router.message(F.photo)
@router.message(F.video)
async def media_handler(message: Message) -> None:
    description = descriptionbuilder(message)

    if message.from_user.id == ADMIN:
        await message.reply(text='Please select option', reply_markup=keyboardbuilder(True if message.video else False, True), disable_notification=True)
    else:
        if message.animation:
            await message.answer(text='Thank you for the GIF!', disable_notification=True)
        elif message.photo:
            await message.answer(text='Thank you for the picture!', disable_notification=True)
        elif message.video:
            await message.answer(text='Thank you for the video!', disable_notification=True)

        await message.copy_to(chat_id=ADMIN_CHANNEL, reply_markup=keyboardbuilder(True if message.video else False, False), caption=description)


@router.callback_query(F.data == 'gif', F.from_user.id == ADMIN)
async def gif_handler(callback: CallbackQuery) -> None:
    try:
        if callback.message.reply_to_message:
            message = callback.message.reply_to_message
        else:
            message = callback.message
        video_id = message.video.file_id
        fileinfo = await callback.bot.get_file(file_id=video_id)
        if fileinfo.file_size > 10**8:
            await message.reply(text='Video too big')
            raise ValueError
        else:
            os.makedirs(name='temp', exist_ok=True)
            try:
                os.remove('temp/animation.gif')
                os.remove('temp/video.mp4')
            except:
                pass
            await callback.bot.download(file=video_id, destination='temp/video.mp4')
            await message.reply_animation(
                animation=FSInputFile(path=convert_gif(), filename='animation.gif'),
                reply_markup=keyboardbuilder(False, True))
            try:
                os.remove('temp/animation.gif')
                os.remove('temp/video.mp4')
            except:
                pass
            await callback.message.delete()
    except Exception as e:
        await message.reply(text=str(e))


@router.callback_query(F.data == 'reject', F.from_user.id == ADMIN)
async def reject_handler(callback: CallbackQuery | Message) -> None:
    try:
        if type(callback) == CallbackQuery:
            msg = callback.message
        else:
            msg = callback
        try:
            msg_id = msg.reply_to_message.message_id
        except:
            msg_id = msg.message_id
        if msg_id in media_album.keys():
            for item in media_album[msg_id][1]:
                await item.delete()
            await media_album[msg_id][1][0].reply_to_message.delete()
            await msg.delete()
            del media_album[msg_id]
        else:
            try:
                await msg.reply_to_message.delete()
            except:
                pass
        await msg.delete()
    except Exception as e:
        msg.reply(str(e))


@router.message(F.text.regexp(r'https://((stupidpenis)?(girlcock)?(fixup)?x|(vx)?(fx)?twitter).com/\S+'))
async def twitter_handler(message: Message) -> None:
    try:
        description = descriptionbuilder(message)
        tweet_id = urlparse(message.text).path.split('/')[-1]
        with requests.get('https://api.vxtwitter.com/Twitter/status/' + tweet_id) as vxtwitter:
            if 'Failed to scan your link!' in vxtwitter:
                raise ValueError
            else:
                tweet_json = json.loads(vxtwitter.text)
                if tweet_json['mediaURLs']:
                    if len(tweet_json['mediaURLs']) > 1:
                        media_group = MediaGroupBuilder(caption=None if message.from_user.id == ADMIN else f'Subscriber\'s <a href="tg://user?id={str(message.bot.id)}">submission</a>')
                        for media_url in tweet_json['mediaURLs']:
                            with requests.get(media_url, stream=True) as media:
                                if 'https://video.twimg.com' in media_url:
                                    media_group.add_video(media=BufferedInputFile(file=media.content, filename='video.mp4'))
                                elif 'https://pbs.twimg.com' in media_url:
                                    media_group.add_photo(media=BufferedInputFile(file=media.content, filename='photo.jpg'))
                                else:
                                    raise ValueError
                        if message.from_user.id == ADMIN:
                            album = await message.reply_media_group(media=media_group.build())
                            await album[0].reply(text='Please select option', reply_markup=keyboardbuilder(False, True), disable_notification=True)
                            media_album[album[0].message_id] = (media_group, album)
                        else:
                            album = await message.bot.send_media_group(chat_id=ADMIN_CHANNEL, media=media_group.build())
                            await album[0].reply(text='Please select option', reply_markup=keyboardbuilder(False, False), disable_notification=True)
                            media_album[album[0].message_id] = (media_group, album)
                    else:
                        with requests.get(tweet_json['mediaURLs'][0]) as media:
                            if 'https://video.twimg.com' in tweet_json['mediaURLs'][0]:
                                if message.from_user.id == ADMIN:
                                    await message.reply_video(
                                        video=BufferedInputFile(file=media.content, filename='video.mp4'),
                                        reply_markup=keyboardbuilder(True, True))
                                else:
                                    await message.bot.send_video(
                                        chat_id=ADMIN_CHANNEL,
                                        video=BufferedInputFile(file=media.content, filename='video.mp4'),
                                        reply_markup=keyboardbuilder(True, False),
                                        caption=description)
                            elif 'https://pbs.twimg.com' in tweet_json['mediaURLs'][0]:
                                if message.from_user.id == ADMIN:
                                    await message.reply_photo(
                                        photo=BufferedInputFile(file=media.content, filename='photo.jpg'),
                                        reply_markup=keyboardbuilder(False, True))
                                else:
                                    await message.bot.send_photo(
                                        chat_id=ADMIN_CHANNEL,
                                        photo=BufferedInputFile(file=media.content, filename='photo.jpg'),
                                        reply_markup=keyboardbuilder(False, False),
                                        caption=description)
                            else:
                                raise ValueError
                else:
                    raise ValueError
        if message.from_user.id != ADMIN:
            await message.reply(text='Thank you for the Twitter link!', disable_notification=True)
    except Exception as e:
        if message.from_user.id != ADMIN:
            await message.reply(text='Invalid Twitter link', disable_notification=True)
            msg = await message.forward(chat_id=ADMIN_CHANNEL)
            await msg.reply(text=str(e))
        else:
            await message.reply(text=str(e))


@router.message(F.text.regexp(r'https://danbooru.donmai.us/posts/\S+'))
async def danbooru_handler(message: Message) -> None:
    try:
        description = descriptionbuilder(message)
        post = urlparse(message.text).path.split('/')[-1]
        with requests.get(f'https://danbooru.donmai.us/posts/{post}.json') as danbooru:
            danbooru_json = json.loads(danbooru.text)
            with requests.get(danbooru_json['file_url'], stream=True) as media:
                if urlparse(danbooru_json['file_url']).path[-4:] == '.mp4':
                    if message.from_user.id == ADMIN:
                        await message.reply_video(
                            video=BufferedInputFile(file=media.content, filename='video.mp4'),
                            reply_markup=keyboardbuilder(True, True))
                    else:
                        await message.bot.send_video(
                            chat_id=ADMIN_CHANNEL,
                            video=BufferedInputFile(file=media.content, filename='video.mp4'),
                            reply_markup=keyboardbuilder(True, False),
                            caption=description)
                else:
                    if message.from_user.id == ADMIN:
                        await message.reply_photo(
                            photo=BufferedInputFile(file=media.content, filename='photo.jpg'),
                            reply_markup=keyboardbuilder(False, True))
                    else:
                        await message.bot.send_photo(
                            chat_id=ADMIN_CHANNEL,
                            photo=BufferedInputFile(file=media.content, filename='photo.jpg'),
                            reply_markup=keyboardbuilder(False, False),
                            caption=description)
        if message.from_user.id != ADMIN:
            await message.reply(text='Thank you for the Danbooru link!', disable_notification=True)
    except:
        await message.reply('Invalid Danbooru link')
        if message.from_user.id != ADMIN:
            await message.forward(chat_id=ADMIN_CHANNEL)


@router.message(F.text.regexp(r'https://(www.)?(dd)?instagram.com/\S+'))
async def instagram_handler(message: Message) -> None:
    try:
        url = urlparse(message.text)
        full_url = f'https://www.instagram.com{url.path}?{url.query}'

        if url.path.split('/')[1] == 'reel':
            os.makedirs(name='temp', exist_ok=True)
            filename = download_link(full_url, 'temp')
            inputfile = FSInputFile(path=f'{filename}', filename=filename.split('/')[-1])
            if message.from_user.id == ADMIN:
                await message.reply_video(
                    video=inputfile,
                    reply_markup=keyboardbuilder(True, True))
            else:
                await message.bot.send_video(
                    chat_id=ADMIN_CHANNEL,
                    video=inputfile,
                    caption=descriptionbuilder(message),
                    reply_markup=keyboardbuilder(True, False))
            os.remove(f'{filename}')
        elif url.path.split('/')[1] == 'p':
            with requests.get(f'https://www.ddinstagram.com/images/{url.path.split("/")[2]}/1') as pic:
                if message.from_user.id == ADMIN:
                    await message.reply_photo(
                        photo=BufferedInputFile(file=pic.content, filename='photo.jpg'),
                        reply_markup=keyboardbuilder(False, True))
                else:
                    await message.bot.send_photo(
                        chat_id=ADMIN_CHANNEL,
                        photo=BufferedInputFile(file=pic.content, filename='photo.jpg'),
                        reply_markup=keyboardbuilder(False, False),
                        caption=descriptionbuilder(message))
        if message.from_user.id != ADMIN:
            await message.reply(text='Thank you for the Instagram link!', disable_notification=True)
    except Exception as e:
        if message.from_user.id != ADMIN:
            await message.reply("Invalid Instagram link")
            msg = await message.forward(chat_id=ADMIN_CHANNEL)
            await msg.reply(str(e))
        await message.reply(str(e))


@router.callback_query(F.from_user.id == ADMIN)
async def send_handler(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id

    try:
        animation = callback.message.reply_to_message.animation
        photo = callback.message.reply_to_message.photo
        video = callback.message.reply_to_message.video
        media_group_id = callback.message.reply_to_message.media_group_id
        if not any([animation, photo, video, media_group_id]):
            raise ValueError
    except:
        animation = callback.message.animation
        photo = callback.message.photo
        video = callback.message.video
        media_group_id = callback.message.media_group_id

    if callback.data == 'send' or callback.data == 'send_spoiler':
        caption = f'Subscriber\'s <a href="tg://user?id={str(callback.message.bot.id)}">submission</a>'
    else:
        caption = None

    if callback.data == 'send_spoiler' or callback.data == 'send_spoiler_admin':
        spoiler = True
    else:
        spoiler = False

    if media_group_id:
        try:
            msg_id = callback.message.reply_to_message.message_id
        except:
            msg_id = callback.message.message_id
        await callback.bot.send_media_group(
            chat_id=CHANNEL,
            media=media_album[msg_id][0].build())
    elif animation:
        await callback.bot.send_animation(
            chat_id=CHANNEL,
            animation=animation.file_id,
            has_spoiler=spoiler,
            caption=caption)
    elif photo:
        await callback.bot.send_photo(
            chat_id=CHANNEL,
            photo=photo[0].file_id,
            has_spoiler=spoiler,
            caption=caption)
    elif video:
        await callback.bot.send_video(
            chat_id=CHANNEL,
            video=video.file_id,
            has_spoiler=spoiler,
            caption=caption)

    await reject_handler(callback)


@router.message(F.text.regexp(r'^https://.+/.+'))
async def opengraph_handler(message: Message) -> None:
    try:
        description = descriptionbuilder(message)
        og = requests.get(message.text)
        soup = BeautifulSoup(og.text, 'html.parser')
        try:
            url = soup.find('meta', property='og:video')['content']
            is_video = True
        except:
            url = soup.find('meta', property='og:image')['content']
            is_video = False
        with requests.get(url=url, stream=True) as media:
            if is_video:
                if message.from_user.id == ADMIN:
                    await message.reply_video(
                        video=BufferedInputFile(file=media.content, filename='video.mp4'),
                        reply_markup=keyboardbuilder(True, True))
                else:
                    await message.bot.send_video(
                        chat_id=ADMIN_CHANNEL,
                        video=BufferedInputFile(file=media.content, filename='video.mp4'),
                        reply_markup=keyboardbuilder(True, False),
                        caption=description)
            else:
                if message.from_user.id == ADMIN:
                    await message.reply_photo(
                        photo=BufferedInputFile(file=media.content, filename='photo.jpg'),
                        reply_markup=keyboardbuilder(False, True))
                else:
                    await message.bot.send_photo(
                        chat_id=ADMIN_CHANNEL,
                        photo=BufferedInputFile(file=media.content, filename='photo.jpg'),
                        reply_markup=keyboardbuilder(False, False),
                        caption=description)
        if message.from_user.id != ADMIN:
            await message.reply(text='Thank you for the link!', disable_notification=True)
    except:
        await message.reply('Invalid link')
        if message.from_user.id != ADMIN:
            await message.forward(chat_id=ADMIN_CHANNEL)

@router.message()
async def default_handler(message: Message) -> None:
    await message.answer(text='''Please send me one of the following:
- Picture
- Video
- GIF
- Twitter link (Incl. Fixup links)
- Danbooru link (danbooru.donmai.us)
- Open Graph link (e.g. Mastodon)
- Instagram link''', disable_notification=True)
    if message.text != '/start' and message.from_user.id != ADMIN:
        await message.forward(chat_id=ADMIN_CHANNEL)


async def on_startup(bot: Bot) -> None:
    await bot.set_webhook(f'{BASE_WEBHOOK_URL}{WEBHOOK_PATH}', secret_token=WEBHOOK_SECRET)


def main() -> None:
    dp = Dispatcher()
    dp.include_router(router)

    dp.startup.register(on_startup)

    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))

    app = web.Application()

    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)

    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)
