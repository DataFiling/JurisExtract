import os
import asyncio
from typing import Annotated, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Query, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

# --- LIFESPAN MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize playwright once to save resources
    app.state.playwright = await async_playwright().start()
    yield
    # Shutdown: Clean up
    await app.state.playwright.stop()

# --- APP INITIALIZATION ---
# Uvicorn looks for this 'app' variable at the top level
app = FastAPI(
    title="JurisExtract",
    version="1.3.0",
    lifespan=lifespan
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

# --- STEALTH SCRAPER ENGINE ---

async def scrape_de_search(query: str):
    pw = app.state.playwright
    # Launch with high-stealth arguments
    browser = await pw.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-infobars",
            "--window-position=0,0",
            "--ignore-certificate-errors",
        ]
    )
    
    # Context with realistic fingerprinting
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        viewport={'width': 1920, 'height': 1080},
        device_scale_factor=1,
    )

    # ANTI-BOT INJECTION: Remove 'webdriver' property
    await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    page = await context.new_page()
    try:
        url = "https://icis.corp.delaware.gov/ecorp/entitysearch/namesearch.aspx"
        await page.goto(url, wait_until="networkidle", timeout=45000)
        
        # Interact like a human
        search_field = page.locator('input[id*="frmEntityName"]')
        await search_field.wait_for(state="visible")
        await search_field.click()
        await page.keyboard.type(query, delay=120) # Human-like typing speed
        
        await asyncio.sleep(1) # Wait for ASP.NET postback
        await page.click('input[id*="btnSubmit"]')
        
        # Wait for either result table or 'No Records'
        try:
            table_sel = 'table[id*="gvResults"]'
            await page.wait_for_selector(table_sel, timeout=15000)
            
            rows = await page.locator(f"{table_sel} tr").all()
            results = []
            for row in rows[1:]: # Skip headers
                cells = await row.locator('td').all_inner_texts()
                if len(cells) >= 2:
                    results.append({
                        "file_number": cells[0].strip(),
                        "entity_name": cells[1].strip(),
                        "state": "DE"
                    })
            return results
        except:
            # Check for bot-block content
            html_content = await page.content()
            if "Pardon Our Interruption" in html_content or "Access Denied" in html_content:
                return [{"error": "IP Blocked by Delaware Firewall. Proxy required."}]
            return []

    except Exception as e:
        return [{"error": f"Internal Scraper Error: {str(e)}"}]
    finally:
        await browser.close()

# --- ROUTES ---

v1 = APIRouter(prefix="/v1")

@v1.get("/business-search", tags=["Search"])
async def search(q: str):
    data = await scrape_de_search(q)
    if data and "error" in data[0]:
        return {"status": "error", "message": data[0]["error"], "results": []}
    return {"query": q, "count": len(data), "status": "success", "results": data}

app.include_router(v1)

@app.get("/healthz")
def health(): return {"status": "online"}

@app.get("/")
def root(): return {"message": "JurisExtract Legal Intelligence API"}
