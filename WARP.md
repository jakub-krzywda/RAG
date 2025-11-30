# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Repository Overview

This is a Python project for text cleaning, specifically designed to process and clean book text files. The main functionality removes unwanted elements such as page numbers, headers/footers, separators, ISBN information, and bibliography sections from digitized book texts.

## Core Components

- **book_denoiser.py**: Main script containing text cleaning logic with functions to:
  - Detect and remove page numbers
  - Remove repeated short lines (headers/footers)
  - Remove separator characters (***, ---, etc.)
  - Filter out ISBN lines and publisher information
  - Remove bibliography and reference sections
  - Normalize blank lines

## Development Commands

### Running the script
```bash
python3 book_denoiser.py input.txt output.txt
```

If the output file is not specified, the script will automatically create a new file with "_cleaned" suffix:
```bash
python3 book_denoiser.py input.txt
```
This creates `input_cleaned.txt` from `input.txt`.

The script accepts both relative and absolute paths for input and output files.

### Virtual Environment
The repository uses a virtual environment located in `.venv/`. Make sure it's activated before running the script:

```bash
source .venv/bin/activate  # On macOS/Linux
```

## File Structure

- `book_denoiser.py`: Main script with text cleaning logic accepting command-line arguments
- `input.txt`: Example of an input file to be processed (not included in repo)
- `filename_cleaned.txt`: Output file with cleaned text (auto-generated if not specified)
- `.venv/`: Python virtual environment

## Text Processing Pipeline

The script processes text in the following order:
1. Detects repeated short lines that are likely headers/footers
2. Identifies bibliography/reference sections and truncates after them
3. Filters out page numbers, separators, and publisher information
4. Normalizes blank lines (no more than one consecutive blank line)
5. Removes leading and trailing blank lines

## Key Functions

- `is_page_number()`: Detects line numbers with various formatting
- `is_separator()`: Identifies visual separators made of repeated characters
- `detect_repeated_short_lines()`: Automatically detects likely headers/footers
- `clean_book()`: Main processing function that orchestrates the cleaning pipeline
- Command-line interface: Uses argparse and pathlib to handle input/output file paths, with auto-generated output filename when not specified
