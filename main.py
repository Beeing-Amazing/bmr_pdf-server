import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

import extract, utils


app = FastAPI(
    docs_url=None, # no docs
    redoc_url=None,
    openapi_url=None
)

# CORS
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

# LOGGING
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000

    utils.logger.info(
        '%s %s -> %d (%.2f ms)',
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )

    return response


# ENDPOINTS
# ---

app.include_router(extract.router)

