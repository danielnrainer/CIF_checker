"""Comprehensive Field Editing Dialog for CIF validation results"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, 
                            QWidget, QFrame, QPushButton, QSplitter, QGroupBox, 
                            QLineEdit, QTextEdit, QMessageBox)
from PyQt6.QtCore import Qt


class FieldEditingDialog(QDialog):
    """Advanced dialog for viewing validation results with integrated field editing"""
    
    def __init__(self, report, text_editor, parent=None):
        super().__init__(parent)
        self.report = report
        self.text_editor = text_editor
        self.parent_window = parent
        
        self.setWindowTitle("Detailed Results with Field Editing")
        self.setMinimumSize(1000, 700)
        
        # Store references to edit widgets
        self.field_edit_widgets = {}
        
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
        
        # Color code based on status
        status_colors = {
            'fail': "#ffe6e6",     # Light red
            'missing': "#fff3cd",   # Light yellow
            'warning': "#e6f3ff",   # Light blue
            'pass': "#e6ffe6"       # Light green
        }
        bg_color = status_colors.get(result['status'], "#f0f0f0")
        result_frame.setStyleSheet(f"padding: 8px; margin: 3px; background-color: {bg_color}; border-radius: 5px;")
        
        result_layout = QVBoxLayout()
        
        # Field name (clickable)
        field_button = QPushButton(f"📝 Edit: {result['field']}")
        field_button.setStyleSheet("text-align: left; font-weight: bold; background: transparent; border: none; color: #0066cc;")
        field_button.clicked.connect(lambda checked, field=result['field']: self.select_field_for_editing(field))
        result_layout.addWidget(field_button)
        
        message_label = QLabel(f"Issue: {result['message']}")
        message_label.setWordWrap(True)
        result_layout.addWidget(message_label)
        
        level_label = QLabel(f"Level: {result['level'].replace('_', ' ').title()}")
        level_label.setStyleSheet("font-style: italic; color: #666;")
        result_layout.addWidget(level_label)
        
        result_frame.setLayout(result_layout)
        return result_frame
    
    def create_edit_widget(self):
        """Create the field editing widget"""
        edit_widget = QWidget()
        edit_layout = QVBoxLayout()
        
        edit_label = QLabel("Field Editor")
        edit_label.setStyleSheet("font-weight: bold; font-size: 16px; margin-bottom: 10px;")
        edit_layout.addWidget(edit_label)
        
        # Field selection info
        self.selected_field_label = QLabel("Select a field from the left to edit")
        self.selected_field_label.setStyleSheet("color: #666; font-style: italic; margin-bottom: 10px;")
        edit_layout.addWidget(self.selected_field_label)
        
        # Field name input
        field_name_group = QGroupBox("Field Name")
        field_name_layout = QVBoxLayout()
        self.field_name_edit = QLineEdit()
        self.field_name_edit.setPlaceholderText("Enter CIF field name (e.g., _cell_length_a)")
        field_name_layout.addWidget(self.field_name_edit)
        field_name_group.setLayout(field_name_layout)
        edit_layout.addWidget(field_name_group)
        
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
        
        # Help text
        help_text = QLabel(
            "💡 Tips:\n"
            "• Click on field names in the left panel to load them for editing\n"
            "• Use 'Find in File' to locate existing fields\n"
            "• Use 'Add Field' to insert new fields\n"
            "• Use 'Update Field' to modify existing values"
        )
        help_text.setStyleSheet("background: #f0f8ff; padding: 10px; border-radius: 5px; margin-top: 10px;")
        help_text.setWordWrap(True)
        edit_layout.addWidget(help_text)
        
        edit_layout.addStretch()  # Push everything to top
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
        self.field_name_edit.setText(field_name)
        self.selected_field_label.setText(f"Editing: {field_name}")
        self.selected_field_label.setStyleSheet("color: #0066cc; font-weight: bold; margin-bottom: 10px;")
        
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
        
        self.field_value_edit.setText(field_value)
        
        # Enable buttons
        self.find_field_btn.setEnabled(True)
        self.add_field_btn.setEnabled(True) 
        self.update_field_btn.setEnabled(True)
    
    def find_field_in_file(self):
        """Find and highlight the selected field in the main text editor"""
        field_name = self.field_name_edit.text().strip()
        if not field_name:
            return
            
        # Search for the field in the text editor
        cursor = self.text_editor.document().find(field_name)
        if not cursor.isNull():
            self.text_editor.setTextCursor(cursor)
            self.text_editor.ensureCursorVisible()
            QMessageBox.information(self, "Field Found", f"Field '{field_name}' found and highlighted in the editor.")
        else:
            QMessageBox.information(self, "Field Not Found", f"Field '{field_name}' not found in the current file.")
    
    def add_field_to_file(self):
        """Add a new field to the CIF file"""
        field_name = self.field_name_edit.text().strip()
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
        
        QMessageBox.information(self, "Field Added", f"Field '{field_name}' has been added to the file.")
    
    def update_field_in_file(self):
        """Update an existing field in the CIF file"""
        field_name = self.field_name_edit.text().strip()
        field_value = self.field_value_edit.toPlainText().strip()
        
        if not field_name or not field_value:
            QMessageBox.warning(self, "Missing Information", "Please enter both field name and value.")
            return
            
        current_content = self.text_editor.toPlainText()
        lines = current_content.split('\n')
        updated = False
        
        for i, line in enumerate(lines):
            if line.strip().startswith(field_name + " ") or line.strip().startswith(field_name + "\t"):
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
                
            QMessageBox.information(self, "Field Updated", f"Field '{field_name}' has been updated.")
        else:
            # Field not found, offer to add it
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
