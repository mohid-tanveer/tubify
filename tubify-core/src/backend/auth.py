from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Annotated, Any
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, StringConstraints
import re
from databases import Database
import os
from dotenv import load_dotenv

load_dotenv()

# password validation regex
PASSWORD_PATTERN = r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&+])[A-Za-z\d@$!%*#?&+]{8,}$"

# security config
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
    bcrypt__ident="2b",
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

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


class UserInDB(BaseModel):
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


async def get_current_user(
    token: str = Depends(oauth2_scheme), database: Any = None
) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        print(f"looking up user with identifier: {username}")
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    if database:
        user = await database.fetch_one(
            "SELECT * FROM users WHERE username = :username",
            values={"username": token_data.username},
        )
        print(f"found user: {user}")
        if user is None:
            raise credentials_exception
        return UserInDB(
            id=user["id"],
            username=user["username"],
            email=user["email"],
            is_email_verified=user["is_email_verified"],
        )
    raise credentials_exception


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
