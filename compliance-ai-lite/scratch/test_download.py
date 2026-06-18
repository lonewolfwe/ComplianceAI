import asyncio
from pathlib import Path
from config import get_settings
from src.parsers.pdf_downloader import PDFDownloader
import os

def main():
    settings = get_settings()
    settings.scraper_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    downloader = PDFDownloader(settings=settings)
    
    url = "https://rbidocs.rbi.org.in/rdocs/notification/PDFs/NT1438563868F652840A196CF1CB99CD36E53.PDF"
    print(f"Downloading {url} ...")
    try:
        result = downloader.download(url)
        print(f"Success! Saved to {result.path}")
        print(f"File size: {os.path.getsize(result.path)} bytes")
        
        with open(result.path, "rb") as f:
            header = f.read(10)
            print(f"File header: {header}")
            
    except Exception as e:
        print(f"Download failed: {e}")

if __name__ == "__main__":
    main()
