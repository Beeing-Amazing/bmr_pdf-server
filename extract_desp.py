from typing import BinaryIO
from collections import defaultdict

from fastapi import APIRouter, Depends, UploadFile, File
import pdfplumber

import utils
from utils import authenticate

router = APIRouter(prefix="/desp", tags=["desp","pdf","table-extract"])


@router.post("/table")
async def extract_desp(file: UploadFile = File(...), user: str = Depends(authenticate)):
    return extract_desp_file(file.file)

def extract_desp_file(pdf_file: BinaryIO):
    """
    Parse DESP pdf files. Discard header and footer on all pages.
    Extract tables page by page using row positional grouping.
    Keep columns consistent inside content using running average for column center clustering.

    :returns: List of rows as structured dicts with numbered column names
    """
    out = []
    all_rows = []
    centers = []
    with pdfplumber.open(pdf_file) as pdf:
        xTOL = 12
        for page in pdf.pages:
            crop = page.crop((30, 100, page.width - 24, page.height - 32))
            words = crop.extract_words(
                x_tolerance=4,
                y_tolerance=3,
                keep_blank_chars=True,
            )

            # group by row
            rows = defaultdict(list)
            for w in words:
                rows[round(w["top"] / 3)].append(w)
            for row in rows.values():
                row.sort(key=lambda w: w["x0"])

            all_rows.extend(rows.values())

            # compute column centers
            for row in rows.values():
                row_text = " ".join(w["text"] for w in row)
                if row_text.startswith(("OS ", "RMO ")):
                    continue

                for w in row:
                    x = w["x0"]
                    for i, c in enumerate(centers):
                        if abs(x - c) <= xTOL:
                            # update running average
                            centers[i] = (centers[i] + x) / 2
                            break
                    else:
                        centers.append(x)
        centers.sort()

        def nearest_col(x):
            return min(range(len(centers)), key=lambda i: abs(x - centers[i]))
        
        # dict output format
        seen_headers = set()
        for row in all_rows:
            row_text = " ".join(w["text"] for w in row)
            row_dict = {}

            if row_text.startswith(("OS ", "RMO ")):
                for i, w in enumerate(row):
                    row_dict[f"header_row_col_{i}"] = w["text"]
                # filter deduplicates
                row_tuple = tuple(sorted(row_dict.items()))
                if row_tuple not in seen_headers:
                    seen_headers.add(row_tuple)
                    out.append(row_dict)
            else:
                for w in row:
                    key = f"col_{nearest_col(w['x0'])}"
                    if key in row_dict:
                        row_dict[key] += " " + w["text"]
                    else:
                        row_dict[key] = w["text"]
                out.append(row_dict)

        formatted_out = []
        for row in out:
            if not formatted_out or "header_row_col_0" in row:
                formatted_out.append([])
            formatted_out[-1].append(row)

    return {"extract_desp": formatted_out}
