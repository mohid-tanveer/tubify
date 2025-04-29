from databases import Database
import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI

# load environment variables
load_dotenv()

# initialize database
database = Database(os.getenv("DATABASE_URL"))


# database lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # connect to database on startup
    await database.connect()
    print("***database connected***")

    yield

    # disconnect from database on shutdown
    await database.disconnect()
    print("***database disconnected***")
