"""
File hashing utilities for duplicate detection.
"""

import hashlib
import sys
from pathlib import Path
from typing import Optional


def calculate_file_hash(file_path: Path, partial: bool = False) -> Optional[str]:
    """
    Calculate SHA256 hash of a file.
    
    Args:
        file_path: Path to the file
        partial: If True, only hash first 4KB for quick comparison
        
    Returns:
        Hex string of hash or None if error
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
    """
    Get file size in bytes.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File size in bytes or -1 if error
    """
    try:
        return file_path.stat().st_size
    except (OSError, IOError):
        return -1