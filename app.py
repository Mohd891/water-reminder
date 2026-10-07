"""Windows desktop companion with real alpha transparency."""

import json
import sys
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QInputDialog, QLabel, QMenu, QPushButton, QSystemTrayIcon, QWidget,
)

BASE = Path(__file__).resolve().parent
SETTINGS = BASE / "settings.json"
WIDTH, HEIGHT = 400, 390
WALK_STEP = 12
FIRST_REMINDER_SECONDS = 2 * 60


def start_with_windows():
    if sys.platform != "win32":
        return
    import winreg

    command = f'"{sys.executable}" "{Path(__file__).resolve()}"'
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        winreg.SetValueEx(key, "WaterReminderPet", 0, winreg.REG_SZ, command)


def load_settings():
    try:
        data = json.loads(SETTINGS.read_text(encoding="utf-8"))
        return {"name": str(data.get("name") or "")[:32],
                "minutes": max(1, min(240, int(data.get("minutes", 45))))}
    except (OSError, ValueError, TypeError):
        return {"name": "", "minutes": 45}


def icon():
    canvas = QPixmap(64, 64)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#1678AA"))
    painter.drawEllipse(4, 4, 56, 56)
    painter.setBrush(QColor("#D8F5FF"))
    painter.drawEllipse(25, 17, 14, 28)
    painter.end()
    return QIcon(canvas)


class Pet(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.active = False
        self.phase = "idle"
        self.progress = 0
        self.next_due = time.monotonic() + FIRST_REMINDER_SECONDS
        self.last_tick = time.time()

        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(WIDTH, HEIGHT)
        screen = QApplication.primaryScreen().availableGeometry()
        self.start_x = screen.x() - WIDTH
        self.target_x = screen.x() + (screen.width() - WIDTH) // 2
        self.target_y = screen.y() + (screen.height() - HEIGHT) // 2 + 250
        self.move(self.start_x, self.target_y)

        self.bubble = QLabel(self)
        self.bubble.setGeometry(25, 4, 350, 55)
        self.bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bubble.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.bubble.setStyleSheet(
            "QLabel { background-color: rgba(19, 27, 38, 225); color: white;"
            " border-radius: 12px; padding: 5px; font: bold 17px 'Segoe UI'; }")
        self.bubble.hide()

        self.character = QLabel(self)
        self.character.setGeometry(95, 61, 210, 264)
        self.character.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frames = self.load_frames()
        self.idle_frame = self.read_frame(BASE / "character" / "avatar.png")
        self.character.setPixmap(self.idle_frame)

        self.yes = QPushButton("شربت ماء", self)
        self.yes.setGeometry(28, 338, 145, 38)
        self.yes.clicked.connect(self.drink)
        self.later = QPushButton("ذكرني بعد 10 دقايق", self)
        self.later.setGeometry(190, 338, 182, 38)
        self.later.clicked.connect(self.snooze)
        for button in (self.yes, self.later):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                "QPushButton { background-color: white; color: #172833;"
                " border: 1px solid #CDD7DD; border-radius: 9px;"
                " font: 14px 'Segoe UI'; }"
                "QPushButton:hover { background-color: #E6F4FA; }")
            button.hide()

        self.tray = QSystemTrayIcon(icon(), self)
        self.tray.setToolTip("رفيق الماء")
        self.menu = QMenu(self)
        self.menu.addAction("جرب التذكير الآن", self.show_reminder)
        self.menu.addAction("الإعدادات", self.edit_settings)
        self.menu.addSeparator()
        self.menu.addAction("خروج", QApplication.instance().quit)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.tray_clicked)
        self.tray.show()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(40)

    @staticmethod
    def read_frame(path):
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            raise FileNotFoundError(f"Missing character image: {path}")
        return pixmap.scaled(210, 264, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)

    def load_frames(self):
        paths = sorted((BASE / "character").glob("walk_*.png"))
        if not paths:
            paths = [BASE / "character" / "avatar.png"]
        return [self.read_frame(path) for path in paths]

    def show_reminder(self):
        if self.active:
            return
        self.active = True
        self.phase = "enter"
        self.progress = 0
        self.move(self.start_x, self.target_y)
        self.bubble.hide()
        self.yes.hide()
        self.later.hide()
        self.show()

    def tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_reminder()

    def drink(self):
        self.yes.hide()
        self.later.hide()
        self.bubble.setText(f"كفو, بالعافية {self.settings['name']}!")
        self.next_due = time.monotonic() + self.settings["minutes"] * 60
        self.phase = "celebrate"
        self.progress = 0

    def snooze(self):
        self.yes.hide()
        self.later.hide()
        self.bubble.setText("أنا أوريك جاي لك الحين!!")
        self.bubble.show()
        self.next_due = time.monotonic() + 10 * 60
        self.phase = "snooze_message"
        self.progress = 0

    def edit_settings(self):
        name, ok = QInputDialog.getText(None, "اسم الشخصية", "وش اسمك؟",
                                        text=self.settings["name"])
        if not ok:
            return
        minutes, ok = QInputDialog.getInt(None, "وقت التذكير", "ذكّرني كل كم دقيقة؟",
                                           self.settings["minutes"], 1, 240)
        if not ok:
            return
        self.settings = {"name": name.strip()[:32] or "", "minutes": minutes}
        SETTINGS.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        self.next_due = time.monotonic() + minutes * 60

    def tick(self):
        now = time.time()
        if now - self.last_tick > 5:
            # The timer paused while Windows was asleep. Restart the two-minute wait.
            if self.active:
                self.active = False
                self.hide()
            self.next_due = time.monotonic() + FIRST_REMINDER_SECONDS
        self.last_tick = now

        if not self.active:
            if time.monotonic() >= self.next_due:
                self.show_reminder()
            return
        self.progress += 1
        if self.phase == "enter":
            self.move(min(self.target_x, self.x() + WALK_STEP), self.target_y)
            if self.x() >= self.target_x:
                self.phase = "ask"
                self.bubble.setText(f"{self.settings['name']} شربت ماء ولا لا؟؟")
                self.bubble.show()
                self.yes.show()
                self.later.show()
        elif self.phase == "celebrate" and self.progress >= 50:
            self.bubble.hide()
            self.phase = "leave"
        elif self.phase == "snooze_message" and self.progress >= 25:
            self.bubble.hide()
            self.phase = "leave"
        elif self.phase == "leave":
            self.move(self.x() - WALK_STEP, self.target_y)
            if self.x() <= self.start_x:
                self.active = False
                self.hide()
                return
        if self.phase in ("enter", "leave"):
            self.character.setPixmap(self.frames[(self.progress // 7) % len(self.frames)])
        else:
            self.character.setPixmap(self.idle_frame)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    start_with_windows()
    pet = Pet()
    sys.exit(app.exec())
