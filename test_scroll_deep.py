import asyncio
from playwright.async_api import async_playwright
from src.scraper.auth_manager import AuthManager

async def test_scroll_deep():
    auth_manager = AuthManager("linkedin")
    url = "https://www.linkedin.com/jobs/search/?keywords=Human%20Resources&location=Italia&sortBy=DD"
    
    async with async_playwright() as p:
        context = await auth_manager.get_context(p, headless=True, silent=True)
        page = await context.new_page()
        print(f"[*] Apertura: {url}")
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)
        
        # Analizziamo quale elemento è scrollabile nel DOM
        scroll_info = await page.evaluate("""
            () => {
                const elements = Array.from(document.querySelectorAll('*'));
                const scrollable = [];
                for (const el of elements) {
                    const style = window.getComputedStyle(el);
                    const overflowY = style.overflowY;
                    const isScrollable = (overflowY === 'auto' || overflowY === 'scroll') && el.scrollHeight > el.clientHeight;
                    if (isScrollable) {
                        scrollable.push({
                            tag: el.tagName,
                            className: el.className,
                            id: el.id,
                            scrollHeight: el.scrollHeight,
                            clientHeight: el.clientHeight,
                            scrollTop: el.scrollTop
                        });
                    }
                }
                return scrollable;
            }
        """)
        
        print("\n[*] Elementi scrollabili rilevati nella pagina:")
        for idx, el in enumerate(scroll_info, 1):
            print(f"  {idx}. <{el['tag']}> id='{el['id']}' class='{el['className']}' (h={el['clientHeight']}, scrollH={el['scrollHeight']})")
            
        # Proviamo a scrollare ciascun elemento scrollabile e vediamo se compaiono più card
        cards_before = await page.locator("div.job-card-container, li.jobs-search-results__list-item").count()
        print(f"\n[*] Card presenti prima dello scroll: {cards_before}")
        
        # Test scroll continuo sull'elemento con classe contenente 'scaffold-layout__list' o 'jobs-search-results'
        await page.evaluate("""
            () => {
                const target = document.querySelector('.scaffold-layout__list') || 
                               document.querySelector('.jobs-search-results-list') || 
                               document.querySelector('main');
                if (target) {
                    target.scrollTop = target.scrollHeight;
                }
            }
        """)
        await page.wait_for_timeout(2000)
        
        # Proviamo anche con scrollBy progressivo
        for i in range(10):
            await page.evaluate("""
                () => {
                    const target = document.querySelector('.scaffold-layout__list') || 
                                   document.querySelector('.jobs-search-results-list');
                    if (target) {
                        target.scrollBy(0, 1000);
                    } else {
                        window.scrollBy(0, 1000);
                    }
                }
            """)
            await page.wait_for_timeout(500)
            
        cards_after = await page.locator("div.job-card-container, li.jobs-search-results__list-item").count()
        print(f"[*] Card presenti dopo lo scroll: {cards_after}")
        
        await context.close()

if __name__ == "__main__":
    asyncio.run(test_scroll_deep())
