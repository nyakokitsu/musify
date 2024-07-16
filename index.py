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

spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id="bb3126fb131d4ad08a3b07dad8c090f9", client_secret="16f702b0e3b94234ac8bb4b2b64189c8"))


logging.basicConfig(level=logging.INFO)

load_dotenv() 
bot = Bot(token=os.getenv("TOKEN"), parse_mode='HTML')

dp = Dispatcher()

@dp.inline_query(F.query.startswith("search "))
async def search(inline_query: InlineQuery):
    results = spotify.search(q=inline_query.query.replace("search ", ""))
    searchresults = []
    #print(results)
    for song in results['tracks']['items']:
        artists_raw = []
        for data in song["artists"]:
            artists_raw.append(sanitize_data(data["name"]))
        artists = ", ".join(artists_raw)
        searchresults.append(InlineQueryResultArticle(
            id=str(song['id']),  # индекс элемента в list
            title=song['name'],
            description=artists,
            thumbnail_url=song["album"]["images"][0]['url'],
            input_message_content=InputTextMessageContent(message_text=f"https://open.spotify.com/track/{song['id']}")
        ))
    await inline_query.answer(searchresults, is_personal=True)
    

# Хэндлер на команду /start
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
    await message.reply_audio(audio=BufferedInputFile(file, "audio.mp3"), performer=formatted, title=info['name'], thumbnail=URLInputFile(url=info["album"]["images"][0]["url"]), duration=int(info["duration_ms"]/1000)) #thumbnail=URLInputFile(url=str(info[3]))
    await photo.delete()


# Запуск процесса поллинга новых апдейтов
async def main():
    await dp.start_polling(bot)
    

if __name__ == "__main__":
    asyncio.run(main())



