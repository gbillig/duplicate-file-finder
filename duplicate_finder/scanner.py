"""
Directory scanning functionality.
"""

import sys
from pathlib import Path
from typing import List, Dict

from tqdm import tqdm


class ScanResult:
    """Container for scan results and warnings."""
    
    def __init__(self):
        self.files: List[Path] = []
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self.skipped_items: Dict[str, int] = {
            'permission_denied': 0,
            'broken_symlinks': 0,
            'unreadable_files': 0,
            'other_errors': 0
        }


def scan_directory(directory: Path) -> List[Path]:
    """
    Recursively scan directory for all files using streaming approach.
    
    This optimized version processes files as they're discovered without
    collecting all directory entries in memory first. This is much more
    efficient for directories with large numbers of files (100k+).
    
    Args:
        directory: Path to directory to scan
        
    Returns:
        List of Path objects for all files found
    """
    result = scan_directory_detailed(directory)
    
    # Print warnings if any
    if result.warnings:
        print(f"\n⚠️  Scan completed with {len(result.warnings)} warnings:", file=sys.stderr)
        for warning in result.warnings[:5]:  # Show first 5 warnings
            print(f"  • {warning}", file=sys.stderr)
        if len(result.warnings) > 5:
            print(f"  • ... and {len(result.warnings) - 5} more warnings", file=sys.stderr)
    
    # Print summary of skipped items
    total_skipped = sum(result.skipped_items.values())
    if total_skipped > 0:
        print(f"\n📊 Skipped {total_skipped} items:", file=sys.stderr)
        for item_type, count in result.skipped_items.items():
            if count > 0:
                item_name = item_type.replace('_', ' ').title()
                print(f"  • {item_name}: {count}", file=sys.stderr)
    
    return result.files


def scan_directory_detailed(directory: Path) -> ScanResult:
    """
    Recursively scan directory with detailed error tracking and robust error handling.
    
    Args:
        directory: Path to directory to scan
        
    Returns:
        ScanResult containing files, warnings, and error statistics
    """
    result = ScanResult()
    print("Scanning for files...")
    
    try:
        items_processed = 0
        with tqdm(desc="Scanning", unit=" items", leave=False) as pbar:
            try:
                for item in directory.rglob("*"):
                    items_processed += 1
                    pbar.update(1)
                    
                    # Process this item with error handling
                    _process_item(item, result)
                    
                    # Update progress display
                    if items_processed % 1000 == 0 or len(result.files) % 500 == 0:
                        pbar.set_postfix(
                            files=len(result.files), 
                            warnings=len(result.warnings),
                            refresh=False
                        )
                    
                    # Handle very large directories by periodic refresh
                    if items_processed % 10000 == 0:
                        pbar.refresh()
                        
            except PermissionError as e:
                result.errors.append(f"Permission denied accessing directory: {e}")
                result.skipped_items['permission_denied'] += 1
            except OSError as e:
                result.errors.append(f"OS error during directory traversal: {e}")
                result.skipped_items['other_errors'] += 1
                    
    except KeyboardInterrupt:
        print(f"\nScan interrupted. Found {len(result.files)} files so far.", file=sys.stderr)
        raise
    
    return result


def _process_item(item: Path, result: ScanResult) -> None:
    """Process a single directory item with comprehensive error handling."""
    try:
        # Check if it's a symlink first
        if item.is_symlink():
            try:
                # Try to resolve the symlink
                resolved = item.resolve()
                if not resolved.exists():
                    result.warnings.append(f"Broken symlink: {item}")
                    result.skipped_items['broken_symlinks'] += 1
                    return
                elif resolved.is_file():
                    # Use the resolved path for consistency
                    result.files.append(resolved)
                # If it resolves to a directory, we'll encounter it during traversal anyway
            except (OSError, RuntimeError) as e:
                # Handle circular symlinks and other symlink issues
                result.warnings.append(f"Symlink error {item}: {e}")
                result.skipped_items['broken_symlinks'] += 1
                return
        
        # Check if it's a regular file (this also handles resolved symlinks)
        elif item.is_file():
            # Test if we can actually read the file
            try:
                # Quick readability test - try to stat the file
                stat_result = item.stat()
                if stat_result.st_size >= 0:  # Basic sanity check
                    result.files.append(item)
                else:
                    result.warnings.append(f"Invalid file size for: {item}")
                    result.skipped_items['unreadable_files'] += 1
            except (PermissionError, OSError) as e:
                result.warnings.append(f"Cannot access file {item}: {e}")
                result.skipped_items['permission_denied'] += 1
        
        # We ignore directories (they're traversed by rglob) and other special files
        
    except PermissionError as e:
        result.warnings.append(f"Permission denied: {item} ({e})")
        result.skipped_items['permission_denied'] += 1
    except OSError as e:
        result.warnings.append(f"OS error processing {item}: {e}")
        result.skipped_items['other_errors'] += 1
    except Exception as e:
        # Catch-all for unexpected errors
        result.warnings.append(f"Unexpected error processing {item}: {e}")
        result.skipped_items['other_errors'] += 1