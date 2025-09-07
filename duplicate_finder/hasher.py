"""
File hashing utilities for duplicate detection.
"""

import hashlib
import sys
from pathlib import Path
from typing import Optional

# Global warning counter to avoid spam
_warning_counts = {
    'permission_denied': 0,
    'file_not_found': 0,
    'io_errors': 0,
    'other_errors': 0
}

_MAX_WARNINGS_PER_TYPE = 5


def calculate_file_hash(file_path: Path, partial: bool = False) -> Optional[str]:
    """
    Calculate SHA256 hash of a file with robust error handling.
    
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
    
    except PermissionError as e:
        _log_warning('permission_denied', f"Permission denied reading {file_path}: {e}")
        return None
    except FileNotFoundError as e:
        _log_warning('file_not_found', f"File not found {file_path}: {e}")
        return None
    except IsADirectoryError:
        # Silently skip directories that somehow got through
        return None
    except (OSError, IOError) as e:
        _log_warning('io_errors', f"I/O error reading {file_path}: {e}")
        return None
    except Exception as e:
        _log_warning('other_errors', f"Unexpected error reading {file_path}: {e}")
        return None


def get_file_size(file_path: Path) -> int:
    """
    Get file size in bytes with robust error handling.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File size in bytes or -1 if error
    """
    try:
        return file_path.stat().st_size
    except PermissionError:
        # Don't spam warnings for permission errors in size checking
        return -1
    except FileNotFoundError:
        # File disappeared between scan and processing
        return -1
    except (OSError, IOError):
        return -1


def _log_warning(warning_type: str, message: str) -> None:
    """Log warning messages with rate limiting to avoid spam."""
    global _warning_counts
    
    count = _warning_counts.get(warning_type, 0)
    _warning_counts[warning_type] = count + 1  # Always increment counter
    
    if count < _MAX_WARNINGS_PER_TYPE:
        print(f"⚠️  {message}", file=sys.stderr)
    elif count == _MAX_WARNINGS_PER_TYPE:
        warning_name = warning_type.replace('_', ' ').title()
        print(f"⚠️  {warning_name}: Additional warnings suppressed...", file=sys.stderr)
    # Silent after suppression message


def get_warning_summary() -> dict:
    """Get summary of warnings that were logged."""
    return _warning_counts.copy()


def reset_warning_counters() -> None:
    """Reset warning counters (useful for testing)."""
    global _warning_counts
    _warning_counts = {
        'permission_denied': 0,
        'file_not_found': 0,
        'io_errors': 0,
        'other_errors': 0
    }