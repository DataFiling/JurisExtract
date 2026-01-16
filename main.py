import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Query, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

# --- LIFESPAN: Handles Global Playwright State ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    app.state.pw = await async_playwright().start()
    yield
    # Shutdown logic
    await app.state.pw.stop()

app = FastAPI(title="JurisExtract", version="1.4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SCRAPER ENGINE ---

async def scrape_de_search(query: str):
    # Launch with stealth arguments
    browser = await app.state.pw.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"]
    )
    
    # Context with human-like fingerprinting
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Manual Stealth Injection
    await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    page = await context.new_page()
    try:
        url = "https://icis.corp.delaware.gov/ecorp/entitysearch/namesearch.aspx"
        # Increase timeout for government servers
        await page.goto(url, wait_until="networkidle", timeout=60000)
        
        # Fill search field
        search_input = page.locator('input[id*="frmEntityName"]')
        await search_input.wait_for(state="visible")
        await search_input.fill(query)
        
        # Click search and wait for the specific results table
        await page.click('input[id*="btnSubmit"]')
        
        # We wait for the results table OR a 'No Records Found' message
        table_selector = 'table[id*="gvResults"]'
        try:
            # Wait up to 15 seconds for the table to appear
            await page.wait_for_selector(table_selector, timeout=15000)
            
            rows = await page.locator(f"{table_selector} tr").all()
            results = []
            for row in rows[1:]: # Skip header
                cells = await row.locator('td').all_inner_texts()
                if len(cells) >= 2:
                    results.append({
                        "file_number": cells[0].strip(),
                        "entity_name": cells[1].strip()
                    })
            return results
        except:
            # If table doesn't appear, check if it's a 'No Results' or a 'Block'
            content = await page.content()
            if "No Records Found" in content:
                return []
            if "Pardon Our Interruption" in content or "Access Denied" in content:
                return [{"error": "IP Blocked"}]
            return []

    except Exception as e:
        return [{"error": str(e)}]
    finally:
        await browser.close()

# --- API ROUTES ---
v1 = APIRouter(prefix="/v1")

@v1.get("/business-search")
async def search(q: str):
    data = await scrape_de_search(q)
    
    if data and isinstance(data[0], dict) and "error" in data[0]:
        return {"status": "blocked", "message": data[0]["error"], "results": []}
        
    return {
        "query": q,
        "count": len(data),
        "status": "success",
        "results": data
    }

app.include_router(v1)

@app.get("/healthz")
def health(): return {"status": "online"}
