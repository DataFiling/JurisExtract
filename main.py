import asyncio
from apify import Actor
from playwright.async_api import async_playwright

async def main() -> None:
    async with Actor:
        # 1. Capture Input
        actor_input = await Actor.get_input() or {}
        search_query = actor_input.get('query', 'Tesla')
        
        # Initialize variables to prevent "UnboundLocalError"
        browser = None
        context = None
        page = None

        async with async_playwright() as playwright:
            try:
                # 2. Setup Proxy
                # Note: 'RESIDENTIAL' is key for Delaware.
                proxy_config = await Actor.create_proxy_configuration(groups=['RESIDENTIAL'])
                if not proxy_config:
                    raise ValueError("Residential proxies are required but not available.")
                
                proxy_url = await proxy_config.new_url()

                # 3. Launch Browser
                # We use standard Chromium. 
                browser = await playwright.chromium.launch(
                    headless=True, 
                    proxy={'server': proxy_url} if proxy_url else None,
                    args=["--no-sandbox", "--disable-setuid-sandbox"] # Extra stability args
                )

                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                
                # 60s timeout for slow gov site
                context.set_default_timeout(60000)
                page = await context.new_page()

                Actor.log.info(f"Navigating to Delaware search page...")
                await page.goto("https://icis.corp.delaware.gov/ecorp/entitysearch/namesearch.aspx", wait_until="commit")

                # 4. Search Logic
                search_box_selector = 'input[id*="frmEntityName"]'
                # Wait explicitly for the box to appear
                await page.wait_for_selector(search_box_selector, state="visible")
                
                Actor.log.info(f"Typing query: {search_query}")
                await page.locator(search_box_selector).fill(search_query)
                await page.click('input[id*="btnSubmit"]')

                # 5. Extract Results
                table_selector = 'table[id*="gvResults"]'
                Actor.log.info("Waiting for results table...")
                await page.wait_for_selector(table_selector)

                rows = await page.locator(f"{table_selector} tr").all()
                results = []
                
                for row in rows[1:]:
                    cells = await row.locator('td').all_inner_texts()
                    if len(cells) >= 2:
                        results.append({
                            "file_number": cells[0].strip(),
                            "entity_name": cells[1].strip()
                        })

                if results:
                    await Actor.push_data(results)
                    Actor.log.info(f"Success! Found {len(results)} results.")
                else:
                    Actor.log.warning("Table found but no results extracted. (Possible no-match)")

            except Exception as e:
                Actor.log.error(f"CRASH REPORT: {str(e)}")
                
                # SAFELY take a screenshot only if page exists
                if page:
                    try:
                        await Actor.set_value('ERROR_SCREENSHOT', await page.screenshot(full_page=True), content_type='image/png')
                        Actor.log.info("Screenshot saved as 'ERROR_SCREENSHOT'. Check Key-Value Store.")
                    except Exception as img_error:
                        Actor.log.error(f"Could not take screenshot: {str(img_error)}")
            
            finally:
                if browser:
                    await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
