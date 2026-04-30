import asyncio
from playwright.async_api import async_playwright
import os

OUT = os.path.join(os.path.dirname(__file__), '..', 'screenshots')
os.makedirs(OUT, exist_ok=True)

PAGES = [
    ('01-use-cases-hub',              'https://mnemehq.com/use-cases/'),
    ('02-coding-assistant-governance','https://mnemehq.com/use-cases/coding-assistant-governance/'),
    ('03-legacy-codebase-memory',     'https://mnemehq.com/use-cases/legacy-codebase-memory/'),
    ('04-security-compliance',        'https://mnemehq.com/use-cases/security-compliance-guardrails/'),
    ('05-data-platform-governance',   'https://mnemehq.com/use-cases/data-platform-governance/'),
    ('06-design-system-governance',   'https://mnemehq.com/use-cases/design-system-governance/'),
    ('07-multi-agent-governance',     'https://mnemehq.com/use-cases/multi-agent-workflow-governance/'),
]

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1440, 'height': 900})
        for name, url in PAGES:
            print(f'  {name} ...', end=' ', flush=True)
            await page.goto(url, wait_until='networkidle')
            await page.wait_for_timeout(1000)
            path = os.path.join(OUT, f'{name}.png')
            await page.screenshot(path=path, full_page=True)
            size = os.path.getsize(path)
            print(f'saved ({size // 1024} KB)')
        await browser.close()

asyncio.run(main())
