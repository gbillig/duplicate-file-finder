"""
Directory scanning functionality.
"""

import sys
from pathlib import Path
from typing import List

from tqdm import tqdm


def scan_directory(directory: Path) -> List[Path]:
    """
    Recursively scan directory for all files.
    
    Args:
        directory: Path to directory to scan
        
    Returns:
        List of Path objects for all files found
    """
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