
# True Positive (TP): LLM extracted triple matches XML (via fuzzy).
# False Positive (FP): LLM extracted triple does not match XML and isn’t found in publication (hallucination).
# False Negative (FN): XML triple not found in LLM output.
# True Negative (TN): not very meaningful here (absence of triples), so usually ignored.

# open file with extracted data
    # remove subclass predicates
    # go through remaining triples
        # for each subject and object, check if in schema
            # if yes, drop it
            # if no, check if in xml
                # if yes, we found good data
                # if no, check if in publication
                    # if yes, we found data good data not in xml
                    # if no, llm hallucinated

# partial match: pred + 1 var match
# completely wrong: pred only match
# complete miss: not in xml at all
    # factually correct (in publication)
    # factually incorrect (not in publication)

#                       xml
#                   in      out
#               --------------------
#               |        |         |
#           in  |        |         |
#   paper       |--------|---------|
#           out |        |         |
#               |        |         |
#               --------------------

import csv
import sys
from pathlib import Path
from rapidfuzz import fuzz, process
import xml.etree.ElementTree as ET

# Increase CSV field size limit to avoid field-too-large errors
csv.field_size_limit(sys.maxsize)

# --- Helpers ---
def fuzzy_in(text, candidates, threshold=85):
    if not text or not candidates:
        return False
    text = text.lower()
    candidates_lower = [c.lower() for c in candidates]
    match, score, _ = process.extractOne(text, candidates_lower, scorer=fuzz.token_sort_ratio)
    return score >= threshold

