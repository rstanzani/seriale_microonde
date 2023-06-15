# ------------------------------------------------------
# -------------------- mplwidget.py --------------------
# ------------------------------------------------------
from PyQt5.QtWidgets import QWidget, QVBoxLayout

from matplotlib.backends.backend_qt5agg import FigureCanvas

from matplotlib.figure import Figure


class Mplwidget(QWidget):

    def __init__(self, parent = None):

        QWidget.__init__(self, parent)


        self.canvas = FigureCanvas(Figure(figsize=(480,320)))

        vertical_layout = QVBoxLayout()
        vertical_layout.addWidget(self.canvas)

        self.setLayout(vertical_layout)