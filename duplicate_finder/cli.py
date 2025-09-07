#!/usr/bin/env python3
"""
Command-line interface for duplicate file finder.
"""

import argparse
import sys
from pathlib import Path

from .scanner import scan_directory
from .detector import find_duplicates
from .formatter import format_output
from .hasher import get_warning_summary


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
    duplicates, unique_files, duplicate_folders = find_duplicates(files)
    
    # Output results
    format_output(duplicates, unique_files, duplicate_folders)
    
    # Show final warning summary from hashing operations
    warning_summary = get_warning_summary()
    total_hash_warnings = sum(warning_summary.values())
    if total_hash_warnings > 0:
        print(f"\n⚠️  Processing warnings summary:", file=sys.stderr)
        for warning_type, count in warning_summary.items():
            if count > 0:
                warning_name = warning_type.replace('_', ' ').title()
                print(f"  • {warning_name}: {count} files", file=sys.stderr)


if __name__ == "__main__":
    main()