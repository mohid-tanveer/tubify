from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Annotated, Any
from fastapi import HTTPException, status, Depends, APIRouter, Response, Cookie
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, StringConstraints
import re
from databases import Database
import os
from dotenv import load_dotenv
from email_service import send_verification_email, send_password_reset_email
import httpx
from database import database
import urllib.parse

load_dotenv()


# cookie utilities
def set_auth_cookies(response: Response, tokens: Dict[str, str]) -> None:
    # get frontend url from environment for cookie domain
    frontend_url = os.getenv("FRONTEND_URL")
    domain = frontend_url.split("://")[1].split(":")[0] if frontend_url else None
    is_dev = os.getenv("DEV_MODE", "false").lower() == "true"

    cookie_settings = {
        "httponly": True,
        "secure": True,
        "samesite": "lax",
        "domain": None,
        "path": "/",
        "max_age": 7200,  # 2 hours for access token
    }

    response.set_cookie(
        key="access_token", value=tokens["access_token"], **cookie_settings
    )

    # different max_age for refresh token
    refresh_cookie_settings = {**cookie_settings, "max_age": 2592000}  # 30 days
    response.set_cookie(
        key="refresh_token", value=tokens["refresh_token"], **refresh_cookie_settings
    )


def clear_auth_cookies(response: Response) -> None:
    # get frontend url from environment for cookie domain
    frontend_url = os.getenv("FRONTEND_URL")
    domain = frontend_url.split("://")[1].split(":")[0] if frontend_url else None

    cookie_settings = {"domain": domain if domain != "localhost" else None, "path": "/"}

    response.delete_cookie(key="access_token", **cookie_settings)
    response.delete_cookie(key="refresh_token", **cookie_settings)


# create router
router = APIRouter(prefix="/api/auth", tags=["auth"])

