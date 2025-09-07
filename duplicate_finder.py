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


def calculate_file_hash(file_path: Path, partial: bool = False) -> str:
    """
    Calculate SHA256 hash of a file.
    
    Args:
        file_path: Path to the file
        partial: If True, only hash first 4KB for quick comparison
    """
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            if partial:
                # Read only first 4KB for partial hash
                data = f.read(4096)
                if data:
                    sha256_hash.update(data)
            else:
                # Read entire file in chunks
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except (OSError, IOError) as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return None


def get_file_size(file_path: Path) -> int:
    """Get file size in bytes."""
    try:
        return file_path.stat().st_size
    except (OSError, IOError):
        return -1


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
    Find duplicate files using multi-stage comparison.
    
    Stage 1: Group by file size
    Stage 2: Partial hash (first 4KB) for same-size files
    Stage 3: Full hash only when partial hashes match
    
    Returns:
        Tuple of (duplicates_dict, unique_files)
        duplicates_dict: hash -> list of duplicate file paths
        unique_files: list of files with no duplicates
    """
    print("\n=== Stage 1: Grouping files by size ===")
    
    # Stage 1: Group files by size
    size_to_files = defaultdict(list)
    for file_path in tqdm(files, desc="Analyzing sizes", unit=" files", leave=False):
        size = get_file_size(file_path)
        if size >= 0:
            size_to_files[size].append(file_path)
    
    # Count files that need further checking
    files_needing_hash = sum(len(group) for group in size_to_files.values() if len(group) > 1)
    unique_by_size = sum(1 for group in size_to_files.values() if len(group) == 1)
    
    print(f"  Found {len(size_to_files)} unique file sizes")
    print(f"  {unique_by_size} files are unique by size alone")
    print(f"  {files_needing_hash} files need content comparison")
    
    # Early exit if no potential duplicates
    if files_needing_hash == 0:
        unique_files = [f for group in size_to_files.values() for f in group]
        return {}, unique_files
    
    print("\n=== Stage 2: Partial hash comparison ===")
    
    # Stage 2: Partial hash for files with same size
    partial_hash_to_files = defaultdict(list)
    candidates_for_full_hash = []
    
    for size, file_group in tqdm(size_to_files.items(), desc="Partial hashing", unit=" groups", leave=False):
        if len(file_group) == 1:
            # Unique by size
            continue
        
        # Calculate partial hashes for this size group
        size_partial_hashes = defaultdict(list)
        for file_path in file_group:
            partial_hash = calculate_file_hash(file_path, partial=True)
            if partial_hash:
                # Combine size and partial hash for unique key
                key = f"{size}:{partial_hash}"
                size_partial_hashes[key].append(file_path)
        
        # Check which need full hashing
        for partial_key, partial_group in size_partial_hashes.items():
            if len(partial_group) > 1:
                candidates_for_full_hash.extend(partial_group)
            else:
                # Unique by partial hash
                pass
    
    print(f"  {len(candidates_for_full_hash)} files need full content comparison")
    
    print("\n=== Stage 3: Full hash comparison ===")
    
    # Stage 3: Full hash only for files with matching partial hashes
    full_hash_to_files = defaultdict(list)
    
    # Group candidates by size and partial hash for efficient full hashing
    candidate_groups = defaultdict(list)
    for file_path in candidates_for_full_hash:
        size = get_file_size(file_path)
        partial = calculate_file_hash(file_path, partial=True)
        if size >= 0 and partial:
            candidate_groups[f"{size}:{partial}"].append(file_path)
    
    for group_key, group_files in tqdm(candidate_groups.items(), desc="Full hashing", unit=" groups", leave=True):
        for file_path in group_files:
            full_hash = calculate_file_hash(file_path, partial=False)
            if full_hash:
                full_hash_to_files[full_hash].append(file_path)
    
    # Compile final results
    duplicates = {}
    unique_files = []
    
    # Add unique-by-size files
    for size, file_group in size_to_files.items():
        if len(file_group) == 1:
            unique_files.extend(file_group)
    
    # Add files that were unique after partial/full hashing
    processed_files = set(candidates_for_full_hash)
    for size, file_group in size_to_files.items():
        if len(file_group) > 1:
            for file_path in file_group:
                if file_path not in processed_files:
                    unique_files.append(file_path)
    
    # Add duplicates and remaining unique files from full hash
    for full_hash, file_list in full_hash_to_files.items():
        if len(file_list) > 1:
            duplicates[full_hash] = file_list
        else:
            unique_files.extend(file_list)
    
    print(f"  Optimization complete!")
    
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