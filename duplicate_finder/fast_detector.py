"""
Fast metadata-based duplicate detection optimized for HDDs.
"""

import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from collections import defaultdict
import time
from enum import Enum


class FileCategory(Enum):
    """File categories for specialized duplicate detection."""
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"
    OTHER = "other"


# File extensions for each category
PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', 
                   '.raw', '.cr2', '.nef', '.arw', '.dng', '.heic', '.heif', '.webp'}
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm',
                   '.m4v', '.mpg', '.mpeg', '.3gp', '.vob', '.ts', '.m2ts'}
DOCUMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                      '.txt', '.rtf', '.odt', '.ods', '.odp', '.csv'}


@dataclass
class FileMetadata:
    """Metadata for a file used in duplicate detection."""
    path: Path
    size: int
    mtime: float
    name: str
    name_lower: str
    category: FileCategory = FileCategory.OTHER


@dataclass
class DuplicateGroup:
    """A group of files that are potential duplicates."""
    files: List[FileMetadata]
    match_type: str  # 'exact', 'category_match', 'name_only'
    category: FileCategory = FileCategory.OTHER


def categorize_file(file_path: Path) -> FileCategory:
    """
    Categorize a file based on its extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        FileCategory enum value
    """
    extension = file_path.suffix.lower()
    
    if extension in PHOTO_EXTENSIONS:
        return FileCategory.PHOTO
    elif extension in VIDEO_EXTENSIONS:
        return FileCategory.VIDEO
    elif extension in DOCUMENT_EXTENSIONS:
        return FileCategory.DOCUMENT
    else:
        return FileCategory.OTHER


def scan_files_metadata(directory: Path, verbose: bool = False) -> List[FileMetadata]:
    """
    Scan directory and collect file metadata efficiently.
    
    Args:
        directory: Directory to scan
        verbose: Enable verbose output
        
    Returns:
        List of FileMetadata objects
    """
    files = []
    start_time = time.time()
    file_count = 0
    
    if verbose:
        print(f"Scanning directory: {directory}")
    
    try:
        for root, dirs, filenames in os.walk(directory):
            root_path = Path(root)
            
            for filename in filenames:
                file_path = root_path / filename
                
                try:
                    # Get file stats in one call
                    stat_result = file_path.stat()
                    
                    # Categorize the file
                    category = categorize_file(file_path)
                    
                    files.append(FileMetadata(
                        path=file_path,
                        size=stat_result.st_size,
                        mtime=stat_result.st_mtime,
                        name=filename,
                        name_lower=filename.lower(),
                        category=category
                    ))
                    
                    file_count += 1
                    
                    if verbose and file_count % 1000 == 0:
                        elapsed = time.time() - start_time
                        print(f"  Scanned {file_count} files in {elapsed:.1f}s")
                        
                except (OSError, PermissionError) as e:
                    if verbose:
                        print(f"  Warning: Cannot access {file_path}: {e}")
                    continue
                    
    except (OSError, PermissionError) as e:
        if verbose:
            print(f"Error scanning directory {directory}: {e}")
        return []
    
    elapsed = time.time() - start_time
    if verbose:
        print(f"Completed scan: {file_count} files in {elapsed:.1f}s")
    
    return files


def are_duplicates_by_category(file1: FileMetadata, file2: FileMetadata) -> bool:
    """
    Check if two files are duplicates based on simple rules.
    
    For exact duplicates (which is what we want):
    - Same filename (case-insensitive)
    - Same file size
    
    That's it! If these match, it's almost certainly a byte-for-byte copy.
    We don't need to check dates or content.
    
    Args:
        file1: First file metadata
        file2: Second file metadata
        
    Returns:
        True if files are considered duplicates
    """
    # Simple and fast: same name + same size = duplicate
    return (file1.name_lower == file2.name_lower and 
            file1.size == file2.size)


def find_metadata_duplicates(
    files: List[FileMetadata], 
    verbose: bool = False,
    use_categories: bool = True
) -> Tuple[List[DuplicateGroup], List[FileMetadata]]:
    """
    Find duplicate files based on metadata with category-specific rules.
    
    Args:
        files: List of file metadata
        verbose: Enable verbose output
        use_categories: Use category-specific duplicate detection
        
    Returns:
        Tuple of (duplicate_groups, unique_files)
    """
    start_time = time.time()
    
    if verbose:
        print(f"Analyzing {len(files)} files for duplicates...")
        if use_categories:
            # Count files by category
            category_counts = defaultdict(int)
            for f in files:
                category_counts[f.category] += 1
            print("File categories:")
            for cat, count in category_counts.items():
                print(f"  {cat.value}: {count} files")
    
    # Group by filename (case-insensitive)
    name_groups = defaultdict(list)
    for file_meta in files:
        name_groups[file_meta.name_lower].append(file_meta)
    
    duplicate_groups = []
    unique_files = []
    
    for name, file_list in name_groups.items():
        if len(file_list) == 1:
            # Unique filename
            unique_files.extend(file_list)
            continue
        
        if use_categories:
            # Category-specific duplicate detection
            processed = set()
            
            for i, file1 in enumerate(file_list):
                if i in processed:
                    continue
                    
                duplicates = [file1]
                processed.add(i)
                
                for j, file2 in enumerate(file_list[i+1:], i+1):
                    if j in processed:
                        continue
                    
                    if are_duplicates_by_category(file1, file2):
                        duplicates.append(file2)
                        processed.add(j)
                
                if len(duplicates) > 1:
                    duplicate_groups.append(DuplicateGroup(
                        files=duplicates,
                        match_type='category_match',
                        category=duplicates[0].category
                    ))
                else:
                    unique_files.append(file1)
        else:
            # Original exact matching logic
            size_time_groups = defaultdict(list)
            
            for file_meta in file_list:
                # Create key from size and rounded mtime
                key = (file_meta.size, round(file_meta.mtime))
                size_time_groups[key].append(file_meta)
            
            for key, matching_files in size_time_groups.items():
                if len(matching_files) > 1:
                    duplicate_groups.append(DuplicateGroup(
                        files=matching_files,
                        match_type='exact',
                        category=matching_files[0].category
                    ))
                else:
                    unique_files.extend(matching_files)
    
    elapsed = time.time() - start_time
    if verbose:
        print(f"Analysis completed in {elapsed:.1f}s")
        print(f"Found {len(duplicate_groups)} duplicate groups")
    
    return duplicate_groups, unique_files


