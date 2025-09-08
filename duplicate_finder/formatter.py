"""
Output formatting for duplicate detection results.
"""

import json
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


def format_output(duplicates: Dict[str, List[Path]], unique_files: List[Path], duplicate_folders: List[List[Path]] = None, quiet: bool = False) -> None:
    """
    Format and print the results with enhanced grouping and statistics.
    
    Args:
        duplicates: Dictionary mapping hash to list of duplicate files
        unique_files: List of unique files
        duplicate_folders: List of duplicate folder groups (optional)
    """
    if duplicate_folders is None:
        duplicate_folders = []
    
    # Show duplicate folders first (higher priority)
    if duplicate_folders:
        print("\n" + "=" * 60)
        print("📁 DUPLICATE FOLDERS FOUND")
        print("=" * 60)
        
        for group_num, folder_group in enumerate(duplicate_folders, 1):
            # Calculate total size of folder
            total_size = 0
            file_count = 0
            
            for folder_path in folder_group:
                folder_size = 0
                folder_files = 0
                try:
                    for item in folder_path.rglob("*"):
                        try:
                            if item.is_file():
                                size = item.stat().st_size
                                folder_size += size
                                folder_files += 1
                        except (PermissionError, FileNotFoundError, OSError):
                            # Skip files we can't access but continue counting others
                            continue
                    total_size = folder_size  # All folders should have same size
                    file_count = folder_files  # All folders should have same file count
                    break  # We only need to calculate once since all folders are identical
                except (PermissionError, OSError):
                    continue
            
            print(f"\n📂 GROUP {group_num}: {len(folder_group)} identical folders")
            print(f"   Files per folder: {file_count:,}")
            print(f"   Size per folder: {_format_file_size(total_size)}")
            
            # Sort folders by path for consistent display
            for folder_path in sorted(folder_group):
                print(f"   • {folder_path}/")
            
            # Show space that could be saved for this group
            if total_size > 0 and len(folder_group) > 1:
                savings = total_size * (len(folder_group) - 1)
                print(f"   💾 Potential space savings: {_format_file_size(savings)}")
    
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
    
    # Calculate folder statistics
    folder_duplicate_count = sum(len(group) for group in duplicate_folders)
    folder_savings = 0
    for folder_group in duplicate_folders:
        if len(folder_group) > 1:
            # Calculate size of one folder
            try:
                folder_size = 0
                for item in folder_group[0].rglob("*"):
                    try:
                        if item.is_file():
                            folder_size += item.stat().st_size
                    except (PermissionError, FileNotFoundError, OSError):
                        # Skip files we can't access but continue counting others
                        continue
                folder_savings += folder_size * (len(folder_group) - 1)
            except (PermissionError, OSError):
                pass
    
    print(f"📁 Total files scanned: {total_files:,}")
    print(f"👥 Duplicate files: {duplicate_count:,}")
    print(f"📄 Unique files: {len(unique_files):,}")
    print(f"🔗 Duplicate file groups: {len(duplicates):,}")
    print(f"📂 Duplicate folders: {folder_duplicate_count:,}")
    print(f"🗂️  Duplicate folder groups: {len(duplicate_folders):,}")
    
    if duplicates or duplicate_folders:
        print(f"\n💾 Space Analysis:")
        total_combined_savings = potential_savings + folder_savings
        total_combined_duplicates = total_duplicate_size + (folder_savings / (1 if folder_savings == 0 else len(duplicate_folders)))
        
        if duplicates:
            print(f"   File duplicates size: {_format_file_size(total_duplicate_size)}")
            print(f"   File savings potential: {_format_file_size(potential_savings)}")
        
        if duplicate_folders:
            print(f"   Folder savings potential: {_format_file_size(folder_savings)}")
        
        if total_combined_savings > 0:
            print(f"   Total potential savings: {_format_file_size(total_combined_savings)}")
            
        if total_duplicate_size > 0 and potential_savings > 0:
            file_savings_percent = (potential_savings / total_duplicate_size) * 100
            print(f"   File efficiency gain: {file_savings_percent:.1f}% could be saved from files")
    
    print("=" * 60)


