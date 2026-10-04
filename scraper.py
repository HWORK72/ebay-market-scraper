import asyncio
import logging
import random
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse, parse_qs, unquote_plus
from bs4 import BeautifulSoup, Tag
from playwright.async_api import async_playwright, BrowserContext, Page
from playwright_stealth import Stealth
from models import ProductItem

logger: logging.Logger = logging.getLogger(__name__)


class EbayScraper:
    def __init__(self, timeout: int = 30) -> None:
        self._timeout_ms: int = timeout * 1000 if timeout < 1000 else timeout
        self._profile_dir: Path = Path("./browser_profile")

    def _extract_query(self, target_url: str) -> str:
        parsed_url = urlparse(target_url)
        params = parse_qs(parsed_url.query)
        if "_nkw" in params and params["_nkw"]:
            return unquote_plus(params["_nkw"][0])
        return "iphone 15 pro"

    async def _human_scroll(self, page: Page) -> None:
        try:
            viewport = page.viewport_size or {"width": 1280, "height": 800}
            center_x: float = viewport["width"] / 2 + random.uniform(-50, 50)
            center_y: float = viewport["height"] / 2 + random.uniform(-50, 50)
            await page.mouse.move(center_x, center_y)

            scroll_steps: int = random.randint(5, 8)
            for _ in range(scroll_steps):
                if page.is_closed():
                    return
                delta_y: int = random.randint(300, 650)
                await page.mouse.wheel(0, delta_y)
                await asyncio.sleep(random.uniform(0.3, 0.7))

            await page.mouse.wheel(0, -random.randint(50, 150))
            await asyncio.sleep(random.uniform(0.2, 0.5))
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
        stealth_engine: Stealth = Stealth()
        self._profile_dir.mkdir(parents=True, exist_ok=True)
        current_url: str = base_url

        async with async_playwright() as p:
            context: BrowserContext = await p.chromium.launch_persistent_context(
                user_data_dir=str(self._profile_dir.resolve()),
                headless=False,
                channel="chrome",
                no_viewport=True,
                locale="en-US",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                    "--disable-features=Translate",
                    "--no-sandbox"
                ]
            )
            await stealth_engine.apply_stealth_async(context)
            page: Page = context.pages[0] if context.pages else await context.new_page()

            try:
                for page_num in range(1, max_pages + 1):
                    if page.is_closed():
                        logger.warning("Target browser page was closed prematurely")
                        break

                    logger.info(f"Processing catalog page {page_num}/{max_pages}: {current_url}")
                    referer_header: str = "https://www.google.com/" if page_num == 1 else base_url
                    await page.set_extra_http_headers({"Referer": referer_header})

                    await page.goto(current_url, timeout=self._timeout_ms, wait_until="domcontentloaded")
                    await asyncio.sleep(random.uniform(2.0, 3.5))

                    page_title: str = await page.title()
                    if "error" in page_title.lower() or "sorry" in page_title.lower():
                        logger.critical(f"Akamai Edge WAF Block detected on page {page_num}. Page title: '{page_title}'")
                        break

                    if page_num == 1:
                        try:
                            cookie_btn = page.locator("button:has-text('Accept All'), #gdpr-banner-accept, button#gdpr-banner-accept")
                            if await cookie_btn.count() > 0 and await cookie_btn.first.is_visible():
                                logger.info("Dismissing GDPR cookie consent banner")
                                await cookie_btn.first.click()
                                await asyncio.sleep(1.0)
                        except Exception:
                            pass

                    try:
                        await page.wait_for_selector(".srp-results, li.s-card, li.s-item, div.s-item", state="attached", timeout=15000)
                    except Exception:
                        logger.warning(f"Timeout waiting for items on page {page_num}")

                    logger.info("Performing human-like page inspection")
                    await self._human_scroll(page)
                    await asyncio.sleep(random.uniform(1.0, 2.0))

                    if page.is_closed():
                        break

                    html_content: str = await page.content()
                    parsed_items: List[ProductItem] = self.parse_items(html_content)
                    logger.info(f"Extracted {len(parsed_items)} items on page {page_num}")
                    all_results.extend(parsed_items)

                    if page_num < max_pages:
                        next_btn = page.locator("a.pagination__next")
                        if await next_btn.count() > 0:
                            next_url: Optional[str] = await next_btn.first.get_attribute("href")
                            if next_url and next_url.strip():
                                current_url = next_url.strip()
                                logger.info(f"Resolved next catalog URL: {current_url}")
                                await asyncio.sleep(random.uniform(2.0, 3.5))
                            else:
                                logger.warning("Pagination link found but href attribute is empty")
                                break
                        else:
                            logger.warning("Next page pagination control not located")
                            break

            except Exception as exc:
                logger.error(f"Execution error encountered: {exc}", exc_info=True)
            finally:
                if not context.pages or not page.is_closed():
                    await context.close()

        return all_results