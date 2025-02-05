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
from aiogram.utils.markdown import hbold
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from uuid import uuid4
from urllib.parse import urlparse

from yuribot.gifconvert import convert_gif

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

router = Router()


def keyboardbuilder(is_video: bool) -> InlineKeyboardMarkup:
    inline_keyboard = [
        [InlineKeyboardButton(text='✅ Send', callback_data='send')],
        [InlineKeyboardButton(text='⚠️ Send with spoiler', callback_data='send_spoiler')],
        [InlineKeyboardButton(text='❌ Reject', callback_data='reject')],
    ]
    if is_video:
        inline_keyboard.append([InlineKeyboardButton(text='🔁 Convert to GIF', callback_data='gif')])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


@router.message(F.animation)
@router.message(F.photo)
@router.message(F.video)
async def media_handler(message: Message) -> None:
    try:
        description = f'Submitter: {message.from_user.full_name if message.from_user.username == None else "@" + message.from_user.username}'
    except:
        description = 'Unable to get user'

    if message.from_user.id == ADMIN:
        await message.reply(text='Please select option', reply_markup=keyboardbuilder(True if message.video else False), disable_notification=True)
    else:
        if message.animation:
            await message.answer(text='Thank you for the GIF!', disable_notification=True)
        elif message.photo:
            await message.answer(text='Thank you for the picture!', disable_notification=True)
        elif message.video:
            await message.answer(text='Thank you for the video!', disable_notification=True)

        await message.copy_to(chat_id=ADMIN_CHANNEL, reply_markup=keyboardbuilder(True if message.video else False), caption=description)


@router.callback_query(F.data == 'gif')
async def gif_handler(callback: CallbackQuery) -> None:
    try:
        if callback.from_user.id == ADMIN:
            if callback.message.video:
                message = callback.message
            else:
                message = callback.message.reply_to_message
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
                    reply_markup=keyboardbuilder(False))
                try:
                    os.remove('temp/animation.gif')
                    os.remove('temp/video.mp4')
                except:
                    pass
                await callback.message.delete()
        else:
            raise ValueError
    except:
        await message.reply(text='An error occured')


@router.callback_query(F.data == 'reject')
async def reject_handler(callback: CallbackQuery) -> None:
    if callback.from_user.id == ADMIN:
        if callback.message.reply_to_message:
            await callback.message.reply_to_message.delete()
        await callback.message.delete()


@router.message(F.text.regexp(r'https://((stupidpenis)?(girlcock)?(fixup)?x|(vx)?(fx)?twitter).com/\S+'))
async def twitter_handler(message: Message) -> None:
    try:
        description = (f'Submitter: {message.from_user.full_name if message.from_user.username == None else "@" + message.from_user.username}\n'
            f'Source: {message.text}')
        tweet_id = urlparse(message.text).path.split('/')[-1]
        with requests.get('https://api.vxtwitter.com/Twitter/status/' + tweet_id) as vxtwitter:
            if 'Failed to scan your link!' in vxtwitter:
                raise ValueError
            else:
                tweet_json = json.loads(vxtwitter.text)
                if tweet_json['mediaURLs']:
                    for media_url in tweet_json['mediaURLs']:
                        with requests.get(media_url, stream=True) as media:
                            if 'https://video.twimg.com' in media_url:
                                if message.from_user.id == ADMIN:
                                    await message.reply_video(
                                        video=BufferedInputFile(file=media.content, filename='video.mp4'),
                                        reply_markup=keyboardbuilder(True))
                                else:
                                    await message.bot.send_video(
                                        chat_id=ADMIN_CHANNEL,
                                        video=BufferedInputFile(file=media.content, filename='video.mp4'),
                                        reply_markup=keyboardbuilder(True),
                                        caption=description)
                            elif 'https://pbs.twimg.com' in media_url:
                                if message.from_user.id == ADMIN:
                                    await message.reply_photo(
                                        photo=BufferedInputFile(file=media.content, filename='photo.jpg'),
                                        reply_markup=keyboardbuilder(False))
                                else:
                                    await message.bot.send_photo(
                                        chat_id=ADMIN_CHANNEL,
                                        photo=BufferedInputFile(file=media.content, filename='photo.jpg'),
                                        reply_markup=keyboardbuilder(False),
                                        caption=description)
                            else:
                                raise ValueError
                else:
                    raise ValueError
        if message.from_user.id != ADMIN:
            await message.reply(text='Thank you for the Twitter link!', disable_notification=True)
    except:
        await message.reply(text='Invalid Twitter link', disable_notification=True)


@router.message(F.text.regexp(r'https://danbooru.donmai.us/posts/\S+'))
async def danbooru_handler(message: Message) -> None:
    try:
        description = (f'Submitter: {message.from_user.full_name if message.from_user.username == None else "@" + message.from_user.username}\n'
            f'Source: {message.text}')
        post = urlparse(message.text).path.split('/')[-1]
        with requests.get(f'https://danbooru.donmai.us/posts/{post}.json') as danbooru:
            danbooru_json = json.loads(danbooru.text)
            with requests.get(danbooru_json['file_url'], stream=True) as media:
                if urlparse(danbooru_json['file_url']).path[-4:] == '.mp4':
                    if message.from_user.id == ADMIN:
                        await message.reply_video(
                            video=BufferedInputFile(file=media.content, filename='video.mp4'),
                            reply_markup=keyboardbuilder(True))
                    else:
                        await message.bot.send_video(
                            chat_id=ADMIN_CHANNEL,
                            video=BufferedInputFile(file=media.content, filename='video.mp4'),
                            reply_markup=keyboardbuilder(True),
                            caption=description)
                else:
                    if message.from_user.id == ADMIN:
                        await message.reply_photo(
                            photo=BufferedInputFile(file=media.content, filename='photo.jpg'),
                            reply_markup=keyboardbuilder(False))
                    else:
                        await message.bot.send_photo(
                            chat_id=ADMIN_CHANNEL,
                            photo=BufferedInputFile(file=media.content, filename='photo.jpg'),
                            reply_markup=keyboardbuilder(False),
                            caption=description)
    except:
        await message.reply('Invalid Danbooru link')


@router.callback_query()
async def send_handler(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id

    try:
        animation = callback.message.reply_to_message.animation
        photo = callback.message.reply_to_message.photo
        video = callback.message.reply_to_message.video
        if not any([animation, photo, video]):
            raise ValueError
    except:
        animation = callback.message.animation
        photo = callback.message.photo
        video = callback.message.video

    if user_id == ADMIN:
        if animation:
            await callback.bot.send_animation(chat_id=CHANNEL, animation=animation.file_id, has_spoiler=True if callback.data == 'send_spoiler' else False)
        elif photo:
            await callback.bot.send_photo(chat_id=CHANNEL, photo=photo[0].file_id, has_spoiler=True if callback.data == 'send_spoiler' else False)
        elif video:
            await callback.bot.send_video(chat_id=CHANNEL, video=video.file_id, has_spoiler=True if callback.data == 'send_spoiler' else False)

        if callback.message.reply_to_message:
            await callback.message.reply_to_message.delete()
        await callback.message.delete()


@router.message()
async def default_handler(message: Message) -> None:
    await message.answer(text='''Please send me one of the following:
- Picture
- Video
- GIF
- Twitter link
- Danbooru link (danbooru.donmai.us)''', disable_notification=True)


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