# password validation regex
PASSWORD_PATTERN = r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&+])[A-Za-z\d@$!%*#?&+]{8,}$"

# security config
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
    bcrypt__ident="2b",
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# JWT config
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 2
REFRESH_TOKEN_EXPIRE_DAYS = 30


# models
class UserBase(BaseModel):
    email: EmailStr
    username: Annotated[str, StringConstraints(min_length=3, max_length=50)]


class UserCreate(UserBase):
    password: Annotated[str, StringConstraints(min_length=8)]


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class User(BaseModel):
    id: int
    username: str
    email: str
    is_email_verified: bool


# password and token utilities
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password(password: str) -> bool:
    return bool(re.match(PASSWORD_PATTERN, password))


def create_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def create_tokens(username: str) -> Dict[str, str]:
    access_token_expires = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    access_token = create_token(
        data={"sub": username, "type": "access"}, expires_delta=access_token_expires
    )
    refresh_token = create_token(
        data={"sub": username, "type": "refresh"}, expires_delta=refresh_token_expires
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


# get database instance
def get_db():
    return database


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    access_token: Optional[str] = Cookie(None),
    database: Database = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # try to get token from cookie if not provided in header
        token_to_use = token or access_token
        if not token_to_use:
            raise credentials_exception

        payload = jwt.decode(token_to_use, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        token_data = TokenData(username=username)
    except JWTError as e:
        raise credentials_exception
    except Exception as e:
        raise credentials_exception

    user = await database.fetch_one(
        "SELECT * FROM users WHERE username = :username",
        values={"username": token_data.username},
    )
    if user is None:
        raise credentials_exception
    return User(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        is_email_verified=user["is_email_verified"],
    )


# email verification
def generate_verification_token() -> str:
    return os.urandom(32).hex()


async def verify_email(token: str, database: Database) -> bool:
    user = await database.fetch_one(
        """
        UPDATE users 
        SET is_email_verified = TRUE, 
            email_verification_token = NULL 
        WHERE email_verification_token = :token 
        RETURNING *
        """,
        values={"token": token},
    )
    return user is not None


# authentication endpoints
@router.post("/register", response_model=Token)
async def register(
    user: UserCreate, response: Response, database: Database = Depends(get_db)
):
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
    RETURNING id
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

    # execute the query and get the user ID
    result = await database.fetch_one(query, values)
    user_id = result["id"]

    # create profile for the new user
    default_avatar = (
        f"https://ui-avatars.com/api/?name={urllib.parse.quote(user.username)}"
    )
    await database.execute(
        """
        INSERT INTO profiles (user_id, bio, profile_picture)
        VALUES (:user_id, :bio, :profile_picture)
        """,
        values={
            "user_id": user_id,
            "bio": "",
            "profile_picture": default_avatar,
        },
    )

    # send verification email
    await send_verification_email(user.email, verification_token)

    # set cookies
    set_auth_cookies(response, tokens)
    return tokens


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    response: Response = None,
    database: Database = Depends(get_db),
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

        return tokens

    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login",
        )


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=Token)
async def refresh_token(
    response: Response,
    refresh_token: str = Cookie(None, alias="refresh_token"),
    database: Database = Depends(get_db),
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
        return tokens

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not refresh tokens",
        )


@router.get("/verify-email/{token}")
async def verify_email_endpoint(token: str, database: Database = Depends(get_db)):
    # first check if the token exists
    user = await database.fetch_one(
        "SELECT * FROM users WHERE email_verification_token = :token",
        values={"token": token},
    )

    # if no user found with this token
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    # if user is already verified
    if user["is_email_verified"]:
        return {"message": "Email already verified"}

    try:
        # update the user's verification status
        await database.execute(
            """
            UPDATE users 
            SET is_email_verified = TRUE, 
                email_verification_token = NULL 
            WHERE email_verification_token = :token
            """,
            values={"token": token},
        )

        # return success message
        return {"message": "Email verified successfully"}
    except Exception as e:
        print(f"Error verifying email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify email",
        )


@router.post("/reset-password/request")
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


@router.post("/reset-password/{token}")
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


@router.post("/resend-verification")
async def resend_verification_email_endpoint(
    current_user: User = Depends(get_current_user),
    access_token: str = Cookie(None, alias="access_token"),
    database: Database = Depends(get_db),
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


@router.get("/check-username/{username}")
async def check_username(username: str, database: Database = Depends(get_db)):
    # check if username exists
    existing_user = await database.fetch_one(
        "SELECT username FROM users WHERE username = :username",
        values={"username": username},
    )
    return {"available": existing_user is None}


@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/google")
async def google_login():
    url = f"https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "redirect_uri": f"{os.getenv('FRONTEND_URL')}/auth/google/callback",
        "response_type": "code",
        "scope": "email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    return {"url": auth_url}


@router.get("/google/callback")
async def google_callback(
    code: str, response: Response, database: Database = Depends(get_db)
):
    try:
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "redirect_uri": f"{os.getenv('FRONTEND_URL')}/auth/google/callback",
            "grant_type": "authorization_code",
            "code": code,
        }

        # skip ssl verification in dev mode
        verify_ssl = os.getenv("DEV_MODE", "false").lower() != "true"
        async with httpx.AsyncClient(verify=verify_ssl) as client:
            token_response = await client.post(token_url, data=data)
            token_data = token_response.json()

            headers = {"Authorization": f"Bearer {token_data['access_token']}"}
            user_info_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo", headers=headers
            )
            user_info = user_info_response.json()

            # check if user exists
            user = await database.fetch_one(
                "SELECT * FROM users WHERE oauth_provider = 'google' AND oauth_id = :oauth_id",
                values={"oauth_id": user_info["id"]},
            )

            if not user:
                # create username from email
                username = user_info["email"].split("@")[0]
                # create new user with tokens using username
                tokens = await create_tokens(username)
                await database.execute(
                    """
                    INSERT INTO users (
                        username, email, oauth_provider, oauth_id, is_email_verified,
                        access_token, refresh_token, access_token_expires_at, refresh_token_expires_at
                    ) VALUES (
                        :username, :email, 'google', :oauth_id, true,
                        :access_token, :refresh_token, :access_expires, :refresh_expires
                    )
                    """,
                    {
                        "username": username,
                        "email": user_info["email"],
                        "oauth_id": user_info["id"],
                        "access_token": tokens["access_token"],
                        "refresh_token": tokens["refresh_token"],
                        "access_expires": datetime.now(timezone.utc)
                        + timedelta(hours=2),
                        "refresh_expires": datetime.now(timezone.utc)
                        + timedelta(days=30),
                    },
                )
            else:
                # create new tokens for existing user
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
                    {
                        "access_token": tokens["access_token"],
                        "refresh_token": tokens["refresh_token"],
                        "access_expires": datetime.now(timezone.utc)
                        + timedelta(hours=2),
                        "refresh_expires": datetime.now(timezone.utc)
                        + timedelta(days=30),
                        "user_id": user["id"],
                    },
                )

            # set cookies
            set_auth_cookies(response, tokens)
            return {"message": "Authentication successful", "tokens": tokens}

    except Exception as e:
        print(f"Google OAuth error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate with Google: {str(e)}",
        )


