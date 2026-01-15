import os
from typing import Annotated
from fastapi import FastAPI, Request, HTTPException, Query, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

# --- INITIALIZATION ---
app = FastAPI(
    title="JurisExtract",
    description="Professional Legal Data Extraction API for Business & Court Records.",
    version="1.0.0",
)

# Enable CORS for RapidAPI's testing playground
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SECURITY ---
RAPID_SECRET = os.getenv("RAPIDAPI_PROXY_SECRET")

@app.middleware("http")
async def verify_rapidapi_request(request: Request, call_next):
    # Skip security for system health checks or the root welcome page
    if request.url.path in ["/healthz", "/", "/docs", "/openapi.json"]:
        return await call_next(request)
    
    if RAPID_SECRET:
        proxy_header = request.headers.get("X-RapidAPI-Proxy-Secret")
        if proxy_header != RAPID_SECRET:
            raise HTTPException(status_code=403, detail="Unauthorized: Access via RapidAPI only.")
    
    return await call_next(request)

# --- V1 ROUTER (Version 1 Endpoints) ---
v1 = APIRouter(prefix="/v1")

@v1.get("/business-search", tags=["Search"], summary="Find businesses by name")
async def search_business(
    q: Annotated[str, Query(description="The company name to search", example="Tesla Inc")],
    state: Annotated[str, Query(description="State code", example="DE")] = "DE"
):
    """Scrapes state registries for matching legal entities."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()
        try:
            # Add your specific scraping logic here
            return {"query": q, "state": state, "status": "success", "results": []}
        finally:
            await browser.close()

@v1.get("/business-details/{entity_id}", tags=["Details"], summary="Get full company profile")
async def get_details(entity_id: str):
    """Extracts deep records like Registered Agents and Filing History."""
    return {"entity_id": entity_id, "data": "Deep extraction placeholder"}

# Include the V1 router in the main app
app.include_router(v1)

# --- SYSTEM ENDPOINTS ---
@app.get("/healthz", include_in_schema=False)
def health():
    return {"status": "online"}

@app.get("/", include_in_schema=False)
def root():
    return {"message": "JurisExtract API is online. Please use /v1/ endpoints via RapidAPI."}
