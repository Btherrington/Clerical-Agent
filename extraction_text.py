import argparse
from pathlib import Path
from docx import Document
import pymupdf
from PIL import Image
import pytesseract

def parse_args():
    parser = argparse.ArgumentParser(description="Extraction of text")
    parser.add_argument("--file-name", required=True)
    return parser.parse_args()

def text_extraction(file_path):
    text_list = []
    document = Document(file_path)
    for para in document.paragraphs:
        text_list.append(para.text)
    return "\n".join(text_list)

def pdf_extraction(file_path):
    text_list = []
    doc = pymupdf.open(file_path)
    for page in doc:
        text = page.get_text()
        text_list.append(text)
    return "\n".join(text_list)

def image_extraction(file_path):
    return pytesseract.image_to_string(Image.open(file_path))

def extract_text(file_path):
    ext = Path(file_path).suffix
    extension_check = {".pdf": pdf_extraction, ".docx": text_extraction, ".jpg": image_extraction, ".png": image_extraction}
    return extension_check[ext](file_path)




if __name__ == "__main__":
    args = parse_args()
    example_image = extract_text(args.file_name)
    print(f"Result: '{example_image}'")
    print(f"Length: {len(example_image)}")
    print(example_image)
