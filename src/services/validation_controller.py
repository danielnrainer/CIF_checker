"""
Validation Controller Service for CIF Checker

This service handles all validation-related operations including:
- CIF syntax validation
- Field checking and validation
- Field rules validation
- Configuration management for checks
- Special validation logic (3DED, deprecated fields, etc.)

Extracted from main_window.py as part of the refactoring effort to reduce file complexity
and improve separation of concerns.
"""

import os
from typing import Optional, Callable, Dict, Any, List, Tuple
from PyQt6.QtWidgets import QMessageBox, QWidget, QDialog, QFileDialog
from PyQt6.QtCore import pyqtSignal, QObject

from utils.CIF_field_parsing import CIFFieldChecker
from utils.CIF_parser import CIFParser
from utils.field_rules_validator import FieldRulesValidator
from utils.cif_dictionary_manager import CIFDictionaryManager, CIFVersion, get_resource_path
from utils.cif_format_converter import CIFFormatConverter
from gui.dialogs import CheckConfigDialog, RESULT_ABORT, RESULT_STOP_SAVE
from gui.dialogs.input_dialog import CIFInputDialog
from gui.dialogs.field_rules_validation_dialog import FieldRulesValidationDialog


class ValidationController(QObject):
    """
    Manages all CIF validation operations including field checking, syntax validation,
    and rule validation.
    
    This service provides centralized validation management with callback-based UI integration,
    following the same pattern as FileManager and SettingsManager for consistent architecture.
    """
    
    # Signals for status updates
    status_message_requested = pyqtSignal(str, int)  # message, timeout_ms
    window_title_update_requested = pyqtSignal(str)  # new_title
    
    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize the Validation Controller.
        
        Args:
            parent: Parent widget for dialogs
        """
        super().__init__()
        self.parent = parent
        
        # Core validation components
        self.field_checker = CIFFieldChecker()
        self.cif_parser = CIFParser()
        self.field_rules_validator: Optional[FieldRulesValidator] = None
        self.dict_manager: Optional[CIFDictionaryManager] = None
        self.format_converter: Optional[CIFFormatConverter] = None
        
        # Field definition variables
        self.custom_field_rules_file: Optional[str] = None
        self.current_field_set: str = '3DED'  # Default to 3DED
        
        # UI callback functions
        self._text_content_callback: Optional[Callable[[], str]] = None
        self._set_text_callback: Optional[Callable[[str], None]] = None
        self._status_callback: Optional[Callable[[str, int], None]] = None
        self._title_callback: Optional[Callable[[str], None]] = None
        
        # Load default field sets
        self._load_default_field_sets()
        
    def set_callbacks(self,
                     text_content_callback: Optional[Callable[[], str]] = None,
                     set_text_callback: Optional[Callable[[str], None]] = None,
                     status_callback: Optional[Callable[[str, int], None]] = None,
                     title_callback: Optional[Callable[[str], None]] = None):
        """
        Set callback functions for UI integration.
        
        Args:
            text_content_callback: Function to get current text editor content
            set_text_callback: Function to set text editor content
            status_callback: Function to update status bar (message, timeout_ms)
            title_callback: Function to update window title
        """
        self._text_content_callback = text_content_callback
        self._set_text_callback = set_text_callback
        self._status_callback = status_callback
        self._title_callback = title_callback
    
    def set_dictionary_components(self, dict_manager: CIFDictionaryManager, format_converter: CIFFormatConverter):
        """
        Set the dictionary manager and format converter instances.
        
        Args:
            dict_manager: The CIF dictionary manager instance
            format_converter: The CIF format converter instance
        """
        self.dict_manager = dict_manager
        self.format_converter = format_converter
        self.field_rules_validator = FieldRulesValidator(dict_manager, format_converter)
        
    def _load_default_field_sets(self):
        """Load default field definition sets."""
        try:
            field_rules_dir = get_resource_path('field_rules')
            self.field_checker.load_field_set('3DED', os.path.join(field_rules_dir, '3ded.cif_rules'))
            self.field_checker.load_field_set('HP', os.path.join(field_rules_dir, 'hp.cif_rules'))
        except Exception as e:
            print(f"Warning: Failed to load default field sets: {e}")
    
    def _get_text_content(self) -> str:
        """Get current text content if callback is available."""
        if self._text_content_callback:
            return self._text_content_callback()
        return ""
    
    def _set_text_content(self, content: str):
        """Set text content if callback is available."""
        if self._set_text_callback:
            self._set_text_callback(content)
    
    def _update_status(self, message: str, timeout_ms: int = 5000):
        """Update status bar if callback is available."""
        if self._status_callback:
            self._status_callback(message, timeout_ms)
    
    def _update_title(self, title: str):
        """Update window title if callback is available."""
        if self._title_callback:
            self._title_callback(title)
    
    def set_field_set(self, field_set_name: str) -> bool:
        """
        Set the current field definition set.
        
        Args:
            field_set_name: Name of the field set ('3DED', 'HP', 'Custom')
            
        Returns:
            True if field set was changed successfully
        """
        if field_set_name == 'Custom':
            if not self.custom_field_rules_file:
                # Prompt user to select a custom file
                file_filter = "Field Rules (*.cif_rules);;All Files (*.*)"
                file_path, _ = QFileDialog.getOpenFileName(
                    self.parent, "Select Custom Field Rules File", "", file_filter)
                
                if not file_path:
                    return False  # User cancelled
                
                # Try to load the custom field set
                try:
                    self.field_checker.load_field_set('Custom', file_path)
                    self.custom_field_rules_file = file_path
                except Exception as e:
                    QMessageBox.critical(self.parent, "Error Loading Field Rules", 
                                       f"Failed to load custom field rules:\n{str(e)}")
                    return False
        
        self.current_field_set = field_set_name
        return True
    
    def get_current_field_set(self) -> str:
        """Get the currently selected field set name."""
        return self.current_field_set
    
    def validate_cif(self) -> List[str]:
        """
        Basic CIF syntax validation.
        
        Returns:
            List of error messages
        """
        text = self._get_text_content()
        lines = text.splitlines()
        errors = []
        
        # Check for basic CIF syntax rules
        in_multiline = False
        for i, line in enumerate(lines, 1):
            # Check for semicolon-delimited values
            if line.startswith(';'):
                in_multiline = not in_multiline
                continue
                
            if not in_multiline:
                # Check for field names
                if line.strip() and not line.strip().startswith('#'):
                    if line.strip().startswith('_'):
                        parts = line.split(maxsplit=1)
                        if len(parts) < 2:
                            errors.append(f"Line {i}: Field '{line.strip()}' has no value")
                    # Check quoted values
                    elif "'" in line or '"' in line:
                        quote_char = "'" if "'" in line else '"'
                        if line.count(quote_char) % 2 != 0:
                            errors.append(f"Line {i}: Unmatched quote")
        
        if in_multiline:
            errors.append("Unclosed multiline value (missing semicolon)")
            
        return errors

    def check_line(self, prefix: str, default_value=None, multiline: bool = False, description: str = ""):
        """
        Check and potentially update a CIF field value.
        
        Args:
            prefix: Field name prefix to check
            default_value: Default value to suggest
            multiline: Whether field supports multiline input
            description: Field description
            
        Returns:
            Result code from the dialog
        """
        return self.check_line_with_config(prefix, default_value, multiline, description, None)

    def check_line_with_config(self, prefix: str, default_value=None, multiline: bool = False, 
                             description: str = "", config=None):
        """
        Check and potentially update a CIF field value with configuration.
        
        Args:
            prefix: Field name prefix to check
            default_value: Default value to suggest
            multiline: Whether field supports multiline input
            description: Field description
            config: Configuration dictionary from CheckConfigDialog
            
        Returns:
            Result code from the dialog (RESULT_ABORT, RESULT_STOP_SAVE, or None)
        """
        from gui.dialogs import CIFInputDialog, MultilineInputDialog
        
        removable_chars = "'"
        lines = self._get_text_content().splitlines()
        found_line = -1
        found_value = ""
        
        # Search for the field
        for i, line in enumerate(lines):
            if line.strip().startswith(prefix):
                found_line = i
                parts = line.split(maxsplit=1)
                if len(parts) > 1:
                    found_value = parts[1].strip().strip(removable_chars)
                break
        
        # Apply configuration filters if available
        if config:
            # Skip if configured to skip existing fields
            if found_line != -1 and config.get('skip_existing_fields', False):
                return None
                
            # Skip if configured to skip missing fields and field is missing
            if found_line == -1 and config.get('skip_missing_fields', False):
                return None
        
        # Determine dialog type and show it
        if multiline:
            dialog = MultilineInputDialog(found_value, self.parent)
            dialog.setWindowTitle(f"Edit {prefix}")
        else:
            dialog = CIFInputDialog(
                f"Edit {prefix}",  # title
                f"Edit the field: {prefix}\n\nDescription: {description}\n\nSuggested value: {default_value}\n\n",  # text 
                found_value,      # value
                default_value or "",  # default_value
                self.parent       # parent
            )
        
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted:
            if multiline:
                new_value = dialog.getText()
            else:
                new_value = dialog.getValue()
            
            if found_line != -1:
                # Update existing line
                if new_value:
                    if multiline:
                        # Handle multiline values with semicolon delimiters
                        lines[found_line] = f"{prefix}"
                        lines.insert(found_line + 1, ";")
                        lines.insert(found_line + 2, new_value)
                        lines.insert(found_line + 3, ";")
                    else:
                        lines[found_line] = f"{prefix} '{new_value}'"
                else:
                    # Remove the line if value is empty
                    lines.pop(found_line)
            else:
                # Add new line
                if new_value:
                    if multiline:
                        lines.extend([f"{prefix}", ";", new_value, ";"])
                    else:
                        lines.append(f"{prefix} '{new_value}'")
            
            # Update the text content
            self._set_text_content('\n'.join(lines))
            return None
            
        elif hasattr(dialog, 'RESULT_USE_DEFAULT') and result == dialog.RESULT_USE_DEFAULT:
            new_value = default_value or ""
            
            if found_line != -1:
                # Update existing line with default value
                if new_value:
                    if multiline:
                        lines[found_line] = f"{prefix}"
                        lines.insert(found_line + 1, ";")
                        lines.insert(found_line + 2, new_value)
                        lines.insert(found_line + 3, ";")
                    else:
                        lines[found_line] = f"{prefix} '{new_value}'"
                else:
                    lines.pop(found_line)
            else:
                # Add new line with default value
                if new_value:
                    if multiline:
                        lines.extend([f"{prefix}", ";", new_value, ";"])
                    else:
                        lines.append(f"{prefix} '{new_value}'")
            
            # Update the text content
            self._set_text_content('\n'.join(lines))
            return None
            
        elif (hasattr(dialog, 'RESULT_ABORT') and result == dialog.RESULT_ABORT) or result == CIFInputDialog.RESULT_ABORT:
            return RESULT_ABORT
            
        elif (hasattr(dialog, 'RESULT_STOP_SAVE') and result == dialog.RESULT_STOP_SAVE) or result == CIFInputDialog.RESULT_STOP_SAVE:
            return RESULT_STOP_SAVE
            
        else:
            # Dialog was cancelled
            return None

    def start_checks(self) -> bool:
        """
        Start checking CIF fields using the selected field definition set.
        
        Returns:
            True if checks completed successfully, False otherwise
        """
        # Validate field set selection
        if self.current_field_set == 'Custom':
            if not self.custom_field_rules_file:
                QMessageBox.warning(
                    self.parent,
                    "No Custom File Selected",
                    "Please select a custom field definition file first."
                )
                return False
            
            # Check if custom field set is loaded
            fields = self.field_checker.get_field_set('Custom')
            if not fields:
                QMessageBox.warning(
                    self.parent,
                    "Custom File Not Loaded",
                    "The custom field definition file could not be loaded. "
                    "Please select a valid file."
                )
                return False
        
        # Mandatory validation before starting checks (if not done already)
        if not self._ensure_field_rules_validated():
            return False  # User cancelled or validation failed
        
        # Show configuration dialog first
        config_dialog = CheckConfigDialog(self.parent)
        if config_dialog.exec() != QDialog.DialogCode.Accepted:
            return False  # User cancelled
        
        # Get configuration settings
        config = config_dialog.get_config()
        
        # Store the initial state for potential restore
        initial_state = self._get_text_content()
        
        # Single field set processing
        success = self._process_single_field_set(config, initial_state)
        if not success:
            return False
        
        # If we get here, checks completed successfully
        if config.get('reformat_after_checks', False):
            # Note: reformat_file would need to be available via callback or moved here
            pass
        
        self._update_title("EDCIF-check")
        QMessageBox.information(self.parent, "Checks Complete", "Field checking completed successfully!")
        return True

    def _process_single_field_set(self, config: Dict, initial_state: str) -> bool:
        """
        Process a single field set (3DED, HP, or Custom).
        
        Args:
            config: Configuration dictionary from CheckConfigDialog
            initial_state: Initial text state for restoration if needed
            
        Returns:
            True if processing was successful
        """
        try:
            # Special handling for 3DED: Check CIF format compatibility
            if self.current_field_set == '3DED':
                self._handle_3ded_format_compatibility()
            
            # Get the selected field set
            fields = self.field_checker.get_field_set(self.current_field_set)
            if not fields:
                QMessageBox.warning(self.parent, "Warning", f"No {self.current_field_set} field definitions loaded.")
                return False
            
            # Update window title to show which field set is being used
            field_set_display = {
                '3DED': '3D ED',
                'Custom': f'Custom ({os.path.basename(self.custom_field_rules_file) if self.custom_field_rules_file else "Unknown"})'
            }
            
            title = f"EDCIF-check - Checking with {field_set_display.get(self.current_field_set, self.current_field_set)} fields"
            self._update_title(title)
            
            # Parse the current CIF content
            content = self._get_text_content()
            self.cif_parser.parse_file(content)
            
            # For custom sets, handle DELETE/EDIT operations first
            if self.current_field_set == 'Custom':
                success = self._handle_custom_operations(fields)
                if not success:
                    return False
            
            # Process CHECK actions (standard field checking)
            for field_def in fields:
                # Skip DELETE/EDIT actions as they're already processed
                if hasattr(field_def, 'action') and field_def.action in ['DELETE', 'EDIT']:
                    continue
                    
                result = self.check_line_with_config(
                    field_def.name,
                    field_def.default_value,
                    False,
                    field_def.description,
                    config
                )
                
                if result == RESULT_ABORT:
                    self._set_text_content(initial_state)
                    self._update_title("EDCIF-check")
                    QMessageBox.information(self.parent, "Checks Aborted", "All changes have been reverted.")
                    return False
                elif result == RESULT_STOP_SAVE:
                    break
            
            # Apply special 3DED handling if needed
            if self.current_field_set == '3DED':
                self._apply_3ded_special_checks(config, initial_state)
            
            return True
            
        except Exception as e:
            self._set_text_content(initial_state)
            self._update_title("EDCIF-check")
            QMessageBox.critical(self.parent, "Error During Checks", f"An error occurred: {str(e)}")
            return False

    def _handle_3ded_format_compatibility(self):
        """Handle CIF format compatibility for 3DED field set."""
        if not self.dict_manager:
            return
            
        # Detect CIF format of current file
        content = self._get_text_content()
        cif_format = self.dict_manager.detect_cif_format(content)
        
        # Load appropriate 3DED rules based on CIF format
        field_rules_dir = get_resource_path('field_rules')
        if cif_format.upper() == 'CIF1':
            # Load CIF1 version of 3DED rules
            cif1_rules_path = os.path.join(field_rules_dir, '3ded_cif1.cif_rules')
            if os.path.exists(cif1_rules_path):
                self.field_checker.load_field_set('3DED', cif1_rules_path)
                QMessageBox.information(
                    self.parent, 
                    "CIF Format Compatibility", 
                    f"Detected CIF1 format. Automatically switched to CIF1-compatible 3D ED field rules."
                )
            else:
                QMessageBox.warning(
                    self.parent, 
                    "Compatibility Issue", 
                    f"CIF1 format detected, but CIF1-compatible 3D ED rules not found.\n"
                    f"Using default CIF2 rules which may cause validation issues."
                )
        else:
            # Load default CIF2 version of 3DED rules
            default_rules_path = os.path.join(field_rules_dir, '3ded.cif_rules')
            if os.path.exists(default_rules_path):
                self.field_checker.load_field_set('3DED', default_rules_path)

    def _handle_custom_operations(self, fields) -> bool:
        """
        Handle DELETE/EDIT operations for custom field sets.
        
        Args:
            fields: List of field definitions
            
        Returns:
            True if operations were handled successfully
        """
        current_content = self._get_text_content()
        operations_applied = []
        
        for field_def in fields:
            if hasattr(field_def, 'action'):
                if field_def.action == 'DELETE':
                    lines = current_content.splitlines()
                    lines, deleted = self.field_checker._delete_field(lines, field_def.name)
                    if deleted:
                        operations_applied.append(f"DELETED: {field_def.name}")
                        current_content = '\n'.join(lines)
                elif field_def.action == 'EDIT':
                    lines = current_content.splitlines()
                    lines, edited = self.field_checker._edit_field(lines, field_def.name, field_def.default_value)
                    if edited:
                        operations_applied.append(f"EDITED: {field_def.name} -> {field_def.default_value}")
                        current_content = '\n'.join(lines)
        
        # Update content after DELETE/EDIT operations
        if operations_applied:
            self._set_text_content(current_content)
            ops_summary = '\n'.join(operations_applied)
            QMessageBox.information(self.parent, "Operations Applied", 
                                  f"Applied {len(operations_applied)} operations:\n\n{ops_summary}")
        
        return True

    def _apply_3ded_special_checks(self, config: Dict, initial_state: str):
        """
        Apply special 3DED checks for space groups and absolute configuration.
        
        Args:
            config: Configuration dictionary
            initial_state: Initial text state for restoration if needed
        """
        if not self.dict_manager:
            return
            
        sohncke_groups = [1, 3, 4, 5, 16, 17, 18, 19, 20, 21, 22, 23, 24, 75, 76, 77, 78, 79, 80, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 143, 144, 145, 146, 149, 150, 151, 152, 153, 154, 155, 168, 169, 170, 171, 172, 173, 177, 178, 179, 180, 181, 182, 195, 196, 197, 198, 199, 207, 208, 209, 210, 211, 212, 213, 214]
        SG_number = None
        lines = self._get_text_content().splitlines()
        
        # Find space group number
        for line in lines:
            if line.startswith("_space_group_IT_number"):
                parts = line.split()
                if len(parts) > 1:
                    try:
                        SG_number = int(parts[1].strip("'\""))
                    except Exception:
                        pass
                break
        
        # Check if we need absolute configuration handling
        if SG_number is not None and SG_number in sohncke_groups:
            # Detect CIF format to use appropriate field names
            content = self._get_text_content()
            detected_version = self.dict_manager.detect_cif_version(content)
            
            # Determine field names based on CIF format
            if detected_version == CIFVersion.CIF2:
                abs_config_field = "_chemical.absolute_configuration"
                z_score_field = "_refine_ls.abs_structure_z-score"
            else:
                # Use CIF1 format for CIF1, MIXED, and UNKNOWN
                abs_config_field = "_chemical_absolute_configuration"
                z_score_field = "_refine_ls_abs_structure_z-score"
            
            found = False
            for line in lines:
                if line.startswith(abs_config_field):
                    found = True
                    break
            
            if found:
                result = self.check_line_with_config(
                    abs_config_field, 
                    default_value='dyn', 
                    multiline=False, 
                    description="Specify if/how absolute structure was determined.", 
                    config=config
                )
                if result == RESULT_ABORT:
                    self._set_text_content(initial_state)
                    return

    def _ensure_field_rules_validated(self) -> bool:
        """
        Ensure field definitions are validated before starting checks.
        
        Returns:
            True if validation passed or was skipped, False if cancelled
        """
        if not self.field_rules_validator:
            return True  # Skip validation if validator not available
            
        try:
            # Determine which field rules file to validate
            if self.current_field_set == 'Custom' and self.custom_field_rules_file:
                file_path = self.custom_field_rules_file
            else:
                # Use built-in field rules
                field_rules_dir = get_resource_path('field_rules')
                file_map = {
                    '3DED': '3ded.cif_rules',
                    'HP': 'hp.cif_rules'
                }
                if self.current_field_set not in file_map:
                    return True  # Unknown field set, skip validation
                file_path = os.path.join(field_rules_dir, file_map[self.current_field_set])
            
            if not os.path.exists(file_path):
                return True  # File doesn't exist, skip validation
            
            # Read the field definition file
            with open(file_path, 'r', encoding='utf-8') as f:
                field_rules_content = f.read()
            
            # Get CIF content for format analysis
            cif_content = self._text_content_callback() if self._text_content_callback else None
            
            # Run validation  
            validation_result = self.field_rules_validator.validate_field_rules(
                field_rules_content, cif_content
            )
            
            if validation_result.has_issues:
                # Show issues to user
                issues_text = '\n'.join([f"• {issue.description}" for issue in validation_result.issues[:10]])  # Limit to first 10
                if len(validation_result.issues) > 10:
                    issues_text += f"\n... and {len(validation_result.issues) - 10} more issues"
                
                reply = QMessageBox.question(
                    self.parent,
                    "Field Rules Validation Issues",
                    f"Issues found in field definitions that may affect checking:\n\n"
                    f"{issues_text}\n\n"
                    f"Total issues: {len(validation_result.issues)}\n\n"
                    "Do you want to continue anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                return reply == QMessageBox.StandardButton.Yes
            
            return True
            
        except Exception as e:
            QMessageBox.warning(
                self.parent,
                "Validation Error",
                f"Could not validate field rules: {str(e)}\n\nContinuing without validation."
            )
            return True

    def validate_field_rules(self):
        """Show field rules validation dialog for user-selected file."""
        file_filter = "Field Rules (*.cif_rules);;All Files (*.*)"
        file_path, _ = QFileDialog.getOpenFileName(
            self.parent, "Select Field Definition File to Validate", "",
            file_filter)
        
        if file_path:
            self._validate_field_rules_file(file_path)

    def _validate_field_rules_file(self, file_path: str):
        """
        Validate a specific field rules file and show results.
        
        Args:
            file_path: Path to the field rules file to validate
        """
        if not self.field_rules_validator:
            QMessageBox.warning(
                self.parent,
                "Validation Not Available",
                "Field rules validator is not initialized."
            )
            return
            
        try:
            dialog = FieldRulesValidationDialog(
                file_path, self.field_rules_validator, self.parent)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(
                self.parent, "Validation Error",
                f"Failed to validate field rules file:\n{str(e)}")

    def check_deprecated_fields(self) -> List[str]:
        """
        Check for deprecated fields in the current CIF content.
        
        Returns:
            List of deprecated field names found
        """
        if not self.dict_manager:
            return []
            
        try:
            content = self._get_text_content()
            deprecated_fields = []
            
            lines = content.splitlines()
            for line in lines:
                line = line.strip()
                if line.startswith('_') and not line.startswith('#'):
                    field_name = line.split()[0]
                    # Check if field is deprecated using dictionary manager
                    # This would require implementing deprecated field checking in the dictionary manager
                    # For now, return empty list as placeholder
                    pass
            
            return deprecated_fields
            
        except Exception as e:
            print(f"Error checking deprecated fields: {e}")
            return []

    def get_field_checker(self) -> CIFFieldChecker:
        """Get the field checker instance."""
        return self.field_checker
    
    def get_cif_parser(self) -> CIFParser:
        """Get the CIF parser instance."""
        return self.cif_parser
    
    def is_initialized(self) -> bool:
        """
        Check if the validation controller is properly initialized.
        
        Returns:
            True if all required components are available
        """
        return (self.field_checker is not None and 
                self.cif_parser is not None and
                self.dict_manager is not None)