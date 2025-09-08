#!/usr/bin/env python3
"""
Command-line interface for duplicate file finder.
"""

import argparse
import sys
import logging
from pathlib import Path

from .scanner import scan_directory
from .detector import find_duplicates
from .memory_efficient_detector import find_duplicates_memory_efficient
from .formatter import format_output, format_json_output
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
    parser.add_argument(
        "-o", "--output",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress non-error output",
    )
    parser.add_argument(
        "--memory-efficient",
        action="store_true",
        help="Use memory-efficient mode for very large directories",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for memory-efficient mode (default: 1000)",
    )
    parser.add_argument(
        "--adaptive",
        action="store_true",
        help="Use adaptive optimization based on system resources",
    )
    parser.add_argument(
        "--workers",
        type=int,
        help="Manual override for worker count",
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Validate conflicting flags
    if args.verbose and args.quiet:
        print("Error: Cannot use both --verbose and --quiet flags", file=sys.stderr)
        sys.exit(1)
    
    # Setup logging based on verbosity
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format='%(message)s')
    elif args.quiet:
        logging.basicConfig(level=logging.ERROR, format='%(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    # Validate input path
    if not args.path.exists():
        print(f"Error: Path '{args.path}' does not exist", file=sys.stderr)
        sys.exit(1)
    
    if not args.path.is_dir():
        print(f"Error: Path '{args.path}' is not a directory", file=sys.stderr)
        sys.exit(1)
    
    if not args.quiet:
        print(f"Scanning directory: {args.path}\n")
    
    # Scan for files
    files = scan_directory(args.path, verbose=args.verbose, quiet=args.quiet)
    if not files:
        if not args.quiet:
            print("No files found in the specified directory.")
        sys.exit(0)
    
    if not args.quiet:
        print(f"\nFound {len(files)} files.")
    
    # Find duplicates
    if args.memory_efficient:
        if not args.quiet:
            print(f"Using memory-efficient mode with batch size {args.batch_size}")
        duplicates, unique_files, duplicate_folders = find_duplicates_memory_efficient(
            files, 
            batch_size=args.batch_size,
            verbose=args.verbose, 
            quiet=args.quiet
        )
    else:
        duplicates, unique_files, duplicate_folders = find_duplicates(
            files, 
            verbose=args.verbose, 
            quiet=args.quiet,
            adaptive=args.adaptive,
            manual_workers=args.workers
        )
    
    # Output results based on format
    if args.output == "json":
        format_json_output(duplicates, unique_files, duplicate_folders)
    else:
        format_output(duplicates, unique_files, duplicate_folders, quiet=args.quiet)
    
    # Show final warning summary from hashing operations (unless quiet or json)
    if not args.quiet and args.output != "json":
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