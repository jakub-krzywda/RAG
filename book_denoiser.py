import re
import argparse
from pathlib import Path
from collections import Counter

# słowa-klucze po których ucinamy resztę książki (bibliografia, przypisy itd.)
BIBLIO_KEYWORDS = [
    "bibliografia",
    "przypisy",
    "references",
    "bibliography",
    "literatura",
    "spis literatury"
]

def is_page_number(line: str) -> bool:
    s = line.strip()
    # bardzo krótkie linie z samymi cyframi lub np. "- 123 -"
    s = re.sub(r"[–\-—\s]", "", s)
    return bool(s) and s.isdigit() and len(s) <= 4

def is_separator(line: str) -> bool:
    s = line.strip()
    # same gwiazdki, kreski, kropki itd.
    return bool(re.fullmatch(r"[*\-–—•·\.]{3,}", s))

def is_isbn_line(line: str) -> bool:
    s = line.lower()
    if "isbn" in s:
        return True
    # prosta heurystyka: dużo cyfr + myślniki
    digits = sum(c.isdigit() for c in s)
    hyphens = s.count("-")
    return digits >= 10 and hyphens >= 2

def is_publisher_line(line: str) -> bool:
    s = line.lower().strip()
    # proste heurystyki wydawnicze
    patterns = [
        "wydawnictwo",
        "drukarnia",
        "copyright",
        "all rights reserved",
        "project gutenberg"
    ]
    return any(p in s for p in patterns)

def detect_repeated_short_lines(lines, max_len=60, min_freq=5):
    """
    Wykrywa typowe nagłówki/stopki stron:
    krótkie linie, które powtarzają się często.
    """
    counter = Counter()
    for line in lines:
        s = line.strip()
        if s and len(s) <= max_len:
            counter[s] += 1
    repeated = {text for text, cnt in counter.items() if cnt >= min_freq}
    return repeated

def is_bibliography_header(line: str) -> bool:
    s = line.strip().lower()
    # dokładne dopasowania nagłówków
    return any(s == kw or s.startswith(kw) for kw in BIBLIO_KEYWORDS)

def clean_book(input_path: Path, output_path: Path):
    with open(input_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # najpierw wykryjemy powtarzające się krótkie linie (nagłówki/stopki)
    repeated_short = detect_repeated_short_lines(lines)

    cleaned_lines = []
    in_bibliography = False
    blank_streak = 0

    for line in lines:
        raw = line.rstrip("\n")

        # jeśli już weszliśmy w bibliografię – ucinamy resztę
        if in_bibliography:
            continue

        # nagłówki/stopki stron
        if raw.strip() in repeated_short:
            continue

        # bibliografia / przypisy – od tego miejsca dalej nic nie zapisujemy
        if is_bibliography_header(raw):
            in_bibliography = True
            continue

        # numery stron
        if is_page_number(raw):
            continue

        # separatory typu *** --- ...
        if is_separator(raw):
            continue

        # linie z ISBN, info o wydawnictwie
        if is_isbn_line(raw) or is_publisher_line(raw):
            continue

        # normalizacja pustych linii (max 1 pod rząd)
        if raw.strip() == "":
            blank_streak += 1
            if blank_streak > 1:
                continue
            cleaned_lines.append("")
        else:
            blank_streak = 0
            cleaned_lines.append(raw)

    # ewentualnie dodatkowe sprzątanie: usunięcie wiodących/początkowych pustych linii
    while cleaned_lines and cleaned_lines[0].strip() == "":
        cleaned_lines.pop(0)
    while cleaned_lines and cleaned_lines[-1].strip() == "":
        cleaned_lines.pop()

    with open(output_path, "w", encoding="utf-8") as f:
        for line in cleaned_lines:
            f.write(line + "\n")

    print(f"Zapisano oczyszczony tekst do: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean book text files by removing headers, footers, page numbers, and bibliography.")
    parser.add_argument("input_file", type=Path, help="Path to input text file")
    parser.add_argument("output_file", nargs="?", type=Path, help="Path to output cleaned text file (optional)")
    
    args = parser.parse_args()
    
    input_path = Path(args.input_file)
    
    if args.output_file:
        output_path = Path(args.output_file)
    else:
        output_path = input_path.with_name(f"{input_path.stem}_cleaned{input_path.suffix}")
    
    clean_book(input_path, output_path)
