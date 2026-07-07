from typing import BinaryIO
from collections import defaultdict

from fastapi import APIRouter, Depends, UploadFile, File
import pdfplumber

import utils
from utils import authenticate

router = APIRouter(prefix="/desp", tags=["desp","pdf","table-extract"])


@router.post("/table")
def extract_desp(file: UploadFile = File(...), user: str = Depends(authenticate)):
    return extract_desp_file(file.file)

def extract_desp_file(pdf_file: BinaryIO):
    """
    Parse DESP pdf files. Discard header and footer on all pages.
    Extract tables page by page using row positional grouping.
    Keep columns consistent inside content using running average for column center clustering.

    :returns: List of rows as structured dicts with numbered column names
    """
    out = []
    with pdfplumber.open(pdf_file) as pdf:
        xTOL = 12
        for page_num, page in enumerate(pdf.pages):
            crop = page.crop((30, 100, page.width - 24, page.height - 32))

            words = crop.extract_words(
                x_tolerance=4,
                y_tolerance=3,
                keep_blank_chars=True,
            )

            if not words:
                continue

            # group by row
            rows = defaultdict(list)
            for w in words:
                row_key = round(w["top"] / 3)
                rows[row_key].append(w)

            # page-wise centers
            centers = []
            for row in rows.values():
                row.sort(key=lambda w: w["x0"])
                row_text = " ".join(w["text"] for w in row)

                if any(row_text.startswith(x) for x in ["OS ", "RMO "]):
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

            def nearest_col(x, centers):
                return min(range(len(centers)), key=lambda i: abs(x - centers[i]))

            # dict output format
            for row in rows.values():
                row.sort(key=lambda w: w["x0"])
                row_text = " ".join(w["text"] for w in row)
                row_dict = {}

                if any(row_text.startswith(x) for x in ["OS ", "RMO "]):
                    # Special naming for OS rows
                    for i, w in enumerate(row):
                        row_dict[f"os_col_{i}"] = w["text"]
                else:
                    # discovered column centers
                    for w in row:
                        col = nearest_col(w["x0"], centers)
                        key = f"col_{col}"

                        if key in row_dict:
                            row_dict[key] += " " + w["text"]
                        else:
                            row_dict[key] = w["text"]
                out.append(row_dict)

    return { "extract_desp": out }

