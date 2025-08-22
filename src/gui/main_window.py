from PyQt6.QtWidgets import (QMainWindow, QWidget, QTextEdit, 
                           QPushButton, QVBoxLayout, QHBoxLayout, QMenu,
                           QFileDialog, QMessageBox, QLineEdit, QCheckBox, 
                           QDialog, QLabel, QFontDialog, QScrollArea, QFrame,
                           QComboBox, QSplitter, QTextEdit, QGridLayout,
                           QGroupBox, QPushButton)
from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtGui import (QTextCharFormat, QSyntaxHighlighter, QColor, QFont, 
                        QFontMetrics, QTextCursor, QTextDocument)
import os
import json
from utils.cif_analyzer import CIFAnalyzer, CIFVersion, CrystallographyMethod
from utils.cif_dictionary_manager import CIFDictionaryManager
from utils.CIF_parser import CIFParser
from utils.ed_validator import ED3DValidator
from utils.cif_converter import CIFConverter


# Dialog result codes for consistency
RESULT_ABORT = 2
RESULT_STOP_SAVE = 3

class CIFSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        
        # Field names (starting with _) - only at the beginning of lines
        self.field_format = QTextCharFormat()
        self.field_format.setForeground(QColor("#0000FF"))  # Blue
        self.highlighting_rules.append((
            QRegularExpression(r'^\s*_[^\s]+'),
            self.field_format
        ))
        
        # Values in quotes
        self.value_format = QTextCharFormat()
        self.value_format.setForeground(QColor("#008000"))  # Green
        self.highlighting_rules.append((
            QRegularExpression(r"'[^']*'"),
            self.value_format
        ))
        
        # Multi-line values format
        self.multiline_format = QTextCharFormat()
        self.multiline_format.setForeground(QColor("#800080"))  # Purple
        
        # State for tracking multiline blocks
        self.in_multiline = False

    def highlightBlock(self, text):
        # Check if previous block was in a multiline state
        if self.previousBlockState() == 1:
            self.in_multiline = True
        else:
            self.in_multiline = False
            
        # Apply standard rules first
        for pattern, format in self.highlighting_rules:
            matches = pattern.globalMatch(text)
            while matches.hasNext():
                match = matches.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)
        
        # Handle multiline values
        if text.startswith(';'):
            self.setFormat(0, len(text), self.multiline_format)
            self.in_multiline = not self.in_multiline
        elif self.in_multiline:
            self.setFormat(0, len(text), self.multiline_format)
        
        # Set state for next block
        self.setCurrentBlockState(1 if self.in_multiline else 0)

class MultilineInputDialog(QDialog):
    # Define result codes as class attributes
    RESULT_ABORT = 2  # User wants to abort all changes
    RESULT_STOP_SAVE = 3  # User wants to stop but save changes

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Text")
        layout = QVBoxLayout(self)
        
        self.textEdit = QTextEdit()
        self.textEdit.setText(text)
        layout.addWidget(self.textEdit)
        
        buttonBox = QHBoxLayout()
        
        # Save (OK) button
        saveButton = QPushButton("OK")
        saveButton.clicked.connect(self.accept)
        
        # Cancel button
        cancelButton = QPushButton("Cancel Current")
        cancelButton.clicked.connect(self.reject)
        
        # Abort button
        abortButton = QPushButton("Abort All Changes")
        abortButton.clicked.connect(self.abort_changes)
        
        # Stop & Save button
        stopSaveButton = QPushButton("Stop && Save")
        stopSaveButton.clicked.connect(self.stop_and_save)
        
        buttonBox.addWidget(saveButton)
        buttonBox.addWidget(cancelButton)
        buttonBox.addWidget(abortButton)
        buttonBox.addWidget(stopSaveButton)
        layout.addLayout(buttonBox)
        
        self.setMinimumWidth(800)  # Increased width to accommodate buttons
        self.setMinimumHeight(400)

    def getText(self):
        return self.textEdit.toPlainText()
        
    def abort_changes(self):
        self.done(self.RESULT_ABORT)
        
    def stop_and_save(self):
        self.done(self.RESULT_STOP_SAVE)

class CIFInputDialog(QDialog):
    # Define result codes as class attributes
    RESULT_ABORT = 2  # User wants to abort all changes
    RESULT_STOP_SAVE = 3  # User wants to stop but save changes

    def __init__(self, title, text, value="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        
        layout = QVBoxLayout(self)
        
        # Add text label
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)
        
        # Add input field
        self.inputField = QLineEdit(self)
        self.inputField.setText(value)
        layout.addWidget(self.inputField)
        
        # Add buttons
        buttonBox = QHBoxLayout()
        
        okButton = QPushButton("OK")
        okButton.clicked.connect(self.accept)
        
        cancelButton = QPushButton("Cancel Current")
        cancelButton.clicked.connect(self.reject)
        
        abortButton = QPushButton("Abort All Changes")
        abortButton.clicked.connect(self.abort_changes)
        
        stopSaveButton = QPushButton("Stop && Save")
        stopSaveButton.clicked.connect(self.stop_and_save)
        
        buttonBox.addWidget(okButton)
        buttonBox.addWidget(cancelButton)
        buttonBox.addWidget(abortButton)
        buttonBox.addWidget(stopSaveButton)
        
        layout.addLayout(buttonBox)
        self.setMinimumWidth(600)

    def getValue(self):
        return self.inputField.text()
        
    def abort_changes(self):
        self.done(self.RESULT_ABORT)
        
    def stop_and_save(self):
        self.done(self.RESULT_STOP_SAVE)

    @staticmethod
    def getText(parent, title, text, value=""):
        dialog = CIFInputDialog(title, text, value, parent)
        result = dialog.exec()
        
        if result == QDialog.DialogCode.Accepted:
            return dialog.getValue(), QDialog.DialogCode.Accepted
        elif result == CIFInputDialog.RESULT_ABORT:
            return None, CIFInputDialog.RESULT_ABORT
        elif result == CIFInputDialog.RESULT_STOP_SAVE:
            return dialog.getValue(), CIFInputDialog.RESULT_STOP_SAVE
        else:
            return None, QDialog.DialogCode.Rejected

class CIFEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.modified = False
        self.recent_files = []
        self.max_recent_files = 5
        
        # Initialize modern CIF analysis system
        self.dict_manager = CIFDictionaryManager()
        self.cif_analyzer = CIFAnalyzer(self.dict_manager)
        self.cif_parser = CIFParser()
        
        # Initialize specialized 3D ED validator
        self.ed3d_validator = ED3DValidator()
        
        # Initialize CIF format converter with dictionary manager
        self.cif_converter = CIFConverter(self.dict_manager)
        
        # Current analysis results
        self.current_analysis = None
        
        # Load settings
        self.load_settings()
        
        self.init_ui()
        self.select_initial_file()

    def load_settings(self):
        """Load editor settings from JSON file"""
        self.settings = {
            'font_family': 'Courier New',
            'font_size': 10,
            'line_numbers_enabled': True,
            'syntax_highlighting_enabled': True,
            'show_ruler': True  # New setting for the ruler
        }
        
        settings_path = os.path.join(os.path.dirname(__file__), 'editor_settings.json')
        try:
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    saved_settings = json.load(f)
                    self.settings.update(saved_settings)
        except Exception as e:
            print(f"Error loading settings: {e}")

    def save_settings(self):
        """Save editor settings to JSON file"""
        settings_path = os.path.join(os.path.dirname(__file__), 'editor_settings.json')
        try:
            with open(settings_path, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def apply_settings(self):
        """Apply current settings to the editor"""
        # Create font from settings
        font = QFont(self.settings['font_family'], self.settings['font_size'])
        
        # Create a QFontMetrics object to measure character width
        metrics = QFontMetrics(font)
        char_width = metrics.horizontalAdvance('x')  # Width of a typical character
          # Position the ruler at 80 characters
        ruler_x = int(char_width * 80 + self.text_editor.document().documentMargin())
        self.ruler.setGeometry(ruler_x, 0, 1, self.text_editor.height())
        self.ruler.setVisible(self.settings['show_ruler'])
        
        # Apply font to editor and line numbers
        self.text_editor.setFont(font)
        self.line_numbers.setFont(font)
        
        # Update other settings
        self.line_numbers.setVisible(self.settings['line_numbers_enabled'])
        if hasattr(self, 'highlighter'):
            self.highlighter.setDocument(
                self.text_editor.document() if self.settings['syntax_highlighting_enabled'] 
                else None
            )

    def change_font(self):
        """Open font dialog to change editor font"""
        current_font = self.text_editor.font()
        font, ok = QFontDialog.getFont(current_font, self,
                                     "Select Editor Font",
                                     QFontDialog.FontDialogOption.MonospacedFonts)
        if ok:
            self.settings['font_family'] = font.family()
            self.settings['font_size'] = font.pointSize()
            self.apply_settings()
            self.save_settings()
            
    def toggle_line_numbers(self):
        """Toggle line numbers visibility"""
        self.settings['line_numbers_enabled'] = not self.settings['line_numbers_enabled']
        self.apply_settings()
        self.save_settings()
        
    def toggle_syntax_highlighting(self):
        """Toggle syntax highlighting"""
        self.settings['syntax_highlighting_enabled'] = not self.settings['syntax_highlighting_enabled']
        self.apply_settings()
        self.save_settings()
        
    def toggle_ruler(self):
        """Toggle ruler visibility"""
        self.settings['show_ruler'] = not self.settings['show_ruler']
        self.ruler.setVisible(self.settings['show_ruler'])
        self.save_settings()

    def update_analysis_display(self):
        """Update the analysis results display"""
        if not self.current_analysis:
            return
        
        analysis = self.current_analysis
        
        # Create analysis summary text
        summary_parts = []
        summary_parts.append(f"📁 File: {os.path.basename(analysis.file_path)}")
        
        # Show current vs target version
        target_version = self.version_selector.currentData()
        if analysis.cif_version == target_version:
            summary_parts.append(f"📝 CIF Version: {analysis.cif_version.value} ✅")
        else:
            summary_parts.append(f"📝 Current: {analysis.cif_version.value} | Target: {target_version.value} ⚠️")
        
        summary_parts.append(f"📊 Fields Found: {analysis.field_count}")
        
        # Format detected methods
        methods_str = ", ".join([m.value.replace('_', ' ').title() for m in analysis.detected_methods])
        summary_parts.append(f"🔬 Methods: {methods_str}")
        
        # Add confidence scores
        if analysis.confidence_scores:
            high_confidence = [f"{k}: {v:.0%}" for k, v in analysis.confidence_scores.items() if v > 0.8]
            if high_confidence:
                summary_parts.append(f"✅ High Confidence: {', '.join(high_confidence)}")
        
        # Add recommendations
        if analysis.recommendations:
            summary_parts.append(f"\n💡 Recommendations:")
            for rec in analysis.recommendations[:3]:  # Show first 3
                summary_parts.append(f"  • {rec}")
        
        analysis_text = "\n".join(summary_parts)
        
        # Update status bar with analysis summary
        target_version = self.version_selector.currentData()
        version_match = "✅" if analysis.cif_version == target_version else "⚠️"
        self.status_bar.showMessage(f"Current: {analysis.cif_version.value} | Target: {target_version.value} {version_match} | {len(analysis.detected_methods)} methods | {analysis.field_count} fields", 5000)
        
        # For now, show analysis in a message box (we can make this a permanent panel later)
        QMessageBox.information(self, "CIF Analysis Results", analysis_text)

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
        self.status_bar.addPermanentWidget(self.path_label)
        self.status_bar.addPermanentWidget(self.cursor_label)
          # Create text editor with line numbers
        text_widget = QWidget()
        text_layout = QHBoxLayout(text_widget)
        
        self.line_numbers = QTextEdit()
        self.line_numbers.setFixedWidth(50)
        self.line_numbers.setReadOnly(True)
        self.line_numbers.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.text_editor = QTextEdit()
        self.text_editor.textChanged.connect(self.handle_text_changed)
        self.text_editor.cursorPositionChanged.connect(self.update_cursor_position)

        # Create ruler overlay
        self.ruler = QWidget(self.text_editor)
        self.ruler.setFixedWidth(1)  # 1 pixel wide line
        self.ruler.setStyleSheet("background-color: #E0E0E0;")  # Light gray color
        self.ruler.hide()  # Initially hidden until we position it

        # Apply font and other settings
        self.apply_settings()
        
        # Sync scrolling between line numbers and text editor
        self.text_editor.verticalScrollBar().valueChanged.connect(
            self.line_numbers.verticalScrollBar().setValue)
        
        text_layout.addWidget(self.line_numbers)
        text_layout.addWidget(self.text_editor)
        main_layout.addWidget(text_widget)
        
        # Create CIF version control panel
        version_layout = QHBoxLayout()
        
        version_label = QLabel("Target CIF Version:")
        version_label.setToolTip("Select the CIF format version to validate against and convert to")
        
        self.version_selector = QComboBox()
        self.version_selector.addItem("CIF 1.0", CIFVersion.CIF1)
        self.version_selector.addItem("CIF 2.0", CIFVersion.CIF2)
        self.version_selector.setCurrentIndex(0)  # Default to CIF 1.0
        self.version_selector.currentTextChanged.connect(self.on_version_changed)
        
        convert_button = QPushButton("🔄 Convert Format")
        convert_button.clicked.connect(self.convert_cif_format)
        convert_button.setToolTip("Convert the current CIF to the selected format version")
        
        suggest_fields_button = QPushButton("💡 Suggest Fields")
        suggest_fields_button.clicked.connect(self.suggest_missing_fields)
        suggest_fields_button.setToolTip("Suggest missing fields for the selected CIF version")
        
        version_layout.addWidget(version_label)
        version_layout.addWidget(self.version_selector)
        version_layout.addWidget(convert_button)
        version_layout.addWidget(suggest_fields_button)
        version_layout.addStretch()  # Push everything to the left
        
        main_layout.addLayout(version_layout)
        
        # Create button layout
        button_layout = QHBoxLayout()
        
        # Create buttons
        analyze_button = QPushButton("🔍 Analyze CIF")
        analyze_button.clicked.connect(self.analyze_cif)
        analyze_button.setToolTip("Comprehensive CIF analysis - detects format version and crystallography methods")
        
        check_3ded_button = QPushButton("🔬 3D ED Check")
        check_3ded_button.clicked.connect(self.start_checks_3ded)
        check_3ded_button.setToolTip("Specialized 3D electron diffraction validation - comprehensive compliance check")
        
        check_hp_button = QPushButton("⚡ HP Check")
        check_hp_button.clicked.connect(self.start_checks_hp)
        check_hp_button.setToolTip("Check for high pressure crystallography compatibility")
        
        refine_details_button = QPushButton("📝 Edit Details")
        refine_details_button.clicked.connect(self.check_refine_special_details)
        
        format_button = QPushButton("📐 Reformat")
        format_button.clicked.connect(self.reformat_file)
        format_button.setToolTip("Reformat file to 80-character line length")
        
        save_button = QPushButton("💾 Save")
        save_button.clicked.connect(self.save_file)
        
        # Add buttons to layout
        button_layout.addWidget(analyze_button)
        button_layout.addWidget(check_3ded_button)
        button_layout.addWidget(check_hp_button)
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
        
        check_3ded_action = action_menu.addAction("Start Checks (3DED)")
        check_3ded_action.triggered.connect(self.start_checks_3ded)
        
        check_hp_action = action_menu.addAction("Start Checks (HP)")
        check_hp_action.triggered.connect(self.start_checks_hp)
        
        action_menu.addSeparator()
        
        convert_action = action_menu.addAction("Convert CIF Format")
        convert_action.triggered.connect(self.convert_cif_format)
        
        suggest_action = action_menu.addAction("Suggest Missing Fields")
        suggest_action.triggered.connect(self.suggest_missing_fields)
        
        action_menu.addSeparator()
        
        refine_details_action = action_menu.addAction("Edit Refinement Details")
        refine_details_action.triggered.connect(self.check_refine_special_details)
        
        format_action = action_menu.addAction("Reformat File")
        format_action.triggered.connect(self.reformat_file)

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
        line_numbers_action.setChecked(self.settings['line_numbers_enabled'])
        line_numbers_action.triggered.connect(self.toggle_line_numbers)
        
        ruler_action = view_menu.addAction("Show 80-Char Ruler")
        ruler_action.setCheckable(True)
        ruler_action.setChecked(self.settings['show_ruler'])
        ruler_action.triggered.connect(self.toggle_ruler)
        
        syntax_action = view_menu.addAction("Syntax Highlighting")
        syntax_action.setCheckable(True)
        syntax_action.setChecked(self.settings['syntax_highlighting_enabled'])
        syntax_action.triggered.connect(self.toggle_syntax_highlighting)
        
        # Enable undo/redo
        self.text_editor.setUndoRedoEnabled(True)

        # Apply syntax highlighter
        self.highlighter = CIFSyntaxHighlighter(self.text_editor.document())

        # Apply saved settings
        self.apply_settings()

    def select_initial_file(self):
        file_filter = "CIF Files (*.cif);;All Files (*.*)"
        self.current_file, _ = QFileDialog.getOpenFileName(
            self, "Select a CIF File", "", file_filter)
        if not self.current_file:
            QMessageBox.information(self, "No File Selected", 
                                  "Please select a CIF file to continue.")
        else:
            self.open_file(initial=True)

    def update_recent_files_menu(self):
        self.recent_menu.clear()
        for filepath in self.recent_files:
            action = self.recent_menu.addAction(filepath)
            action.triggered.connect(lambda checked, path=filepath: self.open_recent_file(path))
            
    def open_recent_file(self, filepath):
        if not filepath or not os.path.exists(filepath):
            QMessageBox.warning(self, "File Not Found",
                              f"Could not find file:\n{filepath}")
            self.recent_files.remove(filepath)
            self.update_recent_files_menu()
            return
        self.current_file = filepath
        self.open_file(initial=True)
        
    def add_to_recent_files(self, filepath):
        if filepath in self.recent_files:
            self.recent_files.remove(filepath)
        self.recent_files.insert(0, filepath)
        if len(self.recent_files) > self.max_recent_files:
            self.recent_files.pop()
        self.update_recent_files_menu()

    def open_file(self, initial=False):
        if not initial:
            file_filter = "CIF Files (*.cif);;All Files (*.*)"
            filepath, _ = QFileDialog.getOpenFileName(
                self, "Open File", "", file_filter)
            if not filepath:
                return
        else:
            filepath = self.current_file

        try:
            with open(filepath, "r") as file:
                content = file.read()
            self.text_editor.setText(content)
            self.current_file = filepath
            self.modified = False
            self.update_status_bar()
            self.update_line_numbers()
            self.add_to_recent_files(filepath)
            self.setWindowTitle(f"EDCIF-check - {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file:\n{e}")

    def save_file(self):
        if self.current_file:
            reply = QMessageBox.question(self, "Confirm Save",
                f"Do you want to overwrite the existing file?\n{self.current_file}",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel)
            
            if reply == QMessageBox.StandardButton.Cancel:
                return
            elif reply == QMessageBox.StandardButton.Yes:
                self.save_to_file(self.current_file)
            else:
                self.save_file_as()
        else:
            self.save_file_as()

    def save_file_as(self):
        file_filter = "CIF Files (*.cif);;All Files (*.*)"
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save File As", "", file_filter)
        if filepath:
            self.save_to_file(filepath)

    def on_version_changed(self):
        """Handle CIF version selector change"""
        selected_version = self.version_selector.currentData()
        if hasattr(self, 'current_analysis') and self.current_analysis:
            # Update status to show target version
            self.status_bar.showMessage(f"Target: {selected_version.value} | Current: {self.current_analysis.cif_version.value}", 3000)

    def convert_cif_format(self):
        """Convert the current CIF to the selected format version"""
        if not self.current_file:
            QMessageBox.warning(self, "Warning", "Please open a CIF file first.")
            return
        
        target_version = self.version_selector.currentData()
        current_content = self.text_editor.toPlainText()
        
        try:
            if target_version == CIFVersion.CIF1:
                converted_content, changes = self.cif_converter.convert_to_cif1(current_content)
            elif target_version == CIFVersion.CIF2:
                converted_content, changes = self.cif_converter.convert_to_cif2(current_content)
            else:
                QMessageBox.warning(self, "Warning", "Please select a valid CIF version.")
                return
            
            if not changes:
                QMessageBox.information(self, "Conversion Result", 
                                      f"File is already in {target_version.value} format or no changes needed.")
                return
            
            # Show conversion summary (truncate if too many changes)
            max_changes_display = 10
            if len(changes) <= max_changes_display:
                changes_text = '\n'.join(changes)
            else:
                visible_changes = changes[:max_changes_display]
                changes_text = '\n'.join(visible_changes) + f'\n... and {len(changes) - max_changes_display} more changes'
            
            reply = QMessageBox.question(self, "Convert CIF Format", 
                                       f"Apply the following changes to convert to {target_version.value}?\n\n" +
                                       f"Changes ({len(changes)}):\n{changes_text}",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                self.text_editor.setPlainText(converted_content)
                self.modified = True
                # Update window title to reflect current file
                if self.current_file:
                    self.setWindowTitle(f"EDCIF-check - {self.current_file}")
                else:
                    self.setWindowTitle("EDCIF-check")
                self.status_bar.showMessage(f"Converted to {target_version.value} format with {len(changes)} changes", 5000)
                
                # Re-analyze to update version detection
                self.analyze_cif()
        
        except Exception as e:
            QMessageBox.critical(self, "Conversion Error", f"Error converting CIF format:\n{str(e)}")

    def suggest_missing_fields(self):
        """Suggest missing fields for the selected CIF version"""
        if not self.current_file:
            QMessageBox.warning(self, "Warning", "Please open a CIF file first.")
            return
        
        target_version = self.version_selector.currentData()
        current_content = self.text_editor.toPlainText()
        
        try:
            suggestions = self.cif_converter.suggest_missing_fields(current_content, target_version)
            
            if not suggestions:
                QMessageBox.information(self, "Field Suggestions", 
                                      f"No additional fields needed for {target_version.value} format.\n" +
                                      "Your CIF appears to have the essential fields.")
            else:
                suggestions_text = '\n'.join(f"• {suggestion}" for suggestion in suggestions[:20])  # Limit to 20
                if len(suggestions) > 20:
                    suggestions_text += f"\n... and {len(suggestions) - 20} more"
                
                dialog = QMessageBox(self)
                dialog.setWindowTitle("Field Suggestions")
                dialog.setText(f"Suggestions for {target_version.value} format:")
                dialog.setDetailedText(suggestions_text)
                dialog.setIcon(QMessageBox.Icon.Information)
                dialog.exec()
        
        except Exception as e:
            QMessageBox.critical(self, "Suggestion Error", f"Error generating field suggestions:\n{str(e)}")

    def analyze_cif(self):
        """Modern CIF analysis using the new CIFAnalyzer"""
        if not self.current_file:
            QMessageBox.warning(self, "Warning", "Please open a CIF file first.")
            return None
        
        try:
            # Analyze the current file
            self.current_analysis = self.cif_analyzer.analyze_cif_file(self.current_file)
            
            # Update the analysis display
            self.update_analysis_display()
            
            return self.current_analysis
            
        except Exception as e:
            QMessageBox.critical(self, "Analysis Error", f"Error analyzing CIF file:\n{str(e)}")
            return None

    def validate_cif(self):
        """Legacy validation method - now calls modern analysis"""
        analysis = self.analyze_cif()
        if not analysis:
            return []
        
        # Convert analysis to legacy error format for compatibility
        errors = []
        
        # Add basic syntax errors
        text = self.text_editor.toPlainText()
        lines = text.splitlines()
        
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

    def save_to_file(self, filepath):
        # errors = self.validate_cif()
        # if errors:
        #     error_text = "\n".join(errors)
        #     reply = QMessageBox.warning(
        #         self, "CIF Validation Errors",
        #         f"The following validation errors were found:\n\n{error_text}\n\nSave anyway?",
        #         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
        #     if reply == QMessageBox.StandardButton.No:
        #         return
                
        try:
            with open(filepath, "w") as file:
                content = self.text_editor.toPlainText().strip()
                file.write(content)
            self.current_file = filepath
            self.modified = False
            self.update_status_bar()
            QMessageBox.information(self, "Success", 
                                  f"File saved successfully:\n{filepath}")
            self.setWindowTitle(f"EDCIF-check - {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{e}")

    def check_line(self, prefix, default_value=None, multiline=False, description=""):
        """Check and potentially update a CIF field value."""
        removable_chars = "'"
        lines = self.text_editor.toPlainText().splitlines()
        
        for i, line in enumerate(lines):
            if line.startswith(prefix):
                current_value = " ".join(line.split()[1:])
                value, result = CIFInputDialog.getText(
                    self, "Edit Line",
                    f"Edit the line:\n{line}\n\nDescription: {description}\n\nSuggested value: {default_value}\n\n",
                    current_value)
                
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

        QMessageBox.warning(self, "Line Not Found",
                          f"The line starting with '{prefix}' was not found.")
        return self.add_missing_line(prefix, lines, default_value, multiline, description)

    def add_missing_line(self, prefix, lines, default_value=None, multiline=False, description=""):
        """Add a missing CIF field with value."""
        value, result = CIFInputDialog.getText(
            self, "Add Missing Line",
            f"The line starting with '{prefix}' is missing.\n\nDescription: {description}\nSuggested value: {default_value}",
            default_value if default_value else "")
        
        if result in [CIFInputDialog.RESULT_ABORT, CIFInputDialog.RESULT_STOP_SAVE]:
            return result
            
        removable_chars = "'"
        if result != QDialog.DialogCode.Accepted:
            return result
            
        if not value:
            value = "?"

        stripped_value = value.strip(removable_chars)
        if multiline:
            insert_index = len(lines)
            for i, line in enumerate(lines):
                if line.startswith(prefix.split("_")[0]):
                    insert_index = i + 1
            lines.insert(insert_index, 
                        f"{prefix} \n;\n{stripped_value}\n;")
        else:
            # Only quote if value has spaces or special chars
            if ' ' in stripped_value or ',' in stripped_value:
                formatted_value = f"'{stripped_value}'"
            else:
                formatted_value = stripped_value
            lines.append(f"{prefix} {formatted_value}")
        
        self.text_editor.setText("\n".join(lines))
        return result    
    
    def check_refine_special_details(self):
        """Check and edit _refine_special_details field, creating it if needed."""
        content = self.text_editor.toPlainText()
        
        # Parse the CIF content using the new parser
        self.cif_parser.parse_file(content)
        
        template = (
            "STRUCTURE REFINEMENT\n"
            "- Refinement method\n"
            "- Special constraints and restraints\n"
            "- Special treatments"
        )
        
        # Get current value or use template
        current_value = self.cif_parser.get_field_value('_refine_special_details')
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
            
            # Update the field in the parser
            self.cif_parser.set_field_value('_refine_special_details', updated_content)
            
            # Generate updated CIF content and update the text editor
            updated_cif = self.cif_parser.generate_cif_content()
            self.text_editor.setText(updated_cif)
            self.modified = True
            self.update_status_bar()
            
            return QDialog.DialogCode.Accepted
        
        return QDialog.DialogCode.Rejected

    def start_checks_3ded(self):
        """3D ED validation using specialized validator with CIF version awareness."""
        if not self.current_file:
            QMessageBox.warning(self, "Warning", "Please open a CIF file first.")
            return
        
        try:
            # Get current CIF content
            cif_content = self.text_editor.toPlainText()
            
            # Get the detected CIF version (if analysis was run) or detect it
            cif_version = None
            if hasattr(self, 'current_analysis') and self.current_analysis:
                cif_version = self.current_analysis.cif_version
            else:
                # Run a quick analysis to get the CIF version
                analysis = self.cif_analyzer.analyze_cif_file(self.current_file)
                cif_version = analysis.cif_version
            
            # Run specialized 3D ED validation with version awareness
            validation_report = self.ed3d_validator.validate_cif_content(cif_content, cif_version)
            
            # Display 3D ED validation results
            self.display_3d_ed_validation_results(validation_report, cif_version)
            
        except Exception as e:
            QMessageBox.critical(self, "Validation Error", 
                               f"Error during 3D ED validation:\n{str(e)}")
    
    def display_3d_ed_validation_results(self, report, cif_version=None):
        """Display 3D ED validation results"""
        if report["validation_status"] == "not_applicable":
            QMessageBox.information(
                self, "3D ED Validation",
                "❌ Not a 3D ED experiment\n\n"
                + report["message"]
            )
            return
        
        # Create detailed message
        title = "🔬 3D Electron Diffraction Validation Report"
        
        # Overall status
        status_icon = {
            "excellent": "✅",
            "warnings": "⚠️", 
            "issues_found": "❌"
        }.get(report["validation_status"], "❓")
        
        message_parts = []
        message_parts.append(f"{status_icon} **{report['method_detected']}** detected")
        if cif_version:
            message_parts.append(f"📝 **CIF Version:** {cif_version.value}")
        message_parts.append("")
        message_parts.append("📊 **Validation Summary:**")
        
        summary = report["summary"]
        message_parts.append(f"• Total checks: {summary['total_checks']}")
        message_parts.append(f"• ✅ Passed: {summary['passed']}")
        
        if summary['failed'] > 0:
            message_parts.append(f"• ❌ Failed: {summary['failed']}")
        if summary['warnings'] > 0:
            message_parts.append(f"• ⚠️ Warnings: {summary['warnings']}")
        if summary['missing'] > 0:
            message_parts.append(f"• 📝 Missing: {summary['missing']}")
        
        message_parts.append("")
        message_parts.append("🎯 **Validation Status:**")
        message_parts.append(report["validation_summary"])
        
        # Add critical issues if any
        critical_issues = [r for r in report["detailed_results"] 
                          if r["status"] in ["fail", "missing"] and r["level"] == "essential"]
        
        if critical_issues:
            message_parts.append("")
            message_parts.append("🚨 **Critical Issues to Fix:**")
            for issue in critical_issues[:5]:  # Show first 5
                message_parts.append(f"• {issue['field']}: {issue['message']}")
        
        # Add recommendations
        if report["recommendations"]:
            message_parts.append("")
            message_parts.append("💡 **Recommendations:**")
            for rec in report["recommendations"][:3]:  # Show first 3
                message_parts.append(f"• {rec}")
        
        # Show detailed dialog
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText("\n".join(message_parts))
        
        # Style the dialog appropriately
        if report["validation_status"] == "excellent":
            msg_box.setIcon(QMessageBox.Icon.Information)
        elif report["validation_status"] == "warnings":
            msg_box.setIcon(QMessageBox.Icon.Warning)
        else:
            msg_box.setIcon(QMessageBox.Icon.Critical)
        
        # Add detailed results button
        if len(report["detailed_results"]) > 5:
            details_button = msg_box.addButton("Show All Details", QMessageBox.ButtonRole.ActionRole)
            msg_box.addButton(QMessageBox.StandardButton.Ok)
            
            result = msg_box.exec()
            
            # Show detailed results if requested
            if msg_box.clickedButton() == details_button:
                self.show_detailed_3d_ed_results_with_editing(report)
        else:
            msg_box.exec()
    
    def show_detailed_3d_ed_results(self, report):
        """Show detailed validation results in a separate dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Detailed 3D ED Validation Results")
        dialog.setMinimumSize(800, 600)
        
        layout = QVBoxLayout()
        
        # Create scroll area for detailed results
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        
        # Group results by status
        result_groups = {
            "✅ Passed": [r for r in report["detailed_results"] if r["status"] == "pass"],
            "❌ Failed": [r for r in report["detailed_results"] if r["status"] == "fail"], 
            "📝 Missing": [r for r in report["detailed_results"] if r["status"] == "missing"],
            "⚠️ Warnings": [r for r in report["detailed_results"] if r["status"] == "warning"]
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
                result_frame = QFrame()
                result_frame.setFrameStyle(QFrame.Shape.Box)
                result_frame.setStyleSheet("padding: 5px; margin: 2px; background-color: #f5f5f5;")
                
                result_layout = QVBoxLayout()
                
                field_label = QLabel(f"Field: {result['field']}")
                field_label.setStyleSheet("font-weight: bold;")
                result_layout.addWidget(field_label)
                
                message_label = QLabel(f"Message: {result['message']}")
                result_layout.addWidget(message_label)
                
                level_label = QLabel(f"Level: {result['level'].replace('_', ' ').title()}")
                level_label.setStyleSheet("font-style: italic; color: #666;")
                result_layout.addWidget(level_label)
                
                result_frame.setLayout(result_layout)
                scroll_layout.addWidget(result_frame)
        
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        
        layout.addWidget(scroll_area)
        
        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        
        dialog.setLayout(layout)
        dialog.exec()

    def show_detailed_3d_ed_results_with_editing(self, report):
        """Show detailed validation results with inline editing capabilities"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Detailed Results with Field Editing")
        dialog.setMinimumSize(1000, 700)
        
        layout = QVBoxLayout()
        
        # Create splitter for results and editing
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side: Results list (similar to existing)
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
            "❌ Failed": [r for r in report["detailed_results"] if r["status"] == "fail"], 
            "📝 Missing": [r for r in report["detailed_results"] if r["status"] == "missing"],
            "⚠️ Warnings": [r for r in report["detailed_results"] if r["status"] == "warning"],
            "✅ Passed": [r for r in report["detailed_results"] if r["status"] == "pass"]
        }
        
        self.field_edit_widgets = {}  # Store references to edit widgets
        
        for group_name, results in result_groups.items():
            if not results:
                continue
                
            # Group header
            header = QLabel(f"{group_name} ({len(results)})")
            header.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px;")
            scroll_layout.addWidget(header)
            
            # Results in this group
            for result in results:
                result_frame = QFrame()
                result_frame.setFrameStyle(QFrame.Shape.Box)
                
                # Color code based on status
                if result['status'] == 'fail':
                    bg_color = "#ffe6e6"  # Light red
                elif result['status'] == 'missing':
                    bg_color = "#fff3cd"  # Light yellow
                elif result['status'] == 'warning':
                    bg_color = "#e6f3ff"  # Light blue
                else:
                    bg_color = "#e6ffe6"  # Light green
                    
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
                scroll_layout.addWidget(result_frame)
        
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        
        results_layout.addWidget(scroll_area)
        results_widget.setLayout(results_layout)
        
        # Right side: Field editing area
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
        
        # Add both sides to splitter
        splitter.addWidget(results_widget)
        splitter.addWidget(edit_widget)
        splitter.setSizes([400, 600])  # Give more space to editor
        
        layout.addWidget(splitter)
        
        # Bottom buttons
        bottom_layout = QHBoxLayout()
        
        apply_all_btn = QPushButton("🚀 Apply All Recommendations")
        apply_all_btn.clicked.connect(lambda: self.apply_all_recommendations(report))
        bottom_layout.addWidget(apply_all_btn)
        
        bottom_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        bottom_layout.addWidget(close_button)
        
        layout.addLayout(bottom_layout)
        
        dialog.setLayout(layout)
        dialog.exec()

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
        self.modified = True
        
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
            self.modified = True
            QMessageBox.information(self, "Field Updated", f"Field '{field_name}' has been updated.")
        else:
            # Field not found, offer to add it
            reply = QMessageBox.question(self, "Field Not Found", 
                                       f"Field '{field_name}' not found. Would you like to add it as a new field?")
            if reply == QMessageBox.StandardButton.Yes:
                self.add_field_to_file()

    def apply_all_recommendations(self, report):
        """Apply all possible automatic recommendations"""
        applied_count = 0
        
        # Get recommendations that can be automatically applied
        auto_applicable = []
        
        for result in report["detailed_results"]:
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
            self.modified = True
            
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

    def start_checks_hp(self):
        """Start modern CIF analysis focused on high pressure crystallography."""
        if not self.current_file:
            QMessageBox.warning(self, "Warning", "Please open a CIF file first.")
            return
        
        # Perform analysis
        analysis = self.analyze_cif()
        if not analysis:
            return
        
        # Check if high pressure is detected
        hp_detected = CrystallographyMethod.HIGH_PRESSURE in analysis.detected_methods
        
        if hp_detected:
            confidence = analysis.confidence_scores.get('high_pressure', 0)
            QMessageBox.information(
                self, "High Pressure Analysis",
                f"✅ High pressure crystallography detected with {confidence:.0%} confidence!\n\n"
                f"CIF Version: {analysis.cif_version.value}\n"
                f"Fields found: {analysis.field_count}\n\n"
                f"The file appears to be properly configured for HP crystallography."
            )
        else:
            # Show recommendations for making it HP-compatible
            recommendations = []
            recommendations.append("To make this file compatible with HP crystallography:")
            recommendations.append("• Add _diffrn.ambient_pressure or _diffrn_ambient_pressure")
            recommendations.append("• Consider adding _exptl_crystal.pressure_history")
            recommendations.append("• Add pressure-related keywords in descriptions")
            
            QMessageBox.warning(
                self, "High Pressure Check",
                "\n".join(recommendations)
            )    
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
        self.modified = True
        self.update_line_numbers()
        self.update_status_bar()
    
    def update_line_numbers(self):
        text = self.text_editor.toPlainText()
        num_lines = text.count('\n') + 1
        numbers = '\n'.join(str(i) for i in range(1, num_lines + 1))
        self.line_numbers.setText(numbers)
        
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
        path = self.current_file if self.current_file else "Untitled"
        modified = "*" if self.modified else ""
        self.path_label.setText(f"{path}{modified} | ")

    def resizeEvent(self, event):
        """Handle resize events to update the ruler position"""
        super().resizeEvent(event)
        if hasattr(self, 'ruler'):
            self.ruler.setGeometry(self.ruler.x(), 0, 1, self.text_editor.height())

    def show_find_dialog(self):
        """Show a dialog for finding text in the editor"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Find")
        layout = QVBoxLayout(dialog)
        
        # Search input
        search_label = QLabel("Find what:")
        search_input = QLineEdit()
        layout.addWidget(search_label)
        layout.addWidget(search_input)
        
        # Options
        case_checkbox = QCheckBox("Match case")
        layout.addWidget(case_checkbox)
        
        # Buttons
        button_layout = QHBoxLayout()
        find_next_button = QPushButton("Find Next")
        find_next_button.clicked.connect(lambda: self.find_text(
            search_input.text(), 
            case_sensitive=case_checkbox.isChecked()
        ))
        button_layout.addWidget(find_next_button)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.close)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec()

    def show_replace_dialog(self):
        """Show a dialog for finding and replacing text in the editor"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Find and Replace")
        layout = QVBoxLayout(dialog)
        
        # Find input
        find_label = QLabel("Find what:")
        find_input = QLineEdit()
        layout.addWidget(find_label)
        layout.addWidget(find_input)
        
        # Replace input
        replace_label = QLabel("Replace with:")
        replace_input = QLineEdit()
        layout.addWidget(replace_label)
        layout.addWidget(replace_input)
        
        # Options
        case_checkbox = QCheckBox("Match case")
        layout.addWidget(case_checkbox)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        find_next_button = QPushButton("Find Next")
        find_next_button.clicked.connect(lambda: self.find_text(
            find_input.text(), 
            case_sensitive=case_checkbox.isChecked()
        ))
        
        replace_button = QPushButton("Replace")
        replace_button.clicked.connect(lambda: self.replace_text(
            find_input.text(),
            replace_input.text(),
            case_sensitive=case_checkbox.isChecked()
        ))
        
        replace_all_button = QPushButton("Replace All")
        replace_all_button.clicked.connect(lambda: self.replace_all_text(
            find_input.text(),
            replace_input.text(),
            case_sensitive=case_checkbox.isChecked()
        ))
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.close)
        
        button_layout.addWidget(find_next_button)
        button_layout.addWidget(replace_button)
        button_layout.addWidget(replace_all_button)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        dialog.setLayout(layout)
        dialog.exec()

    def find_text(self, text, case_sensitive=False):
        """Find the next occurrence of text in the editor"""
        flags = QTextDocument.FindFlag.FindBackward
        if case_sensitive:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
            
        cursor = self.text_editor.textCursor()
        found = self.text_editor.find(text)
        
        if not found:
            # If not found, try from the start
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.text_editor.setTextCursor(cursor)
            found = self.text_editor.find(text)
            
            if not found:
                QMessageBox.information(self, "Find", f"Cannot find '{text}'")

    def replace_text(self, find_text, replace_text, case_sensitive=False):
        """Replace the next occurrence of find_text with replace_text"""
        cursor = self.text_editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == find_text:
            cursor.insertText(replace_text)
            
        self.find_text(find_text, case_sensitive)

    def replace_all_text(self, find_text, replace_text, case_sensitive=False):
        """Replace all occurrences of find_text with replace_text"""
        cursor = self.text_editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.text_editor.setTextCursor(cursor)
        
        count = 0
        while self.text_editor.find(find_text):
            cursor = self.text_editor.textCursor()
            cursor.insertText(replace_text)
            count += 1
            
        if count > 0:
            QMessageBox.information(self, "Replace All", 
                                  f"Replaced {count} occurrence(s)")
        else:
            QMessageBox.information(self, "Replace All", 
                                  f"Cannot find '{find_text}'")