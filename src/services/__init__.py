"""
Services Package
================

Contains service classes that handle business logic and operations
separate from the UI layer.

Services included:
- FileManager: Handles file operations (open, save, recent files)
"""

from .file_manager import CIFFileManager

__all__ = ['CIFFileManager']