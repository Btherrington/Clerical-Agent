# Commission Audit File Classifier

Classifies commercial real estate documents for commission audits. Extracts text from PDFs (including scanned docs via OCR), sends to Claude API for classification, then organizes files into deal folders.

## How it works

1. **Extract text** from PDFs, Word docs, and scanned images (pymupdf + pytesseract OCR)
2. **Classify** each file via Claude API — matches to a deal, identifies doc type and execution status
3. **Organize** files into deal folders with an Unexecuted/ subfolder for drafts

## Setup

```bash
pip install -r requirements.txt
```

Requires [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) installed on your system.

## Usage

1. Update the paths at the top of `commission_audit.py` (SOURCE_DIR, DEALS_CSV, OUTPUT_DIR)
2. Set your API key: `set ANTHROPIC_API_KEY=sk-ant-...`
3. Run: `python commission_audit.py`

## Deal CSV format

year,num,property,type,location,close_date,buyer_seller

## Tech

- **pymupdf** — PDF text extraction
- **pytesseract + Pillow** — OCR for scanned documents
- **python-docx** — Word document parsing
- **anthropic** — Claude API with prompt caching
