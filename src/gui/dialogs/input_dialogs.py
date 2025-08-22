"""Custom input dialogs for CIF Editor with enhanced functionality"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, 
                            QPushButton, QLineEdit, QLabel)
from PyQt6.QtCore import Qt


# Dialog result codes for consistency
RESULT_ABORT = 2
RESULT_STOP_SAVE = 3


class MultilineInputDialog(QDialog):
    """Dialog for editing multiline text with additional control options"""
    
    # Define result codes as class attributes
    RESULT_ABORT = RESULT_ABORT  # User wants to abort all changes
    RESULT_STOP_SAVE = RESULT_STOP_SAVE  # User wants to stop but save changes

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
        """Get the edited text"""
        return self.textEdit.toPlainText()
        
    def abort_changes(self):
        """Signal that user wants to abort all changes"""
        self.done(self.RESULT_ABORT)
        
    def stop_and_save(self):
        """Signal that user wants to stop but save current changes"""
        self.done(self.RESULT_STOP_SAVE)


class CIFInputDialog(QDialog):
    """Dialog for single-line input with enhanced control options"""
    
    # Define result codes as class attributes
    RESULT_ABORT = RESULT_ABORT  # User wants to abort all changes
    RESULT_STOP_SAVE = RESULT_STOP_SAVE  # User wants to stop but save changes

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
        """Get the input value"""
        return self.inputField.text()
        
    def abort_changes(self):
        """Signal that user wants to abort all changes"""
        self.done(self.RESULT_ABORT)
        
    def stop_and_save(self):
        """Signal that user wants to stop but save current changes"""
        self.done(self.RESULT_STOP_SAVE)

    @staticmethod
    def getText(parent, title, text, value=""):
        """Static method to get text input with enhanced dialog"""
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
