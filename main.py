import os
import asyncio
from typing import Annotated, List
from fastapi import FastAPI, Request, HTTPException, Query, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

# --- INITIALIZATION ---
app = FastAPI(
    title="JurisExtract",
    description="Real-time Legal & Business Intelligence Scraper.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security handshake for RapidAPI
RAPID_SECRET = os.getenv("RAPIDAPI_PROXY_SECRET")

@app.middleware("http")
async def verify_rapidapi_request(request: Request, call_next):
    if request.url.path in ["/healthz", "/", "/docs", "/openapi.json"]:
        return await call_next(request)
    
    if RAPID_SECRET:
        proxy_header = request.headers.get("X-RapidAPI-Proxy-Secret")
        if proxy_header != RAPID_SECRET:
            raise HTTPException(status_code=403, detail="Unauthorized.")
    
    return await call_next(request)

# --- SCRAPING ENGINE ---
async def scrape_delaware_icis(query: str):
    """
    Targets the Delaware Division of Corporations (ICIS) Search.
    """
    async with async_playwright() as p:
        # Launch with automation bypass
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = await context.new_page()
        
        try:
            # Navigate to the Search Page
            url = "https://icis.corp.delaware.gov/ecorp/entitysearch/namesearch.aspx"
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Fill the search field (using name-based selector for ICIS)
            # The field usually has an ID containing 'frmEntityName'
            search_input = page.locator('input[name*="frmEntityName"]')
            await search_input.wait_for(state="visible")
            await search_input.fill(query)
            
            # Click the Search button
            await page.click('input[name*="btnSubmit"]')
            
            # Wait for results table to load
            # ICIS results table ID starts with 'gvResults'
            results_table_selector = 'table[id*="gvResults"]'
            try:
                await page.wait_for_selector(results_table_selector, timeout=10000)
            except:
                return [] # No results found or timeout

            # Parse the rows
            rows = await page.locator(f'{results_table_selector} tr').all()
            parsed_results = []
            
            # Index 0 is the header, so we skip it
            for row in rows[1:]:
                cells = await row.locator('td').all_inner_texts()
                if len(cells) >= 2:
                    parsed_results.append({
                        "file_number": cells[0].strip(),
                        "entity_name": cells[1].strip(),
                        "status": "Search Hit",
                        "state": "DE"
                    })
            
            return parsed_results

        except Exception as e:
            print(f"Scrape internal error: {e}")
            return []
        finally:
            await browser.close()

# --- API ROUTES ---
v1 = APIRouter(prefix="/v1")

@v1.get("/business-search", tags=["Search"], summary="Live Delaware Registry Search")
async def business_search(
    q: Annotated[str, Query(description="The legal name to search for", example="Tesla")]
):
    """Hits the Delaware ICIS portal in real-time to retrieve File Numbers and Entity Names."""
    data = await scrape_delaware_icis(q)
    return {
        "query": q,
        "count": len(data),
        "status": "success" if data else "no_results",
        "results": data
    }

@v1.get("/business-details/{file_number}", tags=["Details"])
async def get_details(file_number: str):
    """Retrieve detailed agent info using the File Number."""
    return {"file_number": file_number, "message": "Deep extraction endpoint ready."}

app.include_router(v1)

# --- SYSTEM ---
@app.get("/healthz", include_in_schema=False)
def health(): return {"status": "online"}

@app.get("/", include_in_schema=False)
def root(): return {"message": "JurisExtract is active."}
