from fastapi import FastAPI, Request
import redis
import os
import spotipy
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
r = redis.Redis(host=os.getenv("REDIS_HOST"), port=int(os.getenv("REDIS_PORT")), db=0, password=os.getenv("REDIS_PWD"))
sp = spotipy.oauth2.SpotifyOAuth(client_id=os.getenv("SPOT_ID"), client_secret=os.getenv("SPOT_SECRET"), redirect_uri="https://musify.nyako.tk/auth/callback")


@app.get("/auth/callback")
def root(request: Request):
    params = request.query_params
    user = params['state']
    code = params['code']
    token = sp.get_access_token(code=code)
    token['state'] = user
    r.set(user, str(token))
    return 'You may close this page.'
