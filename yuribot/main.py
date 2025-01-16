import configparser
import json
import logging
import requests

from aiohttp import web

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.markdown import hbold
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from uuid import uuid4
from urllib.parse import urlparse

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

inline_keyboard = [
	[InlineKeyboardButton(text='✅ Send', callback_data="send")],
	[InlineKeyboardButton(text='⚠️ Send with spoiler', callback_data="send_spoiler")],
    [InlineKeyboardButton(text='❌ Reject', callback_data="reject")],
]
inline_keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


@router.message(F.animation)
@router.message(F.photo)
@router.message(F.video)
async def media_handler(message: Message) -> None:
    try:
        description = f'Submitter: {message.from_user.full_name if message.from_user.username == None else "@" + message.from_user.username}'
    except:
        description = 'Unable to get user'

    if message.from_user.id == ADMIN:
        await message.reply(text='Please select option', reply_markup=inline_keyboard, disable_notification=True)
    else:
        if message.animation:
            await message.answer(text='Thank you for the GIF!', disable_notification=True)
        elif message.photo:
            await message.answer(text='Thank you for the picture!', disable_notification=True)
        elif message.video:
            await message.answer(text='Thank you for the video!', disable_notification=True)

        await message.copy_to(chat_id=ADMIN_CHANNEL, reply_markup=inline_keyboard, caption=description)


@router.callback_query(F.data == 'reject')
async def reject_handler(callback: CallbackQuery) -> None:
    if callback.from_user.id == ADMIN:
        if callback.message.reply_to_message:
            await callback.message.reply_to_message.delete()
        await callback.message.delete()


@router.message(F.text.regexp(r'https://((girlcock)?x|(vx)?(fx)?twitter).com\S+'))
async def link_handler(message: Message) -> None:
    try:
        description = (f'Submitter: {message.from_user.full_name if message.from_user.username == None else "@" + message.from_user.username}\n'
            f'Source: {message.text}')
        tweet_id = urlparse(message.text).path.split('/')[-1]
        with requests.get('https://api.vxtwitter.com/Twitter/status/' + tweet_id) as vxtwitter:
            if 'Failed to scan your link!' in vxtwitter:
                raise ValueError
            else:
                tweet_json = json.loads(vxtwitter.text)
                for media_url in tweet_json['mediaURLs']:
                    with requests.get(media_url, stream=True) as media:
                        if 'https://video.twimg.com' in media_url:
                            if message.from_user.id == ADMIN:
                                await message.reply_video(
                                    video=BufferedInputFile(file=media.content, filename='video.mp4'),
                                    reply_markup=inline_keyboard)
                            else:
                                await message.bot.send_video(
                                    chat_id=ADMIN_CHANNEL,
                                    video=BufferedInputFile(file=media.content, filename='video.mp4'),
                                    reply_markup=inline_keyboard,
                                    caption=description)
                        elif 'https://pbs.twimg.com' in media_url:
                            if message.from_user.id == ADMIN:
                                await message.reply_photo(
                                    photo=BufferedInputFile(file=media.content, filename='photo.jpg'),
                                    reply_markup=inline_keyboard)
                            else:
                                await message.bot.send_photo(
                                    chat_id=ADMIN_CHANNEL,
                                    photo=BufferedInputFile(file=media.content, filename='photo.jpg'),
                                    reply_markup=inline_keyboard,
                                    caption=description)
                        else:
                            raise ValueError
        if message.from_user.id != ADMIN:
            await message.answer(text='Thank you for the link!', disable_notification=True)
    except:
        await message.answer(text='Invalid link', disable_notification=True)


@router.callback_query()
async def send_handler(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    if callback.message.reply_to_message:
        animation = callback.message.reply_to_message.animation
        photo = callback.message.reply_to_message.photo
        video = callback.message.reply_to_message.video
    else:
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
    await message.answer(text='Please send me a picture, video, GIF or Twitter link', disable_notification=True)


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
