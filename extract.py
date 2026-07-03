from typing import BinaryIO
from collections import defaultdict
import statistics
import re

from fastapi import APIRouter, Depends, UploadFile, File

import pdfplumber

import utils
from utils import authenticate


router = APIRouter(prefix="/extract", tags=["files","pdf","table-extract"])


@router.post("/ec")
def extract_ec(file: UploadFile = File(...), user: str = Depends(authenticate)):
    return extract_ec_file(file.file)

def is_number_like(s : str):
    return bool(re.match(r"^\s*-?\d+([.,]\d+)?\s*$", s))

def row_similarity(prev, curr):
    """
    Heuristic: decide if curr is a continuation of prev
    Criteria: is curr mostly empty and has no numeric data?
    """
    prev_nonempty = sum(bool(str(x).strip()) for x in prev)
    curr_nonempty = sum(bool(str(x).strip()) for x in curr)
    # has few filled columns
    sparse_curr = curr_nonempty <= 2
    # last columns (numeric)
    prev_tail = prev[-3:] if len(prev) >= 3 else []
    curr_tail = curr[-3:] if len(curr) >= 3 else []

    # has empty or partial numeric columns
    tail_empty = all(not str(x).strip() for x in curr_tail)
    return sparse_curr and tail_empty

def merge_wrapped_rows(rows):
    merged = []
    for i, row in enumerate(rows):
        if not merged:
            merged.append(row)
            continue
        prev = merged[-1]

        # detect overflow row
        if row_similarity(prev, row) and (i >= 2):
            # merge w safe concat
            new_row = []
            for a, b in zip(prev, row):
                a = a or ""
                b = b or ""
                new_row.append((a + " " + b).strip())

            merged[-1] = new_row
        else:
            merged.append(row)
    return merged


def extract_ec_file(pdf_file: BinaryIO):
    """
    Parse EC pdf files. Discard header on all pages.
    Extract tables page by page using predetermined column positions.

    :returns: List of all found rows
    """
    out = []
    with pdfplumber.open(pdf_file) as pdf:
        header_row_kw = ["Descrição","Preço"]
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
            idxs_drop = []
            for i, row in enumerate(result):
                row = ["" if cell is None else cell for cell in row] # if parse fails handle edge cases

                if not any(s.strip() for s in row):
                    idxs_drop.append(i)
                if (page_num > 0) and all(cell in row for cell in header_row_kw):
                    idxs_drop.append(i)
                elif any(s.strip() for s in row[-3:]):
                    qt, prec, tot = row[-3:]
                    qt = qt.lower().strip().removesuffix("un").strip().replace(",",".")
                    prec = prec.strip().replace(",",".")
                    tot = tot.strip().replace(",",".").replace(" ","")

                    result[i][-3:] = [qt,prec,tot]
            remove = set(idxs_drop)
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
    return { "extract_ec" : merge_wrapped_rows(flattened) }


@router.post("/desp")
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

