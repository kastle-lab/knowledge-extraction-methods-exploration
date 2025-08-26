import csv
from pathlib import Path

# 👇 Change this to your base directory
ROOT_DIR = "extracted-knowledge"

def clean_triples(input_file):
    triples = []
    with open(input_file, newline='', encoding='utf-8') as infile:
        reader = csv.reader(infile)
        for row in reader:
            if not row:
                continue  # skip empty lines

            # case 1: proper triple
            if len(row) == 3:
                # skip header row
                if [c.strip().lower() for c in row] == ["subject", "predicate", "object"]:
                    continue
                triples.append([c.strip() for c in row])
            
            # case 2: single cell with commas inside -> split manually
            elif len(row) == 1 and "," in row[0]:
                parts = [p.strip() for p in row[0].split(",", 2)]  # split into 3 parts max
                if len(parts) == 3:
                    triples.append(parts)

            # else: malformed row → skip
            else:
                continue

    # overwrite the same file
    with open(input_file, "w", newline='', encoding='utf-8') as outfile:
        writer = csv.writer(outfile, quoting=csv.QUOTE_ALL)
        writer.writerows(triples)

def should_clean(file_path: Path) -> bool:
    # skip any file in .ipynb_checkpoints
    if ".ipynb_checkpoints" in file_path.parts:
        return False
    # condition 1: filename contains "knowledge-extraction"
    if "knowledge-extraction" in file_path.name:
        return True
    # condition 2: any parent directory contains "knowledge-extraction"
    if any("knowledge-extraction" in part for part in file_path.parts):
        return True
    return False

def process_directory(root_dir):
    root_path = Path(root_dir)
    for file_path in root_path.rglob("*"):
        if file_path.is_file():
            if should_clean(file_path):
                try:
                    clean_triples(file_path)
                    print(f"✅ Cleaned: {file_path.relative_to(root_path)}")
                except Exception as e:
                    print(f"❌ Error cleaning {file_path.relative_to(root_path)}: {e}")
            else:
                if ".ipynb_checkpoints" not in file_path.parts:
                    print(f"⏩ Skipped: {file_path.relative_to(root_path)}")
        # else: skip directories silently


if __name__ == "__main__":
    process_directory(ROOT_DIR)
