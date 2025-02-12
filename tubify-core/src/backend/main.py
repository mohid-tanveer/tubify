from fastapi import FastAPI, HTTPException, Depends, status, Response, Cookie
from dotenv import load_dotenv
import os, ssl, httpx, uvicorn
from databases import Database
from sqlalchemy import create_engine, MetaData
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi_csrf_protect import CsrfProtect
from fastapi_csrf_protect.exceptions import CsrfProtectError
from auth import (
    UserCreate,
    Token,
    get_password_hash,
    verify_password,
    create_tokens,
    get_current_user,
    generate_verification_token,
    validate_password,
    verify_email,
    UserInDB,
)
from email_service import send_verification_email, send_password_reset_email
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime, timedelta, timezone
from fastapi.security import APIKeyCookie
from fastapi.responses import JSONResponse
from pydantic_settings import BaseSettings

# load environment variables
load_dotenv()

# initialize fastapi app and database
database = Database(os.getenv("DATABASE_URL"))
metadata = MetaData()
engine = create_engine(os.getenv("DATABASE_URL"))

# development mode flag (set to False in production)
DEV_MODE = os.getenv("DEV_MODE").lower() == "true"

# OAuth configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL")

# cookie settings
COOKIE_NAME = "session"
cookie_scheme = APIKeyCookie(name=COOKIE_NAME, auto_error=False)


def set_auth_cookies(response: Response, tokens: dict):
    """Set secure HTTP-only cookies for authentication"""
    # set access token cookie
    response.set_cookie(
        key="access_token",
        value=tokens["access_token"],
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7200,  # 2 hours
        path="/",
        domain="localhost",  # explicitly set domain for local development
    )

    # set refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=2592000,  # 30 days
        path="/",
        domain="localhost",  # explicitly set domain for local development
    )


def clear_auth_cookies(response: Response):
    """Clear authentication cookies"""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")


# set database to load on startup and close on shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.connect()
    print("***database connected***")
    # initialize database with schema if not already initialized
    try:
        with open("schema.sql", "r") as schema_file:
            schema = schema_file.read()
            statements = [stmt.strip() for stmt in schema.split(";") if stmt.strip()]
            for statement in statements:
                if statement:
                    await database.execute(statement)
        print("***schema initialized***")
    except Exception as e:
        print(f"Error initializing schema: {str(e)}")
        raise e

    yield
    await database.disconnect()
    print("***database disconnected***")


app = FastAPI(lifespan=lifespan)

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


class CsrfSettings(BaseSettings):
    secret_key: str = os.getenv("JWT_SECRET_KEY")
    cookie_samesite: str = "lax"


@CsrfProtect.load_config
def get_csrf_config():
    return CsrfSettings()


@app.exception_handler(CsrfProtectError)
async def csrf_protect_exception_handler(request, exc):
    print("CSRF token missing or invalid")
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": "CSRF token missing or invalid"},
    )


