from pathlib import Path
import os
# --- Configuration Settings ---

# Database Configuration (Example for XAMPP default settings)
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',        # Default XAMPP MySQL user
    'password': '',        # Default XAMPP MySQL password (often empty)
    'database': 'engineering_ocr_db',  # Name of your database
    'autocommit': True
}

# File Paths
# Use pathlib for better path handling (optional but recommended)

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Directory for storing uploaded PDFs
PDF_STORAGE_DIR = BASE_DIR / "data" / "pdfs"
# Create if it doesn't exist
PDF_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Directory for storing temporary images (PDF pages, crops)
IMAGE_STORAGE_DIR = BASE_DIR / "data" / "images"
IMAGE_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Path to the YOLOv8 model
MODEL_PATH = BASE_DIR / "models" / "best.pt"

# OCR Engine Choice (configure the one you intend to use primarily)
# Options could be 'easyocr', 'paddleocr', 'tesseract'
OCR_ENGINE = 'easyocr'  # Change this based on your preference/setup
