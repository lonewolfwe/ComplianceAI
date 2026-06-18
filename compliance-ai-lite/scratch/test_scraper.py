import asyncio
from config import get_settings
from src.scraper.rbi_scraper import RBIScraper

def main():
    settings = get_settings()
    settings.scraper_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    scraper = RBIScraper(settings=settings)
    
    circulars = scraper.fetch_latest()
    print(f"Extracted {len(circulars)} circulars:")
    for c in circulars[:3]:
        print(f"Title: {c.title}")
        print(f"Date: {c.date}")
        print(f"URL: {c.pdf_url}")
        print("---")

if __name__ == "__main__":
    main()
