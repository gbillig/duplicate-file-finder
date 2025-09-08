"""
Parallel file hashing utilities for improved I/O performance.
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

from tqdm import tqdm

from .hasher import calculate_file_hash, get_file_size
from .adaptive_optimizer import AdaptiveWorkerPool, get_adaptive_config


def get_optimal_worker_count(path: Optional[Path] = None, adaptive: bool = False) -> int:
    """
    Determine optimal number of worker threads based on system capabilities.
    
    Args:
        path: Optional path for disk type detection
        adaptive: Use adaptive optimization
    
    Returns:
        Number of worker threads to use
    """
    if adaptive:
        config = get_adaptive_config(path)
        return config['io_workers']
    
    # Legacy simple calculation
    cpu_count = os.cpu_count() or 4
    optimal_workers = min(cpu_count * 2, 16)
    return optimal_workers


def parallel_hash_files(
    files: List[Path], 
    partial: bool = False,
    desc: str = "Hashing files",
    quiet: bool = False,
    max_workers: Optional[int] = None
) -> Dict[Path, Optional[str]]:
    """
    Hash multiple files in parallel using ThreadPoolExecutor.
    
    Args:
        files: List of file paths to hash
        partial: If True, only hash first 4KB
        desc: Description for progress bar
        quiet: Suppress progress output
        max_workers: Maximum number of worker threads (None for auto)
        
    Returns:
        Dictionary mapping file paths to their hashes
    """
    if not files:
        return {}
    
    # Determine worker count
    if max_workers is None:
        max_workers = get_optimal_worker_count()
    
    results = {}
    
    # Use ThreadPoolExecutor for parallel I/O
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all hashing tasks
        future_to_file = {
            executor.submit(calculate_file_hash, file_path, partial): file_path
            for file_path in files
        }
        
        # Process results as they complete with progress bar
        with tqdm(
            total=len(files), 
            desc=desc, 
            unit=" files", 
            disable=quiet,
            leave=False
        ) as pbar:
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    hash_value = future.result()
                    results[file_path] = hash_value
                except Exception as e:
                    # Handle any unexpected errors
                    print(f"Error hashing {file_path}: {e}", file=sys.stderr)
                    results[file_path] = None
                finally:
                    pbar.update(1)
    
    return results


def parallel_hash_by_groups(
    file_groups: Dict[str, List[Path]],
    partial: bool = False,
    desc: str = "Hashing groups",
    quiet: bool = False,
    max_workers: Optional[int] = None
) -> Dict[str, Dict[str, List[Path]]]:
    """
    Hash files within groups in parallel, maintaining group structure.
    
    Args:
        file_groups: Dictionary grouping files (e.g., by size)
        partial: If True, only hash first 4KB
        desc: Description for progress bar
        quiet: Suppress progress output
        max_workers: Maximum number of worker threads
        
    Returns:
        Dictionary of group_key -> hash -> list of files
    """
    if max_workers is None:
        max_workers = get_optimal_worker_count()
    
    results = {}
    
    # Flatten all files for parallel processing
    all_files = []
    file_to_group = {}
    
    for group_key, group_files in file_groups.items():
        for file_path in group_files:
            all_files.append(file_path)
            file_to_group[file_path] = group_key
    
    # Hash all files in parallel
    file_hashes = parallel_hash_files(
        all_files, 
        partial=partial, 
        desc=desc, 
        quiet=quiet,
        max_workers=max_workers
    )
    
    # Reorganize results by group and hash
    for file_path, hash_value in file_hashes.items():
        group_key = file_to_group[file_path]
        
        if group_key not in results:
            results[group_key] = defaultdict(list)
        
        if hash_value is not None:
            results[group_key][hash_value].append(file_path)
    
    return results


def parallel_size_and_hash(
    files: List[Path],
    quiet: bool = False,
    max_workers: Optional[int] = None
) -> Tuple[Dict[int, List[Path]], Dict[Path, Optional[str]]]:
    """
    Get file sizes and calculate partial hashes in parallel.
    
    This is optimized for the initial stages of duplicate detection where
    we need both size information and partial hashes.
    
    Args:
        files: List of file paths
        quiet: Suppress progress output
        max_workers: Maximum number of worker threads
        
    Returns:
        Tuple of (size_to_files dict, file_to_partial_hash dict)
    """
    if max_workers is None:
        max_workers = get_optimal_worker_count()
    
    size_to_files = defaultdict(list)
    file_to_hash = {}
    
    def process_file(file_path: Path) -> Tuple[Path, int, Optional[str]]:
        """Process a single file: get size and partial hash."""
        size = get_file_size(file_path)
        if size >= 0:
            # Only calculate hash for valid files
            partial_hash = calculate_file_hash(file_path, partial=True)
            return file_path, size, partial_hash
        return file_path, size, None
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = [executor.submit(process_file, f) for f in files]
        
        # Process results with progress bar
        with tqdm(
            total=len(files),
            desc="Analyzing files",
            unit=" files",
            disable=quiet,
            leave=False
        ) as pbar:
            for future in as_completed(futures):
                try:
                    file_path, size, partial_hash = future.result()
                    if size >= 0:
                        size_to_files[size].append(file_path)
                        if partial_hash:
                            file_to_hash[file_path] = partial_hash
                except Exception as e:
                    print(f"Error processing file: {e}", file=sys.stderr)
                finally:
                    pbar.update(1)
    
    return dict(size_to_files), file_to_hash


def parallel_hash_files_adaptive(
    files: List[Path],
    partial: bool = False,
    desc: str = "Hashing files",
    quiet: bool = False,
    path: Optional[Path] = None
) -> Dict[Path, Optional[str]]:
    """
    Hash multiple files in parallel using adaptive optimization.
    
    This version automatically adjusts worker counts based on system
    resources and workload characteristics.
    
    Args:
        files: List of file paths to hash
        partial: If True, only hash first 4KB
        desc: Description for progress bar
        quiet: Suppress progress output
        path: Path for disk type detection
        
    Returns:
        Dictionary mapping file paths to their hashes
    """
    if not files:
        return {}
    
    # Get the path from first file if not provided
    if path is None and files:
        path = files[0].parent
    
    # Create adaptive worker pool
    pool = AdaptiveWorkerPool(path)
    
    # Get optimal worker count for this workload
    workers = pool.get_io_workers(len(files)) if partial else pool.get_cpu_workers(len(files))
    
    if not quiet:
        print(f"  Using {workers} adaptive workers for {desc}")
        if len(files) > 1000:
            print(f"  System: {pool.profile.disk_type.upper()}, {pool.profile.cpu_count} CPUs, {pool.profile.memory_gb:.1f}GB RAM")
    
    results = {}
    
    # Use ThreadPoolExecutor with adaptive worker count
    with ThreadPoolExecutor(max_workers=workers) as executor:
        # Submit all hashing tasks
        future_to_file = {}
        for file_path in files:
            future = executor.submit(calculate_file_hash, file_path, partial)
            future_to_file[future] = (file_path, time.time())
        
        # Process results with performance tracking
        with tqdm(
            total=len(files),
            desc=desc,
            unit=" files",
            disable=quiet,
            leave=False
        ) as pbar:
            for future in as_completed(future_to_file):
                file_path, start_time = future_to_file[future]
                elapsed = time.time() - start_time
                
                try:
                    hash_value = future.result()
                    results[file_path] = hash_value
                    
                    # Record performance for adaptive adjustment
                    if partial:
                        pool.record_io_time(elapsed)
                    else:
                        pool.record_cpu_time(elapsed)
                        
                except Exception as e:
                    print(f"Error hashing {file_path}: {e}", file=sys.stderr)
                    results[file_path] = None
                finally:
                    pbar.update(1)
    
    return results