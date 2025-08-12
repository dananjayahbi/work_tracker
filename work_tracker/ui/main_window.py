import sys
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QApplication, QMessageBox, QSystemTrayIcon, QMenu, QAction
from PyQt5.QtCore import Qt, QTimer, QTime, QDateTime
from PyQt5.QtGui import QIcon
from .settings_dialog import SettingsDialog
from work_tracker.db.database import DatabaseManager

# --- Windows idle detection ---
try:
    import ctypes
    from ctypes import Structure, c_uint, byref, sizeof
    class LASTINPUTINFO(Structure):
        _fields_ = [("cbSize", c_uint), ("dwTime", c_uint)]
    def get_system_idle_seconds() -> int:
        last = LASTINPUTINFO()
        last.cbSize = sizeof(last)
        if ctypes.windll.user32.GetLastInputInfo(byref(last)) == 0:
            return 0
        tick = ctypes.windll.kernel32.GetTickCount()
        idle_ms = tick - last.dwTime
        return int(idle_ms / 1000)
except Exception:
    def get_system_idle_seconds() -> int:
        return 0

class WorkTracker(QMainWindow):
    def __init__(self, db: DatabaseManager | None = None):
        super().__init__()
        self.db_manager = db or DatabaseManager()
        self.active_session_id = self.db_manager.get_active_session()
        self.last_activity_ts = QDateTime.currentDateTime()  # simplistic activity tracker
        self.break_timer_secs = 0
        self.setup_ui()
        self.setup_tray()
        self.setup_timer()
        self.update_display()

    # --- UI ---
    def setup_ui(self) -> None:
        # We will re-assemble to inject labels cleanly
        self.setWindowTitle("Work Tracker")
        self.setWindowIcon(QIcon(str(__import__('pathlib').Path(__file__).resolve().parent.parent / 'assets' / 'icon.png')))
        self.setFixedSize(300, 250)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        central = QWidget(); self.setCentralWidget(central)
        layout = QVBoxLayout(central); layout.setSpacing(8); layout.setContentsMargins(15,15,15,15)
        self.status_label = QLabel("●", alignment=Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size:20px;color:#ff4444;")
        layout.addWidget(self.status_label)
        self.daily_label = QLabel("Daily: 0h 0m 0s / 8h 0m 0s", alignment=Qt.AlignCenter)
        self.countdown_label = QLabel("Remaining: 8h 0m 0s", alignment=Qt.AlignCenter)
        self.weekly_label = QLabel("Weekly: 0h 0m 0s / 40h 0m 0s", alignment=Qt.AlignCenter)
        self.streak_label = QLabel("Streak: 0 days", alignment=Qt.AlignCenter)
        self.streak_label.setStyleSheet("font-size:11px;font-weight:500;color:#FFD54F;")
        self.schedule_label = QLabel("", alignment=Qt.AlignCenter)
        self.schedule_label.setStyleSheet("font-size:10px;color:#cccccc;")
        for lbl in (self.daily_label, self.countdown_label, self.weekly_label, self.streak_label, self.schedule_label):
            lbl.setStyleSheet("font-size:11px;font-weight:500;color:#ffffff;")
            layout.addWidget(lbl)
        btn_layout = QHBoxLayout()
        self.start_stop_btn = QPushButton("Start")
        settings_btn = QPushButton("⚙"); settings_btn.setFixedSize(30,30)
        self.start_stop_btn.clicked.connect(self.toggle_work)
        settings_btn.clicked.connect(self.open_settings)
        btn_layout.addWidget(self.start_stop_btn); btn_layout.addWidget(settings_btn)
        layout.addLayout(btn_layout)
        self.setStyleSheet("""
            QMainWindow { background-color:#2b2b2b; }
            QLabel { color:#ffffff; font-size:12px; font-weight:500; }
            QPushButton { background-color:#4CAF50; border:none; border-radius:5px; padding:8px 12px; color:white; font-weight:bold; font-size:11px; }
            QPushButton:hover { background-color:#45a049; }
            QPushButton:pressed { background-color:#3d8b40; }
            QPushButton#stop { background-color:#f44336; }
            QPushButton#stop:hover { background-color:#d32f2f; }
        """)

    def setup_tray(self) -> None:
        # System tray for notifications and quick actions
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("Work Tracker")
        menu = QMenu()
        act_toggle = QAction("Start/Stop", self); act_toggle.triggered.connect(self.toggle_work)
        act_show = QAction("Show", self); act_show.triggered.connect(self.showNormal)
        act_quit = QAction("Quit", self); act_quit.triggered.connect(QApplication.instance().quit)
        menu.addAction(act_toggle); menu.addAction(act_show); menu.addSeparator(); menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.show()

    # --- Timer ---
    def setup_timer(self) -> None:
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_tick)
        self.timer.start(1000)

    def on_tick(self) -> None:
        # Update every second
        self.update_display()
        # Break reminders
        if self.db_manager.get_bool_setting('notifications_enabled', True):
            self.break_timer_secs += 1
            interval = self.db_manager.get_int_setting('break_interval_min', 60) * 60
            if interval and self.break_timer_secs > 0 and self.break_timer_secs % interval == 0 and self.active_session_id:
                self.notify("Break time", "You've been working for a while. Take a short break.")
        # Idle detection with auto-pause
        idle_min = self.db_manager.get_int_setting('idle_threshold_min', 10)
        if self.active_session_id and idle_min > 0:
            try:
                if get_system_idle_seconds() >= idle_min * 60:
                    self.db_manager.end_session(self.active_session_id)
                    self.active_session_id = None
                    self.start_stop_btn.setText("Start")
                    self.start_stop_btn.setObjectName("")
                    self.status_label.setStyleSheet("font-size:20px;color:#ff4444;")
                    self.notify("Paused due to inactivity", f"No input detected for {idle_min} minutes. Session paused.")
            except Exception:
                # Fallback gentle reminder if idle detection fails
                if self.break_timer_secs % max(1, idle_min * 60) == 0:
                    self.notify("Idle check", "If you're away, consider pausing the session.")

    # --- Logic ---
    def toggle_work(self) -> None:
        if self.active_session_id:
            self.db_manager.end_session(self.active_session_id)
            self.active_session_id = None
            self.start_stop_btn.setText("Start")
            self.start_stop_btn.setObjectName("")
            self.status_label.setStyleSheet("font-size:20px;color:#ff4444;")
            self.notify("Session ended", "Work session stopped.")
        else:
            self.active_session_id = self.db_manager.start_session()
            self.start_stop_btn.setText("Stop")
            self.start_stop_btn.setObjectName("stop")
            self.status_label.setStyleSheet("font-size:20px;color:#44ff44;")
            self.notify("Session started", "Work session started.")
            self.break_timer_secs = 0
        self.start_stop_btn.setStyle(self.start_stop_btn.style())
        self.update_display()

    def notify(self, title: str, message: str) -> None:
        if not self.db_manager.get_bool_setting('notifications_enabled', True):
            return
        try:
            # Use tray notifications (supported on Windows for PyQt5)
            self.tray.showMessage(title, message, self.windowIcon(), 4000)
        except Exception:
            # Fallback
            QMessageBox.information(self, title, message)

    def update_display(self) -> None:
        try:
            daily_goal_h = int(self.db_manager.get_setting('daily_goal') or 8)
            weekly_goal_h = int(self.db_manager.get_setting('weekly_goal') or 40)
            daily_secs = self.db_manager.get_daily_time_seconds()
            weekly_secs = self.db_manager.get_weekly_time_seconds()
            self.daily_label.setText(f"Daily: {self.format_time(daily_secs)} / {self.format_time(daily_goal_h*3600)}")
            self.weekly_label.setText(f"Weekly: {self.format_time(weekly_secs)} / {self.format_time(weekly_goal_h*3600)}")
            remaining = max(0, daily_goal_h*3600 - daily_secs)
            if remaining>0:
                self.countdown_label.setText(f"Remaining: {self.format_time(remaining)}")
                self.countdown_label.setStyleSheet("color:#ffffff;font-size:11px;font-weight:500;")
                # Custom goal alerts when near threshold
                threshold = self.db_manager.get_int_setting('goal_alert_threshold', 90)
                pct = (daily_secs / (daily_goal_h*3600)) * 100 if daily_goal_h else 0
                if 0 < threshold <= 120 and pct >= threshold and not hasattr(self, '_goal_alerted'):
                    self.notify("Goal almost there!", f"You've reached {pct:.0f}% of today's goal.")
                    self._goal_alerted = True
                if pct < threshold and hasattr(self, '_goal_alerted'):
                    delattr(self, '_goal_alerted')
            else:
                self.countdown_label.setText("Goal reached! 🎉")
                self.countdown_label.setStyleSheet("color:#4CAF50;font-size:11px;font-weight:bold;")
                # Gamification: streak and badge
                streak = self.db_manager.consecutive_goal_days()
                self.streak_label.setText(f"Streak: {streak} day{'s' if streak!=1 else ''} 🔥")
                if streak in (7, 30, 100):
                    self.notify("Achievement unlocked!", f"{streak}-day streak maintained. Great job!")
            # Schedule guidance
            if self.db_manager.get_bool_setting('schedule_enabled', False):
                wd = self.db_manager.get_setting('work_days') or 'Mon,Tue,Wed,Thu,Fri'
                start = self.db_manager.get_setting('work_start') or '09:00'
                end = self.db_manager.get_setting('work_end') or '17:00'
                today_name = QDateTime.currentDateTime().toString('ddd')
                if today_name in [d.strip() for d in wd.split(',') if d.strip()]:
                    self.schedule_label.setText(f"Today schedule: {start} - {end}")
                else:
                    self.schedule_label.setText("Today is outside scheduled work days")
            else:
                self.schedule_label.setText("")
        except Exception as e:
            print(f"Display update error: {e}")

    # --- Helpers ---
    def format_time(self, secs: int) -> str:
        h = secs // 3600; m = (secs % 3600)//60; s = secs % 60
        return f"{h}h {m}m {s}s"

    # --- Dialogs ---
    def open_settings(self) -> None:
        dlg = SettingsDialog(self.db_manager, self)
        dlg.exec_()
        self.update_display()

    def closeEvent(self, event):
        try:
            # End active session to avoid dangling active flag
            if getattr(self, 'active_session_id', None):
                try:
                    self.db_manager.end_session(self.active_session_id)
                except Exception:
                    pass
                self.active_session_id = None
            # Stop timers
            if getattr(self, 'timer', None):
                try:
                    self.timer.stop()
                except Exception:
                    pass
            # Hide tray icon
            if getattr(self, 'tray', None):
                try:
                    self.tray.hide()
                except Exception:
                    pass
        finally:
            event.accept()
            # Ensure full app exit
            try:
                QApplication.instance().quit()
            except Exception:
                pass

# Entry function

def run():
    app = QApplication(sys.argv)
    tracker = WorkTracker()
    tracker.show()
    app.setApplicationName("Work Tracker")
    app.setApplicationVersion("2.0")
    return app.exec_()
