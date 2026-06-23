"""测试图标是否显示。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QIcon, QPixmap

app = QApplication(sys.argv)

icon_path = Path("assets/icon.png").resolve()
print("Exists:", icon_path.exists())

pix = QPixmap(str(icon_path))
print("Pixmap null:", pix.isNull())

icon = QIcon(pix)
app.setWindowIcon(icon)

w = QWidget()
w.setWindowTitle("Test Icon")
w.resize(300, 200)
w.show()
app.processEvents()

print("Done - can you see the icon?")
print("If not, we need a .ico file instead of .png")
input("Press Enter to exit...")
