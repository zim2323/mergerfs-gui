import sys
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout

class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DrivePool Mirror Test")
        self.setGeometry(100, 100, 300, 100)
        
        layout = QVBoxLayout()
        label = QLabel("Python + PyQt6 is working on CachyOS!", self)
        layout.addWidget(label)
        self.setLayout(layout)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
