import asyncio
import logging
import os
from re import Match
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import FSInputFile, URLInputFile, InputMediaAudio, Audio, InlineQuery, CallbackQuery, InlineQueryResultAudio, InputTextMessageContent, InlineQueryResultArticle, BufferedInputFile
from aiogram.filters.command import Command
from aiogram.handlers import ChosenInlineResultHandler
from aiogram import html
import glob
from dotenv import load_dotenv

from utils import sanitize_data
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from librespot.core import Session
from librespot.metadata import TrackId
from librespot.audio.decoders import AudioQuality, VorbisOnlyAudioQuality
import redis


session = Session.Builder().stored_file().create()
token = session.tokens().get("user-read-email")
is_premium = session.get_user_attribute("type") == "premium"
audio_quality = AudioQuality.VERY_HIGH if is_premium else AudioQuality.HIGH

load_dotenv() 
spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id=os.getenv("SPOT_ID"), client_secret=os.getenv("SPOT_SECRET")))

r = redis.Redis(host=os.getenv("REDIS_HOST"), port=int(os.getenv("REDIS_PORT")), db=0)


client_id = os.getenv("SPOT_ID")
client_secret = os.getenv("SPOT_SECRET")
scope = (
    "user-read-playback-state playlist-read-private playlist-read-collaborative"
    " app-remote-control user-modify-playback-state user-library-modify"
    " user-library-read"
)
sp_auth = spotipy.oauth2.SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri="https://musify.nyako.tk/auth/callback",
    scope=scope,
)


logging.basicConfig(level=logging.INFO)


bot = Bot(token=os.getenv("TOKEN"), parse_mode='HTML')

dp = Dispatcher()


