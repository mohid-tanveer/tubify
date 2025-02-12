from fastapi import FastAPI, HTTPException, Depends, status, Response, Cookie
from dotenv import load_dotenv
import os, ssl, httpx, uvicorn
from databases import Database
from sqlalchemy import create_engine, MetaData
from fastapi.middleware.cors import CORSMiddleware
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError
from auth import router as auth_router
from spotify_auth import router as spotify_router
from database import database, lifespan

# load environment variables
load_dotenv()

# initialize fastapi app with database lifespan
app = FastAPI(lifespan=lifespan)

# development mode flag (set to False in production)
DEV_MODE = os.getenv("DEV_MODE").lower() == "true"

# OAuth configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# enable SSL in fastapi
context = ssl.create_default_context()
if DEV_MODE:
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
context.load_cert_chain(os.getenv("CERT_FILE"), os.getenv("KEY_FILE"))

# add routers
app.include_router(auth_router)
app.include_router(spotify_router)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        ssl_keyfile=os.getenv("KEY_FILE"),
        ssl_certfile=os.getenv("CERT_FILE"),
        ssl_verify=not DEV_MODE,
    )
