#!/usr/bin/env python3
"""
Duplicate File Finder - Find duplicate files in a directory.
"""

import argparse
import hashlib
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

from tqdm import tqdm


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Find duplicate files in a directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Directory path to scan for duplicates",
    )
    return parser.parse_args()


def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except (OSError, IOError) as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return None


def scan_directory(directory: Path) -> List[Path]:
    """Recursively scan directory for all files."""
    files = []
    print("Scanning for files...")
    try:
        # First, count total items for progress bar
        all_items = list(directory.rglob("*"))
        
        # Now filter files with progress bar
        for item in tqdm(all_items, desc="Scanning", unit=" items", leave=False):
            if item.is_file():
                files.append(item)
    except PermissionError as e:
        print(f"Permission denied: {e}", file=sys.stderr)
    return files


def find_duplicates(files: List[Path]) -> Tuple[Dict[str, List[Path]], List[Path]]:
    """
    Find duplicate files based on content hash.
    
    Returns:
        Tuple of (duplicates_dict, unique_files)
        duplicates_dict: hash -> list of duplicate file paths
        unique_files: list of files with no duplicates
    """
    hash_to_files = defaultdict(list)
    
    print("\nCalculating file hashes...")
    for file_path in tqdm(files, desc="Hashing", unit=" files", leave=True):
        file_hash = calculate_file_hash(file_path)
        if file_hash:
            hash_to_files[file_hash].append(file_path)
    
    duplicates = {}
    unique_files = []
    
    for file_hash, file_list in hash_to_files.items():
        if len(file_list) > 1:
            duplicates[file_hash] = file_list
        else:
            unique_files.extend(file_list)
    
    return duplicates, unique_files


def format_output(duplicates: Dict[str, List[Path]], unique_files: List[Path]) -> None:
    """Format and print the results."""
    if duplicates:
        print("=== DUPLICATE FILES ===\n")
        for hash_value, file_list in duplicates.items():
            print(f"The following {len(file_list)} files are identical:")
            for file_path in sorted(file_list):
                try:
                    size = file_path.stat().st_size
                    print(f"  - {file_path} ({size:,} bytes)")
                except OSError:
                    print(f"  - {file_path}")
            print()
    else:
        print("No duplicate files found.\n")
    
    print(f"=== UNIQUE FILES ===\n")
    if unique_files:
        print(f"Found {len(unique_files)} unique files:")
        for file_path in sorted(unique_files)[:10]:  # Show first 10
            print(f"  - {file_path}")
        if len(unique_files) > 10:
            print(f"  ... and {len(unique_files) - 10} more")
    else:
        print("No unique files found.")
    
    # Summary
    print(f"\n=== SUMMARY ===")
    total_files = sum(len(files) for files in duplicates.values()) + len(unique_files)
    duplicate_count = sum(len(files) for files in duplicates.values())
    print(f"Total files scanned: {total_files}")
    print(f"Duplicate files: {duplicate_count}")
    print(f"Unique files: {len(unique_files)}")
    print(f"Duplicate groups: {len(duplicates)}")


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Validate input path
    if not args.path.exists():
        print(f"Error: Path '{args.path}' does not exist", file=sys.stderr)
        sys.exit(1)
    
    if not args.path.is_dir():
        print(f"Error: Path '{args.path}' is not a directory", file=sys.stderr)
        sys.exit(1)
    
    print(f"Scanning directory: {args.path}\n")
    
    # Scan for files
    files = scan_directory(args.path)
    if not files:
        print("No files found in the specified directory.")
        sys.exit(0)
    
    print(f"\nFound {len(files)} files.")
    
    # Find duplicates
    duplicates, unique_files = find_duplicates(files)
    
    # Output results
    format_output(duplicates, unique_files)


if __name__ == "__main__":
    main()