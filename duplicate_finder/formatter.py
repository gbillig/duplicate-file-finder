"""
Output formatting for duplicate detection results.
"""

from pathlib import Path
from typing import Dict, List


def _format_file_size(size: int) -> str:
    """Format file size in human-readable format."""
    if size < 1024:
        return f"{size} bytes"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"


def _get_file_info(file_path: Path) -> tuple[int, str]:
    """Get file size and formatted size string."""
    try:
        size = file_path.stat().st_size
        return size, _format_file_size(size)
    except OSError:
        return 0, "unknown size"


def _calculate_space_savings(duplicates: Dict[str, List[Path]]) -> tuple[int, int]:
    """Calculate total duplicate size and potential space savings."""
    total_duplicate_size = 0
    potential_savings = 0
    
    for file_list in duplicates.values():
        if len(file_list) > 1:
            # Get size of first file (all duplicates have same size)
            try:
                file_size = file_list[0].stat().st_size
                total_duplicate_size += file_size * len(file_list)
                potential_savings += file_size * (len(file_list) - 1)
            except OSError:
                pass
    
    return total_duplicate_size, potential_savings


def format_output(duplicates: Dict[str, List[Path]], unique_files: List[Path]) -> None:
    """
    Format and print the results with enhanced grouping and statistics.
    
    Args:
        duplicates: Dictionary mapping hash to list of duplicate files
        unique_files: List of unique files
    """
    if duplicates:
        print("\n" + "=" * 60)
        print("🔍 DUPLICATE FILES FOUND")
        print("=" * 60)
        
        # Sort duplicate groups by size (largest first) for better visibility
        sorted_duplicates = sorted(
            duplicates.items(),
            key=lambda x: _get_file_info(x[1][0])[0],
            reverse=True
        )
        
        for group_num, (hash_value, file_list) in enumerate(sorted_duplicates, 1):
            file_size, size_str = _get_file_info(file_list[0])
            
            print(f"\n📁 GROUP {group_num}: {len(file_list)} identical files ({size_str} each)")
            print(f"   Hash: {hash_value[:16]}...")
            
            # Sort files by path for consistent display
            for file_path in sorted(file_list):
                print(f"   • {file_path}")
            
            # Show space that could be saved for this group
            if file_size > 0 and len(file_list) > 1:
                savings = file_size * (len(file_list) - 1)
                print(f"   💾 Potential space savings: {_format_file_size(savings)}")
    else:
        print("\n✅ No duplicate files found.")
    
    # Unique files section (condensed)
    print(f"\n" + "=" * 60)
    print("📄 UNIQUE FILES")
    print("=" * 60)
    
    if unique_files:
        print(f"Found {len(unique_files):,} unique files")
        
        if len(unique_files) <= 20:
            # Show all files if not too many
            for file_path in sorted(unique_files):
                size, size_str = _get_file_info(file_path)
                print(f"   • {file_path} ({size_str})")
        else:
            # Show sample of unique files
            print("Sample of unique files:")
            for file_path in sorted(unique_files)[:10]:
                size, size_str = _get_file_info(file_path)
                print(f"   • {file_path} ({size_str})")
            print(f"   ... and {len(unique_files) - 10:,} more unique files")
    else:
        print("No unique files found.")
    
    # Enhanced summary with space analysis
    print(f"\n" + "=" * 60)
    print("📊 SUMMARY STATISTICS")
    print("=" * 60)
    
    total_files = sum(len(files) for files in duplicates.values()) + len(unique_files)
    duplicate_count = sum(len(files) for files in duplicates.values())
    total_duplicate_size, potential_savings = _calculate_space_savings(duplicates)
    
    print(f"📁 Total files scanned: {total_files:,}")
    print(f"👥 Duplicate files: {duplicate_count:,}")
    print(f"📄 Unique files: {len(unique_files):,}")
    print(f"🔗 Duplicate groups: {len(duplicates):,}")
    
    if duplicates:
        print(f"\n💾 Space Analysis:")
        print(f"   Total size of duplicates: {_format_file_size(total_duplicate_size)}")
        print(f"   Potential space savings: {_format_file_size(potential_savings)}")
        if total_duplicate_size > 0:
            savings_percent = (potential_savings / total_duplicate_size) * 100
            print(f"   Efficiency gain: {savings_percent:.1f}% space could be saved")
    
    print("=" * 60)