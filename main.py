async def scrape_de_search(query: str):
    async with async_playwright() as p:
        # Layer 1: Enhanced Stealth Launch
        browser = await p.chromium.launch(
            headless=True, 
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        
        # Layer 2: Mask the WebDriver property
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        
        # This script runs before the website loads to hide Playwright
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page = await context.new_page()
        
        try:
            url = "https://icis.corp.delaware.gov/ecorp/entitysearch/namesearch.aspx"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Layer 3: Human-like interaction
            search_input = page.locator('input[id*="frmEntityName"]')
            await search_input.wait_for(state="visible")
            await search_input.click() # Focus the field first
            await page.keyboard.type(query, delay=100) # Type slowly like a person
            
            await asyncio.sleep(1) # Wait for the form to register input
            await page.click('input[id*="btnSubmit"]')
            
            # Wait for results
            try:
                table_selector = 'table[id*="gvResults"]'
                await page.wait_for_selector(table_selector, timeout=15000)
                
                rows = await page.locator(f"{table_selector} tr").all()
                results = []
                for row in rows[1:]:
                    cells = await row.locator('td').all_inner_texts()
                    if len(cells) >= 2:
                        results.append({
                            "file_number": cells[0].strip(),
                            "entity_name": cells[1].strip()
                        })
                return results
            except:
                return [] # Or return the error message for debugging

        except Exception as e:
            return [{"error": str(e)}]
        finally:
            await browser.close()
