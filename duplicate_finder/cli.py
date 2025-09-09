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
from .fast_detector import fast_find_duplicates, format_duplicate_report
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
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use fast metadata-only mode (no hashing) - optimized for HDDs",
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()
    
    # Validate conflicting flags
    if args.verbose and args.quiet:
        print("Error: Cannot use both --verbose and --quiet flags", file=sys.stderr)
        sys.exit(1)
    
    if args.fast and (args.memory_efficient or args.adaptive or args.workers):
        print("Error: --fast mode cannot be combined with --memory-efficient, --adaptive, or --workers", file=sys.stderr)
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
    
    if not args.quiet and args.output != "json":
        print(f"Scanning directory: {args.path}\n")
    
    # Fast mode - use metadata-only detection
    if args.fast:
        if not args.quiet and args.output != "json":
            print("Using fast metadata-only mode (optimized for HDDs)")
        
        try:
            duplicate_groups, unique_files = fast_find_duplicates(
                args.path, 
                verbose=args.verbose, 
                quiet=args.quiet
            )
            
            # Output results
            if args.output == "json":
                # Convert to expected format for JSON output
                import json
                
                # Build JSON structure directly
                json_output = {
                    "duplicate_files": [],
                    "unique_files": [],
                    "duplicate_folders": [],
                    "statistics": {}
                }
                
                # Add duplicate groups
                for group in duplicate_groups:
                    group_data = {
                        "files": [],
                        "count": len(group.files),
                        "match_type": group.match_type
                    }
                    for file_meta in group.files:
                        group_data["files"].append({
                            "path": str(file_meta.path),
                            "size": file_meta.size,
                            "size_formatted": f"{file_meta.size / (1024*1024):.1f} MB"
                        })
                    json_output["duplicate_files"].append(group_data)
                
                # Add unique files
                for file_meta in unique_files:
                    json_output["unique_files"].append({
                        "path": str(file_meta.path),
                        "size": file_meta.size,
                        "size_formatted": f"{file_meta.size / (1024*1024):.1f} MB"
                    })
                
                # Add statistics
                total_files = len(unique_files) + sum(len(g.files) for g in duplicate_groups)
                duplicate_files_count = sum(len(g.files) for g in duplicate_groups)
                total_duplicate_size = sum(
                    g.files[0].size * (len(g.files) - 1) 
                    for g in duplicate_groups
                )
                
                json_output["statistics"] = {
                    "total_files": total_files,
                    "duplicate_files_count": duplicate_files_count,
                    "unique_files_count": len(unique_files),
                    "duplicate_groups_count": len(duplicate_groups),
                    "total_potential_savings": total_duplicate_size,
                    "total_potential_savings_formatted": f"{total_duplicate_size / (1024**3):.2f} GB"
                }
                
                print(json.dumps(json_output, indent=2))
            else:
                output = format_duplicate_report(duplicate_groups, unique_files, args.verbose)
                print(output)
            
            sys.exit(0)
            
        except Exception as e:
            print(f"Error in fast mode: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Standard modes - scan for files first
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