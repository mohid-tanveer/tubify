from fastapi import FastAPI
import uvicorn
from dotenv import load_dotenv
import os, ssl

# load environment variables
load_dotenv()

# initialize fastapi app
app = FastAPI()


# enable SSL in fastapi
context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
context.load_cert_chain(os.getenv("CERT_FILE"), os.getenv("KEY_FILE"))

# import and register blueprints
# from auth import auth_bp
# from spotify_auth import spotify_auth_bp

# app.register_blueprint(auth_bp)
# app.register_blueprint(spotify_auth_bp)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, ssl_context=context)
