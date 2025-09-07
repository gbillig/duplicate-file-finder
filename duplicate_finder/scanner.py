"""
Directory scanning functionality.
"""

import sys
from pathlib import Path
from typing import List

from tqdm import tqdm


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
    files = []
    print("Scanning for files...")
    
    try:
        items_processed = 0
        with tqdm(desc="Scanning", unit=" items", leave=False) as pbar:
            for item in directory.rglob("*"):
                items_processed += 1
                pbar.update(1)
                
                if item.is_file():
                    files.append(item)
                    # Update postfix every 1000 items to avoid too frequent updates
                    if items_processed % 1000 == 0 or len(files) % 500 == 0:
                        pbar.set_postfix(files=len(files), refresh=False)
                
                # Handle very large directories by periodic refresh
                if items_processed % 10000 == 0:
                    pbar.refresh()
                    
    except PermissionError as e:
        print(f"Permission denied: {e}", file=sys.stderr)
    except KeyboardInterrupt:
        print(f"\nScan interrupted. Found {len(files)} files so far.", file=sys.stderr)
        raise
    
    return files