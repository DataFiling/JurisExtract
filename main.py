import os
from typing import Annotated
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import async_playwright

# 1. Initialize App with Metadata for RapidAPI
app = FastAPI(
    title="JurisExtract",
    description="Professional Legal Data Extraction API for Business & Court Records.",
    version="1.0.0",
    contact={"name": "JurisExtract Support", "url": "https://jurisextract.com"},
    openapi_tags=[
        {"name": "Search", "description": "Endpoints for finding entities and cases."},
        {"name": "Details", "description": "Deep-dive extraction for specific records."}
    ]
)

# 2. Enable CORS (Required for RapidAPI testing playground)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows RapidAPI's domain to access your Railway server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Security Lock: RapidAPI Proxy Secret
RAPID_SECRET = os.getenv("RAPIDAPI_PROXY_SECRET")

@app.middleware("http")
async def verify_rapidapi_request(request: Request, call_next):
    # Skip security for local dev or health checks
    if request.url.path in ["/healthz", "/"]:
        return await call_next(request)
    
    if RAPID_SECRET:
        proxy_header = request.headers.get("X-RapidAPI-Proxy-Secret")
        if proxy_header != RAPID_SECRET:
            raise HTTPException(status_code=403, detail="Unauthorized: Direct access is restricted.")
    
    return await call_next(request)

# 4. Search Endpoint
@app.get("/v1/business-search", tags=["Search"], summary="Find businesses by name")
async def search_business(
    q: Annotated[str, Query(description="The company name to search for", example="Tesla Inc")],
    state: Annotated[str, Query(description="State code (e.g. DE, CA, FL)", example="DE")] = "DE"
):
    """
    Scrapes official state registries to find matching legal entities.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()
        
        try:
            # Example logic for a general biz search portal
            await page.goto(f"https://example-gov-site.gov/search?name={q}&state={state}")
            # Placeholder for selector logic
            title = await page.title()
            return {"query": q, "state": state, "status": "success", "source": title, "results": []}
        except Exception as e:
            return {"error": str(e)}
        finally:
            await browser.close()

# 5. System Health Check
@app.get("/healthz", include_in_schema=False)
def health():
    return {"status": "online"}

@app.get("/", include_in_schema=False)
def root():
    return {"message": "JurisExtract API is running. Visit /docs for documentation."}
