import os
from typing import Annotated
from fastapi import FastAPI, Request, HTTPException, Query, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

# 1. Initialize FastAPI with metadata
app = FastAPI(
    title="JurisExtract",
    description="Professional Legal Data Extraction API for Business & Court Records.",
    version="1.0.0",
)

# 2. Enable CORS (Required for the RapidAPI Playground to work)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Security: Proxy Secret Handshake
# On Railway, create a variable called RAPIDAPI_PROXY_SECRET
RAPID_SECRET = os.getenv("RAPIDAPI_PROXY_SECRET")

@app.middleware("http")
async def verify_rapidapi_request(request: Request, call_next):
    # Exclude system endpoints and docs from the security check
    if request.url.path in ["/healthz", "/", "/docs", "/openapi.json"]:
        return await call_next(request)
    
    # If a secret is set on Railway, verify the incoming header
    if RAPID_SECRET:
        proxy_header = request.headers.get("X-RapidAPI-Proxy-Secret")
        if proxy_header != RAPID_SECRET:
            raise HTTPException(status_code=403, detail="Unauthorized: Access restricted to RapidAPI.")
    
    return await call_next(request)

# 4. Define Version 1 Router
v1 = APIRouter(prefix="/v1")

@v1.get("/business-search", tags=["Search"], summary="Find companies by name")
async def search_business(
    q: Annotated[str, Query(description="Company name to search", example="Tesla Inc")],
    state: Annotated[str, Query(description="2-letter state code", example="DE")] = "DE"
):
    """Scrapes official state registries for legal entities."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()
        try:
            # Your scraping logic goes here
            return {"query": q, "state": state, "status": "success", "results": []}
        finally:
            await browser.close()

@v1.get("/business-details/{entity_id}", tags=["Details"], summary="Get full company profile")
async def get_details(entity_id: str):
    """Deep extraction for Registered Agents and Filing History."""
    return {"entity_id": entity_id, "data": "Detailed record placeholder"}

# Include the V1 routes in the app
app.include_router(v1)

# 5. System Health Check (Hidden from RapidAPI Docs)
@app.get("/healthz", include_in_schema=False)
def health():
    return {"status": "online"}

@app.get("/", include_in_schema=False)
def root():
    return {"message": "JurisExtract API is online. Use /v1/ endpoints via RapidAPI."}
