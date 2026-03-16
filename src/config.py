from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()

class Config:
    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set in the environment variables.")
        
        self.gemini_fast_model = os.getenv("GEMINI_FAST_MODEL", "gemini-3-flash-preview")
        self.gemini_advanced_model = os.getenv("GEMINI_ADVANCED_MODEL", "gemini-3.1-pro-preview")
        self.base_dir = Path(__file__).parent.parent
        self.debug_dir = self.base_dir / "debug"
        self.debug_dir.mkdir(exist_ok=True)
        self.dpi = 210   

config = Config()


