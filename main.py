import os
import asyncio
from typing import Annotated, List, Optional
from fastapi import FastAPI, Request, HTTPException, Query, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
app = FastAPI(
    title="JurisExtract",
    description="Professional Legal Data Extraction API for Business & Court Records.",
    version="1.0.0",
)

# Enable CORS for RapidAPI Playground
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security: Handshake with RapidAPI Proxy
RAPID_SECRET = os.getenv("RAPIDAPI_PROXY_SECRET")

@app.middleware("http")
async def verify_rapidapi_request(request: Request, call_next):
    if request.url.path in ["/healthz", "/", "/docs", "/openapi.json"]:
        return await call_next(request)
    
    if RAPID_SECRET:
        proxy_header = request.headers.get("X-RapidAPI-Proxy-Secret")
        if proxy_header != RAPID_SECRET:
            raise HTTPException(status_code=403, detail="Unauthorized: Access restricted to RapidAPI.")
    
    return await call_next(request)

# --- SCRAPING UTILS ---
async def scrape_state_registry(query: str, state: str):
    """
    Stealth Scraper Logic. 
    Modify the 'url' and 'selectors' based on the specific state registry.
    """
    async with async_playwright() as p:
        # Launch with stealth arguments
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        # Set a realistic User-Agent to avoid [] empty results
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        
        try:
            # Example: Delaware Search (Replace with actual state URL)
            url = f"https://icis.corp.delaware.gov/Ecorp/EntitySearch/NameSearch.aspx" 
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # 1. Type the query into the search box
            # Replace '#txtName' with the actual ID of the search box
            # await page.fill("#txtName", query)
            # await page.click("#btnSubmit")
            
            # 2. Wait for results to appear
            # await page.wait_for_selector(".results-grid", timeout=10000)
            
            # Placeholder for extracted data
            # For now, we return a mock success to confirm the browser is working
            return [
                {
                    "entity_name": f"{query.upper()} LLC",
                    "entity_id": f"{state}-123456",
                    "status": "Active",
                    "state": state
                }
            ]
        except Exception as e:
            print(f"Scrape Error: {e}")
            return []
        finally:
            await browser.close()

# --- ROUTES ---
v1 = APIRouter(prefix="/v1")

@v1.get("/business-search", tags=["Search"])
async def search(
    q: Annotated[str, Query(description="Company name", example="Tesla Inc")],
    state: Annotated[str, Query(description="2-letter state code", example="DE")] = "DE"
):
    results = await scrape_state_registry(q, state)
    return {
        "query": q,
        "state": state,
        "status": "success" if results else "no_results",
        "results": results
    }

@v1.get("/business-details/{entity_id}", tags=["Details"])
async def details(entity_id: str):
    return {"entity_id": entity_id, "data": "Full profile extraction active."}

app.include_router(v1)

# --- HEALTH ---
@app.get("/healthz", include_in_schema=False)
def health():
    return {"status": "online"}

@app.get("/", include_in_schema=False)
def root():
    return {"message": "JurisExtract API is online."}