@dp.callback_query(F.data.startswith('close_menu_'))
async def close(callback: CallbackQuery):
    track_id = callback.data.replace("close_menu_", "")
    buttons = [
        [types.InlineKeyboardButton(text="🔽 open menu", callback_data=f"open_menu_{track_id}")]
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.edit_message_reply_markup(chat_id=callback.message.chat.id, message_id=callback.message.message_id, reply_markup=keyboard)



@dp.callback_query(F.data.startswith('open_menu_'))
async def openmenu(callback: CallbackQuery):
    track_id = callback.data.replace("open_menu_", "")
    print(track_id)
    buttons = [
        [types.InlineKeyboardButton(text="❤️", callback_data=f"like_{track_id}")],
        [types.InlineKeyboardButton(text="recommendations", switch_inline_query_current_chat=f"recs {track_id}")],
        [types.InlineKeyboardButton(text="share", switch_inline_query=f"https://open.spotify.com/track/{track_id}"),
         types.InlineKeyboardButton(text="spotify", url=f"https://open.spotify.com/track/{track_id}")],
         [types.InlineKeyboardButton(text="🔼 close menu", callback_data=f"close_menu_{track_id}")]
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.edit_message_reply_markup(chat_id=callback.message.chat.id, message_id=callback.message.message_id, reply_markup=keyboard)


@dp.inline_query(F.query.regexp(r'^(https?://)?open\.spotify\.com/track/(?P<TrackID>[0-9a-zA-Z]{22})(\?si=.+?)?$').as_("track"))
async def tracklink(inline_query: InlineQuery):
    song = spotify.track(track_id=inline_query.query)
    artists_raw = []
    for data in song["artists"]:
        artists_raw.append(sanitize_data(data["name"]))
    artists = ", ".join(artists_raw)
    album = song["album"]
    buttons = [
        [types.InlineKeyboardButton(text="one moment....", callback_data="wait")]
    ]
    kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await inline_query.answer([InlineQueryResultAudio(
            id=str("audio" + song["id"]),  # индекс элемента в list
            title=song['name'],
            performer=f'{artists}',
            thumbnail_url=song["album"]["images"][0]['url'],
            audio_url="https://nyako.tk/empty.mp3",
            reply_markup=kb,
            audio_duration=int(song["duration_ms"]/1000)
        )],
        is_personal=True,
        cache_time=0)
    # input_message_content=InputTextMessageContent(message_text=f"<a href='https://open.spotify.com/track/{song['id']}'>Spotify</a>"),


@dp.chosen_inline_result()
async def process_audio(chosen: ChosenInlineResultHandler):
    print(chosen)
    if (chosen.result_id.startswith("audio")):
        track_id = chosen.result_id.replace("audio", "")
        info = spotify.track(track_id=track_id, market="ES") # ES for Russian metadata
        artists_raw = []
        for data in info["artists"]:
            artists_raw.append(sanitize_data(data["name"]))
        artists = ", ".join(artists_raw)
        track_id = TrackId.from_uri(f"spotify:track:{track_id}")
        stream = session.content_feeder().load(track_id, VorbisOnlyAudioQuality(audio_quality), False, None)
        file = stream.input_stream.stream().read(-1)
        message = await bot.send_audio(
                        os.getenv("LOG_CHAT_ID"),
                        BufferedInputFile(
                            file,
                            "%s- %s.mp3"
                            % (
                                artists,
                                info["name"],
                            ),
                        ),
                        title=info["name"], 
                        performer=artists,
                        thumbnail=URLInputFile(url=info["album"]["images"][0]["url"]),
                        duration=int(info["duration_ms"]/1000)
        )
        
        await bot.edit_message_media(media=InputMediaAudio(media=message.audio.file_id, title=info["name"], performer=artists, thumbnail=URLInputFile(url=info["album"]["images"][0]["url"]), duration=int(info["duration_ms"]/1000)), inline_message_id=chosen.inline_message_id)
        await bot.edit_message_caption(inline_message_id=chosen.inline_message_id, caption=f"<a href='https://open.spotify.com/track/{song['id']}'>Spotify</a> | <a href='https://t.me/musify_bot'>Musify</a>")

@dp.inline_query(F.query.startswith("search "))
async def search(inline_query: InlineQuery):
    results = spotify.search(q=inline_query.query.replace("search ", ""))
    searchresults = []
    for song in results['tracks']['items']:
        artists_raw = []
        for data in song["artists"]:
            artists_raw.append(sanitize_data(data["name"]))
        artists = ", ".join(artists_raw)
        album = song["album"]
        release_year = album["release_date"] if album["release_date_precision"] == "year" else album["release_date"].split("-")[0]
        searchresults.append(InlineQueryResultArticle(
            id=str(song['id']),
            title=song['name'],
            description=f'{artists} ⦁ {album["name"]} ⦁ {release_year}',
            thumbnail_url=song["album"]["images"][0]['url'],
            input_message_content=InputTextMessageContent(message_text=f"https://open.spotify.com/track/{song['id']}")
        ))
    await inline_query.answer(searchresults, is_personal=True)
    
@dp.inline_query(F.query.startswith("recs "))
async def recs(inline_query: InlineQuery):
    print(inline_query.query.replace("recs ", ""))
    results = spotify.recommendations(seed_tracks=[inline_query.query.replace("recs ", "")], market="ES")
    recsresults = []
    for song in results['tracks']:
        artists_raw = []
        for data in song["artists"]:
            artists_raw.append(sanitize_data(data["name"]))
        artists = ", ".join(artists_raw)
        album = song["album"]
        release_year = album["release_date"] if album["release_date_precision"] == "year" else album["release_date"].split("-")[0]
        recsresults.append(InlineQueryResultArticle(
            id=str(song['id']),
            title=song['name'],
            description=f'{artists} ⦁ {album["name"]} ⦁ {release_year}',
            thumbnail_url=song["album"]["images"][0]['url'],
            input_message_content=InputTextMessageContent(message_text=f"https://open.spotify.com/track/{song['id']}")
        ))
    await inline_query.answer(recsresults, is_personal=True)

'''
@dp.inline_query(F.query == "")
async def np(inline_query: InlineQuery):
    
        searchresults.append(InlineQueryResultArticle(
            id=str(song['id']),  # индекс элемента в list
            title=song['name'],
            description=f"{artists} • {song['year']}",
            thumbnail_url=song["album"]["images"][0]['url'],
            input_message_content=InputTextMessageContent(message_text=f"https://open.spotify.com/track/{song['id']}")
        ))
    await inline_query.answer(searchresults, is_personal=True)
'''

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    buttons = [
        [types.InlineKeyboardButton(text="search", switch_inline_query_current_chat="search ")],
        #[types.InlineKeyboardButton(text="auth", url=sp_auth.get_authorize_url(message.from_user.id))]
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.reply("Hey! I'm musify bot! I can help you to listen spotify music in telegram! \nSend me link to any spotify track or try searching.", reply_markup=keyboard)
    

@dp.message(F.text.regexp(r'^(https?://)?open\.spotify\.com/track/(?P<TrackID>[0-9a-zA-Z]{22})(\?si=.+?)?$').as_("track"))
async def sendtrack(message: types.Message, track: Match[str]):
    
    info = spotify.track(track_id=track[2], market="ES") # ES for Russian metadata
    #artists = ", ".join(info[0])
    photo = await message.reply("⏳")
    track_id = TrackId.from_uri(f"spotify:track:{track[2]}")
    stream = session.content_feeder().load(track_id, VorbisOnlyAudioQuality(audio_quality), False, None)
    await bot.send_chat_action(chat_id=message.chat.id, action="upload_voice")
    file = stream.input_stream.stream().read(-1)
    
    formatted = ""
    if len(info['artists']) > 1:
        for x in info['artists']:
            formatted += x['name'] + ", "
    else:
        formatted = info['artists'][0]['name']
    buttons = [
        [types.InlineKeyboardButton(text="🔽 open menu", callback_data=f"open_menu_{track[2]}")]
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.reply_audio(audio=BufferedInputFile(file, "audio.mp3"), performer=formatted, title=info['name'], thumbnail=URLInputFile(url=info["album"]["images"][0]["url"]), duration=int(info["duration_ms"]/1000), reply_markup=keyboard) #thumbnail=URLInputFile(url=str(info[3]))
    await photo.delete()


async def main():
    await dp.start_polling(bot)
    

if __name__ == "__main__":
    asyncio.run(main())



