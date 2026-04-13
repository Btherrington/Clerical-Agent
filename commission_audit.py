import os
import csv
import json
import re
import shutil
import pymupdf
from docx import Document
from PIL import Image
import pytesseract
import anthropic


SOURCE_DIR = r"C:\path\to\your\documents"
DEALS_CSV  = r"C:\path\to\deals.csv"
OUTPUT_DIR = r"C:\path\to\Audit_Organized"
RESULTS_FILE = "classifications.json"
MAX_TEXT   = 10000     
COST_LIMIT = 50.00     




def extract_pdf(path):
    """Read text from a PDF. If a page is scanned, use OCR instead."""
    doc = pymupdf.open(path)
    all_text = []

    for page in doc:
        text = page.get_text().strip()

        if text:
            all_text.append(text)
        else:
           
            pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            ocr_text = pytesseract.image_to_string(img).strip()
            if ocr_text:
                all_text.append(ocr_text)

    doc.close()
    return "\n".join(all_text)


def extract_docx(path):
    """Read text from a Word document."""
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_image(path):
    """Read text from an image using OCR."""
    return pytesseract.image_to_string(Image.open(path)).strip()


def extract_text(path):
    """Pick the right extractor based on file type."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".pdf":              return extract_pdf(path)
        if ext in (".docx", ".doc"):   return extract_docx(path)
        if ext in (".jpg", ".jpeg", ".png", ".tiff"): return extract_image(path)
    except Exception:
        pass
    return ""



def load_deals(csv_path):
    """Read the deal list. Returns a list of dicts."""
    deals = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            deals.append({
                "year": int(row["year"]),
                "num": int(row["num"]),
                "property": row["property"].strip(),
                "type": row["type"].strip(),
                "location": row["location"].strip(),
                "close_date": row.get("close_date", "").strip(),
                "buyer_seller": row.get("buyer_seller", "").strip(),
            })
    return deals



def build_prompt(deals):
    """Build the system prompt with the deal list for Claude."""
    lines = [
        "You classify commercial real estate files for a commission audit.",
        "",
        "DEAL LIST:",
        "ID | Property | Type | Location | Close | Buyer/Seller",
    ]
    for d in deals:
        did = f"{d['year']}-{d['num']:02d}"
        bs = d["buyer_seller"] or "-"
        lines.append(f"{did} | {d['property']} | {d['type']} | "
                      f"{d['location']} | {d['close_date']} | {bs}")

    lines.append("")
    lines.append("DOC TYPES: Purchase and Sale Agreement | Lease Agreement | RECAD | "
                  "Brokerage Agreement | Closing Statement | Agency Disclosure | "
                  "Single Agent Designation | Amendment/Addendum | Letter of Intent | "
                  "Option Agreement | Other/Unknown")
    lines.append("")
    lines.append("EXECUTION STATUS: Fully Executed | Partially Executed | Draft | Unknown")
    lines.append("")
    lines.append('Return ONLY JSON: {"deal_id":"YYYY-NN","doc_type":"...","exec_status":"...","confidence":"high|medium|low"}')
    return "\n".join(lines)


def classify_file(client, prompt, filename, text):
    """Send one file to Claude and get back a classification."""
    message = f"Filename: {filename}\n\n"
    if text.strip():
        message += f"Text:\n{text[:MAX_TEXT]}"
    else:
        message += "(No text available. Classify from filename only.)"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=150,
        system=[{
            "type": "text",
            "text": prompt,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": message}],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw).strip()
    return json.loads(raw)



def make_deal_folder_name(deal):
    """Turn a deal into a folder name like '2025_39_13_Acres_Hwy_64'."""
    prop = re.sub(r"[^a-zA-Z0-9 _-]", "", deal["property"])
    prop = prop.strip().replace(" ", "_")
    return f"{deal['year']}_{deal['num']:02d}_{prop}"


def move_file(source_path, dest_folder, filename):
    """Move a file into dest_folder, adding _1/_2 if name already exists."""
    os.makedirs(dest_folder, exist_ok=True)
    dest_name = filename
    n = 1
    while os.path.exists(os.path.join(dest_folder, dest_name)):
        base, ext = os.path.splitext(filename)
        dest_name = f"{base}_{n}{ext}"
        n += 1
    shutil.move(source_path, os.path.join(dest_folder, dest_name))



def main():
    
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    deals = load_deals(DEALS_CSV)
    prompt = build_prompt(deals)
    deal_lookup = {f"{d['year']}-{d['num']:02d}": d for d in deals}

   
    results = {}
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            results = json.load(f)

    
    valid_exts = {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".tiff"}
    files = [f for f in sorted(os.listdir(SOURCE_DIR))
             if os.path.splitext(f)[1].lower() in valid_exts]

    print(f"Files to process: {len(files)}")
    print(f"Already done: {len(results)}")
    total_cost = 0.0

    
    for i, filename in enumerate(files, 1):
        if filename in results:
            continue
        if total_cost >= COST_LIMIT:
            print(f"Cost limit ${COST_LIMIT} reached, stopping.")
            break

        filepath = os.path.join(SOURCE_DIR, filename)
        text = extract_text(filepath)

        try:
            result = classify_file(client, prompt, filename, text)
        except Exception as e:
            print(f"  Error on {filename}: {e}")
            continue

        results[filename] = result

       
        if i % 10 == 0:
            with open(RESULTS_FILE, "w") as f:
                json.dump(results, f, indent=2)

        deal_id = result.get("deal_id") or "null"
        doc_type = result.get("doc_type", "?")
        print(f"  {i}/{len(files)}  {deal_id:<10} {doc_type:<30} {filename}")

  
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)

   
    print(f"\nOrganizing files into {OUTPUT_DIR} ...")

    for filename, result in results.items():
        filepath = os.path.join(SOURCE_DIR, filename)
        if not os.path.exists(filepath):
            continue

        deal_id = result.get("deal_id")
        exec_status = result.get("exec_status", "Unknown")

        if deal_id and deal_id in deal_lookup:
            deal = deal_lookup[deal_id]
            folder = make_deal_folder_name(deal)

            if exec_status == "Draft":
                dest = os.path.join(OUTPUT_DIR, folder, "Unexecuted")
            else:
                dest = os.path.join(OUTPUT_DIR, folder)
        else:
            dest = os.path.join(OUTPUT_DIR, "Needs_Review")

        move_file(filepath, dest, filename)

    print("Done.")


if __name__ == "__main__":
    main()
