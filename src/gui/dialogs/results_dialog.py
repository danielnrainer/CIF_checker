"""Results display dialogs for CIF validation"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QScrollArea, 
                            QWidget, QFrame, QPushButton)


class ValidationResultsDialog(QDialog):
    """Dialog for displaying detailed validation results"""
    
    def __init__(self, report, title="Detailed Validation Results", parent=None):
        super().__init__(parent)
        self.report = report
        
        self.setWindowTitle(title)
        self.setMinimumSize(800, 600)
        
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout()
        
        # Create scroll area for detailed results
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        
        # Group results by status
        result_groups = {
            "✅ Passed": [r for r in self.report["detailed_results"] if r["status"] == "pass"],
            "❌ Failed": [r for r in self.report["detailed_results"] if r["status"] == "fail"], 
            "📝 Missing": [r for r in self.report["detailed_results"] if r["status"] == "missing"],
            "⚠️ Warnings": [r for r in self.report["detailed_results"] if r["status"] == "warning"]
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
        
        layout.addWidget(scroll_area)
        
        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
        
        self.setLayout(layout)
    
    def create_result_frame(self, result):
        """Create a frame for displaying a single validation result"""
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
        return result_frame