# authentication endpoints
@app.post("/api/auth/register", response_model=Token)
async def register(user: UserCreate, response: Response):
    # check if username exists
    existing_user = await database.fetch_one(
        "SELECT username FROM users WHERE username = :username",
        values={"username": user.username},
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # check if email exists
    existing_email = await database.fetch_one(
        "SELECT email FROM users WHERE email = :email", values={"email": user.email}
    )
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # validate password
    if not validate_password(user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters and contain at least one letter, one number, and one special character",
        )

    # create user
    verification_token = generate_verification_token()
    hashed_password = get_password_hash(user.password)
    tokens = await create_tokens(user.username)

    query = """
    INSERT INTO users (username, email, password_hash, email_verification_token,
                      access_token, refresh_token, access_token_expires_at, refresh_token_expires_at)
    VALUES (:username, :email, :password_hash, :verification_token,
            :access_token, :refresh_token, :access_expires, :refresh_expires)
    """
    values = {
        "username": user.username,
        "email": user.email,
        "password_hash": hashed_password,
        "verification_token": verification_token,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "access_expires": datetime.now(timezone.utc) + timedelta(hours=2),
        "refresh_expires": datetime.now(timezone.utc) + timedelta(days=30),
    }

    await database.execute(query, values)

    # send verification email
    await send_verification_email(user.email, verification_token)

    # set cookies
    set_auth_cookies(response, tokens)
    return tokens


@app.post("/api/auth/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), response: Response = None
):
    try:
        # check if user exists
        user = await database.fetch_one(
            """
            SELECT * FROM users 
            WHERE username = :username OR email = :username
            """,
            values={"username": form_data.username},
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username/email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # verify password
        if not verify_password(form_data.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username/email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # create new tokens
        tokens = await create_tokens(user["username"])

        # update tokens in database
        await database.execute(
            """
            UPDATE users 
            SET access_token = :access_token,
                refresh_token = :refresh_token,
                access_token_expires_at = :access_expires,
                refresh_token_expires_at = :refresh_expires,
                last_login = CURRENT_TIMESTAMP
            WHERE id = :user_id
            """,
            values={
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "access_expires": datetime.now(timezone.utc) + timedelta(hours=2),
                "refresh_expires": datetime.now(timezone.utc) + timedelta(days=30),
                "user_id": user["id"],
            },
        )

        # set cookies
        if response:
            set_auth_cookies(response, tokens)
            print("Setting auth cookies:", tokens)

        return tokens

    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login",
        )


@app.post("/api/auth/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"message": "Logged out successfully"}


@app.post("/api/auth/refresh", response_model=Token)
async def refresh_token(
    response: Response, refresh_token: str = Cookie(None, alias="refresh_token")
):
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
        )

    try:
        user = await database.fetch_one(
            "SELECT * FROM users WHERE refresh_token = :token",
            values={"token": refresh_token},
        )

        if not user or datetime.now(timezone.utc) > user["refresh_token_expires_at"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        tokens = await create_tokens(user["username"])

        # update tokens in database
        await database.execute(
            """
            UPDATE users 
            SET access_token = :access_token,
                refresh_token = :refresh_token,
                access_token_expires_at = :access_expires,
                refresh_token_expires_at = :refresh_expires
            WHERE id = :user_id
            """,
            values={
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "access_expires": datetime.now(timezone.utc) + timedelta(hours=2),
                "refresh_expires": datetime.now(timezone.utc) + timedelta(days=30),
                "user_id": user["id"],
            },
        )

        # set new cookies
        set_auth_cookies(response, tokens)
        return {"message": "Tokens refreshed successfully"}

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not refresh tokens",
        )


@app.get("/api/auth/verify-email/{token}")
async def verify_email_endpoint(token: str):
    print(f"Attempting to verify email with token: {token}")

    # check if token exists in database
    user_before = await database.fetch_one(
        "SELECT * FROM users WHERE email_verification_token = :token OR (email_verification_token IS NULL AND is_email_verified = TRUE)",
        values={"token": token},
    )
    print(f"User before verification: {user_before}")

    if user_before and user_before["is_email_verified"]:
        return {"message": "Email already verified"}

    success = await verify_email(token, database)
    print(f"Verification success: {success}")

    # check user state after verification
    user_after = await database.fetch_one(
        "SELECT * FROM users WHERE id = :id",
        values={"id": user_before["id"] if user_before else None},
    )
    print(f"User after verification: {user_after}")

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )
    return {"message": "Email verified successfully"}


@app.post("/api/auth/reset-password/request")
async def request_password_reset(email: str):
    user = await database.fetch_one(
        "SELECT * FROM users WHERE email = :email", values={"email": email}
    )

    if not user:
        # return success even if email doesn't exist to prevent email enumeration
        return {
            "message": "If an account exists with this email, you will receive a password reset link"
        }

    reset_token = generate_verification_token()

    # store the reset token and its expiry
    await database.execute(
        """
        UPDATE users 
        SET password_reset_token = :token,
            password_reset_expires = :expires
        WHERE email = :email
        """,
        values={
            "token": reset_token,
            "expires": datetime.now(timezone.utc) + timedelta(hours=1),
            "email": email,
        },
    )

    # send password reset email
    await send_password_reset_email(email, reset_token)

    return {
        "message": "If an account exists with this email, you will receive a password reset link"
    }


@app.post("/api/auth/reset-password/{token}")
async def reset_password(token: str, password: str):
    # find user with valid reset token
    user = await database.fetch_one(
        """
        SELECT * FROM users 
        WHERE password_reset_token = :token 
        AND password_reset_expires > :now
        """,
        values={"token": token, "now": datetime.now(timezone.utc)},
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # validate new password
    if not validate_password(password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters and contain at least one letter, one number, and one special character",
        )

    # update password and clear reset token
    hashed_password = get_password_hash(password)
    await database.execute(
        """
        UPDATE users 
        SET password_hash = :password_hash,
            password_reset_token = NULL,
            password_reset_expires = NULL
        WHERE id = :user_id
        """,
        values={"password_hash": hashed_password, "user_id": user["id"]},
    )

    return {"message": "Password has been reset successfully"}


# OAuth endpoints
@app.get("/api/auth/google")
async def google_login():
    return {
        "url": f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"response_type=code&"
        f"scope=email profile&"
        f"redirect_uri={FRONTEND_URL}/auth/google/callback"
    }


@app.get("/api/auth/google/callback")
async def google_callback(code: str, response: Response):
    # in development mode, SSL verification is disabled
    verify_ssl = not DEV_MODE
    if DEV_MODE:
        print("Warning: SSL verification is disabled (development mode)")

    async with httpx.AsyncClient(verify=verify_ssl) as client:
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": f"{FRONTEND_URL}/auth/google/callback",
        }
        print("Token request data:", token_data)

        try:
            token_response = await client.post(token_url, data=token_data)
            print("Token response status:", token_response.status_code)
            print("Token response body:", token_response.text)

            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to get access token: {token_response.text}",
                )

            token_data = token_response.json()
            if "access_token" not in token_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No access token in response",
                )

            access_token = token_data["access_token"]
            print(f"access_token: {access_token}")

            user_info = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if user_info.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to get user info: {user_info.text}",
                )

            google_user = user_info.json()
            google_id = google_user.get("id")

            if not google_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Could not get Google user ID",
                )

            # create or update user
            user = await database.fetch_one(
                """
                SELECT * FROM users 
                WHERE oauth_id = :oauth_id AND oauth_provider = 'google'
                """,
                values={"oauth_id": google_id},
            )

            if not user:
                # create username from email but remove domain
                username = google_user["email"].split("@")[0]
                tokens = await create_tokens(username)  # use username instead of email
                await database.execute(
                    """
                    INSERT INTO users (
                        email, username, oauth_provider, oauth_id,
                        is_email_verified, access_token, refresh_token,
                        access_token_expires_at, refresh_token_expires_at
                    ) VALUES (
                        :email, :username, 'google', :oauth_id,
                        TRUE, :access_token, :refresh_token,
                        :access_expires, :refresh_expires
                    )
                    """,
                    values={
                        "email": google_user["email"],
                        "username": username,
                        "oauth_id": google_id,
                        "access_token": tokens["access_token"],
                        "refresh_token": tokens["refresh_token"],
                        "access_expires": datetime.now(timezone.utc)
                        + timedelta(hours=2),
                        "refresh_expires": datetime.now(timezone.utc)
                        + timedelta(days=30),
                    },
                )
            else:
                tokens = await create_tokens(user["username"])
                await database.execute(
                    """
                    UPDATE users 
                    SET access_token = :access_token,
                        refresh_token = :refresh_token,
                        access_token_expires_at = :access_expires,
                        refresh_token_expires_at = :refresh_expires,
                        last_login = CURRENT_TIMESTAMP
                    WHERE id = :user_id
                    """,
                    values={
                        "access_token": tokens["access_token"],
                        "refresh_token": tokens["refresh_token"],
                        "access_expires": datetime.now(timezone.utc)
                        + timedelta(hours=2),
                        "refresh_expires": datetime.now(timezone.utc)
                        + timedelta(days=30),
                        "user_id": user["id"],
                    },
                )

            # Set auth cookies
            set_auth_cookies(response, tokens)
            return {"message": "Authentication successful"}

        except HTTPException:
            raise
        except Exception as e:
            print(f"Error in Google callback: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing Google callback: {str(e)}",
            )


