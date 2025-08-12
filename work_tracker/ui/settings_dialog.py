from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, QGroupBox, QFormLayout, QSpinBox,
                             QLabel, QHBoxLayout, QPushButton, QMessageBox, QCheckBox, QComboBox, QGridLayout, QLineEdit)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from work_tracker.db.database import DatabaseManager
from datetime import date
import io

class SettingsDialog(QDialog):
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle("Settings & Analytics")
        self.setFixedSize(620, 500)
        self.setup_ui()
        self.load_settings()
        self.apply_style()

    def apply_style(self):
        self.setStyleSheet("""
            QDialog { background-color:#2b2b2b; color:#ffffff; }
            QLabel { color:#ffffff; font-size:12px; }
            QSpinBox, QLineEdit { background-color:#404040; border:2px solid #555555; border-radius:5px; padding:5px; color:#ffffff; font-size:12px; }
            QSpinBox:focus, QLineEdit:focus { border-color:#4CAF50; }
            QPushButton { background-color:#4CAF50; border:none; border-radius:5px; padding:8px 16px; color:white; font-weight:bold; font-size:12px; }
            QPushButton:hover { background-color:#45a049; }
            QPushButton:pressed { background-color:#3d8b40; }
            QGroupBox { color:white; font-weight:bold; border:2px solid #555555; border-radius:5px; margin:10px 0; padding-top:10px; }
            QGroupBox::title { subcontrol-origin: margin; left:10px; padding:0 10px 0 10px; }
        """)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(); layout.addWidget(self.tabs)
        # Settings tab
        self.settings_tab = QWidget(); settings_layout = QVBoxLayout(self.settings_tab)
        goals_group = QGroupBox("Work Goals"); goals_layout = QFormLayout(goals_group)
        self.daily_spin = QSpinBox(); self.daily_spin.setRange(1,24); self.daily_spin.setSuffix(" h")
        self.weekly_spin = QSpinBox(); self.weekly_spin.setRange(1,168); self.weekly_spin.setSuffix(" h")
        goals_layout.addRow("Daily Goal:", self.daily_spin)
        goals_layout.addRow("Weekly Goal:", self.weekly_spin)
        settings_layout.addWidget(goals_group)

        # Notifications & Alerts
        notif_group = QGroupBox("Notifications & Alerts"); notif_form = QFormLayout(notif_group)
        self.notifications_enabled = QCheckBox("Enable desktop notifications")
        self.break_interval = QSpinBox(); self.break_interval.setRange(5, 240); self.break_interval.setSuffix(" min")
        self.goal_alert_threshold = QSpinBox(); self.goal_alert_threshold.setRange(50, 120); self.goal_alert_threshold.setSuffix(" %")
        notif_form.addRow(self.notifications_enabled)
        notif_form.addRow("Break reminder every:", self.break_interval)
        notif_form.addRow("Goal alert threshold:", self.goal_alert_threshold)
        settings_layout.addWidget(notif_group)

        # Idle Detection
        idle_group = QGroupBox("Idle Detection"); idle_form = QFormLayout(idle_group)
        self.idle_threshold = QSpinBox(); self.idle_threshold.setRange(1, 120); self.idle_threshold.setSuffix(" min")
        idle_form.addRow("Pause if idle for:", self.idle_threshold)
        settings_layout.addWidget(idle_group)

        # Schedule
        sched_group = QGroupBox("Custom Work Schedule"); sched_form = QFormLayout(sched_group)
        self.schedule_enabled = QCheckBox("Enable schedule guidance")
        self.work_days = QLineEdit()
        self.work_days.setPlaceholderText("Mon,Tue,Wed,Thu,Fri")
        self.work_start = QLineEdit(); self.work_start.setPlaceholderText("09:00")
        self.work_end = QLineEdit(); self.work_end.setPlaceholderText("17:00")
        sched_form.addRow(self.schedule_enabled)
        sched_form.addRow("Work days (CSV):", self.work_days)
        sched_form.addRow("Start time:", self.work_start)
        sched_form.addRow("End time:", self.work_end)
        settings_layout.addWidget(sched_group)

        settings_layout.addStretch()
        btn_layout = QHBoxLayout(); save_btn = QPushButton("Save Settings"); close_btn = QPushButton("Close")
        save_btn.clicked.connect(self.save_settings); close_btn.clicked.connect(self.close)
        btn_layout.addWidget(save_btn); btn_layout.addWidget(close_btn); settings_layout.addLayout(btn_layout)
        self.tabs.addTab(self.settings_tab, "Settings")

        # Analytics tab
        self.analytics_tab = QWidget(); a_layout = QVBoxLayout(self.analytics_tab)
        self.stats_label = QLabel()
        self.monthly_label = QLabel()
        self.yearly_label = QLabel()
        for l in (self.stats_label, self.monthly_label, self.yearly_label):
            l.setTextInteractionFlags(Qt.TextSelectableByMouse)
        a_layout.addWidget(self.stats_label)
        a_layout.addWidget(self.monthly_label)
        a_layout.addWidget(self.yearly_label)
        a_layout.addStretch()
        self.tabs.addTab(self.analytics_tab, "Analytics")

    def load_settings(self):
        self.daily_spin.setValue(int(self.db_manager.get_setting('daily_goal') or 8))
        self.weekly_spin.setValue(int(self.db_manager.get_setting('weekly_goal') or 40))
        self.notifications_enabled.setChecked(self.db_manager.get_bool_setting('notifications_enabled', True))
        self.break_interval.setValue(self.db_manager.get_int_setting('break_interval_min', 60))
        self.goal_alert_threshold.setValue(self.db_manager.get_int_setting('goal_alert_threshold', 90))
        self.idle_threshold.setValue(self.db_manager.get_int_setting('idle_threshold_min', 10))
        self.schedule_enabled.setChecked(self.db_manager.get_bool_setting('schedule_enabled', False))
        self.work_days.setText(self.db_manager.get_setting('work_days') or 'Mon,Tue,Wed,Thu,Fri')
        self.work_start.setText(self.db_manager.get_setting('work_start') or '09:00')
        self.work_end.setText(self.db_manager.get_setting('work_end') or '17:00')
        self.update_statistics()

    def save_settings(self):
        self.db_manager.set_setting('daily_goal', str(self.daily_spin.value()))
        self.db_manager.set_setting('weekly_goal', str(self.weekly_spin.value()))
        self.db_manager.set_setting('notifications_enabled', '1' if self.notifications_enabled.isChecked() else '0')
        self.db_manager.set_setting('break_interval_min', str(self.break_interval.value()))
        self.db_manager.set_setting('goal_alert_threshold', str(self.goal_alert_threshold.value()))
        self.db_manager.set_setting('idle_threshold_min', str(self.idle_threshold.value()))
        self.db_manager.set_setting('schedule_enabled', '1' if self.schedule_enabled.isChecked() else '0')
        self.db_manager.set_setting('work_days', self.work_days.text().strip())
        self.db_manager.set_setting('work_start', self.work_start.text().strip())
        self.db_manager.set_setting('work_end', self.work_end.text().strip())
        self.update_statistics()
        QMessageBox.information(self, "Saved", "Settings saved successfully")

    def update_statistics(self):
        today_secs = self.db_manager.get_daily_time_seconds()
        week_secs = self.db_manager.get_weekly_time_seconds()
        self.stats_label.setText(f"Today: {self.format_time(today_secs)}\nWeek: {self.format_time(week_secs)}\n")
        # Attempt to render charts if matplotlib is available
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from matplotlib.ticker import MaxNLocator

            # Monthly bar chart
            months = self.db_manager.get_monthly_hours(6)
            fig1, ax1 = plt.subplots(figsize=(5, 2.0), dpi=150)
            ax1.bar([m for m, _ in months], [h for _, h in months], color="#4CAF50")
            ax1.set_title('Last 6 months (hours)')
            ax1.set_ylabel('Hours')
            ax1.set_xlabel('Month')
            ax1.yaxis.set_major_locator(MaxNLocator(integer=True))
            buf1 = io.BytesIO(); fig1.tight_layout(); fig1.savefig(buf1, format='png', facecolor='#2b2b2b'); plt.close(fig1)
            buf1.seek(0); pm1 = QPixmap(); pm1.loadFromData(buf1.getvalue(), 'PNG'); self.monthly_label.setPixmap(pm1)

            # Yearly line chart
            years = self.db_manager.get_yearly_hours(5)
            fig2, ax2 = plt.subplots(figsize=(5, 2.0), dpi=150)
            ax2.plot([y for y, _ in years], [h for _, h in years], marker='o', color="#03A9F4")
            ax2.set_title('Yearly totals (hours)')
            ax2.set_ylabel('Hours')
            ax2.set_xlabel('Year')
            ax2.yaxis.set_major_locator(MaxNLocator(integer=True))
            buf2 = io.BytesIO(); fig2.tight_layout(); fig2.savefig(buf2, format='png', facecolor='#2b2b2b'); plt.close(fig2)
            buf2.seek(0); pm2 = QPixmap(); pm2.loadFromData(buf2.getvalue(), 'PNG'); self.yearly_label.setPixmap(pm2)
        except Exception:
            # If matplotlib not available or rendering fails, keep text fallback set above
            pass
        # Advanced analytics summaries
        months = self.db_manager.get_monthly_hours(6)
        years = self.db_manager.get_yearly_hours(5)
        self.monthly_label.setText("Last 6 months: " + ", ".join([f"{m}: {h}h" for m, h in months]))
        self.yearly_label.setText("Yearly: " + ", ".join([f"{y}: {h}h" for y, h in years]))

    def format_time(self, secs: int) -> str:
        h = secs // 3600; m = (secs % 3600)//60; s = secs % 60
        return f"{h}h {m}m {s}s"
