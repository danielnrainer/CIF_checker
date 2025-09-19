"""
Settings Management Service for CIF Checker

This service handles all settings-related operations including:
- Dictionary management (load, add, info display, suggestions)
- Editor settings coordination
- Configuration persistence

Extracted from main_window.py as part of the refactoring effort to reduce file complexity
and improve separation of concerns.
"""

import os
from typing import Optional, Callable, Dict, Any
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget
from PyQt6.QtCore import pyqtSignal, QObject

from utils.cif_dictionary_manager import CIFDictionaryManager
from utils.cif_format_converter import CIFFormatConverter
from gui.dialogs.dictionary_info_dialog import DictionaryInfoDialog
from gui.dialogs.dictionary_suggestion_dialog import show_dictionary_suggestions


class SettingsManager(QObject):
    """
    Manages all application settings including dictionary management and editor preferences.
    
    This service provides centralized settings management with callback-based UI integration,
    following the same pattern as FileManager for consistent architecture.
    """
    
    # Signals for status updates
    status_message_requested = pyqtSignal(str, int)  # message, timeout_ms
    dictionary_status_update_requested = pyqtSignal()
    
    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize the Settings Manager.
        
        Args:
            parent: Parent widget for dialogs
        """
        super().__init__()
        self.parent = parent
        
        # Core components
        self.dict_manager: Optional[CIFDictionaryManager] = None
        self.format_converter: Optional[CIFFormatConverter] = None
        
        # UI callback functions
        self._status_callback: Optional[Callable[[str, int], None]] = None
        self._dictionary_status_callback: Optional[Callable[[], None]] = None
        self._text_content_callback: Optional[Callable[[], str]] = None
        
    def set_callbacks(self,
                     status_callback: Optional[Callable[[str, int], None]] = None,
                     dictionary_status_callback: Optional[Callable[[], None]] = None,
                     text_content_callback: Optional[Callable[[], str]] = None):
        """
        Set callback functions for UI integration.
        
        Args:
            status_callback: Function to update status bar (message, timeout_ms)
            dictionary_status_callback: Function to update dictionary status display
            text_content_callback: Function to get current text editor content
        """
        self._status_callback = status_callback
        self._dictionary_status_callback = dictionary_status_callback
        self._text_content_callback = text_content_callback
    
    def set_dictionary_manager(self, dict_manager: CIFDictionaryManager):
        """
        Set the dictionary manager instance.
        
        Args:
            dict_manager: The CIF dictionary manager instance
        """
        self.dict_manager = dict_manager
        self.format_converter = CIFFormatConverter(dict_manager)
    
    def _update_status(self, message: str, timeout_ms: int = 5000):
        """Update status bar if callback is available."""
        if self._status_callback:
            self._status_callback(message, timeout_ms)
    
    def _update_dictionary_status(self):
        """Update dictionary status display if callback is available."""
        if self._dictionary_status_callback:
            self._dictionary_status_callback()
    
    def _get_text_content(self) -> str:
        """Get current text content if callback is available."""
        if self._text_content_callback:
            return self._text_content_callback()
        return ""
    
    def load_custom_dictionary(self) -> bool:
        """
        Load a custom CIF dictionary file.
        
        Returns:
            True if dictionary was loaded successfully, False otherwise
        """
        try:
            file_filter = "CIF Dictionary Files (*.dic);;All Files (*.*)"
            file_path, _ = QFileDialog.getOpenFileName(
                self.parent, "Select CIF Dictionary File", "", file_filter)
            
            if not file_path:
                return False  # User cancelled
            
            # Show loading message
            self._update_status("Loading dictionary...")
            
            # Create new dictionary manager with custom path
            new_dict_manager = CIFDictionaryManager(file_path)
            
            # Test that it loads correctly by accessing the mappings
            # This will trigger the lazy loading and catch any parse errors
            new_dict_manager._ensure_loaded()
            
            # Check that the dictionary actually contains mappings
            if not new_dict_manager._cif1_to_cif2 and not new_dict_manager._cif2_to_cif1:
                raise ValueError("The selected file does not appear to contain valid CIF dictionary mappings.")
            
            # If we get here, the dictionary loaded successfully
            self.dict_manager = new_dict_manager
            self.format_converter = CIFFormatConverter(self.dict_manager)
            
            # Update status displays
            self._update_dictionary_status()
            self._update_status(f"Successfully loaded dictionary: {os.path.basename(file_path)}", 5000)
            
            # Show success message
            QMessageBox.information(self.parent, "Dictionary Loaded", 
                                  f"Successfully loaded CIF dictionary:\n{file_path}")
            return True
                                  
        except FileNotFoundError:
            QMessageBox.critical(self.parent, "File Error", 
                               f"Dictionary file not found:\n{file_path}")
            self._update_status("Dictionary loading failed", 3000)
            return False
        except Exception as e:
            QMessageBox.critical(self.parent, "Dictionary Error", 
                               f"Failed to load CIF dictionary:\n{str(e)}\n\nPlease ensure the file is a valid CIF dictionary.")
            self._update_status("Dictionary loading failed", 3000)
            return False

    def add_additional_dictionary(self) -> bool:
        """
        Add an additional CIF dictionary to extend field coverage.
        
        Returns:
            True if dictionary was added successfully, False otherwise
        """
        if not self.dict_manager:
            QMessageBox.warning(self.parent, "No Dictionary Manager", 
                              "Dictionary manager is not initialized.")
            return False
            
        try:
            file_filter = "CIF Dictionary Files (*.dic);;All Files (*.*)"
            file_path, _ = QFileDialog.getOpenFileName(
                self.parent, "Select Additional CIF Dictionary", "", file_filter)
            
            if not file_path:
                return False  # User cancelled
            
            # Show loading message
            self._update_status("Adding dictionary...")
            
            # Add the dictionary to the existing manager
            success = self.dict_manager.add_dictionary(file_path)
            
            if success:
                # Update the format converter with the enhanced dictionary manager
                self.format_converter = CIFFormatConverter(self.dict_manager)
                
                # Update status displays
                self._update_dictionary_status()
                
                dict_name = os.path.basename(file_path)
                self._update_status(f"Successfully added dictionary: {dict_name}", 5000)
                
                # Get dictionary info for the success message
                dict_info = self.dict_manager.get_dictionary_info()
                total_dicts = dict_info['total_dictionaries']
                total_mappings = dict_info['total_cif1_mappings']
                
                QMessageBox.information(self.parent, "Dictionary Added", 
                                      f"Successfully added CIF dictionary:\n{file_path}\n\n"
                                      f"Total dictionaries loaded: {total_dicts}\n"
                                      f"Total field mappings: {total_mappings}")
                return True
            else:
                self._update_status("Failed to add dictionary", 3000)
                return False
                                  
        except FileNotFoundError:
            QMessageBox.critical(self.parent, "File Error", 
                               f"Dictionary file not found:\n{file_path}")
            self._update_status("Dictionary adding failed", 3000)
            return False
        except ValueError as e:
            QMessageBox.critical(self.parent, "Dictionary Error", 
                               f"Invalid dictionary file:\n{str(e)}")
            self._update_status("Dictionary adding failed", 3000)
            return False
        except Exception as e:
            QMessageBox.critical(self.parent, "Dictionary Error", 
                               f"Failed to add CIF dictionary:\n{str(e)}\n\nPlease ensure the file is a valid CIF dictionary.")
            self._update_status("Dictionary adding failed", 3000)
            return False

    def show_dictionary_info(self):
        """Show detailed dictionary information dialog."""
        if not self.dict_manager:
            QMessageBox.warning(self.parent, "No Dictionary Manager", 
                              "Dictionary manager is not initialized.")
            return
            
        try:
            dialog = DictionaryInfoDialog(self.dict_manager, self.parent)
            dialog.exec()
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Dictionary info dialog error: {error_details}")
            QMessageBox.critical(self.parent, "Error", 
                               f"Failed to show dictionary information:\n{str(e)}\n\nCheck console for details.")
    
    def suggest_dictionaries(self):
        """Analyze current CIF content and suggest relevant dictionaries."""
        if not self.dict_manager:
            QMessageBox.warning(self.parent, "No Dictionary Manager", 
                              "Dictionary manager is not initialized.")
            return
            
        try:
            # Get current CIF content
            cif_content = self._get_text_content().strip()
            
            if not cif_content:
                QMessageBox.information(self.parent, "No CIF Content", 
                                      "Please open or write a CIF file first to get dictionary suggestions.")
                return
            
            # Analyze CIF and get suggestions
            suggestions = self.dict_manager.suggest_dictionaries_for_cif(cif_content)
            cif_format = self.dict_manager.detect_cif_format(cif_content)
            
            # Status update callback
            def update_status(message: str):
                """Update the status bar with a message."""
                self._update_status(message, 5000)
                self._update_dictionary_status()
            
            # Show suggestions dialog with dictionary manager for downloading
            show_dictionary_suggestions(
                suggestions, 
                cif_format, 
                None,  # Deprecated load_callback
                self.dict_manager,  # Dictionary manager for downloading
                update_status,  # Status update callback
                self.parent
            )
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Dictionary suggestion error: {error_details}")
            QMessageBox.critical(self.parent, "Error", 
                               f"Failed to analyze CIF for dictionary suggestions:\n{str(e)}\n\nCheck console for details.")
    
    def prompt_for_dictionary_suggestions(self, cif_content: str) -> bool:
        """
        Prompt user to get dictionary suggestions when opening a CIF file.
        
        Args:
            cif_content: The CIF content to analyze
            
        Returns:
            True if suggestions were shown, False otherwise
        """
        if not self.dict_manager:
            return False
            
        try:
            # Quick check if there are any potential suggestions
            suggestions = self.dict_manager.suggest_dictionaries_for_cif(cif_content)
            
            if not suggestions:
                return False  # No suggestions available, don't prompt
            
            # Ask user if they want to see dictionary suggestions
            reply = QMessageBox.question(
                self.parent, 
                "Dictionary Suggestions Available",
                f"This CIF file appears to contain specialized data that could benefit from additional dictionaries.\n\n"
                f"Found {len(suggestions)} dictionary suggestion(s) that may enhance field validation and recognition.\n\n"
                "Would you like to see the suggestions?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Use existing suggest_dictionaries method to show the dialog
                self.suggest_dictionaries()
                return True
                
        except Exception as e:
            # Don't show error for this - it's just a convenience prompt
            print(f"Dictionary suggestion prompt error: {e}")
            
        return False
    
    def get_dictionary_manager(self) -> Optional[CIFDictionaryManager]:
        """
        Get the current dictionary manager instance.
        
        Returns:
            The dictionary manager if available, None otherwise
        """
        return self.dict_manager
    
    def get_format_converter(self) -> Optional[CIFFormatConverter]:
        """
        Get the current format converter instance.
        
        Returns:
            The format converter if available, None otherwise
        """
        return self.format_converter
    
    def is_initialized(self) -> bool:
        """
        Check if the settings manager is properly initialized.
        
        Returns:
            True if dictionary manager is available, False otherwise
        """
        return self.dict_manager is not None