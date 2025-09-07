"""
Unit tests for duplicate_finder.py
"""

import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, ANY
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duplicate_finder
import pytest


class TestFileHashing:
    """Test file hashing functionality."""
    
    def test_calculate_file_hash_identical_content(self, tmp_path):
        """Test that identical files produce same hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        content = b"This is test content"
        
        file1.write_bytes(content)
        file2.write_bytes(content)
        
        hash1 = duplicate_finder.calculate_file_hash(file1)
        hash2 = duplicate_finder.calculate_file_hash(file2)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 hex characters
    
    def test_calculate_file_hash_different_content(self, tmp_path):
        """Test that different files produce different hashes."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        
        file1.write_bytes(b"Content A")
        file2.write_bytes(b"Content B")
        
        hash1 = duplicate_finder.calculate_file_hash(file1)
        hash2 = duplicate_finder.calculate_file_hash(file2)
        
        assert hash1 != hash2
    
    def test_calculate_file_hash_empty_file(self, tmp_path):
        """Test hashing of empty file."""
        empty_file = tmp_path / "empty.txt"
        empty_file.touch()
        
        file_hash = duplicate_finder.calculate_file_hash(empty_file)
        # SHA256 of empty string
        expected = hashlib.sha256(b"").hexdigest()
        assert file_hash == expected
    
    def test_calculate_file_hash_nonexistent_file(self, tmp_path):
        """Test handling of nonexistent file."""
        nonexistent = tmp_path / "nonexistent.txt"
        
        with patch('sys.stderr'):
            result = duplicate_finder.calculate_file_hash(nonexistent)
        
        assert result is None


class TestDirectoryScanning:
    """Test directory scanning functionality."""
    
    @patch('duplicate_finder.tqdm')
    def test_scan_directory_recursive(self, mock_tqdm, tmp_path):
        """Test recursive directory scanning."""
        # Make tqdm act as a passthrough
        mock_tqdm.side_effect = lambda x, **kwargs: x
        
        # Create nested structure
        (tmp_path / "subdir1").mkdir()
        (tmp_path / "subdir1" / "subdir2").mkdir()
        
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "subdir1" / "file2.txt"
        file3 = tmp_path / "subdir1" / "subdir2" / "file3.txt"
        
        file1.touch()
        file2.touch()
        file3.touch()
        
        with patch('builtins.print'):
            files = duplicate_finder.scan_directory(tmp_path)
        
        assert len(files) == 3
        assert file1 in files
        assert file2 in files
        assert file3 in files
    
    @patch('duplicate_finder.tqdm')
    def test_scan_directory_empty(self, mock_tqdm, tmp_path):
        """Test scanning empty directory."""
        mock_tqdm.side_effect = lambda x, **kwargs: x
        
        with patch('builtins.print'):
            files = duplicate_finder.scan_directory(tmp_path)
        assert files == []
    
    @patch('duplicate_finder.tqdm')
    def test_scan_directory_ignores_directories(self, mock_tqdm, tmp_path):
        """Test that directories are not included in file list."""
        mock_tqdm.side_effect = lambda x, **kwargs: x
        
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        file1 = tmp_path / "file.txt"
        file1.touch()
        
        with patch('builtins.print'):
            files = duplicate_finder.scan_directory(tmp_path)
        
        assert len(files) == 1
        assert file1 in files
        assert subdir not in files


class TestDuplicateFinding:
    """Test duplicate finding logic."""
    
    @patch('duplicate_finder.tqdm')
    @patch('builtins.print')
    def test_find_duplicates_with_duplicates(self, mock_print, mock_tqdm, tmp_path):
        """Test finding actual duplicates."""
        # Make tqdm act as a passthrough
        mock_tqdm.side_effect = lambda x, **kwargs: x
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file3 = tmp_path / "file3.txt"
        file4 = tmp_path / "unique.txt"
        
        # Create duplicates
        duplicate_content = b"Duplicate content"
        file1.write_bytes(duplicate_content)
        file2.write_bytes(duplicate_content)
        file3.write_bytes(duplicate_content)
        
        # Create unique file
        file4.write_bytes(b"Unique content")
        
        files = [file1, file2, file3, file4]
        duplicates, unique_files = duplicate_finder.find_duplicates(files)
        
        assert len(duplicates) == 1
        assert len(unique_files) == 1
        assert file4 in unique_files
        
        # Check duplicate group
        dup_group = list(duplicates.values())[0]
        assert len(dup_group) == 3
        assert file1 in dup_group
        assert file2 in dup_group
        assert file3 in dup_group
    
    @patch('duplicate_finder.tqdm')
    @patch('builtins.print')
    def test_find_duplicates_no_duplicates(self, mock_print, mock_tqdm, tmp_path):
        # Make tqdm act as a passthrough
        mock_tqdm.side_effect = lambda x, **kwargs: x
        """Test when no duplicates exist."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        
        file1.write_bytes(b"Content 1")
        file2.write_bytes(b"Content 2")
        
        files = [file1, file2]
        duplicates, unique_files = duplicate_finder.find_duplicates(files)
        
        assert len(duplicates) == 0
        assert len(unique_files) == 2
    
    @patch('duplicate_finder.tqdm')
    @patch('builtins.print')
    def test_find_duplicates_all_duplicates(self, mock_print, mock_tqdm, tmp_path):
        # Make tqdm act as a passthrough
        mock_tqdm.side_effect = lambda x, **kwargs: x
        """Test when all files are duplicates."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        
        content = b"Same content"
        file1.write_bytes(content)
        file2.write_bytes(content)
        
        files = [file1, file2]
        duplicates, unique_files = duplicate_finder.find_duplicates(files)
        
        assert len(duplicates) == 1
        assert len(unique_files) == 0
    
    @patch('duplicate_finder.tqdm')
    @patch('builtins.print')
    def test_find_duplicates_multiple_groups(self, mock_print, mock_tqdm, tmp_path):
        # Make tqdm act as a passthrough
        mock_tqdm.side_effect = lambda x, **kwargs: x
        """Test multiple duplicate groups."""
        # Group 1
        file1a = tmp_path / "file1a.txt"
        file1b = tmp_path / "file1b.txt"
        
        # Group 2
        file2a = tmp_path / "file2a.txt"
        file2b = tmp_path / "file2b.txt"
        
        # Unique
        file3 = tmp_path / "unique.txt"
        
        file1a.write_bytes(b"Group 1")
        file1b.write_bytes(b"Group 1")
        file2a.write_bytes(b"Group 2")
        file2b.write_bytes(b"Group 2")
        file3.write_bytes(b"Unique")
        
        files = [file1a, file1b, file2a, file2b, file3]
        duplicates, unique_files = duplicate_finder.find_duplicates(files)
        
        assert len(duplicates) == 2
        assert len(unique_files) == 1
        assert file3 in unique_files


