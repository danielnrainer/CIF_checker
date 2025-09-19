from PyQt6.QtWidgets import (QMainWindow, QWidget, QTextEdit, 
                           QPushButton, QVBoxLayout, QHBoxLayout, QMenu,
                           QFileDialog, QMessageBox, QLineEdit, QCheckBox, 
                           QDialog, QLabel, QFontDialog, QGroupBox, QRadioButton,
                           QButtonGroup)
from PyQt6.QtCore import Qt, QRegularExpression, QTimer
from PyQt6.QtGui import (QTextCharFormat, QSyntaxHighlighter, QColor, QFont, 
                        QFontMetrics, QTextCursor, QTextDocument)
import os
import json
import sys
from typing import Dict, List, Tuple
from utils.CIF_field_parsing import CIFFieldChecker
from utils.CIF_parser import CIFParser
from utils.cif_dictionary_manager import CIFDictionaryManager, CIFVersion, get_resource_path
from utils.cif2_only_extensions import ExtendedCIFDictionaryManager
from utils.cif_format_converter import CIFFormatConverter
from utils.field_rules_validator import FieldRulesValidator
from services.file_manager import CIFFileManager
from services.settings_manager import SettingsManager
from services.validation_controller import ValidationController
from .dialogs import (CIFInputDialog, MultilineInputDialog, CheckConfigDialog, 
                     RESULT_ABORT, RESULT_STOP_SAVE)
from .dialogs.dictionary_info_dialog import DictionaryInfoDialog
from .dialogs.field_conflict_dialog import FieldConflictDialog
from .dialogs.field_rules_validation_dialog import FieldRulesValidationDialog
from .dialogs.dictionary_suggestion_dialog import show_dictionary_suggestions
from .editor import CIFSyntaxHighlighter, CIFTextEditor


class CIFEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize file manager
        self.file_manager = CIFFileManager(parent_widget=self)
        
        # Initialize settings manager
        self.settings_manager = SettingsManager(parent=self)
        
        # Initialize validation controller
        self.validation_controller = ValidationController(parent=self)
        
        config_path = os.path.dirname(__file__)
        
        # Initialize CIF dictionary manager and format converter
        base_dict_manager = CIFDictionaryManager()
        self.dict_manager = ExtendedCIFDictionaryManager(base_dict_manager)
        self.format_converter = CIFFormatConverter(self.dict_manager)
        self.current_cif_version = CIFVersion.UNKNOWN
        
        # Maintain backwards compatibility - delegate to validation controller
        self.field_checker = self.validation_controller.get_field_checker()
        self.cif_parser = self.validation_controller.get_cif_parser()
        
        self.init_ui()
        self.setup_file_manager_callbacks()
        self.setup_settings_manager_callbacks()
        self.setup_validation_controller_callbacks()
        self.update_dictionary_status()
        self.select_initial_file()
    
    @property
    def field_rules_validator(self):
        """Get field rules validator from validation controller."""
        return self.validation_controller.field_rules_validator
    
    @property
    def current_field_set(self):
        """Get current field set from validation controller."""
        return self.validation_controller.current_field_set
    
    @current_field_set.setter
    def current_field_set(self, value):
        """Set current field set in validation controller."""
        self.validation_controller.current_field_set = value
    
    @property
    def custom_field_rules_file(self):
        """Get custom field rules file path from validation controller."""
        return self.validation_controller.custom_field_rules_file
    
    @custom_field_rules_file.setter
    def custom_field_rules_file(self, value):
        """Set custom field rules file path in validation controller."""
        self.validation_controller.custom_field_rules_file = value

    def load_settings(self):
        """Load editor settings - delegated to text editor component"""
        # This method is now handled by the CIFTextEditor component
        pass

    def save_settings(self):
        """Save editor settings - delegated to text editor component"""
        # This method is now handled by the CIFTextEditor component
        pass

    def apply_settings(self):
        """Apply current settings - delegated to text editor component"""
        # This method is now handled by the CIFTextEditor component
        pass

    def change_font(self):
        """Open font dialog to change editor font"""
        self.cif_text_editor.change_font()
            
    def toggle_line_numbers(self):
        """Toggle line numbers visibility"""
        self.cif_text_editor.toggle_line_numbers()
        
    def toggle_syntax_highlighting(self):
        """Toggle syntax highlighting"""
        self.cif_text_editor.toggle_syntax_highlighting()
        
    def toggle_ruler(self):
        """Toggle ruler visibility"""
        self.cif_text_editor.toggle_ruler()
        self.save_settings()

    def init_ui(self):
        self.setWindowTitle("EDCIF-check")
        self.setGeometry(100, 100, 900, 700)

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Create status bar
        self.status_bar = self.statusBar()
        self.path_label = QLabel()
        self.cursor_label = QLabel()
        self.cif_version_label = QLabel("CIF Version: Unknown")
        self.dictionary_label = QLabel("Dictionary: Default")
        self.status_bar.addPermanentWidget(self.path_label)
        self.status_bar.addPermanentWidget(self.cif_version_label)
        self.status_bar.addPermanentWidget(self.dictionary_label)
        self.status_bar.addPermanentWidget(self.cursor_label)
        
        # Create CIF text editor component
        self.cif_text_editor = CIFTextEditor()
        self.cif_text_editor.textChanged.connect(self.handle_text_changed)
        self.cif_text_editor.cursorPositionChanged.connect(self.update_cursor_position)
        
        # Provide access to the underlying text editor for backwards compatibility
        self.text_editor = self.cif_text_editor.text_editor
        self.line_numbers = self.cif_text_editor.line_numbers
        self.ruler = self.cif_text_editor.ruler
        
        main_layout.addWidget(self.cif_text_editor)
        
        # Create field definition selection section
        field_selection_group = QGroupBox("CIF Field Definition Selection")
        field_selection_layout = QVBoxLayout(field_selection_group)
        
        # Create radio button group for field definition selection
        self.field_rules_group = QButtonGroup()
        
        # Radio buttons for built-in field definitions
        radio_layout = QHBoxLayout()
        
        self.radio_3ded = QRadioButton("3D ED")
        self.radio_3ded.setChecked(True)  # Default selection
        self.radio_3ded.toggled.connect(lambda checked: self.validation_controller.set_field_set('3DED') if checked else None)
        
        self.radio_custom = QRadioButton("Custom File")
        self.radio_custom.toggled.connect(lambda checked: self.validation_controller.set_field_set('Custom') if checked else None)
        
        # Add radio buttons to group and layout
        self.field_rules_group.addButton(self.radio_3ded)
        self.field_rules_group.addButton(self.radio_custom)
        
        radio_layout.addWidget(self.radio_3ded)
        radio_layout.addWidget(self.radio_custom)
        
        # Custom file selection layout
        custom_file_layout = QHBoxLayout()
        self.custom_file_button = QPushButton("Select Custom File...")
        self.custom_file_button.clicked.connect(self.select_custom_field_rules_file)
        self.custom_file_button.setEnabled(False)  # Initially disabled
        
        self.custom_file_label = QLabel("No custom file selected")
        self.custom_file_label.setStyleSheet("color: gray; font-style: italic;")
        
        custom_file_layout.addWidget(self.custom_file_button)
        custom_file_layout.addWidget(self.custom_file_label)
        custom_file_layout.addStretch()
        
        field_selection_layout.addLayout(radio_layout)
        field_selection_layout.addLayout(custom_file_layout)
        
        main_layout.addWidget(field_selection_group)
        
        # Create button layout
        button_layout = QHBoxLayout()
        
        # Create buttons
        start_checks_button = QPushButton("Start Checks")
        start_checks_button.clicked.connect(self.validation_controller.start_checks)
        refine_details_button = QPushButton("Edit Refinement Special Details")
        refine_details_button.clicked.connect(self.check_refine_special_details)
        format_button = QPushButton("Reformat File")
        format_button.clicked.connect(self.reformat_file)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_file)
        
        # Add buttons to layout
        button_layout.addWidget(start_checks_button)
        button_layout.addWidget(refine_details_button)
        button_layout.addWidget(format_button)
        button_layout.addWidget(save_button)
        
        main_layout.addLayout(button_layout)        # Create menu bar
        menubar = self.menuBar()
        
        # File menu with recent files
        file_menu = menubar.addMenu("File")
        
        open_action = file_menu.addAction("Open")
        open_action.triggered.connect(self.open_file)
        
        self.recent_menu = QMenu("Recent Files", self)
        file_menu.addMenu(self.recent_menu)
        
        save_as_action = file_menu.addAction("Save As")
        save_as_action.triggered.connect(self.save_file_as)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)
        
        # Actions menu
        action_menu = menubar.addMenu("Actions")
        
        start_checks_action = action_menu.addAction("Start Checks")
        start_checks_action.triggered.connect(self.validation_controller.start_checks)
        
        refine_details_action = action_menu.addAction("Edit Refinement Special Details")
        refine_details_action.triggered.connect(self.check_refine_special_details)
        
        format_action = action_menu.addAction("Reformat File")
        format_action.triggered.connect(self.reformat_file)

        # CIF Format menu
        format_menu = menubar.addMenu("CIF Format")
        
        detect_version_action = format_menu.addAction("Detect CIF Version")
        detect_version_action.triggered.connect(self.detect_cif_version)
        
        format_menu.addSeparator()
        
        convert_to_cif1_action = format_menu.addAction("Convert to CIF1")
        convert_to_cif1_action.triggered.connect(self.convert_to_cif1)
        
        convert_to_cif2_action = format_menu.addAction("Convert to CIF2")
        convert_to_cif2_action.triggered.connect(self.convert_to_cif2)
        
        format_menu.addSeparator()
        
        fix_mixed_action = format_menu.addAction("Fix Mixed Format")
        fix_mixed_action.triggered.connect(self.fix_mixed_format)
        
        resolve_aliases_action = format_menu.addAction("Resolve Field Aliases")
        resolve_aliases_action.triggered.connect(self.standardize_cif_fields)
        
        check_deprecated_action = format_menu.addAction("Check Deprecated Fields")
        check_deprecated_action.triggered.connect(self.check_deprecated_fields)
        
        format_menu.addSeparator()
        
        add_compatibility_action = format_menu.addAction("Add Legacy Compatibility Fields")
        add_compatibility_action.triggered.connect(self.add_legacy_compatibility_fields)
        add_compatibility_action.setToolTip("Add deprecated fields alongside modern equivalents for validation tool compatibility")

        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        
        # Undo/Redo
        undo_action = edit_menu.addAction("Undo")
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self.text_editor.undo)
        
        redo_action = edit_menu.addAction("Redo")
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(self.text_editor.redo)
        
        edit_menu.addSeparator()
        
        # Find
        find_action = edit_menu.addAction("Find")
        find_action.setShortcut("Ctrl+F")
        find_action.triggered.connect(self.show_find_dialog)
        
        # Find and Replace
        replace_action = edit_menu.addAction("Find and Replace")
        replace_action.setShortcut("Ctrl+H")
        replace_action.triggered.connect(self.show_replace_dialog)
        
        edit_menu.addSeparator()
        
        # View menu for editor settings
        view_menu = menubar.addMenu("View")
        
        font_action = view_menu.addAction("Change Font...")
        font_action.triggered.connect(self.change_font)
        
        line_numbers_action = view_menu.addAction("Show Line Numbers")
        line_numbers_action.setCheckable(True)
        line_numbers_action.setChecked(self.cif_text_editor.settings['line_numbers_enabled'])
        line_numbers_action.triggered.connect(self.toggle_line_numbers)
        
        ruler_action = view_menu.addAction("Show 80-Char Ruler")
        ruler_action.setCheckable(True)
        ruler_action.setChecked(self.cif_text_editor.settings['show_ruler'])
        ruler_action.triggered.connect(self.toggle_ruler)
        
        syntax_action = view_menu.addAction("Syntax Highlighting")
        syntax_action.setCheckable(True)
        syntax_action.setChecked(self.cif_text_editor.settings['syntax_highlighting_enabled'])
        syntax_action.triggered.connect(self.toggle_syntax_highlighting)
        
        # Settings menu
        settings_menu = menubar.addMenu("Settings")
        
        # Dictionary management section
        dict_info_action = settings_menu.addAction("Dictionary Information...")
        dict_info_action.triggered.connect(self.show_dictionary_info)
        
        settings_menu.addSeparator()
        
        load_dict_action = settings_menu.addAction("Replace Core CIF Dictionary...")
        load_dict_action.triggered.connect(self.load_custom_dictionary)
        
        add_dict_action = settings_menu.addAction("Add Additional CIF Dictionary...")
        add_dict_action.triggered.connect(self.add_additional_dictionary)
        
        suggest_dict_action = settings_menu.addAction("Suggest Dictionaries for Current CIF...")
        suggest_dict_action.triggered.connect(self.suggest_dictionaries)
        
        settings_menu.addSeparator()
        
        # Field definition validation
        validate_field_defs_action = settings_menu.addAction("Validate Field Rules...")
        validate_field_defs_action.triggered.connect(self.validation_controller.validate_field_rules)
        
        # Enable undo/redo
        self.text_editor.setUndoRedoEnabled(True)

    def setup_file_manager_callbacks(self):
        """Set up callbacks for file manager to communicate with UI."""
        self.file_manager.register_callbacks(
            on_file_opened=self._on_file_opened,
            on_file_saved=self._on_file_saved,
            on_recent_files_updated=self._on_recent_files_updated,
            on_error=self._on_file_manager_error
        )
    
    def setup_settings_manager_callbacks(self):
        """Set up callbacks for settings manager to communicate with UI."""
        self.settings_manager.set_callbacks(
            status_callback=lambda msg, timeout: self.status_bar.showMessage(msg, timeout),
            dictionary_status_callback=self.update_dictionary_status,
            text_content_callback=lambda: self.text_editor.toPlainText()
        )
        
        # Initialize the settings manager with current dictionary manager
        self.settings_manager.set_dictionary_manager(self.dict_manager)
    
    def setup_validation_controller_callbacks(self):
        """Set up callbacks for validation controller to communicate with UI."""
        self.validation_controller.set_callbacks(
            text_content_callback=lambda: self.text_editor.toPlainText(),
            set_text_callback=lambda content: self.text_editor.setText(content),
            status_callback=lambda msg, timeout: self.status_bar.showMessage(msg, timeout),
            title_callback=lambda title: self.setWindowTitle(title)
        )
        
        # Initialize the validation controller with dictionary components
        self.validation_controller.set_dictionary_components(self.dict_manager, self.format_converter)
    
    def _on_file_opened(self, filepath: str, content: str):
        """Handle file opened event from file manager."""
        self.text_editor.setText(content)
        
        # Detect CIF version
        self.detect_and_update_cif_version(content)
        
        self.update_status_bar()
        self.setWindowTitle(f"EDCIF-check - {filepath}")
        
        # Prompt for dictionary suggestions after opening CIF file
        self.prompt_for_dictionary_suggestions(content)
    
    def _on_file_saved(self, filepath: str):
        """Handle file saved event from file manager."""
        self.update_status_bar()
        self.setWindowTitle(f"EDCIF-check - {filepath}")
    
    def _on_recent_files_updated(self, recent_files: List[str]):
        """Handle recent files list updated event."""
        self.update_recent_files_menu()
    
    def _on_file_manager_error(self, title: str, message: str):
        """Handle file manager errors."""
        QMessageBox.critical(self, title, message)
    
    def _set_modified(self, modified: bool = True):
        """Set the modified state and update UI."""
        self.file_manager.set_modified(modified)
        self.update_status_bar()
    
    def _ensure_cif2_header(self, content: str) -> str:
        """
        Ensure CIF2 content has proper header.
        
        Args:
            content: CIF file content
            
        Returns:
            Content with CIF2 header if needed
        """
        # Detect if this is CIF2 format
        detected_version = self.dict_manager.detect_cif_version(content)
        
        if detected_version == CIFVersion.CIF2:
            lines = content.splitlines()
            
            # Check if CIF2 header already exists in first few lines
            has_header = any(line.strip().startswith('#\\#CIF_2.0') for line in lines[:5])
            
            if not has_header:
                # Add CIF2 header at the beginning
                lines.insert(0, '#\\#CIF_2.0')
                lines.insert(1, '')  # Add empty line after header
                return '\\n'.join(lines)
        
        return content

    def select_initial_file(self):
        """Select initial file on startup."""
        self.file_manager.select_initial_file()

    def update_recent_files_menu(self):
        """Update the recent files menu with current list."""
        self.recent_menu.clear()
        recent_files = self.file_manager.get_recent_files()
        for filepath in recent_files:
            action = self.recent_menu.addAction(filepath)
            action.triggered.connect(lambda checked, path=filepath: self.open_recent_file(path))
            
    def open_recent_file(self, filepath):
        """Open a file from recent files list."""
        self.file_manager.open_recent_file(filepath)
        
    def add_to_recent_files(self, filepath):
        """Add file to recent files list (now handled by file manager)."""
        # This method is now handled by the file manager automatically
        pass

    def open_file(self, initial=False):
        """Open a file using file dialog."""
        if not initial:
            self.file_manager.open_file_dialog()
        else:
            # For initial=True, we assume current_file is already set
            # This case is handled by the file manager's callback system
            pass

    def save_file(self):
        """Save current file content."""
        original_content = self.text_editor.toPlainText()
        # Ensure CIF2 files have proper header
        content = self._ensure_cif2_header(original_content)
        
        # Update editor if header was added
        if content != original_content:
            self.text_editor.setText(content)
            self._set_modified(True)
        
        self.file_manager.save_file(content)

    def save_file_as(self):
        """Save file with new name."""
        original_content = self.text_editor.toPlainText()
        # Ensure CIF2 files have proper header
        content = self._ensure_cif2_header(original_content)
        
        # Update editor if header was added
        if content != original_content:
            self.text_editor.setText(content)
            self._set_modified(True)
        
        self.file_manager.save_file_as(content)

    def validate_cif(self):
        """Basic CIF syntax validation"""
        return self.validation_controller.validate_cif()

    def check_line(self, prefix, default_value=None, multiline=False, description=""):
        """Check and potentially update a CIF field value."""
        return self.validation_controller.check_line(prefix, default_value, multiline, description)

    def add_missing_line(self, prefix, lines, default_value=None, multiline=False, description=""):
        """Add a missing CIF field with value.""" 
        # This functionality is now handled by ValidationController
        # But we need to maintain the interface for backward compatibility
        return self.validation_controller.check_line(prefix, default_value, multiline, description)    
    
    def check_line_with_config(self, prefix, default_value=None, multiline=False, description="", config=None):
        """Check and potentially update a CIF field value with configuration options."""
        if self.dict_manager.is_field_deprecated(prefix):
            modern_equivalent = self.dict_manager.get_modern_equivalent(prefix, prefer_format="CIF1")
            if modern_equivalent:
                # Show deprecated field warning with suggestion
                reply = QMessageBox.question(
                    self, 
                    "Deprecated Field Warning",
                    f"The field '{prefix}' is deprecated.\n\n"
                    f"Modern equivalent: '{modern_equivalent}'\n\n"
                    f"Would you like to replace it with the modern equivalent?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Yes
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    # Replace deprecated field with modern equivalent
                    return self._replace_deprecated_field(prefix, modern_equivalent)
                elif reply == QMessageBox.StandardButton.Cancel:
                    return QDialog.DialogCode.Rejected
                # If No, continue with the deprecated field
            else:
                # No modern equivalent available
                reply = QMessageBox.question(
                    self,
                    "Deprecated Field Warning", 
                    f"The field '{prefix}' is deprecated and has no modern equivalent.\n\n"
                    f"It's recommended to remove this field.\n\n"
                    f"Continue with deprecated field?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.No:
                    return QDialog.DialogCode.Rejected
        
        removable_chars = "'"
        lines = self.text_editor.toPlainText().splitlines()
        
        # Check if field exists
        field_found = False
        for i, line in enumerate(lines):
            if line.startswith(prefix):
                field_found = True
                current_value = " ".join(line.split()[1:]).strip(removable_chars)
                
                # If skip_matching_defaults is enabled and current value matches default
                if config.get('skip_matching_defaults', False) and default_value:
                    # Clean both values for comparison
                    clean_current = current_value.strip().strip("'\"")
                    clean_default = str(default_value).strip().strip("'\"")
                    if clean_current == clean_default:
                        return QDialog.DialogCode.Accepted  # Skip this field
                
                # Show normal edit dialog
                value, result = CIFInputDialog.getText(
                    self, "Edit Line",
                    f"Edit the line:\n{line}\n\nDescription: {description}\n\nSuggested value: {default_value}\n\n",
                    current_value, default_value)
                
                if result in [CIFInputDialog.RESULT_ABORT, CIFInputDialog.RESULT_STOP_SAVE]:
                    return result
                elif result == QDialog.DialogCode.Accepted and value:
                    # Preserve original quoting style - only quote if value has spaces or special chars
                    stripped_value = value.strip(removable_chars)
                    if ' ' in stripped_value or ',' in stripped_value:
                        formatted_value = f"'{stripped_value}'"
                    else:
                        formatted_value = stripped_value
                    lines[i] = f"{prefix} {formatted_value}"
                    self.text_editor.setText("\n".join(lines))
                return result
        
        # Field not found - handle missing field
        if not field_found:
            return self.add_missing_line_with_config(prefix, lines, default_value, multiline, description, config)
        
        return QDialog.DialogCode.Accepted
    
    def add_missing_line_with_config(self, prefix, lines, default_value=None, multiline=False, description="", config=None):
        """Add a missing CIF field with value, respecting configuration options."""
        return self.validation_controller.add_missing_line_with_config(
            prefix, lines, default_value, multiline, description, config
        )
    
    def _replace_deprecated_field(self, deprecated_field, modern_field):
        """Replace a deprecated field with its modern equivalent in the CIF content"""
        content = self.text_editor.toPlainText()
        lines = content.splitlines()
        
        field_replaced = False
        for i, line in enumerate(lines):
            if line.startswith(deprecated_field):
                # Extract the value from the deprecated field
                parts = line.split(maxsplit=1)
                if len(parts) > 1:
                    value = parts[1]
                    lines[i] = f"{modern_field} {value}"
                    field_replaced = True
                    break
        
        if field_replaced:
            self.text_editor.setText("\n".join(lines))
            QMessageBox.information(
                self, 
                "Field Updated", 
                f"Successfully replaced deprecated field '{deprecated_field}' with '{modern_field}'"
            )
            return QDialog.DialogCode.Accepted
        else:
            QMessageBox.warning(
                self, 
                "Field Not Found", 
                f"Could not find deprecated field '{deprecated_field}' to replace"
            )
            return QDialog.DialogCode.Rejected
    
    def check_refine_special_details(self):
        """Check and edit _refine_special_details field, creating it if needed."""
        content = self.text_editor.toPlainText()
        
        # Parse the CIF content using the new parser
        self.cif_parser.parse_file(content)
        
        # Detect CIF version to determine the correct field name
        detected_version = self.dict_manager.detect_cif_version(content)
        
        # Determine the appropriate field name based on CIF version
        if detected_version == CIFVersion.CIF2:
            field_name = '_refine.special_details'
        elif detected_version == CIFVersion.MIXED:
            # For MIXED format, check which field actually exists in the content
            if self.cif_parser.get_field_value('_refine.special_details') is not None:
                field_name = '_refine.special_details'
            elif self.cif_parser.get_field_value('_refine_special_details') is not None:
                field_name = '_refine_special_details'
            else:
                # Neither exists, so decide based on the predominant format
                # Check if this looks more like CIF2 by counting modern vs legacy fields
                all_fields = list(self.cif_parser.fields.keys())
                cif2_fields = [f for f in all_fields if '.' in f]
                cif1_fields = [f for f in all_fields if '.' not in f]
                
                # If more CIF2 fields, use CIF2 naming
                if len(cif2_fields) >= len(cif1_fields):
                    field_name = '_refine.special_details'
                else:
                    field_name = '_refine_special_details'
        else:
            # Default to CIF1 format (covers CIF1, UNKNOWN)
            field_name = '_refine_special_details'
        
        template = (
            "STRUCTURE REFINEMENT\n"
            "- Refinement method\n"
            "- Special constraints and restraints\n"
            "- Special treatments"
        )
        
        # Get current value from the appropriate field name, or use template
        current_value = self.cif_parser.get_field_value(field_name)
        if current_value is None:
            current_value = template
        
        # Open dialog for editing
        dialog = MultilineInputDialog(current_value, self)
        dialog.setWindowTitle("Edit Refinement Special Details")
        result = dialog.exec()
        
        if result in [MultilineInputDialog.RESULT_ABORT, MultilineInputDialog.RESULT_STOP_SAVE]:
            return result
        elif result == QDialog.DialogCode.Accepted:
            updated_content = dialog.getText()
            
            # Update the field in the parser using the appropriate field name
            self.cif_parser.set_field_value(field_name, updated_content)
            
            # Generate updated CIF content and update the text editor
            updated_cif = self.cif_parser.generate_cif_content()
            self.text_editor.setText(updated_cif)
            self._set_modified()
            self.update_status_bar()
            
            return QDialog.DialogCode.Accepted
        
        return QDialog.DialogCode.Rejected

    def set_field_set(self, field_set_name):
        """Set the current field set selection."""
        self.current_field_set = field_set_name
        
        # Enable/disable custom file button based on selection
        if field_set_name == 'Custom':
            self.custom_file_button.setEnabled(True)
            if not self.custom_field_rules_file:
                self.custom_file_label.setText("Please select a custom file")
                self.custom_file_label.setStyleSheet("color: red; font-style: italic;")
        else:
            self.custom_file_button.setEnabled(False)
            self.custom_file_label.setText("No custom file selected")
            self.custom_file_label.setStyleSheet("color: gray; font-style: italic;")
    
    def select_custom_field_rules_file(self):
        """Open file dialog to select a custom field definition file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Field Definition File",
            "",
            "Field Rules Files (*.cif_rules);;All Files (*)"
        )
        
        if file_path:
            self._load_custom_field_rules_file(file_path)
    
    def _load_custom_field_rules_file(self, file_path: str, skip_validation: bool = False):
        """Load a custom field definition file with optional validation."""
        try:
            # Read the file content for validation
            with open(file_path, 'r', encoding='utf-8') as f:
                field_rules_content = f.read()
            
            # Offer validation if not skipping
            if not skip_validation:
                reply = QMessageBox.question(
                    self, "Validate Field Definitions",
                    "Would you like to validate this field definition file for common issues?\n\n"
                    "This can help identify and fix:\n"
                    "• Mixed CIF1/CIF2 formats\n"
                    "• Duplicate/alias fields\n"
                    "• Unknown fields\n\n"
                    "Recommended for better compatibility.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    # Get CIF content for format analysis if available
                    cif_content = self.text_editor.toPlainText() if hasattr(self, 'text_editor') else None
                    
                    # Validate the field definitions
                    validation_result = self.field_rules_validator.validate_field_rules(
                        field_rules_content, cif_content
                    )
                    
                    if validation_result.has_issues:
                        # Show validation dialog
                        dialog = FieldRulesValidationDialog(
                            validation_result, field_rules_content, file_path, 
                            self.field_rules_validator, self
                        )
                        
                        # Connect validation completion signal
                        dialog.validation_completed.connect(
                            lambda fixed_content, changes: self._on_validation_completed(
                                file_path, fixed_content, changes
                            )
                        )
                        
                        if dialog.exec() == QDialog.DialogCode.Accepted:
                            # Check if fixes were applied
                            if dialog.fixed_content:
                                # Use the fixed content instead
                                field_rules_content = dialog.fixed_content
                    else:
                        QMessageBox.information(
                            self, "Validation Complete",
                            "✅ No issues found in the field definition file!"
                        )
            
            # Try to load the field definition file
            self.field_checker.load_field_set('Custom', file_path)
            self.custom_field_rules_file = file_path
            
            # Update the label to show the selected file
            file_name = os.path.basename(file_path)
            self.custom_file_label.setText(f"Using: {file_name}")
            self.custom_file_label.setStyleSheet("color: green; font-weight: bold;")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Loading Custom File",
                f"Failed to load field definition file:\n{str(e)}\n\n"
                "Please ensure the file is in the correct format."
            )
            self.custom_file_label.setText("Error loading file")
            self.custom_file_label.setStyleSheet("color: red; font-style: italic;")
    
    def _on_validation_completed(self, file_path: str, fixed_content: str, changes: List[str]):
        """Handle completion of field definition validation."""
        try:
            # Write the fixed content to a temporary file and load it
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.cif_rules', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(fixed_content)
                temp_path = temp_file.name
            
            # Load the fixed content
            self.field_checker.load_field_set('Custom', temp_path)
            
            # Clean up temp file
            os.unlink(temp_path)
            
            # Show success message
            QMessageBox.information(
                self, "Field Definitions Updated",
                f"Field definitions loaded with {len(changes)} fixes applied:\n\n" +
                "\n".join(f"• {change}" for change in changes[:5]) +
                (f"\n• ... and {len(changes) - 5} more" if len(changes) > 5 else "")
            )
            
        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Failed to load fixed field definitions: {str(e)}"
            )
    
    def start_checks(self):
        """Start checking CIF fields using the selected field definition set."""
        success = self.validation_controller.start_checks()
        if success:
            # Handle reformat if needed (would need to be passed to validation controller)
            pass

    def reformat_file(self):
        """Reformat CIF file to handle long lines and properly format values, preserving semicolon blocks."""
        try:
            # Use the CIF parser's reformatting functionality
            current_content = self.text_editor.toPlainText()
            reformatted_content = self.cif_parser.reformat_for_line_length(current_content)
            
            # Update the text editor with the reformatted content
            self.text_editor.setText(reformatted_content)
            
            QMessageBox.information(self, "Reformatting Completed",
                                  "The file has been successfully reformatted with proper line length handling.")
        except Exception as e:
            QMessageBox.critical(self, "Reformatting Error",
                               f"An error occurred while reformatting:\n{str(e)}")

    def insert_line_breaks(self, text, limit):
        words = text.split()
        line_length = 0
        lines = []
        current_line = []
        
        for word in words:
            if line_length + len(word) + 1 > limit:
                lines.append(" ".join(current_line))
                current_line = [word]
                line_length = len(word)
            else:
                current_line.append(word)
                line_length += len(word) + 1
        
        if current_line:
            lines.append(" ".join(current_line))
        
        return "\n".join(lines)

    def handle_text_changed(self):
        self._set_modified()
        self.update_status_bar()
        
        # Schedule CIF version detection (delayed to avoid constant updates)
        if hasattr(self, 'version_detect_timer'):
            self.version_detect_timer.stop()
        else:
            self.version_detect_timer = QTimer()
            self.version_detect_timer.setSingleShot(True)
            self.version_detect_timer.timeout.connect(lambda: self.detect_and_update_cif_version())
        
        self.version_detect_timer.start(1000)  # 1 second delay
    
    def update_cursor_position(self):
        cursor = self.text_editor.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.columnNumber() + 1
        current_line = cursor.block().text()
        line_length = len(current_line)
        
        # Update status bar with enhanced position info
        status = f"Ln {line}, Col {column} | Length: {line_length}/80"
        if line_length > 80:
            status += " (Over limit!)"
        self.cursor_label.setText(status)
        # Change color if line is too long
        if line_length > 80:
            self.cursor_label.setStyleSheet("color: red;")
        else:
            self.cursor_label.setStyleSheet("")

    def update_status_bar(self):
        path = self.file_manager.get_current_filepath() or "Untitled"
        modified = "*" if self.file_manager.is_file_modified() else ""
        self.path_label.setText(f"{path}{modified} | ")

    def update_dictionary_status(self):
        """Update the dictionary status label in the status bar"""
        try:
            # Get dictionary information
            dict_info = self.dict_manager.get_dictionary_info()
            total_dicts = dict_info['total_dictionaries']
            
            if total_dicts == 1:
                # Single dictionary - show its name
                dict_path = getattr(self.dict_manager.parser, 'cif_core_path', None)
                if dict_path and dict_path != 'cif_core.dic':
                    dict_name = os.path.basename(dict_path)
                    self.dictionary_label.setText(f"Dictionary: {dict_name}")
                else:
                    self.dictionary_label.setText("Dictionary: Default")
            else:
                # Multiple dictionaries - show count and primary
                primary_dict = dict_info.get('primary_dictionary', '')
                primary_name = os.path.basename(primary_dict) if primary_dict else 'Default'
                additional_count = total_dicts - 1
                
                self.dictionary_label.setText(f"Dictionaries: {primary_name} +{additional_count}")
                
                # Set tooltip with full list
                loaded_dicts = self.dict_manager.get_loaded_dictionaries()
                dict_names = [os.path.basename(path) for path in loaded_dicts]
                tooltip_text = f"Loaded dictionaries:\\n" + "\\n".join([f"• {name}" for name in dict_names])
                self.dictionary_label.setToolTip(tooltip_text)
                
        except Exception:
            # Fallback if there's any issue
            self.dictionary_label.setText("Dictionary: Unknown")

    def show_find_dialog(self):
        """Show a dialog for finding text in the editor"""
        self.cif_text_editor.show_find_dialog()

    def show_replace_dialog(self):
        """Show a dialog for finding and replacing text in the editor"""
        self.cif_text_editor.show_replace_dialog()

    def find_text(self, text, case_sensitive=False):
        """Find the next occurrence of text in the editor"""
        return self.cif_text_editor.find_text(text, case_sensitive)

    def replace_text(self, find_text, replace_text, case_sensitive=False):
        """Replace the next occurrence of find_text with replace_text"""
        self.cif_text_editor.replace_text(find_text, replace_text, case_sensitive)

    def replace_all_text(self, find_text, replace_text, case_sensitive=False):
        """Replace all occurrences of find_text with replace_text"""
        return self.cif_text_editor.replace_all_text(find_text, replace_text, case_sensitive)
    
    def detect_and_update_cif_version(self, content=None):
        """Detect CIF version and update the status display"""
        if content is None:
            content = self.text_editor.toPlainText()
        
        self.current_cif_version = self.dict_manager.detect_cif_version(content)
        self.update_cif_version_display()
    
    def update_cif_version_display(self):
        """Update the CIF version display in the status bar"""
        version_text = {
            CIFVersion.CIF1: "CIF Version: 1.x",
            CIFVersion.CIF2: "CIF Version: 2.0",
            CIFVersion.MIXED: "CIF Version: Mixed (1.x/2.0)",
            CIFVersion.UNKNOWN: "CIF Version: Unknown"
        }
        
        color = {
            CIFVersion.CIF1: "green",
            CIFVersion.CIF2: "blue", 
            CIFVersion.MIXED: "orange",
            CIFVersion.UNKNOWN: "red"
        }
        
        text = version_text.get(self.current_cif_version, "CIF Version: Unknown")
        self.cif_version_label.setText(text)
        self.cif_version_label.setStyleSheet(f"color: {color.get(self.current_cif_version, 'black')}")
    
    def detect_cif_version(self):
        """Menu action to detect and display CIF version information"""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        version = self.dict_manager.detect_cif_version(content)
        self.current_cif_version = version
        self.update_cif_version_display()
        
        # Show detailed information
        version_info = {
            CIFVersion.CIF1: "CIF version 1.x detected\nThis file uses traditional CIF1 format.",
            CIFVersion.CIF2: "CIF version 2.0 detected\nThis file uses modern CIF2 format with UTF-8 encoding.",
            CIFVersion.MIXED: "Mixed CIF format detected\nThis file contains both CIF1 and CIF2 elements.\nConsider using 'Fix Mixed Format' to resolve.",
            CIFVersion.UNKNOWN: "Unknown CIF format\nCould not determine CIF version from the content."
        }
        
        QMessageBox.information(self, "CIF Version Detection", 
                              version_info.get(version, "Unknown format detected."))
    
    def convert_to_cif1(self):
        """Convert current CIF content to CIF1 format"""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        try:
            converted_content, changes = self.format_converter.convert_to_cif1(content)
            if converted_content != content:
                self.text_editor.setText(converted_content)
                self._set_modified()
                self.current_cif_version = CIFVersion.CIF1
                self.update_cif_version_display()
                change_summary = f"Made {len(changes)} changes:\n" + "\n".join(changes[:5])
                if len(changes) > 5:
                    change_summary += f"\n... and {len(changes)-5} more"
                QMessageBox.information(self, "Conversion Complete", 
                                      f"File successfully converted to CIF1 format.\n\n{change_summary}")
            else:
                QMessageBox.information(self, "No Changes", 
                                      "File is already in CIF1 format or no conversion was needed.")
        except Exception as e:
            QMessageBox.critical(self, "Conversion Error", 
                               f"Failed to convert to CIF1:\n{str(e)}")
    
    def convert_to_cif2(self):
        """Convert current CIF content to CIF2 format"""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        try:
            converted_content, changes = self.format_converter.convert_to_cif2(content)
            if converted_content != content:
                self.text_editor.setText(converted_content)
                self._set_modified()
                self.current_cif_version = CIFVersion.CIF2
                self.update_cif_version_display()
                change_summary = f"Made {len(changes)} changes:\n" + "\n".join(changes[:5])
                if len(changes) > 5:
                    change_summary += f"\n... and {len(changes)-5} more"
                QMessageBox.information(self, "Conversion Complete", 
                                      f"File successfully converted to CIF2 format.\n" +
                                      f"Note: Save with UTF-8 encoding.\n\n{change_summary}")
            else:
                QMessageBox.information(self, "No Changes", 
                                      "File is already in CIF2 format or no conversion was needed.")
        except Exception as e:
            QMessageBox.critical(self, "Conversion Error", 
                               f"Failed to convert to CIF2:\n{str(e)}")
    
    def fix_mixed_format(self):
        """Fix mixed CIF format by converting to consistent format"""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        # First detect current version
        version = self.dict_manager.detect_cif_version(content)
        if version != CIFVersion.MIXED:
            QMessageBox.information(self, "No Mixed Format", 
                                  "File does not appear to have mixed CIF format.")
            return
        
        # Ask user which format to convert to
        reply = QMessageBox.question(self, "Choose Target Format",
                                   "Convert mixed format to:\n\n" +
                                   "Yes: CIF2 (recommended for new files)\n" +
                                   "No: CIF1 (for legacy compatibility)\n" +
                                   "Cancel: Abort conversion",
                                   QMessageBox.StandardButton.Yes |
                                   QMessageBox.StandardButton.No |
                                   QMessageBox.StandardButton.Cancel)
        
        if reply == QMessageBox.StandardButton.Cancel:
            return
        
        try:
            if reply == QMessageBox.StandardButton.Yes:
                # Convert to CIF2
                fixed_content, changes = self.format_converter.fix_mixed_format(content, target_version=CIFVersion.CIF2)
                target_version = CIFVersion.CIF2
                format_name = "CIF2"
            else:
                # Convert to CIF1
                fixed_content, changes = self.format_converter.fix_mixed_format(content, target_version=CIFVersion.CIF1)
                target_version = CIFVersion.CIF1
                format_name = "CIF1"
            
            if fixed_content != content:
                self.text_editor.setText(fixed_content)
                self._set_modified()
                self.current_cif_version = target_version
                self.update_cif_version_display()
                change_summary = f"Made {len(changes)} changes:\n" + "\n".join(changes[:5])
                if len(changes) > 5:
                    change_summary += f"\n... and {len(changes)-5} more"
                QMessageBox.information(self, "Format Fixed", 
                                      f"Mixed format successfully resolved to {format_name}.\n\n{change_summary}")
            else:
                QMessageBox.information(self, "No Changes", 
                                      "No format issues were found to fix.")
        except Exception as e:
            QMessageBox.critical(self, "Fix Error", 
                               f"Failed to fix mixed format:\n{str(e)}")

    def standardize_cif_fields(self):
        """Resolve CIF field alias conflicts with user control"""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        try:
            # Check for alias conflicts first
            conflicts = self.dict_manager.detect_field_aliases_in_cif(content)
            
            if not conflicts:
                QMessageBox.information(self, "No Alias Conflicts", 
                                      "No field alias conflicts were found.\n\n" +
                                      "This tool only resolves cases where the same field " +
                                      "appears in multiple forms (e.g., both _diffrn_source_type " +
                                      "and _diffrn_source_make in the same file).")
                return
            
            # Show conflict summary and let user choose resolution approach
            conflict_summary = f"Found {len(conflicts)} field alias conflicts:\n\n"
            for canonical, alias_list in conflicts.items():
                conflict_summary += f"• {canonical}:\n"
                for alias in alias_list:
                    conflict_summary += f"    - {alias}\n"
                conflict_summary += "\n"
            
            # Ask user how they want to resolve conflicts
            reply = QMessageBox.question(self, "Field Alias Conflicts Found",
                                       conflict_summary + 
                                       "How would you like to resolve these conflicts?\n\n" +
                                       "• Yes: Let me choose for each conflict individually\n" +
                                       "• No: Auto-resolve using CIF2 format + first available values\n" +
                                       "• Cancel: Don't resolve conflicts",
                                       QMessageBox.StandardButton.Yes |
                                       QMessageBox.StandardButton.No |
                                       QMessageBox.StandardButton.Cancel)
            
            if reply == QMessageBox.StandardButton.Cancel:
                return
            elif reply == QMessageBox.StandardButton.Yes:
                # Let user resolve conflicts individually
                dialog = FieldConflictDialog(conflicts, content, self, self.dict_manager)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    resolutions = dialog.get_resolutions()
                else:
                    return  # User cancelled
            else:
                # Auto-resolve using CIF2 format + first available values
                resolutions = self._auto_resolve_conflicts(conflicts, content)
            
            # Apply the resolutions
            if resolutions:
                resolved_content, changes = self.dict_manager.apply_field_conflict_resolutions(content, resolutions)
                
                if changes:
                    self.text_editor.setText(resolved_content)
                    self._set_modified()
                    
                    change_summary = f"Successfully resolved {len(conflicts)} field alias conflicts:\n\n"
                    for change in changes:
                        change_summary += f"• {change}\n"
                    
                    QMessageBox.information(self, "Conflicts Resolved", change_summary)
                else:
                    QMessageBox.information(self, "No Changes Made", 
                                          "No changes were needed to resolve the conflicts.")
                
        except Exception as e:
            QMessageBox.critical(self, "Conflict Resolution Error", 
                               f"Failed to resolve field alias conflicts:\n{str(e)}")
    
    def _auto_resolve_conflicts(self, conflicts: Dict[str, List[str]], cif_content: str) -> Dict[str, Tuple[str, str]]:
        """Auto-resolve conflicts using CIF2 format and first available values"""
        resolutions = {}
        
        lines = cif_content.split('\n')
        
        for canonical_field, alias_list in conflicts.items():
            # Use CIF2 format (canonical field)
            chosen_field = canonical_field
            
            # Find the first available value
            chosen_value = ""
            for alias in alias_list:
                for line in lines:
                    line_stripped = line.strip()
                    if line_stripped.startswith(alias + ' '):
                        parts = line_stripped.split(None, 1)
                        if len(parts) > 1:
                            chosen_value = parts[1]
                            break
                if chosen_value:
                    break
            
            # Fallback if no value found
            if not chosen_value:
                chosen_value = "?"
            
            resolutions[canonical_field] = (chosen_field, chosen_value)
        
        return resolutions

    def check_deprecated_fields(self):
        """Check for deprecated fields in the current CIF file and offer to replace them"""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        try:
            # Parse CIF content to find all fields
            lines = content.splitlines()
            found_deprecated = []
            
            for line_num, line in enumerate(lines, 1):
                line_stripped = line.strip()
                if line_stripped.startswith('_') and ' ' in line_stripped:
                    field_name = line_stripped.split()[0]
                    if self.dict_manager.is_field_deprecated(field_name):
                        modern_equiv = self.dict_manager.get_modern_equivalent(field_name, prefer_format="CIF1")
                        found_deprecated.append({
                            'field': field_name,
                            'line_num': line_num,
                            'line': line_stripped,
                            'modern': modern_equiv
                        })
            
            if not found_deprecated:
                QMessageBox.information(self, "No Deprecated Fields", 
                                      "No deprecated fields were found in the current CIF file.")
                return
            
            # Build summary of deprecated fields
            summary = f"Found {len(found_deprecated)} deprecated field(s):\n\n"
            for item in found_deprecated:
                summary += f"• Line {item['line_num']}: {item['field']}\n"
                if item['modern']:
                    summary += f"  → Modern equivalent: {item['modern']}\n"
                else:
                    summary += f"  → No modern equivalent (consider removal)\n"
                summary += "\n"
            
            # Check if any fields can actually be replaced
            replaceable_count = sum(1 for item in found_deprecated if item['modern'])
            
            if replaceable_count == 0:
                QMessageBox.information(
                    self, 
                    "Deprecated Fields Found",
                    summary + "None of these deprecated fields have modern equivalents available.\n\n" +
                    "Consider reviewing and potentially removing these fields manually."
                )
                return
            
            # Ask user what to do
            reply = QMessageBox.question(
                self, 
                "Deprecated Fields Found",
                summary + f"Would you like to replace the {replaceable_count} deprecated field(s) " +
                "that have modern equivalents?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Replace deprecated fields
                updated_content = content
                changes_made = []
                
                # Process in reverse order to maintain line numbers
                for item in reversed(found_deprecated):
                    if item['modern']:
                        old_line = item['line']
                        parts = old_line.split(None, 1)
                        if len(parts) > 1:
                            new_line = f"{item['modern']} {parts[1]}"
                            updated_content = updated_content.replace(old_line, new_line)
                            changes_made.append(f"Replaced {item['field']} → {item['modern']}")
                
                if changes_made:
                    self.text_editor.setText(updated_content)
                    self._set_modified()
                    
                    change_summary = f"Successfully updated {len(changes_made)} deprecated field(s):\n\n"
                    for change in changes_made:
                        change_summary += f"• {change}\n"
                    
                    QMessageBox.information(self, "Fields Updated", change_summary)
                else:
                    QMessageBox.information(self, "No Changes Made", 
                                          "No fields could be automatically replaced.")
                
        except Exception as e:
            QMessageBox.critical(self, "Deprecated Field Check Error", 
                               f"Failed to check for deprecated fields:\n{str(e)}")

    def add_legacy_compatibility_fields(self):
        """Add deprecated fields alongside modern equivalents for validation tool compatibility."""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.information(self, "No Content", "Please open a CIF file first.")
            return
        
        try:
            # Parse the current CIF content
            self.cif_parser.parse_file(content)
            
            # Show explanation dialog
            reply = QMessageBox.question(
                self, 
                "Add Legacy Compatibility Fields",
                "This feature adds deprecated fields alongside their modern equivalents "
                "to ensure compatibility with validation tools (like checkCIF/PLAT) that "
                "haven't been updated to recognize modern field names.\n\n"
                "Example: If you have '_diffrn.ambient_temperature', this will also add "
                "'_cell_measurement_temperature' with the same value.\n\n"
                "This is safe and won't affect the scientific meaning of your CIF file.\n\n"
                "Proceed with adding compatibility fields?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
            
            # Add compatibility fields
            report = self.cif_parser.add_legacy_compatibility_fields(self.dict_manager)
            
            # Generate the updated CIF content
            updated_content = self.cif_parser.generate_cif_content()
            
            # Update the editor
            self.text_editor.setText(updated_content)
            self._set_modified()
            
            # Show results
            if "Added" in report:
                QMessageBox.information(
                    self, 
                    "Compatibility Fields Added", 
                    report + "\n\nYour CIF file is now more compatible with legacy validation tools."
                )
            else:
                QMessageBox.information(
                    self, 
                    "No Changes Needed", 
                    report
                )
                
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Compatibility Fields Error", 
                f"Failed to add compatibility fields:\n{str(e)}\n\n"
                "This might happen if the CIF file has parsing issues or if the dictionary "
                "manager is not properly initialized."
            )

    def load_custom_dictionary(self):
        """Load a custom CIF dictionary file."""
        success = self.settings_manager.load_custom_dictionary()
        if success:
            # Update local references to the new dictionary manager
            self.dict_manager = self.settings_manager.get_dictionary_manager()
            self.format_converter = self.settings_manager.get_format_converter()
            # Update validation controller with new dictionary components
            self.validation_controller.set_dictionary_components(self.dict_manager, self.format_converter)

    def add_additional_dictionary(self):
        """Add an additional CIF dictionary to extend field coverage."""
        success = self.settings_manager.add_additional_dictionary()
        if success:
            # Update local references to the enhanced dictionary manager
            self.dict_manager = self.settings_manager.get_dictionary_manager()
            self.format_converter = self.settings_manager.get_format_converter()
            # Update validation controller with enhanced dictionary components
            self.validation_controller.set_dictionary_components(self.dict_manager, self.format_converter)

    def show_dictionary_info(self):
        """Show detailed dictionary information dialog."""
        self.settings_manager.show_dictionary_info()
    
    def suggest_dictionaries(self):
        """Analyze current CIF content and suggest relevant dictionaries."""
        self.settings_manager.suggest_dictionaries()
    
    def prompt_for_dictionary_suggestions(self, cif_content: str):
        """Prompt user to get dictionary suggestions when opening a CIF file."""
        self.settings_manager.prompt_for_dictionary_suggestions(cif_content)
    
    
    def _ensure_field_rules_validated(self) -> bool:
        """
        Ensure field definitions are validated before starting checks.
        Returns True if validation passed or was skipped, False if cancelled.
        """
        # Only validate custom field definitions (built-in ones are assumed correct)
        if self.current_field_set != 'Custom' or not self.custom_field_rules_file:
            return True
        
        try:
            # Read the field definition file
            with open(self.custom_field_rules_file, 'r', encoding='utf-8') as f:
                field_rules_content = f.read()
            
            # Get CIF content for format analysis
            cif_content = self.text_editor.toPlainText() if hasattr(self, 'text_editor') else None
            
            # Validate the field definitions
            validation_result = self.field_rules_validator.validate_field_rules(
                field_rules_content, cif_content
            )
            
            if validation_result.has_issues:
                reply = QMessageBox.question(
                    self, "Field Definition Issues Found",
                    f"Issues found in field definitions that may affect checking:\n\n"
                    f"• {len(validation_result.issues)} issues detected\n"
                    f"• Target CIF format: {validation_result.cif_format_detected}\n\n"
                    "It's recommended to fix these issues before starting checks.\n"
                    "Would you like to review and fix them now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    # Show validation dialog
                    dialog = FieldRulesValidationDialog(
                        validation_result, field_rules_content, self.custom_field_rules_file,
                        self.field_rules_validator, self
                    )
                    
                    # Connect validation completion signal
                    dialog.validation_completed.connect(
                        lambda fixed_content, changes: self._on_validation_completed(
                            self.custom_field_rules_file, fixed_content, changes
                        )
                    )
                    
                    return dialog.exec() == QDialog.DialogCode.Accepted
                
                # User chose to proceed without fixing
                return True
            
            # No issues found
            return True
            
        except Exception as e:
            QMessageBox.critical(
                self, "Validation Error",
                f"Failed to validate field definitions:\n{str(e)}\n\n"
                "Proceeding without validation."
            )
            return True
    
    def validate_field_rules(self):
        """Manual field definition validation (Settings menu)."""
        if self.current_field_set == 'Custom' and self.custom_field_rules_file:
            # Validate the current custom field definition file
            self._validate_field_rules_file(self.custom_field_rules_file)
        else:
            # Ask user to select a file to validate
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Field Definition File to Validate", "",
                "Field Rules Files (*.cif_rules);;All Files (*)"
            )
            
            if file_path:
                self._validate_field_rules_file(file_path)
    
    def _validate_field_rules_file(self, file_path: str):
        """Validate a specific field definition file."""
        try:
            # Read the file content
            with open(file_path, 'r', encoding='utf-8') as f:
                field_rules_content = f.read()
            
            # Get CIF content for format analysis if available
            cif_content = self.text_editor.toPlainText() if hasattr(self, 'text_editor') else None
            
            # Validate the field definitions
            validation_result = self.field_rules_validator.validate_field_rules(
                field_rules_content, cif_content
            )
            
            # Show validation dialog
            dialog = FieldRulesValidationDialog(
                validation_result, field_rules_content, file_path,
                self.field_rules_validator, self
            )
            
            # Connect validation completion signal if this is the current custom file
            if file_path == self.custom_field_rules_file:
                dialog.validation_completed.connect(
                    lambda fixed_content, changes: self._on_validation_completed(
                        file_path, fixed_content, changes
                    )
                )
            
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(
                self, "Validation Error",
                f"Failed to validate field definition file:\n{str(e)}"
            )
