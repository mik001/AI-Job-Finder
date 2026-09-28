import asyncio
from playwright.async_api import async_playwright
from src.scraper.auth_manager import AuthManager

async def test_real_scroll():
    auth_manager = AuthManager("linkedin")
    url = "https://www.linkedin.com/jobs/search/?keywords=Human%20Resources&location=Italia&sortBy=DD"
    
    async with async_playwright() as p:
        context = await auth_manager.get_context(p, headless=True, silent=True)
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        # Test scroll dell'elemento effettivo
        result = await page.evaluate("""
            async () => {
                const listContainer = document.querySelector('.scaffold-layout__list');
                const scrollable = listContainer ? Array.from(listContainer.querySelectorAll('*')).find(el => {
                    const s = window.getComputedStyle(el);
                    return (s.overflowY === 'auto' || s.overflowY === 'scroll') && el.scrollHeight > el.clientHeight;
                }) : null;
                
                if (!scrollable) return { error: 'No scrollable container found' };
                
                const beforeScrollHeight = scrollable.scrollHeight;
                const beforeLiCount = listContainer.querySelectorAll('li').length;
                
                // Scorriamo progressivamente fino in fondo
                const scrollSteps = [];
                for (let i = 0; i < 6; i++) {
                    scrollable.scrollBy(0, 600);
                    await new Promise(r => setTimeout(r, 600));
                    scrollSteps.push({
                        step: i + 1,
                        scrollTop: scrollable.scrollTop,
                        scrollHeight: scrollable.scrollHeight,
                        liCount: listContainer.querySelectorAll('li').length,
                        cardCount: listContainer.querySelectorAll('.job-card-container').length
                    });
                }
                
                return {
                    beforeScrollHeight,
                    beforeLiCount,
                    scrollSteps
                };
            }
        """)
        
        print("Risultato test scorrimento reale:")
        import json
        print(json.dumps(result, indent=2))
        
        await context.close()

if __name__ == "__main__":
    asyncio.run(test_real_scroll())
