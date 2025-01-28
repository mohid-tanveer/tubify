from flask import Flask
from datetime import timedelta
from flask_cors import CORS
from dotenv import load_dotenv
import os, ssl

# load environment variables
load_dotenv()

# initialize flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["TOKEN_EXPIRATION"] = timedelta(hours=1)

# enable CORS
CORS(
    app,
    origins=["https://127.0.0.1:3000", "https://localhost:3000"],
    supports_credentials=True,
)

# enable SSL
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain("localhost.pem", "localhost-key.pem")

# import and register blueprints
# from auth import auth_bp
# from spotify_auth import spotify_auth_bp

# app.register_blueprint(auth_bp)
# app.register_blueprint(spotify_auth_bp)

if __name__ == "__main__":
    app.run(ssl_context=context, debug=True)
