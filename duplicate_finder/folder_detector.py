"""Folder duplicate detection logic."""

import hashlib
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict


class FolderFingerprint:
    """Represents a folder's fingerprint for duplicate detection."""
    
    def __init__(self, folder_path: Path):
        self.folder_path = folder_path
        self.structure_hash = None
        self.content_hash = None
        self.file_count = 0
        self.total_size = 0
        self.relative_files = set()  # Relative paths within folder
    
    def __str__(self):
        return f"FolderFingerprint({self.folder_path}, files={self.file_count}, size={self.total_size})"


def create_folder_fingerprint(folder_path: Path, all_files: List[Path]) -> FolderFingerprint:
    """Create a fingerprint for a folder based on its files."""
    fingerprint = FolderFingerprint(folder_path)
    
    # Find all files that belong to this folder
    folder_files = [f for f in all_files if f.is_relative_to(folder_path) and f != folder_path]
    
    if not folder_files:
        return fingerprint
    
    # Calculate relative paths and sort them for consistent fingerprinting
    relative_paths = []
    total_size = 0
    
    for file_path in folder_files:
        if file_path.is_file():
            try:
                rel_path = file_path.relative_to(folder_path)
                size = file_path.stat().st_size
                relative_paths.append((str(rel_path), size))
                total_size += size
                fingerprint.relative_files.add(str(rel_path))
            except (OSError, ValueError):
                continue
    
    # Sort by relative path for consistent hashing
    relative_paths.sort()
    
    fingerprint.file_count = len(relative_paths)
    fingerprint.total_size = total_size
    
    # Create structure hash (based on relative paths and sizes)
    structure_data = ''.join(f"{path}:{size}" for path, size in relative_paths)
    fingerprint.structure_hash = hashlib.sha256(structure_data.encode()).hexdigest()
    
    return fingerprint


def find_duplicate_folders(all_files: List[Path], file_hashes: Dict[Path, str]) -> List[List[Path]]:
    """Find folders that are complete duplicates of each other."""
    
    # Get all directories from the file list
    directories = set()
    for file_path in all_files:
        if file_path.is_file():
            # Add all parent directories
            current = file_path.parent
            while current != current.parent:  # Stop at filesystem root
                directories.add(current)
                current = current.parent
    
    directories = list(directories)
    
    # Create fingerprints for all directories
    fingerprints = []
    for directory in directories:
        fingerprint = create_folder_fingerprint(directory, all_files)
        if fingerprint.file_count > 0:  # Only consider non-empty folders
            fingerprints.append(fingerprint)
    
    # Group by structure hash first (quick elimination)
    structure_groups = defaultdict(list)
    for fingerprint in fingerprints:
        structure_groups[fingerprint.structure_hash].append(fingerprint)
    
    # For each structure group, verify content is identical
    duplicate_groups = []
    for structure_hash, group in structure_groups.items():
        if len(group) < 2:
            continue
        
        # Verify that all files in these folders have identical content
        verified_groups = verify_folder_content_identical(group, file_hashes)
        duplicate_groups.extend(verified_groups)
    
    # Convert fingerprints back to folder paths
    result = []
    for group in duplicate_groups:
        folder_paths = [fp.folder_path for fp in group]
        result.append(folder_paths)
    
    return result


def verify_folder_content_identical(fingerprints: List[FolderFingerprint], file_hashes: Dict[Path, str]) -> List[List[FolderFingerprint]]:
    """Verify that folders with same structure actually have identical file content."""
    
    if len(fingerprints) < 2:
        return []
    
    # Group fingerprints by their content hash
    content_groups = defaultdict(list)
    
    for fingerprint in fingerprints:
        # Calculate content hash based on file hashes
        content_hash = calculate_folder_content_hash(fingerprint, file_hashes)
        if content_hash:
            fingerprint.content_hash = content_hash
            content_groups[content_hash].append(fingerprint)
    
    # Return groups with 2+ identical folders
    return [group for group in content_groups.values() if len(group) >= 2]


def calculate_folder_content_hash(fingerprint: FolderFingerprint, file_hashes: Dict[Path, str]) -> str:
    """Calculate a hash based on the content of all files in the folder."""
    
    file_content_pairs = []
    
    for rel_path_str in sorted(fingerprint.relative_files):
        full_path = fingerprint.folder_path / rel_path_str
        file_hash = file_hashes.get(full_path)
        if file_hash:
            file_content_pairs.append(f"{rel_path_str}:{file_hash}")
        else:
            # If we don't have a hash for this file, we can't reliably compare
            return None
    
    if not file_content_pairs:
        return None
    
    # Create hash of all file hashes combined
    combined_content = ''.join(file_content_pairs)
    return hashlib.sha256(combined_content.encode()).hexdigest()


def is_folder_duplicate(folder_path: Path, duplicate_folders: List[List[Path]]) -> bool:
    """Check if a folder is part of any duplicate group."""
    for group in duplicate_folders:
        if folder_path in group:
            return True
    return False


def get_files_in_duplicate_folders(duplicate_folders: List[List[Path]], all_files: List[Path]) -> Set[Path]:
    """Get all files that are contained within duplicate folders."""
    duplicate_folder_set = set()
    for group in duplicate_folders:
        duplicate_folder_set.update(group)
    
    files_in_duplicate_folders = set()
    for file_path in all_files:
        if file_path.is_file():
            # Check if this file is within any duplicate folder
            for duplicate_folder in duplicate_folder_set:
                if file_path.is_relative_to(duplicate_folder):
                    files_in_duplicate_folders.add(file_path)
                    break
    
    return files_in_duplicate_folders