@app.get("/api/auth/github")
async def github_login():
    return {
        "url": f"https://github.com/login/oauth/authorize?"
        f"client_id={GITHUB_CLIENT_ID}&"
        f"scope=user:email"
    }


@app.get("/api/auth/github/callback")
async def github_callback(code: str):
    # in development mode, SSL verification is disabled
    verify_ssl = not DEV_MODE
    if DEV_MODE:
        print("Warning: SSL verification is disabled (development mode)")

    async with httpx.AsyncClient(verify=verify_ssl) as client:
        # get access token
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        access_token = token_response.json()["access_token"]

        # get user info
        user_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"token {access_token}",
                "Accept": "application/json",
            },
        )
        github_user = user_response.json()

        # get user email
        emails_response = await client.get(
            "https://api.github.com/user/emails",
            headers={
                "Authorization": f"token {access_token}",
                "Accept": "application/json",
            },
        )
        primary_email = next(
            email["email"] for email in emails_response.json() if email["primary"]
        )

        # create or update user
        user = await database.fetch_one(
            """
            SELECT * FROM users 
            WHERE email = :email AND oauth_provider = 'github'
            """,
            values={"email": primary_email},
        )

        if not user:
            tokens = await create_tokens(github_user["login"])
            await database.execute(
                """
                INSERT INTO users (
                    email, username, oauth_provider, oauth_id,
                    is_email_verified, access_token, refresh_token,
                    access_token_expires_at, refresh_token_expires_at
                ) VALUES (
                    :email, :username, 'github', :oauth_id,
                    TRUE, :access_token, :refresh_token,
                    :access_expires, :refresh_expires
                )
                """,
                values={
                    "email": primary_email,
                    "username": github_user["login"],
                    "oauth_id": str(github_user["id"]),
                    "access_token": tokens["access_token"],
                    "refresh_token": tokens["refresh_token"],
                    "access_expires": datetime.now(timezone.utc) + timedelta(hours=2),
                    "refresh_expires": datetime.now(timezone.utc) + timedelta(days=30),
                },
            )
            return tokens
        else:
            tokens = await create_tokens(user["username"])
            await database.execute(
                """
                UPDATE users 
                SET access_token = :access_token,
                    refresh_token = :refresh_token,
                    access_token_expires_at = :access_expires,
                    refresh_token_expires_at = :refresh_expires,
                    last_login = CURRENT_TIMESTAMP
                WHERE id = :user_id
                """,
                values={
                    "access_token": tokens["access_token"],
                    "refresh_token": tokens["refresh_token"],
                    "access_expires": datetime.now(timezone.utc) + timedelta(hours=2),
                    "refresh_expires": datetime.now(timezone.utc) + timedelta(days=30),
                    "user_id": user["id"],
                },
            )
            return tokens


