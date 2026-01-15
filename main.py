import os
import asyncio
from typing import Annotated
from fastapi import FastAPI, Request, HTTPException, Query, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

app = FastAPI(
    title="JurisExtract",
    description="Legal Entity Scraper for the Delaware ICIS Registry.",
    version="1.2.1"
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
    if RAPID_SECRET and request.headers.get("X-RapidAPI-Proxy-Secret") != RAPID_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized.")
    return await call_next(request)

# --- THE ENGINE ---

async def scrape_de_search(query: str):
    async with async_playwright() as p:
        # Launch with stealth arguments
        browser = await p.chromium.launch(
            headless=True, 
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # 1. Navigate to Delaware ICIS
            url = "https://icis.corp.delaware.gov/ecorp/entitysearch/namesearch.aspx"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # 2. Interact with the 'Entity Name' field
            # We use a CSS selector that targets the partial ID used by ASP.NET
            search_input = page.locator('input[id*="frmEntityName"]')
            await search_input.wait_for(state="visible")
            
            # Mimic human typing speed
            await search_input.click()
            await search_input.fill(query)
            await asyncio.sleep(0.5) 
            
            # 3. Click the Search button
            submit_btn = page.locator('input[id*="btnSubmit"]')
            await submit_btn.click()
            
            # 4. Wait for the results table (gvResults)
            # If this fails, it usually means 'No Results Found' or a Bot Block
            try:
                table_selector = 'table[id*="gvResults"]'
                await page.wait_for_selector(table_selector, timeout=15000)
                
                rows = await page.locator(f"{table_selector} tr").all()
                results = []
                
                # Skip header row [0]
                for row in rows[1:]:
                    cells = await row.locator('td').all_inner_texts()
                    if len(cells) >= 2:
                        results.append({
                            "file_number": cells[0].strip(),
                            "entity_name": cells[1].strip(),
                            "status": "Found",
                            "state": "DE"
                        })
                return results
                
            except Exception:
                # Check if the page explicitly says no records found
                content = await page.content()
                if "No Records Found" in content:
                    return []
                # Otherwise, it might be a block
                return [{"error": "Search timed out or was blocked by the registry."}]

        except Exception as e:
            return [{"error": str(e)}]
        finally:
            await browser.close()

# --- ROUTES ---

v1 = APIRouter(prefix="/v1")

@v1.get("/business-search", tags=["Search"])
async def search(
    q: Annotated[str, Query(description="The legal name to search (e.g., Tesla)", example="Tesla")]
):
    """Hits the Delaware ICIS portal in real-time."""
    data = await scrape_de_search(q)
    
    # Check if we got an error message back
    if data and "error" in data[0]:
        return {"status": "error", "message": data[0]["error"], "results": []}
        
    return {
        "query": q,
        "count": len(data),
        "status": "success" if data else "no_results",
        "results": data
    }

app.include_router(v1)

@app.get("/healthz", include_in_schema=False)
def health(): return {"status": "online"}

@app.get("/", include_in_schema=False)
def root(): return {"message": "JurisExtract API is online."}
