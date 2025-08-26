"""Comprehensive Field Editing Dialog for CIF validation results"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, 
                            QWidget, QFrame, QPushButton, QSplitter, QGroupBox, 
                            QLineEdit, QTextEdit, QMessageBox, QListWidget, QListWidgetItem)
from PyQt6.QtCore import Qt, QTime
import json
import os


class FieldEditingDialog(QDialog):
    """Advanced dialog for viewing validation results with integrated field editing"""
    
    def __init__(self, report, text_editor, parent=None):
        super().__init__(parent)
        self.report = report
        self.text_editor = text_editor
        self.parent_window = parent
        
        self.setWindowTitle("Detailed Results with Field Editing")
        self.setMinimumSize(1200, 800)  # Increased size for new features
        
        # Store references to edit widgets
        self.field_edit_widgets = {}
        
        # Track changes made in this session
        self.session_changes = []
        
        # Load field definitions for 3D ED validation
        self.field_definitions = self.load_3d_ed_field_definitions()
        
        # Extract missing/failed fields for the dropdown
        self.missing_failed_fields = self.extract_missing_failed_fields()
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout()
        
        # Create splitter for results and editing
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side: Results list
        results_widget = self.create_results_widget()
        
        # Right side: Field editing area
        edit_widget = self.create_edit_widget()
        
        # Add both sides to splitter
        splitter.addWidget(results_widget)
        splitter.addWidget(edit_widget)
        splitter.setSizes([400, 600])  # Give more space to editor
        
        layout.addWidget(splitter)
        
        # Bottom buttons
        bottom_layout = self.create_bottom_buttons()
        layout.addLayout(bottom_layout)
        
        self.setLayout(layout)
    
    def load_3d_ed_field_definitions(self):
        """Load the 3D ED field definitions for validation rules and suggestions"""
        try:
            field_def_path = os.path.join(os.path.dirname(__file__), '..', 'field_definitions_3d_ed.json')
            with open(field_def_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load 3D ED field definitions: {e}")
            return {}
    
    def extract_missing_failed_fields(self):
        """Extract all missing, failed, and required fields from the validation report and 3D ED definitions"""
        fields = set()
        current_format = self.detect_cif_format()
        
        # Add missing and failed fields from validation report
        for result in self.report.get("detailed_results", []):
            if result["status"] in ["missing", "fail"]:
                field_name = result["field"]
                # Convert to current format for consistency
                converted_field = self.convert_field_to_format(field_name, current_format)
                fields.add(converted_field)
        
        # Add all essential and recommended fields from 3D ED definitions
        if self.field_definitions:
            # Add essential fields
            for field in self.field_definitions.get("essential", []):
                converted_field = self.convert_field_to_format(field, current_format)
                fields.add(converted_field)
            
            # Add recommended fields
            for field in self.field_definitions.get("recommended", []):
                converted_field = self.convert_field_to_format(field, current_format)
                fields.add(converted_field)
            
            # Add method-specific required fields
            for method, method_data in self.field_definitions.get("method_specific", {}).items():
                for req_level, req_fields in method_data.items():
                    if req_level in ["essential", "required"]:
                        for field in req_fields:
                            converted_field = self.convert_field_to_format(field, current_format)
                            fields.add(converted_field)
        
        return sorted(list(fields))
    
    def get_field_info(self, field_name):
        """Get comprehensive information about a field from the 3D ED definitions"""
        field_info = {
            "default_value": "",
            "description": "",
            "validation_rules": "",
            "allowed_values": "",
            "format_requirements": "",
            "priority": "",
            "category": ""
        }
        
        # Check in different sections of the field definitions
        if field_name in self.field_definitions.get("field_validation", {}):
            validation = self.field_definitions["field_validation"][field_name]
            field_info["default_value"] = validation.get("default", validation.get("common_values", [""])[0] if validation.get("common_values") else "")
            field_info["description"] = validation.get("note", "")
            field_info["priority"] = validation.get("priority", "")
            
            # Format validation rules
            rules = []
            if validation.get("type"):
                rules.append(f"Type: {validation['type']}")
            if validation.get("units"):
                rules.append(f"Units: {validation['units']}")
            if validation.get("typical_range"):
                rules.append(f"Range: {validation['typical_range']}")
            if validation.get("allowed_values"):
                field_info["allowed_values"] = ", ".join(validation["allowed_values"])
                rules.append(f"Allowed values: {field_info['allowed_values']}")
            if validation.get("required_value"):
                rules.append(f"Required value: {validation['required_value']}")
            field_info["validation_rules"] = "\n".join(rules)
            
            field_info["format_requirements"] = validation.get("format_requirements", "")
        
        # Check categories
        for category, fields in [
            ("essential", self.field_definitions.get("essential", [])),
            ("recommended", self.field_definitions.get("recommended", [])),
        ]:
            if field_name in fields:
                field_info["category"] = category
                break
        
        # Check method-specific fields
        for method, method_data in self.field_definitions.get("method_specific", {}).items():
            for req_type, req_fields in method_data.items():
                if field_name in req_fields:
                    field_info["category"] = f"{method} - {req_type}"
                    break
        
        return field_info
    
    def create_results_widget(self):
        """Create the validation results display widget"""
        results_widget = QWidget()
        results_layout = QVBoxLayout()
        
        results_label = QLabel("Validation Results")
        results_label.setStyleSheet("font-weight: bold; font-size: 16px; margin-bottom: 10px;")
        results_layout.addWidget(results_label)
        
        # Create scroll area for detailed results
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        
        # Group results by status
        result_groups = {
            "❌ Failed": [r for r in self.report["detailed_results"] if r["status"] == "fail"], 
            "📝 Missing": [r for r in self.report["detailed_results"] if r["status"] == "missing"],
            "⚠️ Warnings": [r for r in self.report["detailed_results"] if r["status"] == "warning"],
            "✅ Passed": [r for r in self.report["detailed_results"] if r["status"] == "pass"]
        }
        
        for group_name, results in result_groups.items():
            if not results:
                continue
                
            # Group header
            header = QLabel(f"{group_name} ({len(results)})")
            header.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px;")
            scroll_layout.addWidget(header)
            
            # Results in this group
            for result in results:
                result_frame = self.create_result_frame(result)
                scroll_layout.addWidget(result_frame)
        
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        
        results_layout.addWidget(scroll_area)
        results_widget.setLayout(results_layout)
        
        return results_widget
    
    def create_result_frame(self, result):
        """Create a frame for displaying a single validation result"""
        result_frame = QFrame()
        result_frame.setFrameStyle(QFrame.Shape.Box)
        result_frame.setCursor(Qt.CursorShape.PointingHandCursor)  # Show it's clickable
        
        # Color code based on status
        status_colors = {
            'fail': "#ffe6e6",     # Light red
            'missing': "#fff3cd",   # Light yellow
            'warning': "#e6f3ff",   # Light blue
            'pass': "#e6ffe6"       # Light green
        }
        bg_color = status_colors.get(result['status'], "#f0f0f0")
        result_frame.setStyleSheet(
            f"QFrame {{ "
            f"padding: 10px; margin: 5px; "
            f"background-color: {bg_color}; "
            f"border-radius: 5px; "
            f"border: 1px solid #ccc; "
            f"}} "
            f"QFrame:hover {{ "
            f"border: 2px solid #0066cc; "
            f"}}"
        )
        
        # Make the entire frame clickable
        def on_frame_click(event):
            self.select_field_for_editing(result['field'])
        
        result_frame.mousePressEvent = on_frame_click
        
        result_layout = QVBoxLayout()
        result_layout.setSpacing(5)  # Good spacing between elements
        result_layout.setContentsMargins(5, 5, 5, 5)  # Comfortable margins
        
        # Field name - larger and more prominent - NO HEIGHT CONSTRAINT
        field_label = QLabel(f"📝 {result['field']}")
        field_label.setStyleSheet(
            "font-weight: bold; "
            "color: #0066cc; "
            "font-size: 14px; "
        )
        result_layout.addWidget(field_label)
        
        # Message on its own line - NO HEIGHT CONSTRAINT
        message_label = QLabel(result['message'])
        message_label.setWordWrap(True)
        message_label.setStyleSheet(
            "font-size: 12px; "
            "color: #333; "
        )
        result_layout.addWidget(message_label)
        
        # Level on separate line - NO HEIGHT CONSTRAINT
        level_label = QLabel(f"Level: {result['level'].replace('_', ' ').title()}")
        level_label.setStyleSheet(
            "font-size: 11px; "
            "color: #666; "
            "font-style: italic;"
        )
        result_layout.addWidget(level_label)
        
        result_frame.setLayout(result_layout)
        return result_frame
    
    def create_edit_widget(self):
        """Create the enhanced field editing widget with all requested features"""
        edit_widget = QWidget()
        edit_layout = QVBoxLayout()
        
        edit_label = QLabel("Field Editor")
        edit_label.setStyleSheet("font-weight: bold; font-size: 16px; margin-bottom: 10px;")
        edit_layout.addWidget(edit_label)
        
        # Field selection info
        self.selected_field_label = QLabel("Select a field from the dropdown to edit")
        self.selected_field_label.setStyleSheet("color: #666; font-style: italic; margin-bottom: 10px;")
        edit_layout.addWidget(self.selected_field_label)
        
        # 1. Field name list (instead of text field)
        field_name_group = QGroupBox("Field Name")
        field_name_layout = QVBoxLayout()
        
        self.field_name_list = QListWidget()
        self.field_name_list.addItems(self.missing_failed_fields)
        self.field_name_list.currentItemChanged.connect(self.on_field_selection_changed)
        self.field_name_list.setMaximumHeight(150)
        field_name_layout.addWidget(self.field_name_list)
        
        # Add manual field entry as fallback
        manual_field_layout = QHBoxLayout()
        manual_field_layout.addWidget(QLabel("Manual entry:"))
        self.manual_field_edit = QLineEdit()
        self.manual_field_edit.setPlaceholderText("Enter custom field name")
        self.manual_field_edit.textChanged.connect(self.on_manual_field_changed)
        manual_field_layout.addWidget(self.manual_field_edit)
        field_name_layout.addLayout(manual_field_layout)
        
        field_name_group.setLayout(field_name_layout)
        edit_layout.addWidget(field_name_group)
        
        # 3. Field information display (defaults/suggestions)
        field_info_group = QGroupBox("Field Information & Suggestions")
        field_info_layout = QVBoxLayout()
        
        self.field_category_label = QLabel("")
        self.field_category_label.setStyleSheet("font-weight: bold; color: #0066cc;")
        field_info_layout.addWidget(self.field_category_label)
        
        self.field_default_label = QLabel("")
        self.field_default_label.setStyleSheet("background: #e6f3ff; padding: 5px; border-radius: 3px; margin: 2px;")
        field_info_layout.addWidget(self.field_default_label)
        
        self.field_description_label = QLabel("")
        self.field_description_label.setWordWrap(True)
        self.field_description_label.setStyleSheet("background: #f0f8ff; padding: 5px; border-radius: 3px; margin: 2px;")
        field_info_layout.addWidget(self.field_description_label)
        
        # 4. Validation rules and restrictions
        self.field_validation_label = QLabel("")
        self.field_validation_label.setWordWrap(True)
        self.field_validation_label.setStyleSheet("background: #fff3cd; padding: 5px; border-radius: 3px; margin: 2px; font-family: monospace;")
        field_info_layout.addWidget(self.field_validation_label)
        
        field_info_group.setLayout(field_info_layout)
        edit_layout.addWidget(field_info_group)
        
        # Field value input
        field_value_group = QGroupBox("Field Value")
        field_value_layout = QVBoxLayout()
        self.field_value_edit = QTextEdit()
        self.field_value_edit.setMaximumHeight(100)
        self.field_value_edit.setPlaceholderText("Enter the field value")
        field_value_layout.addWidget(self.field_value_edit)
        field_value_group.setLayout(field_value_layout)
        edit_layout.addWidget(field_value_group)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.find_field_btn = QPushButton("🔍 Find in File")
        self.find_field_btn.clicked.connect(self.find_field_in_file)
        self.find_field_btn.setEnabled(False)
        button_layout.addWidget(self.find_field_btn)
        
        self.add_field_btn = QPushButton("➕ Add Field")
        self.add_field_btn.clicked.connect(self.add_field_to_file)
        self.add_field_btn.setEnabled(False)
        button_layout.addWidget(self.add_field_btn)
        
        self.update_field_btn = QPushButton("✏️ Update Field")
        self.update_field_btn.clicked.connect(self.update_field_in_file)
        self.update_field_btn.setEnabled(False)
        button_layout.addWidget(self.update_field_btn)
        
        edit_layout.addLayout(button_layout)
        
        # Help text (Tips)
        help_text = QLabel(
            "💡 Tips:\n"
            "• Select a field from the list above to see suggestions and validation rules\n"
            "• Check the Field Information for default values and restrictions\n"
            "• Use 'Find in File' to locate existing fields\n"
            "• Use 'Add Field' to insert new fields\n"
            "• Use 'Update Field' to modify existing values"
        )
        help_text.setStyleSheet("background: #f0f8ff; padding: 10px; border-radius: 5px; margin-top: 10px;")
        help_text.setWordWrap(True)
        edit_layout.addWidget(help_text)
        
        # 2. Session changes log
        changes_group = QGroupBox("Session Changes")
        changes_layout = QVBoxLayout()
        
        self.changes_list = QTextEdit()
        self.changes_list.setMaximumHeight(120)
        self.changes_list.setPlaceholderText("Changes made in this session will appear here...")
        self.changes_list.setReadOnly(True)
        self.changes_list.setStyleSheet("background: #f8f8f8; font-family: monospace; font-size: 12px;")
        changes_layout.addWidget(self.changes_list)
        
        clear_changes_btn = QPushButton("Clear Changes Log")
        clear_changes_btn.clicked.connect(self.clear_changes_log)
        changes_layout.addWidget(clear_changes_btn)
        
        changes_group.setLayout(changes_layout)
        edit_layout.addWidget(changes_group)
        
        edit_widget.setLayout(edit_layout)
        return edit_widget
    
    def create_bottom_buttons(self):
        """Create the bottom button layout"""
        bottom_layout = QHBoxLayout()
        
        apply_all_btn = QPushButton("🚀 Apply All Recommendations")
        apply_all_btn.clicked.connect(self.apply_all_recommendations)
        bottom_layout.addWidget(apply_all_btn)
        
        bottom_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        bottom_layout.addWidget(close_button)
        
        return bottom_layout
    
    def select_field_for_editing(self, field_name):
        """Load a field for editing in the field editor"""
        # Update the manual field edit and select the corresponding item in the list
        self.manual_field_edit.setText(field_name)
        
        # Find and select the item in the dropdown list
        for i in range(self.field_name_list.count()):
            item = self.field_name_list.item(i)
            if item.text() == field_name:
                self.field_name_list.setCurrentItem(item)
                break
        
        # Update field information
        self.update_field_information(field_name)
        
        # Enable editing buttons
        self.enable_action_buttons()
        
        # Try to find current value in file
        current_content = self.text_editor.toPlainText()
        lines = current_content.split('\n')
        
        field_value = ""
        for line in lines:
            if line.strip().startswith(field_name + " ") or line.strip().startswith(field_name + "\t"):
                # Extract value part
                parts = line.split(None, 1)  # Split on first whitespace
                if len(parts) > 1:
                    field_value = parts[1]
                break
            elif line.strip() == field_name:
                # Field exists but no value on same line - might be multiline
                field_value = "(multiline value - check file)"
                break
        
        # Set the field value in the text edit widget
        self.field_value_edit.setPlainText(field_value)
        
        # Don't log field selections - only log actual CIF file changes
    
    def find_field_in_file(self):
        """Find and highlight the selected field in the main text editor"""
        field_name = self.get_current_field_name()
        if not field_name:
            QMessageBox.warning(self, "No Field Selected", "Please select a field from the dropdown or enter one manually.")
            return
            
        # Search for the field in the text editor
        cursor = self.text_editor.document().find(field_name)
        if not cursor.isNull():
            self.text_editor.setTextCursor(cursor)
            self.text_editor.ensureCursorVisible()
            self.log_change("FOUND", field_name, "Located in editor")
            QMessageBox.information(self, "Field Found", f"Field '{field_name}' found and highlighted in the editor.")
        else:
            self.log_change("NOT FOUND", field_name, "Field not present in file")
            QMessageBox.information(self, "Field Not Found", f"Field '{field_name}' not found in the current file.")
    
    def add_field_to_file(self):
        """Add a new field to the CIF file"""
        field_name = self.get_current_field_name()
        field_value = self.field_value_edit.toPlainText().strip()
        
        if not field_name or not field_value:
            QMessageBox.warning(self, "Missing Information", "Please enter both field name and value.")
            return
        # Insert the field at the end of the data block
        current_content = self.text_editor.toPlainText()
        
        # Find a good insertion point (after data_ line, before any loops)
        lines = current_content.split('\n')
        insert_index = len(lines)
        
        for i, line in enumerate(lines):
            if line.strip().startswith('data_'):
                # Look for the next good spot (after existing individual fields)
                for j in range(i + 1, len(lines)):
                    if lines[j].strip().startswith('loop_') or lines[j].strip().startswith('#'):
                        insert_index = j
                        break
                break
        
        # Create the new field line
        new_line = f"{field_name}    {field_value}"
        
        # Insert the line
        lines.insert(insert_index, new_line)
        
        # Update the editor
        self.text_editor.setText('\n'.join(lines))
        
        # Mark as modified if parent window has this attribute
        if hasattr(self.parent_window, 'modified'):
            self.parent_window.modified = True
        
        # Log the change
        self.log_change("ADDED", field_name, f"Value: {field_value}")
        
        QMessageBox.information(self, "Field Added", f"Field '{field_name}' has been added to the file.")
    
    def update_field_in_file(self):
        """Update an existing field in the CIF file"""
        field_name = self.get_current_field_name()
        field_value = self.field_value_edit.toPlainText().strip()
        
        if not field_name or not field_value:
            QMessageBox.warning(self, "Missing Information", "Please enter both field name and value.")
            return
            
        current_content = self.text_editor.toPlainText()
        lines = current_content.split('\n')
        updated = False
        old_value = ""
        
        for i, line in enumerate(lines):
            if line.strip().startswith(field_name + " ") or line.strip().startswith(field_name + "\t"):
                # Extract old value for logging
                parts = line.split()
                if len(parts) > 1:
                    old_value = " ".join(parts[1:])
                # Update the line
                lines[i] = f"{field_name}    {field_value}"
                updated = True
                break
            elif line.strip() == field_name:
                # Field exists but value might be on next line or multiline
                lines[i] = f"{field_name}    {field_value}"
                updated = True
                break
        
        if updated:
            self.text_editor.setText('\n'.join(lines))
            
            # Mark as modified if parent window has this attribute
            if hasattr(self.parent_window, 'modified'):
                self.parent_window.modified = True
            
            # Log the change
            self.log_change("UPDATED", field_name, f"'{old_value}' → '{field_value}'")
                
            QMessageBox.information(self, "Field Updated", f"Field '{field_name}' has been updated.")
        else:
            # Field not found, offer to add it
            self.log_change("NOT FOUND", field_name, "Field not present for update")
            reply = QMessageBox.question(self, "Field Not Found", 
                                       f"Field '{field_name}' not found. Would you like to add it as a new field?")
            if reply == QMessageBox.StandardButton.Yes:
                self.add_field_to_file()
    
    def apply_all_recommendations(self):
        """Apply all possible automatic recommendations"""
        applied_count = 0
        
        # Get recommendations that can be automatically applied
        auto_applicable = []
        
        for result in self.report["detailed_results"]:
            if result["status"] in ["missing", "fail"]:
                # Check if this is a field that commonly has default values
                field = result["field"]
                if any(keyword in field.lower() for keyword in ["temperature", "pressure", "wavelength", "crystal_system"]):
                    auto_applicable.append(result)
        
        if not auto_applicable:
            QMessageBox.information(self, "No Auto-Fixes", 
                                  "No automatically applicable recommendations found. "
                                  "Please use the field editor for manual corrections.")
            return
        
        # Show preview of what will be applied
        preview_text = "The following fields will be added/updated:\n\n"
        for result in auto_applicable:
            suggested_value = self.get_suggested_default_value(result["field"])
            preview_text += f"• {result['field']} = {suggested_value}\n"
        
        reply = QMessageBox.question(self, "Apply Recommendations", 
                                   preview_text + "\nDo you want to proceed?")
        
        if reply == QMessageBox.StandardButton.Yes:
            current_content = self.text_editor.toPlainText()
            lines = current_content.split('\n')
            
            # Find insertion point
            insert_index = len(lines)
            for i, line in enumerate(lines):
                if line.strip().startswith('data_'):
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip().startswith('loop_') or lines[j].strip().startswith('#'):
                            insert_index = j
                            break
                    break
            
            # Add the fields
            for result in auto_applicable:
                field_name = result["field"]
                suggested_value = self.get_suggested_default_value(field_name)
                new_line = f"{field_name}    {suggested_value}"
                lines.insert(insert_index, new_line)
                insert_index += 1
                applied_count += 1
            
            self.text_editor.setText('\n'.join(lines))
            
            # Mark as modified if parent window has this attribute
            if hasattr(self.parent_window, 'modified'):
                self.parent_window.modified = True
            
            QMessageBox.information(self, "Recommendations Applied", 
                                  f"Successfully applied {applied_count} recommendations!")
    
    def get_suggested_default_value(self, field_name):
        """Get a suggested default value for common fields"""
        defaults = {
            "_diffrn_ambient_temperature": "293",
            "_diffrn_ambient_pressure": "101.3",
            "_diffrn_radiation_wavelength": "0.71073",
            "_crystal_system": "unknown",
            "_space_group_crystal_system": "unknown",
            "_cell_measurement_temperature": "293",
            "_computing_structure_solution": "unknown",
            "_computing_structure_refinement": "unknown",
            "_audit_creation_method": "manual",
        }
        
        # Check for pattern matches
        field_lower = field_name.lower()
        if "temperature" in field_lower:
            return "293"
        elif "pressure" in field_lower:
            return "101.3"
        elif "wavelength" in field_lower:
            return "0.71073"
        elif "system" in field_lower:
            return "unknown"
        
        return defaults.get(field_name, "unknown")
    
    def on_field_selection_changed(self, current, previous):
        """Handle field selection change in the dropdown list"""
        if current:
            field_name = current.text()
            self.manual_field_edit.setText(field_name)
            self.field_value_edit.clear()  # Clear field value when field changes
            self.update_field_information(field_name)
            self.enable_action_buttons()
    
    def on_manual_field_changed(self, text):
        """Handle manual field entry"""
        if text.strip():
            # Clear list selection if manual entry is made
            self.field_name_list.clearSelection()
            self.field_value_edit.clear()  # Clear field value when field changes
            self.update_field_information(text.strip())
            self.enable_action_buttons()
        else:
            self.disable_action_buttons()
    
    def update_field_information(self, field_name):
        """Update the field information display with defaults and validation rules"""
        # Detect current CIF format and convert field name if needed
        current_format = self.detect_cif_format()
        converted_field_name = self.convert_field_to_format(field_name, current_format)
        
        # Update the manual field edit to show the format-converted name
        if converted_field_name != field_name:
            self.manual_field_edit.setText(converted_field_name)
            field_name = converted_field_name
        
        field_info = self.get_field_info(field_name)
        
        if not field_info:
            self.field_category_label.setText(f"Format: {current_format}")
            self.field_default_label.setText("No information available for this field")
            self.field_description_label.setText("")
            self.field_validation_label.setText("")
            return
        
        # Update category with format information
        category = field_info.get('category', 'Unknown')
        importance = field_info.get('importance', 'optional')
        self.field_category_label.setText(f"Category: {category} ({importance.title()}) | Format: {current_format}")
        
        # Update default value
        default_value = field_info.get('default_value', '')
        if default_value:
            # Convert to string to avoid TypeError with setPlainText
            default_value_str = str(default_value)
            self.field_default_label.setText(f"Suggested default: {default_value_str}")
            # Pre-fill the value editor only if it's empty
            if not self.field_value_edit.toPlainText().strip():
                self.field_value_edit.setPlainText(default_value_str)
        else:
            self.field_default_label.setText("No default value suggested")
        
        # Update description
        description = field_info.get('description', '')
        if description:
            self.field_description_label.setText(f"Description: {description}")
        else:
            self.field_description_label.setText("")
        
        # Update validation rules
        validation_rules = []
        if 'required_format' in field_info:
            validation_rules.append(f"Format: {field_info['required_format']}")
        if 'allowed_values' in field_info:
            values = field_info['allowed_values']
            if isinstance(values, list) and len(values) <= 5:
                validation_rules.append(f"Allowed values: {', '.join(map(str, values))}")
            elif isinstance(values, list):
                validation_rules.append(f"Allowed values: {len(values)} options (see documentation)")
        if 'validation_pattern' in field_info:
            validation_rules.append(f"Pattern: {field_info['validation_pattern']}")
        if 'constraints' in field_info:
            constraints = field_info['constraints']
            if isinstance(constraints, list):
                validation_rules.extend([f"• {c}" for c in constraints])
        
        if validation_rules:
            self.field_validation_label.setText("Validation Rules:\n" + "\n".join(validation_rules))
        else:
            self.field_validation_label.setText("No specific validation rules")
    
    def enable_action_buttons(self):
        """Enable the action buttons when a field is selected"""
        field_name = self.get_current_field_name()
        if field_name:
            self.find_field_btn.setEnabled(True)
            self.add_field_btn.setEnabled(True)
            self.update_field_btn.setEnabled(True)
            self.selected_field_label.setText(f"Selected field: {field_name}")
    
    def disable_action_buttons(self):
        """Disable action buttons when no field is selected"""
        self.find_field_btn.setEnabled(False)
        self.add_field_btn.setEnabled(False)
        self.update_field_btn.setEnabled(False)
        self.selected_field_label.setText("Select a field from the dropdown to edit")
    
    def get_current_field_name(self):
        """Get the currently selected/entered field name"""
        # Check manual entry first
        manual_text = self.manual_field_edit.text().strip()
        if manual_text:
            return manual_text
        
        # Check list selection
        current_item = self.field_name_list.currentItem()
        if current_item:
            return current_item.text()
        
        return ""
    
    def log_change(self, action, field_name, details=""):
        """Log a change to the session changes display"""
        timestamp = QTime.currentTime().toString("hh:mm:ss")
        change_text = f"[{timestamp}] {action}: {field_name}"
        if details:
            change_text += f" - {details}"
        
        current_text = self.changes_list.toPlainText()
        if current_text:
            new_text = current_text + "\n" + change_text
        else:
            new_text = change_text
        
        self.changes_list.setPlainText(new_text)
        
        # Scroll to bottom
        cursor = self.changes_list.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.changes_list.setTextCursor(cursor)
    
    def clear_changes_log(self):
        """Clear the session changes log"""
        self.changes_list.clear()
        self.log_change("SESSION", "Changes log cleared", "")
    
    def detect_cif_format(self):
        """Detect whether the current file uses CIF1 or CIF2 format"""
        content = self.text_editor.toPlainText()
        lines = content.split('\n')
        
        cif1_indicators = 0
        cif2_indicators = 0
        
        for line in lines:
            line_stripped = line.strip()
            if line_stripped.startswith('_'):
                # Check for CIF1 style (underscores)
                if '.' in line_stripped and line_stripped.count('_') >= 2:
                    # Pattern like _category.field
                    if line_stripped.count('.') == 1 and '_' in line_stripped.split('.')[0]:
                        cif2_indicators += 1
                    else:
                        cif1_indicators += 1
                elif line_stripped.count('_') >= 2:
                    # Pattern like _category_field
                    cif1_indicators += 1
        
        # Default to CIF1 if unclear
        return "CIF2" if cif2_indicators > cif1_indicators else "CIF1"
    
    def convert_field_to_format(self, field_name, target_format):
        """Convert a field name to the specified CIF format"""
        if not field_name.startswith('_'):
            return field_name
        
        # Remove leading underscore for processing
        field_without_underscore = field_name[1:]
        
        if target_format == "CIF2":
            # Convert CIF1 to CIF2: _category_field -> _category.field
            if '.' not in field_without_underscore and '_' in field_without_underscore:
                parts = field_without_underscore.split('_', 1)
                if len(parts) == 2:
                    return f"_{parts[0]}.{parts[1]}"
        else:  # CIF1
            # Convert CIF2 to CIF1: _category.field -> _category_field
            if '.' in field_without_underscore:
                field_without_underscore = field_without_underscore.replace('.', '_')
        
        return f"_{field_without_underscore}"
