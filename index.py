import asyncio
import logging
import os
from re import Match
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import FSInputFile, URLInputFile, InlineQuery, InlineQueryResultAudio, InputTextMessageContent, InlineQueryResultArticle, BufferedInputFile
from aiogram.filters.command import Command
from aiogram import html
import glob
from dotenv import load_dotenv

from utils import sanitize_data
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from librespot.core import Session
from librespot.metadata import TrackId
from librespot.audio.decoders import AudioQuality, VorbisOnlyAudioQuality



session = Session.Builder().stored_file().create()
token = session.tokens().get("user-read-email")
is_premium = session.get_user_attribute("type") == "premium"
audio_quality = AudioQuality.VERY_HIGH if is_premium else AudioQuality.HIGH

load_dotenv() 
spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id=os.getenv("SPOT_ID"), client_secret=os.getenv("SPOT_SECRET")))


logging.basicConfig(level=logging.INFO)


bot = Bot(token=os.getenv("TOKEN"), parse_mode='HTML')

dp = Dispatcher()

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
    results = spotify.recommendations(seed_tracks=[inline_query.query.replace("recs ", "")])
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

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    buttons = [
        [types.InlineKeyboardButton(text="search", switch_inline_query_current_chat="search ")]
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.reply("Hey! I'm musify bot! I can help you to listen spotify music in telegram! Send me link to any spotify track or try searching.", reply_markup=keyboard)
    
@dp.message(F.text.regexp(r'^(https?://)?open\.spotify\.com/track/(?P<TrackID>[0-9a-zA-Z]{22})(\?si=.+?)?$').as_("track"))
async def send_welcome(message: types.Message, track: Match[str]):
    
    info = spotify.track(track_id=track[2])
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
        [types.InlineKeyboardButton(text="recommendations", switch_inline_query_current_chat=f"recs {track[2]}")]
    ]
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.reply_audio(audio=BufferedInputFile(file, "audio.mp3"), performer=formatted, title=info['name'], thumbnail=URLInputFile(url=info["album"]["images"][0]["url"]), duration=int(info["duration_ms"]/1000), reply_markup=keyboard) #thumbnail=URLInputFile(url=str(info[3]))
    await photo.delete()


async def main():
    await dp.start_polling(bot)
    

if __name__ == "__main__":
    asyncio.run(main())