class TestMainFunction:
    """Test main function and CLI."""
    
    def test_main_nonexistent_path(self):
        """Test handling of nonexistent path."""
        with patch('sys.argv', ['duplicate_finder.py', '/nonexistent/path']):
            with patch('sys.stderr'):
                with pytest.raises(SystemExit) as exc_info:
                    duplicate_finder.main()
                assert exc_info.value.code == 1
    
    def test_main_file_instead_of_directory(self, tmp_path):
        """Test handling when file is provided instead of directory."""
        test_file = tmp_path / "file.txt"
        test_file.touch()
        
        with patch('sys.argv', ['duplicate_finder.py', str(test_file)]):
            with patch('sys.stderr'):
                with pytest.raises(SystemExit) as exc_info:
                    duplicate_finder.main()
                assert exc_info.value.code == 1
    
    def test_main_empty_directory(self, tmp_path):
        """Test handling of empty directory."""
        with patch('sys.argv', ['duplicate_finder.py', str(tmp_path)]):
            with patch('sys.stdout'):
                with pytest.raises(SystemExit) as exc_info:
                    duplicate_finder.main()
                assert exc_info.value.code == 0


class TestProgressReporting:
    """Test progress reporting functionality."""
    
    @patch('duplicate_finder.tqdm')
    def test_scan_directory_shows_progress(self, mock_tqdm_class, tmp_path):
        """Test that scanning shows progress bar."""
        # Create some test files
        for i in range(3):
            (tmp_path / f"file{i}.txt").touch()
        
        # Configure mock
        mock_progress_bar = MagicMock()
        mock_tqdm_class.return_value = mock_progress_bar
        mock_tqdm_class.side_effect = lambda x, **kwargs: x
        
        with patch('builtins.print') as mock_print:
            files = duplicate_finder.scan_directory(tmp_path)
        
        # Verify tqdm was called with correct parameters
        mock_tqdm_class.assert_called_once()
        call_args = mock_tqdm_class.call_args
        assert 'desc' in call_args[1]
        assert 'Scanning' in call_args[1]['desc']
        
        # Verify we found files
        assert len(files) == 3
    
    @patch('duplicate_finder.tqdm')
    def test_find_duplicates_shows_progress(self, mock_tqdm_class, tmp_path):
        """Test that hashing shows progress bar."""
        # Create test files
        files = []
        for i in range(3):
            file_path = tmp_path / f"file{i}.txt"
            file_path.write_text(f"content{i}")
            files.append(file_path)
        
        # Configure mock
        mock_tqdm_class.side_effect = lambda x, **kwargs: x
        
        with patch('builtins.print'):
            duplicates, unique_files = duplicate_finder.find_duplicates(files)
        
        # Verify tqdm was called for hashing
        assert mock_tqdm_class.call_count >= 1
        calls = mock_tqdm_class.call_args_list
        
        # Find the hashing progress bar call
        hashing_call = None
        for call in calls:
            if len(call[1]) > 0 and 'desc' in call[1]:
                if 'Hashing' in call[1]['desc']:
                    hashing_call = call
                    break
        
        assert hashing_call is not None
        assert 'unit' in hashing_call[1]
        assert 'files' in hashing_call[1]['unit']


class TestArgumentParsing:
    """Test command-line argument parsing."""
    
    def test_parse_arguments_valid_path(self):
        """Test parsing valid path argument."""
        with patch('sys.argv', ['duplicate_finder.py', '/some/path']):
            args = duplicate_finder.parse_arguments()
            assert args.path == Path('/some/path')
    
    def test_parse_arguments_no_args(self):
        """Test handling of missing arguments."""
        with patch('sys.argv', ['duplicate_finder.py']):
            with patch('sys.stderr'):
                with pytest.raises(SystemExit):
                    duplicate_finder.parse_arguments()