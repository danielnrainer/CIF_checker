"""CIF Syntax Highlighter for PyQt6 text editor"""

from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor


class CIFSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for CIF files with field names, values, and multiline blocks"""
    
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
        """Apply syntax highlighting to a block of text"""
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
