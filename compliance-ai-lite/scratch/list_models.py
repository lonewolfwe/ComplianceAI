import os
from dotenv import load_dotenv
import google.generativeai as genai

def main():
    # Load .env explicitly
    load_dotenv()
    
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("GOOGLE_API_KEY not found in environment.")
        return

    genai.configure(api_key=api_key)
    
    print("Available Models supporting generateContent:")
    try:
        models = genai.list_models()
        for m in models:
            if 'generateContent' in m.supported_generation_methods:
                print(f" - {m.name}")
    except Exception as e:
        print(f"Failed to list models: {e}")

if __name__ == "__main__":
    main()