def format_json_output(duplicates: Dict[str, List[Path]], unique_files: List[Path], duplicate_folders: List[List[Path]] = None) -> None:
    """
    Format and print the results as JSON for scripting and programmatic access.
    
    Args:
        duplicates: Dictionary mapping hash to list of duplicate files
        unique_files: List of unique files
        duplicate_folders: List of lists containing duplicate folder paths
    """
    duplicate_folders = duplicate_folders or []
    
    # Convert Path objects to strings for JSON serialization
    json_duplicates = []
    for hash_val, file_list in duplicates.items():
        group = []
        for file_path in file_list:
            try:
                size = file_path.stat().st_size
                group.append({
                    "path": str(file_path),
                    "size": size,
                    "size_formatted": _format_file_size(size)
                })
            except OSError:
                group.append({
                    "path": str(file_path),
                    "size": 0,
                    "size_formatted": "unknown"
                })
        if group:
            json_duplicates.append({
                "hash": hash_val,
                "files": group,
                "count": len(group)
            })
    
    # Convert duplicate folders
    json_duplicate_folders = []
    for folder_group in duplicate_folders:
        group = []
        for folder_path in folder_group:
            try:
                # Calculate folder size
                folder_size = 0
                file_count = 0
                for item in folder_path.rglob("*"):
                    try:
                        if item.is_file():
                            folder_size += item.stat().st_size
                            file_count += 1
                    except (PermissionError, FileNotFoundError, OSError):
                        continue
                
                group.append({
                    "path": str(folder_path),
                    "size": folder_size,
                    "size_formatted": _format_file_size(folder_size),
                    "file_count": file_count
                })
            except (PermissionError, OSError):
                group.append({
                    "path": str(folder_path),
                    "size": 0,
                    "size_formatted": "unknown",
                    "file_count": 0
                })
        
        if group:
            json_duplicate_folders.append({
                "folders": group,
                "count": len(group)
            })
    
    # Convert unique files
    json_unique_files = []
    for file_path in unique_files:
        try:
            size = file_path.stat().st_size
            json_unique_files.append({
                "path": str(file_path),
                "size": size,
                "size_formatted": _format_file_size(size)
            })
        except OSError:
            json_unique_files.append({
                "path": str(file_path),
                "size": 0,
                "size_formatted": "unknown"
            })
    
    # Calculate statistics
    total_duplicate_size, potential_savings = _calculate_space_savings(duplicates)
    
    # Calculate folder savings
    folder_savings = 0
    for folder_group in duplicate_folders:
        if len(folder_group) > 1:
            try:
                folder_size = 0
                for item in folder_group[0].rglob("*"):
                    try:
                        if item.is_file():
                            folder_size += item.stat().st_size
                    except (PermissionError, FileNotFoundError, OSError):
                        continue
                folder_savings += folder_size * (len(folder_group) - 1)
            except (PermissionError, OSError):
                pass
    
    # Create output dictionary
    output = {
        "duplicate_files": json_duplicates,
        "duplicate_folders": json_duplicate_folders,
        "unique_files": json_unique_files,
        "statistics": {
            "total_files": sum(len(files) for files in duplicates.values()) + len(unique_files),
            "duplicate_files_count": sum(len(files) for files in duplicates.values()),
            "unique_files_count": len(unique_files),
            "duplicate_groups_count": len(duplicates),
            "duplicate_folders_count": sum(len(group) for group in duplicate_folders),
            "duplicate_folder_groups_count": len(duplicate_folders),
            "total_duplicate_size": total_duplicate_size,
            "potential_file_savings": potential_savings,
            "potential_folder_savings": folder_savings,
            "total_potential_savings": potential_savings + folder_savings
        }
    }
    
    # Print as formatted JSON
    print(json.dumps(output, indent=2))