def load_xml_gold(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    gold_data = [elem.text.strip().lower() for elem in root.iter() if elem.text]
    return list(set(gold_data))

def load_schema(schema_path):
    schema_terms = set()
    with open(schema_path, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 3:
                subj, _, obj = row[0].strip(), row[1].strip(), row[2].strip()
                if subj:
                    schema_terms.add(subj.lower())
                if obj:
                    schema_terms.add(obj.lower())
    return schema_terms

# --- Load triples safely ---
def load_triples(triples_path):
    triples = []
    try:
        with open(triples_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                # Case 1: proper triple
                if len(row) >= 3:
                    triples.append((row[0].strip().lower(), row[1].strip().lower(), row[2].strip().lower()))
                # Case 2: single cell with commas inside -> split manually
                elif len(row) == 1 and "," in row[0]:
                    parts = [p.strip().lower() for p in row[0].split(",", 2)]
                    if len(parts) == 3:
                        triples.append(tuple(parts))
    except (csv.Error, UnicodeDecodeError) as e:
        print(f"❌ Skipping {triples_path} due to CSV parsing error: {e}")
        return None

    # Deduplicate triples
    triples = list(set(triples))
    return triples

def evaluate_triples(triples, schema_terms, gold_data, publication_text, threshold=85):
    results = []
    pub_text_lower = publication_text.lower()

    for subj, pred, obj in triples:
        if pred in {"subclassof", "rdfs:subclassof"}:
            continue
        
        if fuzzy_in(subj, schema_terms, threshold) and fuzzy_in(obj, schema_terms, threshold):
            decision = "Dropped (in schema)"
        elif fuzzy_in(subj, gold_data, threshold) or fuzzy_in(obj, gold_data, threshold):
            decision = "Good (matches XML)"
        elif fuzzy_in(subj, pub_text_lower.split(), threshold) or fuzzy_in(obj, pub_text_lower.split(), threshold):
            decision = "Good (found in publication, not XML)"
        else:
            decision = "Hallucinated"
        
        results.append({
            "subject": subj,
            "predicate": pred,
            "object": obj,
            "decision": decision
        })
    
    return results

def summarize(results):
    summary = {}
    for r in results:
        d = r["decision"]
        summary[d] = summary.get(d, 0) + 1
    return summary

# --- Process path ---
def process_path(root_path, schema_terms, gold_data, publication_text):
    root = Path(root_path)
    skipped_files = []

    for child in root.iterdir():
        if child.is_file() and child.suffix.lower() == ".csv":
            # Process single top-level file
            triples = load_triples(child)
            if not triples:
                skipped_files.append(child)
                continue
            results = evaluate_triples(triples, schema_terms, gold_data, publication_text)
            summary = summarize(results)

            print(f"\n=== Summary for file: {child.relative_to(root)} ===")
            for decision, count in summary.items():
                print(f"{decision}: {count}")

            # Optional: print all individual results
            # for r in results:
            #     print(r)

        elif child.is_dir():
            # Process all CSVs in this directory
            all_results = []
            for file_path in child.rglob("*.csv"):
                if ".ipynb_checkpoints" in file_path.parts:
                    continue
                triples = load_triples(file_path)
                if triples:
                    results = evaluate_triples(triples, schema_terms, gold_data, publication_text)
                    all_results.extend(results)
                else:
                    skipped_files.append(file_path)

            if all_results:
                summary = summarize(all_results)
                print(f"\n=== Summary for directory: {child.relative_to(root)} ===")
                for decision, count in summary.items():
                    print(f"{decision}: {count}")

                # Optional: print all individual results
                # for r in all_results:
                #     print(r)

    if skipped_files:
        print("\n❌ Skipped files due to errors:")
        for f in skipped_files:
            print(f.relative_to(root))

# --- Example usage ---
if __name__ == "__main__":
    extracted_dir = "extracted-knowledge"  # path to cleaned files
    schema_terms = load_schema("triples.csv")
    gold_data = load_xml_gold("L156_S2_Roy_2007.xml")
    
    with open("publication.md", "r") as f:
        publication_text = f.read()
    
    process_path(extracted_dir, schema_terms, gold_data, publication_text)





# from rapidfuzz import fuzz, process
# import xml.etree.ElementTree as ET
# import csv

# # --- Helpers ---
# def fuzzy_in(text, candidates, threshold=85):
#     """Return True if text matches any candidate above threshold (case-insensitive)."""
#     if not text or not candidates:
#         return False
#     text = text.lower()
#     candidates_lower = [c.lower() for c in candidates]
#     match, score, _ = process.extractOne(text, candidates_lower, scorer=fuzz.token_sort_ratio)
#     return score >= threshold

# # --- Load XML gold standard ---
# def load_xml_gold(xml_path):
#     tree = ET.parse(xml_path)
#     root = tree.getroot()
#     # Adjust depending on XML structure
#     gold_data = [elem.text.strip().lower() for elem in root.iter() if elem.text]
#     return list(set(gold_data))

# # --- Load schema terms from CSV into a set (case-insensitive) ---
# def load_schema(schema_path):
#     schema_terms = set()
#     with open(schema_path, "r") as f:
#         reader = csv.reader(f)
#         for row in reader:
#             if len(row) >= 3:
#                 subj, _, obj = row[0].strip(), row[1].strip(), row[2].strip()
#                 if subj:
#                     schema_terms.add(subj.lower())
#                 if obj:
#                     schema_terms.add(obj.lower())
#     return schema_terms

# # --- Load triples from CSV ---
# def load_triples(triples_path):
#     triples = []
#     with open(triples_path, "r") as f:
#         reader = csv.reader(f)
#         for row in reader:
#             if len(row) >= 3:
#                 triples.append((row[0].strip().lower(), row[1].strip().lower(), row[2].strip().lower()))
#     return triples

# # --- Evaluate triples ---
# def evaluate_triples(triples, schema_terms, gold_data, publication_text, threshold=85):
#     results = []
#     pub_text_lower = publication_text.lower()

#     for subj, pred, obj in triples:
#         if pred in {"subclassof", "rdfs:subclassof"}:
#             continue  # drop subclass predicates
        
#         decision = ""
        
#         # 1. Schema check (both subj and obj must be in schema)
#         if fuzzy_in(subj, schema_terms, threshold) and fuzzy_in(obj, schema_terms, threshold):
#             decision = "Dropped (in schema)"
        
#         # 2. Check gold XML
#         elif fuzzy_in(subj, gold_data, threshold) or fuzzy_in(obj, gold_data, threshold):
#             decision = "Good (matches XML)"
        
#         # 3. Check publication text (case-insensitive)
#         elif fuzzy_in(subj, pub_text_lower.split(), threshold) or fuzzy_in(obj, pub_text_lower.split(), threshold):
#             decision = "Good (found in publication, not XML)"
        
#         else:
#             decision = "Hallucinated"
        
#         results.append({
#             "subject": subj,
#             "predicate": pred,
#             "object": obj,
#             "decision": decision
#         })
    
#     return results

# # --- Example usage ---
# if __name__ == "__main__":
#     # triples = load_triples("phi4-mini_latest-64k-True-False-True-False-knowledge-extraction.csv")
#     triples = load_triples("extracted-knowledge/claude-sonnet-4-20250514-False-False-True-True-knowledge-extraction/Material.csv")
#     schema_terms = load_schema("triples.csv")
#     gold_data = load_xml_gold("L156_S2_Roy_2007.xml")
    
#     with open("publication.md", "r") as f:
#         publication_text = f.read()
    
#     results = evaluate_triples(triples, schema_terms, gold_data, publication_text)
    
#     for r in results:
#         print(r)















# import csv
# import xml.etree.ElementTree as ET
# from difflib import SequenceMatcher

# # -----------------------------
# # Helpers
# # -----------------------------
# def fuzzy_match(a: str, b: str, threshold: float = 0.85) -> bool:
#     """Return True if strings are similar above threshold."""
#     return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= threshold


# def parse_xml_entities(xml_path: str):
#     """Parse XML and collect all text values into a set of entities."""
#     tree = ET.parse(xml_path)
#     root = tree.getroot()

#     entities = set()
#     for elem in root.iter():
#         if elem.text and elem.text.strip():
#             entities.add(elem.text.strip())
#     return entities


# def load_extracted_triples(csv_path: str):
#     """Load triples from a CSV file with columns: subject,predicate,object."""
#     triples = []
#     with open(csv_path, newline="", encoding="utf-8") as csvfile:
#         reader = csv.DictReader(csvfile)
#         for row in reader:
#             subj = row.get("subject", "").strip()
#             pred = row.get("predicate", "").strip()
#             obj = row.get("object", "").strip()
#             if subj and pred and obj:
#                 triples.append((subj, pred, obj))
#     return triples


# def load_schema(csv_path: str):
#     """Load schema elements (subjects, predicates, objects) from a CSV file."""
#     schema = set()
#     with open(csv_path, newline="", encoding="utf-8") as csvfile:
#         reader = csv.DictReader(csvfile)
#         for row in reader:
#             subj = row.get("subject", "").strip()
#             pred = row.get("predicate", "").strip()
#             obj = row.get("object", "").strip()
#             if subj:
#                 schema.add(subj)
#             if pred:
#                 schema.add(pred)
#             if obj:
#                 schema.add(obj)
#     return schema


# def is_in_schema(subject: str, predicate: str, obj: str, schema):
#     """Check whether any part of the triple is in schema."""
#     return subject in schema or predicate in schema or obj in schema


# def check_in_publication(triple, publication_text: str) -> bool:
#     """Naive check: fuzzy search subject/object in publication text."""
#     subj, _, obj = triple
#     return (subj.lower() in publication_text.lower()) or (obj.lower() in publication_text.lower())


# # -----------------------------
# # Core classification
# # -----------------------------
# def classify_triples(extracted_triples, xml_entities, schema, publication_text):
#     results = []

#     for subj, pred, obj in extracted_triples:
#         # skip subclass predicates
#         if pred.lower() == "subclass":
#             continue

#         # drop if in schema
#         if is_in_schema(subj, pred, obj, schema):
#             continue

#         # check if subject or object in XML entities
#         found_in_xml = any(
#             fuzzy_match(subj, e) or fuzzy_match(obj, e) for e in xml_entities
#         )

#         if found_in_xml:
#             results.append(((subj, pred, obj), "good: in xml"))
#             continue

#         # check in publication
#         if check_in_publication((subj, pred, obj), publication_text):
#             results.append(((subj, pred, obj), "good: in publication but not xml"))
#         else:
#             results.append(((subj, pred, obj), "hallucinated"))

#     return results


# # -----------------------------
# # Example usage
# # -----------------------------
# if __name__ == "__main__":
#     xml_entities = parse_xml_entities("L156_S2_Roy_2007.xml")
#     schema = load_schema("triples.csv")  # CSV file with columns subject,predicate,object

#     # load extracted triples from a CSV file
#     extracted_triples = load_extracted_triples("phi4-mini_latest-64k-True-False-True-False-knowledge-extraction.csv")

#     with open("publication.md", encoding="utf-8") as f:
#         publication_text = f.read()

#     results = classify_triples(extracted_triples, xml_entities, schema, publication_text)

#     for triple, status in results:
#         print(triple, "->", status)












# import xml.etree.ElementTree as ET
# from difflib import SequenceMatcher

# # -----------------------------
# # Helpers
# # -----------------------------
# def fuzzy_match(a: str, b: str, threshold: float = 0.85) -> bool:
#     """Return True if strings are similar above threshold."""
#     return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= threshold


# def parse_xml_reference(xml_path: str):
#     """Parse XML into set of reference triples (subject, predicate, object)."""
#     tree = ET.parse(xml_path)
#     root = tree.getroot()

#     triples = set()
#     for triple in root.findall(".//triple"):  # adjust path to your schema
#         subj = triple.findtext("subject")
#         pred = triple.findtext("predicate")
#         obj = triple.findtext("object")
#         if subj and pred and obj:
#             triples.add((subj.strip(), pred.strip(), obj.strip()))
#     return triples


# def is_in_schema(subject: str, predicate: str, obj: str, schema):
#     """Check whether triple matches known schema."""
#     return predicate in schema


# def check_in_publication(triple, publication_text: str) -> bool:
#     """Naive check: fuzzy search subject/object in publication text."""
#     subj, _, obj = triple
#     return (subj.lower() in publication_text.lower()) or (obj.lower() in publication_text.lower())


# # -----------------------------
# # Core evaluation with metrics
# # -----------------------------
# def evaluate_extraction(extracted_triples, xml_triples, schema, publication_text):
#     TP, FP, FN = 0, 0, 0
#     good_but_not_xml = 0

#     # Check each extracted triple
#     for subj, pred, obj in extracted_triples:
#         # skip subclass predicates
#         if pred.lower() == "subclass":
#             continue

#         # drop if in schema
#         if is_in_schema(subj, pred, obj, schema):
#             continue

#         # check against XML
#         found_in_xml = any(
#             fuzzy_match(subj, s) and fuzzy_match(pred, p) and fuzzy_match(obj, o)
#             for (s, p, o) in xml_triples
#         )

#         if found_in_xml:
#             TP += 1
#         else:
#             # check in publication
#             if check_in_publication((subj, pred, obj), publication_text):
#                 good_but_not_xml += 1
#             else:
#                 FP += 1

#     # Count false negatives: XML triples missed by extraction
#     for (s, p, o) in xml_triples:
#         found_in_extracted = any(
#             fuzzy_match(s, subj) and fuzzy_match(p, pred) and fuzzy_match(o, obj)
#             for (subj, pred, obj) in extracted_triples
#         )
#         if not found_in_extracted:
#             FN += 1

#     # Precision, recall, F1
#     precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
#     recall = TP / (TP + FN) if (TP + FN) > 0 else 0.0
#     f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

#     return {
#         "true_positives": TP,
#         "false_positives": FP,
#         "false_negatives": FN,
#         "good_not_in_xml": good_but_not_xml,
#         "precision": precision,
#         "recall": recall,
#         "f1": f1,
#     }


# # -----------------------------
# # Example usage
# # -----------------------------
# if __name__ == "__main__":
#     xml_triples = parse_xml_reference("reference.xml")
#     schema = {"type", "author", "date"}
#     extracted_triples = [
#         ("Aspirin", "treats", "Headache"),
#         ("Ibuprofen", "subclass", "NSAID"),
#         ("Paracetamol", "author", "Smith et al."),
#     ]
#     with open("publication.txt") as f:
#         publication_text = f.read()

#     metrics = evaluate_extraction(extracted_triples, xml_triples, schema, publication_text)

#     for k, v in metrics.items():
#         print(f"{k}: {v}")
