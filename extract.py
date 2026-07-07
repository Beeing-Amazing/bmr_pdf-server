from fastapi import APIRouter

import extract_ec, extract_desp


router = APIRouter(prefix="/extract", tags=["files"])

router.include_router(extract_ec.router)
router.include_router(extract_desp.router)

