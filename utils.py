import os
import time
import logging
from pathlib import Path
from secrets import compare_digest

from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi import HTTPException, Depends

# LOGGING
# ---

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("requests")


# ENV
# ---

def load_dotenv(dotenv : str | Path) -> dict:
    result = {}
    with open(dotenv, "r") as f:
        for line in f:
            line = line.strip()
            if line == "": continue
            words = line.split("=", maxsplit=1)
            if len(words) != 2: continue
            
            try:
               result[str(words[0])] = str(words[1].strip("\""))
            except TypeError:
                pass
    return result

env = load_dotenv(".env")


# AUTH
# ---

USER = env["USER"] if "USER" in env.keys() else None
PASSWORD = env["PASSWORD"] if "PASSWORD" in env.keys() else None

security = HTTPBasic()

def authenticate(
    credentials: HTTPBasicCredentials = Depends(security),
):
    username_ok = compare_digest(credentials.username, USER)
    password_ok = compare_digest(credentials.password, PASSWORD)

    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username

