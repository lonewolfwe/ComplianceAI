import asyncio
from config import get_settings
from src.parsers.pdf_downloader import PDFDownloader
from src.parsers.pdf_parser import PDFParser

def main():
    settings = get_settings()
    # No need to mock the user agent, it is now correct in config.py
    downloader = PDFDownloader(settings=settings)
    parser = PDFParser(settings=settings, downloader=downloader)
    
    url = "https://rbidocs.rbi.org.in/rdocs/notification/PDFs/NT1438563868F652840A196CF1CB99CD36E53.PDF"
    print("Extracting...")
    text = parser.download_and_extract(url)
    print(f"Extracted {len(text)} characters.")
    print("Preview:")
    print(text[:500])

if __name__ == "__main__":
    main()
