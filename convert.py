from typing import BinaryIO
from io import BytesIO
from pathlib import Path
from urllib.parse import quote


from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from weasyprint import HTML

import utils
from utils import authenticate

router = APIRouter(prefix="/convert", tags=["ec","pdf","files"])


@router.post("/html-to-pdf")
async def convert_to_pdf(
    file: UploadFile = File(...),
    user: str = Depends(authenticate)
):
    pdf_file = convert(file.file)
    filename = Path(file.filename).stem + ".pdf"
    encoded_filename = quote(filename)

    return StreamingResponse(
        pdf_file,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{filename}\"; "
                f"filename*=UTF-8''{encoded_filename}"
            )
        }
    )


def convert(html_file: BinaryIO) -> BytesIO:
    """
    Convert uploaded HTML file to PDF.

    :param html_file: Binary file object containing HTML.
    :returns: BytesIO containing generated PDF.
    """

    pdf_bytes = HTML(
        file_obj=html_file
    ).write_pdf()

    pdf_file = BytesIO(pdf_bytes)
    pdf_file.seek(0)

    return pdf_file
