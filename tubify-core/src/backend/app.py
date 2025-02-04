from fastapi import FastAPI
import uvicorn
from dotenv import load_dotenv
import os, ssl

# load environment variables
load_dotenv()

# initialize fastapi app
app = FastAPI()


# enable SSL in fastapi
context = ssl.create_default_context(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(os.getenv("CERT_FILE"), os.getenv("KEY_FILE"))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, ssl_context=context)
