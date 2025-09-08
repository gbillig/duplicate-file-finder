"""
Adaptive optimization for worker counts and system resource utilization.
"""

import os
import platform
import subprocess
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass


@dataclass
class SystemProfile:
    """Profile of system capabilities."""
    cpu_count: int
    memory_gb: float
    disk_type: str  # 'ssd' or 'hdd'
    os_type: str
    io_threads: int  # Recommended I/O threads
    cpu_threads: int  # Recommended CPU-bound threads


def detect_disk_type(path: Path) -> str:
    """
    Detect if the given path is on an SSD or HDD.
    
    Args:
        path: Path to check
        
    Returns:
        'ssd' or 'hdd'
    """
    # Default to SSD (more common now and safer for performance)
    disk_type = 'ssd'
    
    try:
        # Get the disk that contains this path
        path_str = str(path.resolve())
        
        # Platform-specific detection
        if platform.system() == 'Linux':
            # Try to detect via /sys/block
            try:
                # Find which device the path is on
                df_output = subprocess.run(
                    ['df', path_str],
                    capture_output=True,
                    text=True,
                    timeout=5
                ).stdout
                
                # Parse device from df output
                for line in df_output.split('\n')[1:]:
                    if line:
                        device = line.split()[0]
                        if device.startswith('/dev/'):
                            # Extract base device name (e.g., sda from /dev/sda1)
                            base_device = device.replace('/dev/', '').rstrip('0123456789')
                            
                            # Check rotational flag
                            rotational_path = f'/sys/block/{base_device}/queue/rotational'
                            if os.path.exists(rotational_path):
                                with open(rotational_path, 'r') as f:
                                    # 0 = SSD, 1 = HDD
                                    is_rotational = f.read().strip() == '1'
                                    disk_type = 'hdd' if is_rotational else 'ssd'
                                    break
            except (subprocess.TimeoutExpired, Exception):
                pass
        
        elif platform.system() == 'Darwin':  # macOS
            # On macOS, check for solid state via diskutil
            try:
                result = subprocess.run(
                    ['diskutil', 'info', '/'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if 'Solid State' in result.stdout:
                    disk_type = 'ssd'
                elif 'Mechanical' in result.stdout:
                    disk_type = 'hdd'
            except (subprocess.TimeoutExpired, Exception):
                pass
        
        elif platform.system() == 'Windows':
            # On Windows, try to use PowerShell
            try:
                result = subprocess.run(
                    ['powershell', '-Command', 
                     'Get-PhysicalDisk | Select-Object MediaType'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if 'SSD' in result.stdout:
                    disk_type = 'ssd'
                elif 'HDD' in result.stdout:
                    disk_type = 'hdd'
            except (subprocess.TimeoutExpired, Exception):
                pass
    
    except Exception:
        # If detection fails, default to SSD
        pass
    
    return disk_type


def get_memory_gb() -> float:
    """Get available system memory in GB."""
    try:
        import psutil
        return psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        # Fallback if psutil not available
        try:
            if platform.system() == 'Linux':
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if line.startswith('MemTotal:'):
                            kb = int(line.split()[1])
                            return kb / (1024 * 1024)
        except Exception:
            pass
        return 8.0  # Default to 8GB


def profile_system(path: Optional[Path] = None) -> SystemProfile:
    """
    Profile the system to determine optimal worker counts.
    
    Args:
        path: Optional path to check disk type
        
    Returns:
        SystemProfile with recommendations
    """
    cpu_count = os.cpu_count() or 4
    memory_gb = get_memory_gb()
    disk_type = detect_disk_type(path or Path.cwd())
    os_type = platform.system()
    
    # Calculate recommended worker counts based on system profile
    if disk_type == 'ssd':
        # SSDs can handle more concurrent I/O
        io_threads = min(cpu_count * 3, 24)
    else:
        # HDDs benefit less from concurrent I/O due to seek times
        io_threads = min(cpu_count, 8)
    
    # CPU-bound operations (hashing)
    # Leave some cores for system and I/O
    cpu_threads = max(1, cpu_count - 1)
    
    # Adjust based on memory
    if memory_gb < 4:
        # Low memory system - reduce concurrency
        io_threads = min(io_threads, 4)
        cpu_threads = min(cpu_threads, 2)
    elif memory_gb < 8:
        # Medium memory
        io_threads = min(io_threads, 8)
        cpu_threads = min(cpu_threads, 4)
    # High memory systems can use full recommendations
    
    return SystemProfile(
        cpu_count=cpu_count,
        memory_gb=memory_gb,
        disk_type=disk_type,
        os_type=os_type,
        io_threads=io_threads,
        cpu_threads=cpu_threads
    )


class AdaptiveWorkerPool:
    """
    Adaptive worker pool that adjusts based on system resources and workload.
    """
    
    def __init__(self, path: Optional[Path] = None, profile: Optional[SystemProfile] = None):
        """
        Initialize adaptive worker pool.
        
        Args:
            path: Path being processed (for disk type detection)
            profile: Optional pre-computed system profile
        """
        self.profile = profile or profile_system(path)
        self.io_workers = self.profile.io_threads
        self.cpu_workers = self.profile.cpu_threads
        
        # Track performance metrics for dynamic adjustment
        self.io_task_times = []
        self.cpu_task_times = []
        self.adjustment_counter = 0
    
    def get_io_workers(self, file_count: Optional[int] = None) -> int:
        """
        Get optimal I/O worker count.
        
        Args:
            file_count: Optional number of files to process
            
        Returns:
            Optimal number of I/O workers
        """
        workers = self.io_workers
        
        # Adjust based on workload size
        if file_count:
            if file_count < 100:
                # Small workload - reduce workers
                workers = min(workers, 4)
            elif file_count < 1000:
                # Medium workload
                workers = min(workers, 8)
            # Large workloads use full worker count
        
        return max(1, workers)
    
    def get_cpu_workers(self, task_count: Optional[int] = None) -> int:
        """
        Get optimal CPU worker count for hashing.
        
        Args:
            task_count: Optional number of tasks
            
        Returns:
            Optimal number of CPU workers
        """
        workers = self.cpu_workers
        
        # Adjust based on task count
        if task_count:
            if task_count < 50:
                workers = min(workers, 2)
            elif task_count < 500:
                workers = min(workers, 4)
        
        return max(1, workers)
    
    def get_batch_size(self, total_files: int) -> int:
        """
        Get optimal batch size based on system resources.
        
        Args:
            total_files: Total number of files to process
            
        Returns:
            Optimal batch size
        """
        # Base batch size on memory
        if self.profile.memory_gb < 4:
            base_batch = 500
        elif self.profile.memory_gb < 8:
            base_batch = 1000
        elif self.profile.memory_gb < 16:
            base_batch = 2000
        else:
            base_batch = 5000
        
        # Adjust based on disk type
        if self.profile.disk_type == 'hdd':
            # Larger batches for HDDs to minimize seeks
            base_batch = int(base_batch * 1.5)
        
        # Don't make batches too large relative to total
        if total_files < base_batch * 2:
            return max(100, total_files // 4)
        
        return base_batch
    
    def record_io_time(self, elapsed: float) -> None:
        """Record I/O operation time for adaptive adjustment."""
        self.io_task_times.append(elapsed)
        if len(self.io_task_times) > 100:
            self.io_task_times.pop(0)
        self._adjust_workers()
    
    def record_cpu_time(self, elapsed: float) -> None:
        """Record CPU operation time for adaptive adjustment."""
        self.cpu_task_times.append(elapsed)
        if len(self.cpu_task_times) > 100:
            self.cpu_task_times.pop(0)
        self._adjust_workers()
    
    def _adjust_workers(self) -> None:
        """Dynamically adjust worker counts based on performance."""
        self.adjustment_counter += 1
        
        # Only adjust every 50 operations
        if self.adjustment_counter % 50 != 0:
            return
        
        # Analyze I/O performance
        if len(self.io_task_times) >= 20:
            avg_time = sum(self.io_task_times[-20:]) / 20
            if avg_time > 1.0:  # Tasks taking too long
                # Reduce workers if I/O bound
                self.io_workers = max(1, self.io_workers - 1)
            elif avg_time < 0.1:  # Tasks completing very fast
                # Can increase workers
                self.io_workers = min(self.io_workers + 1, self.profile.io_threads * 2)
        
        # Analyze CPU performance
        if len(self.cpu_task_times) >= 20:
            avg_time = sum(self.cpu_task_times[-20:]) / 20
            if avg_time > 2.0:  # Heavy CPU tasks
                # Might benefit from more workers
                self.cpu_workers = min(self.cpu_workers + 1, self.profile.cpu_count)
            elif avg_time < 0.5 and self.cpu_workers > 2:
                # Light tasks, reduce workers
                self.cpu_workers = max(2, self.cpu_workers - 1)
    
    def get_profile_summary(self) -> str:
        """Get a summary of the system profile."""
        return (
            f"System Profile:\n"
            f"  CPU cores: {self.profile.cpu_count}\n"
            f"  Memory: {self.profile.memory_gb:.1f} GB\n"
            f"  Disk type: {self.profile.disk_type.upper()}\n"
            f"  OS: {self.profile.os_type}\n"
            f"  Recommended I/O workers: {self.profile.io_threads}\n"
            f"  Recommended CPU workers: {self.profile.cpu_threads}\n"
            f"  Current I/O workers: {self.io_workers}\n"
            f"  Current CPU workers: {self.cpu_workers}"
        )


def get_adaptive_config(
    path: Optional[Path] = None,
    file_count: Optional[int] = None,
    manual_workers: Optional[int] = None
) -> Dict[str, int]:
    """
    Get adaptive configuration for duplicate detection.
    
    Args:
        path: Path being processed
        file_count: Number of files to process
        manual_workers: Manual override for worker count
        
    Returns:
        Configuration dictionary
    """
    if manual_workers:
        # Manual override
        return {
            'io_workers': manual_workers,
            'cpu_workers': manual_workers,
            'batch_size': 1000
        }
    
    pool = AdaptiveWorkerPool(path)
    
    return {
        'io_workers': pool.get_io_workers(file_count),
        'cpu_workers': pool.get_cpu_workers(file_count),
        'batch_size': pool.get_batch_size(file_count or 10000)
    }