@router.get("/github")
async def github_login():
    url = "https://github.com/login/oauth/authorize"
    params = {
        "client_id": os.getenv("GITHUB_CLIENT_ID"),
        "redirect_uri": f"{os.getenv('FRONTEND_URL')}/auth/github/callback",
        "scope": "user:email",
    }
    auth_url = f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    return {"url": auth_url}


@router.get("/github/callback")
async def github_callback(
    code: str, response: Response, database: Database = Depends(get_db)
):
    try:
        token_url = "https://github.com/login/oauth/access_token"
        data = {
            "client_id": os.getenv("GITHUB_CLIENT_ID"),
            "client_secret": os.getenv("GITHUB_CLIENT_SECRET"),
            "code": code,
            "redirect_uri": f"{os.getenv('FRONTEND_URL')}/auth/github/callback",
        }
        headers = {"Accept": "application/json"}

        # skip ssl verification in dev mode
        verify_ssl = os.getenv("DEV_MODE", "false").lower() != "true"
        async with httpx.AsyncClient(verify=verify_ssl) as client:
            token_response = await client.post(token_url, json=data, headers=headers)
            token_data = token_response.json()

            if "error" in token_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"GitHub OAuth error: {token_data.get('error_description', token_data['error'])}",
                )

            if "access_token" not in token_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No access token received from GitHub",
                )

            # get user info
            user_headers = {"Authorization": f"Bearer {token_data['access_token']}"}
            user_response = await client.get(
                "https://api.github.com/user", headers=user_headers
            )
            user_info = user_response.json()

            # get email
            emails_response = await client.get(
                "https://api.github.com/user/emails", headers=user_headers
            )
            emails = emails_response.json()

            # find primary email
            primary_email = None
            for email in emails:
                if isinstance(email, dict) and email.get("primary"):
                    primary_email = email.get("email")
                    break

            if not primary_email:
                # generate temporary email using username
                primary_email = f"{user_info['login']}@temp.tubify.com"

            # check if user exists
            user = await database.fetch_one(
                "SELECT * FROM users WHERE oauth_provider = 'github' AND oauth_id = :oauth_id",
                values={"oauth_id": str(user_info["id"])},
            )

            if not user:
                # create new user
                tokens = await create_tokens(user_info["login"])
                await database.execute(
                    """
                    INSERT INTO users (
                        username, email, oauth_provider, oauth_id, is_email_verified,
                        access_token, refresh_token, access_token_expires_at, refresh_token_expires_at
                    ) VALUES (
                        :username, :email, 'github', :oauth_id, true,
                        :access_token, :refresh_token, :access_expires, :refresh_expires
                    )
                    """,
                    {
                        "username": user_info["login"],
                        "email": primary_email,
                        "oauth_id": str(user_info["id"]),
                        "access_token": tokens["access_token"],
                        "refresh_token": tokens["refresh_token"],
                        "access_expires": datetime.now(timezone.utc)
                        + timedelta(hours=2),
                        "refresh_expires": datetime.now(timezone.utc)
                        + timedelta(days=30),
                    },
                )
            else:
                # create new tokens for existing user
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
                    {
                        "access_token": tokens["access_token"],
                        "refresh_token": tokens["refresh_token"],
                        "access_expires": datetime.now(timezone.utc)
                        + timedelta(hours=2),
                        "refresh_expires": datetime.now(timezone.utc)
                        + timedelta(days=30),
                        "user_id": user["id"],
                    },
                )

            # set cookies
            set_auth_cookies(response, tokens)
            return {"message": "Authentication successful", "tokens": tokens}

    except Exception as e:
        print(f"GitHub OAuth error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate with GitHub: {str(e)}",
        )
