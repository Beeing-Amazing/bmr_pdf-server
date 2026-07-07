from typing import BinaryIO
import re

from fastapi import APIRouter, Depends, UploadFile, File
import pdfplumber

import utils
from utils import authenticate

router = APIRouter(prefix="/ec", tags=["ec","pdf","table-extract"])


@router.post("/table")
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


ec_clean_header_cols = {
    "code": {"código","codigo","code","Código"},
    "item": {"item","ítem","Item"},
    "description": {"descrição","descriçao","descricão","descricao","Descrição"},
    "dimensions": {"dimensões","dimensoes","Dimensões"},
    "quantity": {"qt. un.","qt un", "qt. un", "qt un.","Qt. Un."},
    "price": {"preço","preco","Preço"},
    "total": {"total","tot.","Total"}
}
ec_rev_header_cols = {
    alias.lower(): final
    for final, aliases in ec_clean_header_cols.items()
    for alias in aliases
}

def clean_ec_header_colname(colname: str) -> str:
    col = colname.strip().lower()
    return ec_rev_header_cols.get(col, col)

def extract_ec_file(pdf_file: BinaryIO):
    """
    Parse EC pdf files. Discard header and footer on all pages.
    Extract tables page by page using predetermined column positions.

    :returns: List of rows as structured dicts with extracted column names
    """
    out = []
    with pdfplumber.open(pdf_file) as pdf:
        header_row_kw = ["Descrição","Preço"]
        header_row_cols = []
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

                if all(cell in row for cell in header_row_kw):
                    header_row_cols = header_row_cols or row
                    idxs_drop.append(i)
                if not any(s.strip() for s in row):
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

    # flatten pages
    flattened = []
    for page in out:
        for row in page:
            flattened.append(row)

    header_row_cols = [clean_ec_header_colname(x) for x in header_row_cols]
    # concat carry desc
    flattened = merge_wrapped_rows(flattened)

    return { "extract_ec": [dict(zip(header_row_cols,row)) for row in flattened] }