def format_duplicate_report(
    duplicate_groups: List[DuplicateGroup],
    unique_files: List[FileMetadata],
    verbose: bool = False
) -> str:
    """
    Format duplicate detection results as human-readable text.
    
    Args:
        duplicate_groups: List of duplicate groups
        unique_files: List of unique files
        verbose: Include detailed information
        
    Returns:
        Formatted report string
    """
    lines = []
    
    # Header
    lines.append("🔍 FAST DUPLICATE DETECTION RESULTS")
    lines.append("=" * 50)
    lines.append("")
    
    # Duplicate groups
    if duplicate_groups:
        lines.append("📄 DUPLICATE FILES")
        lines.append("-" * 30)
        
        # Group duplicates by category for better organization
        groups_by_category = defaultdict(list)
        for group in duplicate_groups:
            groups_by_category[group.category].append(group)
        
        group_num = 1
        for category in [FileCategory.PHOTO, FileCategory.VIDEO, FileCategory.DOCUMENT, FileCategory.OTHER]:
            if category not in groups_by_category:
                continue
                
            category_groups = groups_by_category[category]
            if category_groups:
                lines.append(f"\n🏷️  {category.value.upper()} FILES:")
                
                for group in category_groups:
                    lines.append(f"\n📁 GROUP {group_num} ({len(group.files)} files, {group.match_type}):")
                    group_num += 1
                    
                    for file_meta in group.files:
                        size_mb = file_meta.size / (1024 * 1024)
                        mtime_str = time.strftime('%Y-%m-%d %H:%M:%S', 
                                                 time.localtime(file_meta.mtime))
                        
                        if verbose:
                            lines.append(f"   • {file_meta.path}")
                            lines.append(f"     Size: {size_mb:.2f} MB, Modified: {mtime_str}")
                        else:
                            lines.append(f"   • {file_meta.path}")
    else:
        lines.append("✅ No duplicate files found!")
    
    # Summary
    lines.append("")
    lines.append("📊 SUMMARY")
    lines.append("-" * 20)
    total_files = len(unique_files) + sum(len(group.files) for group in duplicate_groups)
    duplicate_files = sum(len(group.files) for group in duplicate_groups)
    
    lines.append(f"📁 Total files scanned: {total_files}")
    lines.append(f"👥 Duplicate files: {duplicate_files}")
    lines.append(f"📄 Unique files: {len(unique_files)}")
    lines.append(f"🔗 Duplicate groups: {len(duplicate_groups)}")
    
    # Potential space savings
    if duplicate_groups:
        total_duplicate_size = 0
        for group in duplicate_groups:
            # Space saved = (count - 1) * file_size
            group_size = group.files[0].size * (len(group.files) - 1)
            total_duplicate_size += group_size
        
        size_gb = total_duplicate_size / (1024 ** 3)
        lines.append(f"💾 Potential space savings: {size_gb:.2f} GB")
    
    return "\n".join(lines)


def fast_find_duplicates(
    directory: Path,
    verbose: bool = False,
    quiet: bool = False,
    use_categories: bool = True
) -> Tuple[List[DuplicateGroup], List[FileMetadata]]:
    """
    Fast duplicate detection using metadata only with category-specific rules.
    
    Args:
        directory: Directory to scan
        verbose: Enable verbose output
        quiet: Suppress non-essential output
        use_categories: Use category-specific duplicate detection
        
    Returns:
        Tuple of (duplicate_groups, unique_files)
    """
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    
    if not directory.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {directory}")
    
    # Scan files
    files = scan_files_metadata(directory, verbose and not quiet)
    
    if not files:
        if not quiet:
            print("No files found to analyze.")
        return [], []
    
    # Find duplicates with category-specific rules
    duplicate_groups, unique_files = find_metadata_duplicates(
        files, 
        verbose and not quiet,
        use_categories=use_categories
    )
    
    return duplicate_groups, unique_files