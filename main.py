import os
import asyncio
from fastapi import FastAPI, Request, HTTPException
from playwright.async_api import async_playwright

app = FastAPI(title="JurisExtract API")

# Security: Set this in Railway Variables
RAPIDAPI_PROXY_SECRET = os.getenv("RAPIDAPI_PROXY_SECRET", "default_secret_for_local_testing")

@app.middleware("http")
async def verify_request(request: Request, call_next):
    # Only enforce security if not on a local machine
    if not request.url.hostname in ["127.0.0.1", "localhost"]:
        header_secret = request.headers.get("X-RapidAPI-Proxy-Secret")
        if header_secret != RAPIDAPI_PROXY_SECRET:
            raise HTTPException(status_code=403, detail="Unauthorized")
    return await call_next(request)

@app.get("/search")
async def search_business(q: str):
    """Search for business records by name."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Use a real user agent to avoid immediate blocks
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # Example: California BizFile (or similar state portals)
            await page.goto("https://bizfileonline.sos.ca.gov/search/business", timeout=60000)
            
            # 1. Fill the search box
            await page.fill('input[aria-label="Search Business Name"]', q)
            await page.keyboard.press("Enter")
            
            # 2. Wait for results to load
            await page.wait_for_selector('.search-results-item', timeout=10000)
            
            # 3. Extract the first 5 results
            results = await page.eval_on_selector_all('.search-results-item', """
                (items) => items.slice(0, 5).map(item => ({
                    name: item.querySelector('.entity-name')?.innerText,
                    id: item.querySelector('.entity-id')?.innerText,
                    status: item.querySelector('.status')?.innerText,
                    type: item.querySelector('.entity-type')?.innerText
                }))
            """)
            
            return {"query": q, "results": results, "count": len(results)}

        except Exception as e:
            return {"query": q, "error": str(e), "results": []}
        finally:
            await browser.close()

@app.get("/")
def home():
    return {"message": "JurisExtract API is online. Use /search?q=CompanyName"}
