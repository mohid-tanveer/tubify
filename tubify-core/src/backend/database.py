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

    try:
        # initialize database with schema if not already initialized
        try:
            with open("schema.sql", "r") as schema_file:
                schema = schema_file.read()
                statements = [
                    stmt.strip() for stmt in schema.split(";") if stmt.strip()
                ]
                for statement in statements:
                    if statement:
                        await database.execute(statement)
            print("***schema initialized***")
        except Exception as e:
            print(f"error initializing schema: {str(e)}")
            raise e

        yield
    finally:
        # disconnect from database on shutdown
        await database.disconnect()
        print("***database disconnected***")
