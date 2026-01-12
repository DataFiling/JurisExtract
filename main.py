import os
import asyncio
from fastapi import FastAPI, Header, HTTPException, Depends
from playwright.async_api import async_playwright

app = FastAPI(title="JurisExtract Pro")

# --- Security Layer ---
# This ensures only RapidAPI can talk to your Railway server.
RAPID_PROXY_SECRET = os.getenv("RAPID_PROXY_SECRET")

async def verify_rapid_request(x_rapidapi_proxy_secret: str = Header(None)):
    if x_rapidapi_proxy_secret != RAPID_PROXY_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden: Unverified Request")
    return x_rapidapi_proxy_secret

# --- Scraper Logic ---
@app.get("/scrape-docket", dependencies=[Depends(verify_rapid_request)])
async def scrape_docket(court: str, docket_id: str):
    # Map 'court' to actual URLs
    court_map = {
        "scotus": f"https://www.supremecourt.gov/docket/docketfiles/html/public/{docket_id}.html"
    }
    
    url = court_map.get(court.lower())
    if not url:
        return {"success": False, "error": f"Court '{court}' not supported."}

    try:
        async with async_playwright() as p:
            # 1. Launch with optimized flags for Railway's limited resources
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            
            # 2. Set a strict timeout (RapidAPI expects a response within 30-180s)
            context = await browser.new_context(user_agent="Mozilla/5.0 Legal-Scraper/1.0")
            page = await context.new_page()
            page.set_default_timeout(20000) # 20 seconds
            
            # 3. Execution
            response = await page.goto(url, wait_until="domcontentloaded")
            
            if response.status == 404:
                return {"success": False, "error": "Docket not found."}

            # Extract specific metadata
            data = {
                "court": court,
                "docket_id": docket_id,
                "case_name": await page.title(),
                "status": "Success",
                "captured_url": page.url
            }
            
            await browser.close()
            return data

    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/")
async def health():
    return {"status": "online", "engine": "playwright-chromium"}
