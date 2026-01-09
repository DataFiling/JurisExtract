import os
import re
import pdfplumber
import uvicorn
from io import BytesIO
from fastapi import FastAPI, Header, HTTPException, UploadFile, File
from playwright.async_api import async_playwright

app = FastAPI(title="JurisExtract API")

# Security: This must match the Secret Header in your RapidAPI Dashboard
RAPID_SECRET = os.getenv("RAPID_PROXY_SECRET", "default_secret_for_local_testing")

# --- CITATION PARSER ---
class PrecedentParser:
    def __init__(self):
        # Regex for common US legal citations
        self.cite_pattern = re.compile(
            r'(\d+\s+U\.S\.\s+\d+)|(\d+\s+F\.\d?d\s+\d+)|(\d+\s+U\.S\.C\.\s+§+\s+\d+)'
        )

    def get_toa_data(self, pdf_bytes):
        citations = set()
        with pdfplumber.open(pdf_bytes) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    # Look specifically for the Table of Authorities section
                    matches = self.cite_pattern.findall(text)
                    for match in matches:
                        # Extract the non-empty group from the regex match
                        cite = next(group for group in match if group)
                        citations.add(cite.strip())
        return sorted(list(citations))

parser = PrecedentParser()

# --- ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "online", "message": "JurisExtract Legal API is running"}

@app.post("/extract-precedent")
async def extract_precedent(
        file: UploadFile = File(...),
        x_rapidapi_proxy_secret: str = Header(None)
):
    # Verify the request is coming from RapidAPI
    if x_rapidapi_proxy_secret != RAPID_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized access")

    contents = await file.read()
    results = parser.get_toa_data(BytesIO(contents))

    return {
        "filename": file.filename,
        "citation_count": len(results),
        "precedents": results
    }

@app.get("/scrape-docket/{court}/{docket_id}")
async def fetch_docket(
        court: str,
        docket_id: str,
        x_rapidapi_proxy_secret: str = Header(None)
):
    if x_rapidapi_proxy_secret != RAPID_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized access")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # Conceptual URL - replace with the specific court's search portal
        target_url = f"https://www.{court}.uscourts.gov/search?q={docket_id}"
        await page.goto(target_url)
        title = await page.title()
        await browser.close()

    return {"court": court, "docket": docket_id, "summary": title}

if __name__ == "__main__":
    # Runs the server on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)