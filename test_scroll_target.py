import asyncio
from playwright.async_api import async_playwright
from src.scraper.auth_manager import AuthManager

async def test_scroll_target():
    auth_manager = AuthManager("linkedin")
    url = "https://www.linkedin.com/jobs/search/?keywords=Human%20Resources&location=Italia&sortBy=DD"
    
    async with async_playwright() as p:
        context = await auth_manager.get_context(p, headless=True, silent=True)
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        # Troviamo l'elemento scrollabile
        info = await page.evaluate("""
            () => {
                // Troviamo l'elemento che contiene le job card e ha scrollHeight > clientHeight
                const cards = document.querySelectorAll('.job-card-container');
                if (cards.length === 0) return { error: 'no cards' };
                
                // Risaliamo i parent della prima card per trovare il container scrollabile
                let parent = cards[0].parentElement;
                const ancestors = [];
                while (parent && parent !== document.body) {
                    const style = window.getComputedStyle(parent);
                    ancestors.push({
                        tag: parent.tagName,
                        className: parent.className,
                        id: parent.id,
                        clientHeight: parent.clientHeight,
                        scrollHeight: parent.scrollHeight,
                        overflowY: style.overflowY
                    });
                    parent = parent.parentElement;
                }
                return { ancestors };
            }
        """)
        
        print("\n[*] Antenati della prima card:")
        for idx, a in enumerate(info.get('ancestors', []), 1):
            print(f"  {idx}. <{a['tag']}> class='{a['className']}' id='{a['id']}' [overflowY={a['overflowY']}, clientH={a['clientHeight']}, scrollH={a['scrollHeight']}]")
            
        await context.close()

if __name__ == "__main__":
    asyncio.run(test_scroll_target())
