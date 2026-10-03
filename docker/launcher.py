"""Minimal desktop launcher for the openpilot UI."""

import os
import subprocess
import sys
from PyQt5.QtCore import QTimer
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

UI_BINARY = Path("/opt/openpilot/selfdrive/ui/ui")


class Launcher(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.ui_process = None
        self.monitor = QTimer(self)
        self.monitor.timeout.connect(self.check_openpilot)
        self.setWindowTitle("AI Self-Driving Car")
        self.resize(420, 260)
        self.setMinimumSize(360, 220)
        title = QLabel("AI Self-Driving Car")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 18, QFont.Bold))
        self.status = QLabel("OpenPilot 尚未啟動")
        self.status.setAlignment(Qt.AlignCenter)
        button = QPushButton("⚙  開啟 OpenPilot")
        button.setMinimumHeight(72)
        button.setFont(QFont("Arial", 16, QFont.Bold))
        button.clicked.connect(self.start_openpilot)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.status)
        layout.addWidget(button)

    def start_openpilot(self) -> None:
        if not UI_BINARY.is_file() or not os.access(UI_BINARY.with_name("_ui"), os.X_OK):
            self.status.setText("找不到 UI binary，請先完成 scons 編譯")
            return
        if self.ui_process is None or self.ui_process.poll() is not None:
            try:
                with open("/tmp/openpilot-ui.log", "a", encoding="utf-8") as log:
                    self.ui_process = subprocess.Popen(
                        [str(UI_BINARY)], cwd="/opt/openpilot",
                        stdout=log, stderr=log, start_new_session=True,
                    )
            except OSError as error:
                self.status.setText(str(error))
                return
        self.status.setText("OpenPilot 已啟動")
        self.hide()
        QTimer.singleShot(1500, self.resize_openpilot_window)
        self.monitor.start(500)

    def resize_openpilot_window(self) -> None:
        """Start the official UI as a normal, resizable desktop window."""
        if self.ui_process is None or self.ui_process.poll() is not None:
            return
        windows = subprocess.check_output(["wmctrl", "-lp"], text=True)
        for line in windows.splitlines():
            fields = line.split()
            if len(fields) >= 3 and fields[2] == str(self.ui_process.pid):
                subprocess.run(
                    ["wmctrl", "-ir", fields[0], "-e", "0,40,40,1600,900"],
                    check=False,
                )

    def check_openpilot(self) -> None:
        if self.ui_process is None or self.ui_process.poll() is None:
            return
        self.monitor.stop()
        self.ui_process = None
        self.status.setText("OpenPilot 尚未啟動")
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
        # Keep a route back to the launcher when its title-bar close is clicked.
        event.ignore()
        self.showMinimized()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet("QWidget { background: #20232b; color: white; }")
    launcher = Launcher()
    launcher.show()
    raise SystemExit(app.exec_())
