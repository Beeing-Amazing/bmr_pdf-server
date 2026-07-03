from typing import BinaryIO
from collections import defaultdict

from fastapi import APIRouter, Depends, UploadFile, File

import pdfplumber

import utils
from utils import authenticate


router = APIRouter(prefix="/extract", tags=["files","pdf","table-extract"])


@router.post("/ec")
def extract_ec(file: UploadFile = File(...), user: str = Depends(authenticate)):
    return extract_ec_file(file.file)

def extract_ec_file(pdf_file: BinaryIO):
    """
    Parse EC pdf files. Discard header on all pages.
    Extract tables page by page using predetermined column positions.

    :returns: List of all found rows
    """
    out = []
    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            crop = page.crop((20,240,page.width-24,page.height-200))
            # crop.to_image(resolution=150).save(f"crop_ec_{page_num:03}.png",format="PNG")
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
            # clean parsed table
            idxs = []
            for i, row in enumerate(result):
                row = ["" if cell is None else cell for cell in row] # if parse fails handle edge cases

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

            # show debug crop
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
            # im.save(f"debug_ec_{page_num:03}.png")

            out.append(filter)

    flattened = []
    for page in out:
        for row in page:
            flattened.append(row)
    return { "extract_ec" : flattened }


@router.post("/despiece")
def extract_desp(file: UploadFile = File(...), user: str = Depends(authenticate)):
    return extract_desp_file(file.file)

def extract_desp_file(pdf_file: BinaryIO):
    """
    Parse DESP pdf files. Discard header on all pages.
    Extract tables page by page using row positional grouping.

    :returns: List of all found rows
    """
    out = []
    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            crop = page.crop((30,100,page.width-24,page.height-32))
            # crop.to_image(resolution=150).save(f"crop_desp_{page_num:03}.png",format="PNG")

            # parse using detected words instead
            words = crop.extract_words(
                x_tolerance=8,
                y_tolerance=3,
                keep_blank_chars=True,
            )

            # group by row
            rows = defaultdict(list)
            for w in words:
                key = round(w["top"] / 3)   # ~3pts diff
                rows[key].append(w)         # key is grouped x coords

            for row in rows.values():
                row.sort(key=lambda w: w["x0"])
                out.append([w["text"] for w in row])
    return { "extract_desp": out }

