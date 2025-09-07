"""
Output formatting for duplicate detection results.
"""

from pathlib import Path
from typing import Dict, List


def format_output(duplicates: Dict[str, List[Path]], unique_files: List[Path]) -> None:
    """
    Format and print the results.
    
    Args:
        duplicates: Dictionary mapping hash to list of duplicate files
        unique_files: List of unique files
    """
    if duplicates:
        print("\n=== DUPLICATE FILES ===\n")
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
        print("\nNo duplicate files found.\n")
    
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