import asyncio
import logging
from typing import List
from urllib.parse import urlparse, parse_qs, unquote_plus
from bs4 import BeautifulSoup, Tag
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from models import ProductItem

logger: logging.Logger = logging.getLogger(__name__)

class EbayScraper:
    def __init__(self, timeout: int = 30) -> None:
        self._timeout_ms: int = timeout * 1000 if timeout < 1000 else timeout

    def _extract_query(self, target_url: str) -> str:
        parsed_url = urlparse(target_url)
        params = parse_qs(parsed_url.query)
        if "_nkw" in params and params["_nkw"]:
            return unquote_plus(params["_nkw"][0])
        return "iphone 15 pro"

    async def _smooth_scroll(self, page: Page) -> None:
        scroll_script: str = """
        async () => {
            await new Promise((resolve) => {
                let totalHeight = 0;
                let distance = 350;
                let timer = setInterval(() => {
                    let scrollHeight = document.body.scrollHeight;
                    window.scrollBy(0, distance);
                    totalHeight += distance;
                    if (totalHeight >= scrollHeight - window.innerHeight) {
                        clearInterval(timer);
                        resolve();
                    }
                }, 120);
            });
        }
        """
        try:
            await page.evaluate(scroll_script)
        except Exception as exc:
            logger.warning(f"Scroll simulation notice: {exc}")

    def parse_items(self, html_content: str) -> List[ProductItem]:
        items: List[ProductItem] = []
        try:
            soup: BeautifulSoup = BeautifulSoup(html_content, "html.parser")
            listing_elements = soup.select("li.s-card, li.s-item, div.s-card, div.s-item, div.s-item__wrapper")
            for element in listing_elements:
                if not isinstance(element, Tag):
                    continue
                title_node = element.select_one(".s-card__title, .s-item__title, span[role='heading']")
                if not title_node:
                    continue
                title_text: str = title_node.get_text(separator=" ", strip=True)
                if not title_text or "Shop on eBay" in title_text:
                    continue
                if title_text.lower().startswith("new listing"):
                    title_text = title_text[11:].strip()
                price_node = element.select_one(".s-card__price, .s-item__price")
                price_text: str = price_node.get_text(strip=True) if price_node else "N/A"
                shipping_node = element.select_one(".s-card__shipping, .s-item__shipping, .s-item__logisticsCost")
                shipping_text: str = shipping_node.get_text(strip=True) if shipping_node else "Free / Not specified"
                condition_node = element.select_one(".s-card__subtitle, .SECONDARY_INFO, .s-item__subtitle")
                condition_text: str = condition_node.get_text(strip=True) if condition_node else "Not specified"
                link_node = element.select_one("a.s-card__link, a.s-item__link, a[href*='/itm/']")
                link_url: str = link_node.get("href", "").strip() if link_node else ""
                if not link_url:
                    continue
                item: ProductItem = ProductItem(
                    title=title_text,
                    price=price_text,
                    shipping=shipping_text,
                    condition=condition_text,
                    item_url=link_url
                )
                items.append(item)
        except Exception as exc:
            logger.error(f"DOM parsing error: {exc}", exc_info=True)
        return items

    async def scrape_target(self, base_url: str, max_pages: int) -> List[ProductItem]:
        all_results: List[ProductItem] = []
        search_query: str = self._extract_query(base_url)
        async with async_playwright() as p:
            browser: Browser = await p.chromium.launch(
                headless=False,
                channel="chrome",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                    "--disable-features=Translate"
                ]
            )
            context: BrowserContext = await browser.new_context(
                no_viewport=True,
                locale="en-US"
            )
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page: Page = await context.new_page()
            try:
                logger.info("Accessing eBay storefront directly")
                await page.goto("https://www.ebay.com/", timeout=self._timeout_ms, wait_until="domcontentloaded")
                await asyncio.sleep(2.0)
                try:
                    cookie_btn = page.locator("button:has-text('Accept All'), #gdpr-banner-accept")
                    if await cookie_btn.count() > 0 and await cookie_btn.first.is_visible():
                        logger.info("Dismissing GDPR cookie consent banner")
                        await cookie_btn.first.click()
                        await asyncio.sleep(1.0)
                except Exception:
                    pass
                logger.info(f"Simulating human search query: '{search_query}'")
                search_input = page.locator("#gh-ac")
                await search_input.wait_for(timeout=10000)
                await search_input.fill(search_query)
                await asyncio.sleep(0.6)
                logger.info("Executing search via keyboard Enter")
                await search_input.press("Enter")
                for page_num in range(1, max_pages + 1):
                    logger.info(f"Processing search result page {page_num}/{max_pages}")
                    await asyncio.sleep(3.0)
                    try:
                        await page.wait_for_selector(".srp-results, li.s-card, li.s-item, div.s-item", state="attached", timeout=15000)
                    except Exception:
                        logger.warning(f"Timeout waiting for items on page {page_num}")
                    logger.info("Performing human-like page inspection")
                    await self._smooth_scroll(page)
                    await asyncio.sleep(1.5)
                    html_content: str = await page.content()
                    parsed_items: List[ProductItem] = self.parse_items(html_content)
                    logger.info(f"Extracted {len(parsed_items)} items on page {page_num}")
                    all_results.extend(parsed_items)
                    if page_num < max_pages:
                        next_btn = page.locator("a.pagination__next")
                        if await next_btn.count() > 0 and await next_btn.first.is_visible():
                            logger.info("Scrolling down to pagination controls")
                            await next_btn.first.scroll_into_view_if_needed()
                            await asyncio.sleep(2.0)
                            logger.info("Proceeding to next catalog page")
                            await next_btn.first.click()
                            await asyncio.sleep(4.0)
                        else:
                            logger.warning("Next page pagination button not located")
                            break
            except Exception as exc:
                logger.error(f"Execution error encountered: {exc}", exc_info=True)
            finally:
                await context.close()
                await browser.close()
        return all_results