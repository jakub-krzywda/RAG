#!/usr/bin/env python3
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
    "spis literatury",
    "notes"
]

def is_page_number(line: str) -> bool:
    s = line.strip()
    # bardzo krótkie linie z samymi cyframi lub np. "- 123 -"
    s = re.sub(r"[–\-—\s]", "", s)
    return bool(s) and s.isdigit() and len(s) <= 4

def is_separator(line: str) -> bool:
    s = line.strip()
    # same gwiazdki, kreski, kropki itd. (ale nie === które jest separatorem DRM)
    if "===" in s:
        return False
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
        "project gutenberg",
        "zabezpieczony znakiem wodnym",
        "plik jest zabezpieczony"
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

def is_bibliography_section_start(line: str, next_lines: list, line_idx: int, total_lines: int) -> bool:
    """
    Sprawdza czy to rzeczywiście początek sekcji bibliografii/przypisów.
    """
    s = line.strip().lower()
    if not s or len(s) > 50:
        return False
    
    # Sprawdź czy linia pasuje do nagłówka bibliografii
    is_header = False
    for kw in BIBLIO_KEYWORDS:
        # Dokładne dopasowanie lub z numeracją rozdziału
        if s == kw or re.fullmatch(rf"(rozdział\s+)?\d*\.?\s*{re.escape(kw)}[\s\.:;]*", s):
            is_header = True
            break
    
    if not is_header:
        return False
    
    # Jeśli jesteśmy w ostatniej 1/5 książki i znaleźliśmy nagłówek bibliografii,
    # prawdopodobnie to faktycznie bibliografia (nawet bez weryfikacji wzorców)
    if line_idx > total_lines * 0.8:
        return True
    
    # W przeciwnym razie wymagamy weryfikacji wzorców bibliograficznych
    biblio_pattern_count = 0
    citation_like_lines = 0
    
    for next_line in next_lines[:30]:  # Sprawdź następne 30 linii
        nl = next_line.strip()
        if not nl:
            continue
            
        # Wzorce charakterystyczne dla bibliografii
        if re.search(r"\(\d{4}\)", nl):  # (2020)
            biblio_pattern_count += 1
        elif re.search(r"\d{4}[,\.]", nl):  # 2020,
            biblio_pattern_count += 1
        elif re.search(r"[A-Z][a-z]+,\s+[A-Z]\.", nl):  # Kowalski, J.
            biblio_pattern_count += 1
        elif re.search(r"[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+ [A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+,", nl):  # "Nazwisko Imię,"
            biblio_pattern_count += 1
        
        # Linie które wyglądają jak cytowania (zaczynają się od wielkich liter, zawierają daty/miejsca)
        if len(nl) > 20 and nl[0].isupper() and any(x in nl for x in [", ", " – ", "Warszawa", "Kraków", "London", "New York", "red.", "ed.", "przeł."]):
            citation_like_lines += 1
    
    # Jeśli znaleziono wystarczająco dużo wzorców lub linii przypominających cytowania
    return biblio_pattern_count >= 3 or citation_like_lines >= 5

def detect_toc_section(lines):
    """
    Wykrywa początek i koniec spisu treści (TOC).
    Szuka wyraźnego nagłówka "Spis treści" / "Spis rzeczy" i znajduje jego koniec.
    Zwraca (start_idx, end_idx) lub None jeśli nie znaleziono.
    """
    toc_start = None
    
    for i, line in enumerate(lines):
        s = line.strip().lower()
        
        # Szukaj wyraźnego nagłówka spisu treści
        if s in ["spis treści", "spis treści:", "spis rzeczy", "spis rzeczy:", "table of contents", "contents", "contents:"]:
            toc_start = i
            
            # Najpierw znajdź gdzie zaczyna się właściwa treść TOC (pomiń puste linie)
            toc_content_start = i + 1
            while toc_content_start < len(lines) and not lines[toc_content_start].strip():
                toc_content_start += 1
            
            # PRIORYTET 1: Szukaj separatora DRM (===) - to jest najbardziej pewny znacznik końca TOC
            for j in range(toc_content_start, min(toc_content_start + 500, len(lines))):
                line_content = lines[j].strip()
                if "===Lx4t" in line_content or ("===" in line_content and len(line_content) > 30):
                    # Pomiń ten separator i dalsze puste linie
                    k = j + 1
                    while k < len(lines) and not lines[k].strip():
                        k += 1
                    return (toc_start, k)
            
            # PRIORYTET 2: Szukaj innych znaczników końca TOC
            empty_count = 0
            for j in range(toc_content_start, min(toc_content_start + 500, len(lines))):
                line_content = lines[j].strip()
                
                # Linie które sugerują koniec TOC
                if not line_content:
                    empty_count += 1
                    if empty_count >= 5:  # 5 pustych linii
                        return (toc_start, j - 4)
                else:
                    empty_count = 0
                    
                    # Tylko wyraźne sekcje mogą oznaczać koniec TOC
                    lower_line = line_content.lower()
                    # Musi być uppercase lub zawierać charakterystyczne frazy
                    if line_content.isupper() and any(marker in lower_line for marker in ["przedmowa", "wstęp", "wprowadzenie"]):
                        return (toc_start, j)
            
            # Jeśli nie znaleźliśmy końca w sensownym zakresie, ogranicz do 300 linii
            return (toc_start, min(toc_start + 300, len(lines)))
    
    return None

def clean_book(input_path: Path, output_path: Path):
    with open(input_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    total_lines = len(lines)
    
    # Wykryj spis treści
    toc_range = detect_toc_section(lines)
    
    # Wykryj powtarzające się krótkie linie (nagłówki/stopki)
    repeated_short = detect_repeated_short_lines(lines)

    cleaned_lines = []
    in_bibliography = False
    blank_streak = 0

    for i, line in enumerate(lines):
        raw = line.rstrip("\n")

        # Pomiń spis treści
        if toc_range and toc_range[0] <= i < toc_range[1]:
            continue

        # jeśli już weszliśmy w bibliografię – ucinamy resztę
        if in_bibliography:
            continue

        # nagłówki/stopki stron
        if raw.strip() in repeated_short:
            continue

        # bibliografia / przypisy – od tego miejsca dalej nic nie zapisujemy
        # Zbierz następne linie do weryfikacji
        next_lines = [lines[j].rstrip("\n") for j in range(i+1, min(i+31, len(lines)))]
        if is_bibliography_section_start(raw, next_lines, i, total_lines):
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
    if toc_range:
        print(f"Usunięto spis treści (linie {toc_range[0]+1}-{toc_range[1]})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean book text files by removing headers, footers, page numbers, TOC, and bibliography.")
    parser.add_argument("input_file", type=Path, help="Path to input text file")
    parser.add_argument("output_file", nargs="?", type=Path, help="Path to output cleaned text file (optional)")
    
    args = parser.parse_args()
    
    input_path = Path(args.input_file)
    
    if args.output_file:
        output_path = Path(args.output_file)
    else:
        output_path = input_path.with_name(f"{input_path.stem}_cleaned{input_path.suffix}")
    
    clean_book(input_path, output_path)