@app.get("/api/auth/me")
async def get_current_user_info(
    access_token: str = Cookie(None, alias="access_token"),
    refresh_token: str = Cookie(None, alias="refresh_token"),
):
    if not access_token and not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    try:
        if access_token:
            # pass the database instance when calling get_current_user
            user = await get_current_user(token=access_token, database=database)
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_email_verified": user.is_email_verified,
            }
        elif refresh_token:
            # try to refresh the token
            user = await database.fetch_one(
                "SELECT * FROM users WHERE refresh_token = :token",
                values={"token": refresh_token},
            )
            if (
                not user
                or datetime.now(timezone.utc) > user["refresh_token_expires_at"]
            ):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired refresh token",
                )
            return {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "is_email_verified": user["is_email_verified"],
            }
    except Exception as e:
        print(f"Error in get_current_user_info: {str(e)}")  # add logging
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )


@app.post("/api/auth/resend-verification")
async def resend_verification_email(
    current_user: UserInDB = Depends(get_current_user),
    access_token: str = Cookie(None, alias="access_token"),
):
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    if current_user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already verified"
        )

    try:
        # generate new verification token
        verification_token = generate_verification_token()

        # update user's verification token
        await database.execute(
            """
            UPDATE users 
            SET email_verification_token = :token
            WHERE id = :user_id
            """,
            values={"token": verification_token, "user_id": current_user.id},
        )

        # send new verification email
        await send_verification_email(current_user.email, verification_token)

        return {"message": "Verification email sent successfully"}
    except Exception as e:
        print(f"Error sending verification email: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email",
        )


@app.get("/api/auth/check-username/{username}")
async def check_username(username: str):
    # check if username exists
    existing_user = await database.fetch_one(
        "SELECT username FROM users WHERE username = :username",
        values={"username": username},
    )
    return {"available": existing_user is None}


# enable SSL in fastapi
context = ssl.create_default_context()
if DEV_MODE:
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
context.load_cert_chain(os.getenv("CERT_FILE"), os.getenv("KEY_FILE"))

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        ssl_keyfile=os.getenv("KEY_FILE"),
        ssl_certfile=os.getenv("CERT_FILE"),
        ssl_verify=not DEV_MODE,
    )
