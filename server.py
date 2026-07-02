import os
from pathlib import Path
from typing import BinaryIO
from secrets import compare_digest

from fastapi import Depends, FastAPI, UploadFile, File, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

import pdfplumber


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


app = FastAPI(
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"], 
)
app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,
    compresslevel=5
)

# AUTH
# ---


security = HTTPBasic()

env = load_dotenv(".env")
USER = env["USER"] if "USER" in env.keys() else None
PASSWORD = env["PASSWORD"] if "PASSWORD" in env.keys() else None

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


# ENDPOINTS
# ---

@app.post("/extract/ec")
def extract_ec(file: UploadFile = File(...), user: str = Depends(authenticate)):
    return extract_ec_file(file.file)

def extract_ec_file(pdf_file: BinaryIO):
    out = []
    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            if page_num == 0:
                crop = page.crop((20,240,page.width-24,page.height-200))
                # crop.to_image(resolution=150).save("crop.png",format="PNG")
                explicit_lines = [26,80,120,400,455,504,538,page.width-25]

                result = crop.extract_table(
                    table_settings={
                        "vertical_strategy":"explicit",
                        "horizontal_strategy":"text",
                        "explicit_vertical_lines":explicit_lines,
                        # "min_words_horizontal":1,
                        "join_y_tolerance":8,
                    }
                )
                idxs = []
                for i, row in enumerate(result):
                    if not any(s.strip() for s in row):
                        idxs.append(i)
                    elif any(s.strip(" ") for s in row[-3:]):
                        qt, prec, tot = row[-3:]
                        qt = qt.lower().strip().removesuffix("un").strip().replace(",",".")
                        prec = prec.strip().replace(",",".")
                        tot = tot.strip().replace(",",".").replace(" ","")

                        row[-3:] = [qt,prec,tot]

                remove = set(idxs)
                filter = [x for i, x in enumerate(result) if i not in remove]

                # # show debug crop
                # im = crop.to_image(resolution=150)
                # im.debug_tablefinder(
                #     table_settings={
                #         "vertical_strategy": "explicit",
                #         "horizontal_strategy": "text",
                #         "explicit_vertical_lines": explicit_lines,
                #         # "min_words_horizontal":1,
                #         "join_y_tolerance":8,
                #     }
                # )
                # im.save("debug.png")

            else:
                ...
            out.append(filter)

    return out


@app.post("/extract/despiece")
def extract_desp(file: UploadFile = File(...), user: str = Depends(authenticate)):
    return extract_desp_file(file.file)

def extract_desp_file(pdf_file: BinaryIO):
    with pdfplumber.open(pdf_file) as pdf:
        ...
    return None

