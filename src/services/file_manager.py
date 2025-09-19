"""
CIF File Manager Service
========================

Handles all file operations for CIF files including:
- Opening and saving CIF files
- Managing recent files list
- File dialog interactions
- Content reading/writing operations

This service is designed to work with the main window UI while maintaining
separation of concerns between file operations and UI updates.
"""

import os
from typing import Optional, List, Callable, Any
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget


class CIFFileManager:
    """
    Manages all file operations for CIF files.
    
    This service handles file I/O operations while allowing the UI to register
    callbacks for notifications about state changes.
    """
    
    def __init__(self, parent_widget: Optional[QWidget] = None):
        """
        Initialize the file manager.
        
        Args:
            parent_widget: Parent widget for dialog positioning (optional)
        """
        self.parent_widget = parent_widget
        
        # File state
        self.current_file: Optional[str] = None
        self.modified: bool = False
        self.recent_files: List[str] = []
        self.max_recent_files: int = 5
        
        # UI callbacks - these will be set by the main window
        self.on_file_opened: Optional[Callable[[str, str], None]] = None  # (filepath, content)
        self.on_file_saved: Optional[Callable[[str], None]] = None  # (filepath)
        self.on_recent_files_updated: Optional[Callable[[List[str]], None]] = None  # (recent_files)
        self.on_error: Optional[Callable[[str, str], None]] = None  # (title, message)
    
    def set_parent_widget(self, parent: QWidget) -> None:
        """Set the parent widget for dialogs."""
        self.parent_widget = parent
    
    def register_callbacks(self, 
                          on_file_opened: Callable[[str, str], None],
                          on_file_saved: Callable[[str], None],
                          on_recent_files_updated: Callable[[List[str]], None],
                          on_error: Callable[[str, str], None]) -> None:
        """
        Register UI callback functions.
        
        Args:
            on_file_opened: Called when file is successfully opened (filepath, content)
            on_file_saved: Called when file is successfully saved (filepath)  
            on_recent_files_updated: Called when recent files list changes (recent_files)
            on_error: Called when an error occurs (title, message)
        """
        self.on_file_opened = on_file_opened
        self.on_file_saved = on_file_saved
        self.on_recent_files_updated = on_recent_files_updated
        self.on_error = on_error
    
    def select_initial_file(self) -> bool:
        """
        Prompt user to select initial CIF file on startup.
        
        Returns:
            True if file was selected and opened, False otherwise
        """
        file_filter = "CIF Files (*.cif);;All Files (*.*)"
        filepath, _ = QFileDialog.getOpenFileName(
            self.parent_widget, "Select a CIF File", "", file_filter)
        
        if not filepath:
            if self.on_error:
                self.on_error("No File Selected", 
                            "Please select a CIF file to continue.")
            return False
        
        return self.open_file(filepath)
    
    def open_file_dialog(self) -> bool:
        """
        Show open file dialog and open selected file.
        
        Returns:
            True if file was opened successfully, False otherwise
        """
        file_filter = "CIF Files (*.cif);;All Files (*.*)"
        filepath, _ = QFileDialog.getOpenFileName(
            self.parent_widget, "Open File", "", file_filter)
        
        if not filepath:
            return False
            
        return self.open_file(filepath)
    
    def open_file(self, filepath: str) -> bool:
        """
        Open a CIF file and load its content.
        
        Args:
            filepath: Path to the CIF file to open
            
        Returns:
            True if file was opened successfully, False otherwise
        """
        try:
            with open(filepath, "r", encoding="utf-8") as file:
                content = file.read()
            
            self.current_file = filepath
            self.modified = False
            
            # Add to recent files
            self.add_to_recent_files(filepath)
            
            # Notify UI
            if self.on_file_opened:
                self.on_file_opened(filepath, content)
                
            return True
            
        except Exception as e:
            if self.on_error:
                self.on_error("Error", f"Failed to open file:\\n{e}")
            return False
    
    def open_recent_file(self, filepath: str) -> bool:
        """
        Open a file from the recent files list.
        
        Args:
            filepath: Path to the recent file to open
            
        Returns:
            True if file was opened successfully, False otherwise
        """
        if not filepath or not os.path.exists(filepath):
            if self.on_error:
                self.on_error("File Not Found",
                            f"Could not find file:\\n{filepath}")
            
            # Remove from recent files if it doesn't exist
            if filepath in self.recent_files:
                self.recent_files.remove(filepath)
                if self.on_recent_files_updated:
                    self.on_recent_files_updated(self.recent_files)
            return False
        
        return self.open_file(filepath)
    
    def save_file(self, content: str) -> bool:
        """
        Save content to current file or show save dialog.
        
        Args:
            content: Content to save
            
        Returns:
            True if file was saved successfully, False otherwise
        """
        if self.current_file:
            # Show confirmation dialog for overwriting existing file
            reply = QMessageBox.question(
                self.parent_widget, 
                "Confirm Save",
                f"Do you want to overwrite the existing file?\\n{self.current_file}",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Cancel:
                return False
            elif reply == QMessageBox.StandardButton.Yes:
                return self.save_to_file(self.current_file, content)
            else:
                return self.save_file_as(content)
        else:
            return self.save_file_as(content)
    
    def save_file_as(self, content: str) -> bool:
        """
        Show save file dialog and save content to selected file.
        
        Args:
            content: Content to save
            
        Returns:
            True if file was saved successfully, False otherwise
        """
        file_filter = "CIF Files (*.cif);;All Files (*.*)"
        filepath, _ = QFileDialog.getSaveFileName(
            self.parent_widget, "Save File As", "", file_filter)
        
        if not filepath:
            return False
            
        return self.save_to_file(filepath, content)
    
    def save_to_file(self, filepath: str, content: str) -> bool:
        """
        Save content to specified file.
        
        Args:
            filepath: Path where to save the file
            content: Content to save
            
        Returns:
            True if file was saved successfully, False otherwise
        """
        try:
            with open(filepath, "w", encoding="utf-8") as file:
                # Ensure content ends properly (strip and add newline if needed)
                clean_content = content.strip()
                if clean_content:  # Only add newline if content is not empty
                    clean_content += "\\n"
                file.write(clean_content)
            
            self.current_file = filepath
            self.modified = False
            
            # Add to recent files
            self.add_to_recent_files(filepath)
            
            # Notify UI
            if self.on_file_saved:
                self.on_file_saved(filepath)
                
            return True
            
        except Exception as e:
            if self.on_error:
                self.on_error("Error", f"Failed to save file:\\n{e}")
            return False
    
    def add_to_recent_files(self, filepath: str) -> None:
        """
        Add file to recent files list.
        
        Args:
            filepath: Path to add to recent files
        """
        # Remove if already exists to avoid duplicates
        if filepath in self.recent_files:
            self.recent_files.remove(filepath)
        
        # Add to beginning of list
        self.recent_files.insert(0, filepath)
        
        # Limit list size
        if len(self.recent_files) > self.max_recent_files:
            self.recent_files = self.recent_files[:self.max_recent_files]
        
        # Notify UI
        if self.on_recent_files_updated:
            self.on_recent_files_updated(self.recent_files)
    
    def get_current_filename(self) -> str:
        """
        Get the current filename (without path) for display.
        
        Returns:
            Current filename or empty string if no file is open
        """
        if self.current_file:
            return os.path.basename(self.current_file)
        return ""
    
    def get_current_filepath(self) -> Optional[str]:
        """
        Get the current full file path.
        
        Returns:
            Current file path or None if no file is open
        """
        return self.current_file
    
    def is_file_modified(self) -> bool:
        """
        Check if current file has unsaved changes.
        
        Returns:
            True if file has been modified, False otherwise
        """
        return self.modified
    
    def set_modified(self, modified: bool) -> None:
        """
        Set the modified state of the current file.
        
        Args:
            modified: Whether the file has been modified
        """
        self.modified = modified
    
    def get_recent_files(self) -> List[str]:
        """
        Get the list of recent files.
        
        Returns:
            List of recent file paths
        """
        return self.recent_files.copy()
    
    def clear_recent_files(self) -> None:
        """Clear the recent files list."""
        self.recent_files.clear()
        if self.on_recent_files_updated:
            self.on_recent_files_updated(self.recent_files)
    
    def has_current_file(self) -> bool:
        """
        Check if there is a currently open file.
        
        Returns:
            True if a file is currently open, False otherwise
        """
        return self.current_file is not None