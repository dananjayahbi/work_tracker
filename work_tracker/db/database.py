import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

class DatabaseManager:
    def __init__(self, db_name: str = "work_tracker.db"):
        # Ensure DB stored inside this package's db directory
        base_dir = Path(__file__).resolve().parent  # work_tracker/db
        self.db_path = base_dir / db_name
        # Migrate old root-level DB if present
        try:
            root_dir = Path(__file__).resolve().parents[3]
            old_db = root_dir / db_name
            if old_db.exists() and not self.db_path.exists():
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                old_db.replace(self.db_path)
        except Exception:
            # Best-effort migration; ignore if path assumptions fail
            pass
        self.db_name = str(self.db_path)
        self.init_database()

    # --- Core Setup ---
    def init_database(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS work_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('daily_goal', '8'))
        cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('weekly_goal', '40'))
        # New defaults for enhanced features
        defaults: List[Tuple[str, str]] = [
            ('notifications_enabled', '1'),
            ('break_interval_min', '60'),
            ('idle_threshold_min', '10'),
            ('schedule_enabled', '0'),
            ('work_days', 'Mon,Tue,Wed,Thu,Fri'),
            ('work_start', '09:00'),
            ('work_end', '17:00'),
            ('goal_alert_threshold', '90'),
        ]
        for k, v in defaults:
            cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (k, v))
        conn.commit()
        conn.close()

    # --- Session Management ---
    def start_session(self) -> int:
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        now = datetime.now()
        cursor.execute('''
            INSERT INTO work_sessions (date, start_time, is_active) VALUES (?, ?, 1)
        ''', (now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S')))
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return session_id

    def end_session(self, session_id: int) -> int:
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        now = datetime.now()
        cursor.execute('SELECT start_time FROM work_sessions WHERE id = ?', (session_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return 0
        start_time_str = row[0]
        start_dt = datetime.strptime(start_time_str, '%H:%M:%S')
        today = datetime.now().date()
        start_full = datetime.combine(today, start_dt.time())
        duration = int((now - start_full).total_seconds())
        cursor.execute('''
            UPDATE work_sessions SET end_time = ?, duration = ?, is_active = 0 WHERE id = ?
        ''', (now.strftime('%H:%M:%S'), duration, session_id))
        conn.commit()
        conn.close()
        return duration

    def get_active_session(self) -> Optional[int]:
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM work_sessions WHERE date = ? AND is_active = 1', (datetime.now().strftime('%Y-%m-%d'),))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    # --- Time Aggregation ---
    def get_daily_time_seconds(self, date: Optional[str] = None) -> int:
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT COALESCE(SUM(duration),0) FROM work_sessions WHERE date = ? AND is_active = 0', (date,))
        total = cursor.fetchone()[0]
        # include active session
        cursor.execute('SELECT start_time FROM work_sessions WHERE date = ? AND is_active = 1', (date,))
        active = cursor.fetchone()
        if active:
            start_time_str = active[0]
            start_dt = datetime.strptime(start_time_str, '%H:%M:%S')
            today_dt = datetime.strptime(date, '%Y-%m-%d')
            start_full = datetime.combine(today_dt, start_dt.time())
            total += int((datetime.now() - start_full).total_seconds())
        conn.close()
        return int(total)

    def get_weekly_time_seconds(self) -> int:
        today = datetime.now().date()
        monday = today - timedelta(days=today.weekday())
        total = 0
        for i in range(7):
            day = (monday + timedelta(days=i)).strftime('%Y-%m-%d')
            total += self.get_daily_time_seconds(day)
        return total

    # --- Settings ---
    def get_setting(self, key: str) -> Optional[str]:
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def set_setting(self, key: str, value: str) -> None:
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
        conn.commit()
        conn.close()

    def get_int_setting(self, key: str, default: int) -> int:
        try:
            return int(self.get_setting(key) or default)
        except Exception:
            return default

    def get_bool_setting(self, key: str, default: bool) -> bool:
        val = self.get_setting(key)
        if val is None:
            return default
        return val in ('1', 'true', 'True', 'yes', 'on')

    # --- Analytics ---
    def get_analytics_data(self, days: int = 30) -> Dict[str, Any]:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days - 1)
        daily_data: List[Dict[str, Any]] = []
        for i in range(days):
            day = start_date + timedelta(days=i)
            secs = self.get_daily_time_seconds(day.strftime('%Y-%m-%d'))
            daily_data.append({
                'date': day,
                'seconds': secs,
                'hours': round(secs / 3600, 2)
            })
        # weekly grouping
        weekly_map: Dict[str, int] = defaultdict(int)
        for d in daily_data:
            week_monday = (d['date'] - timedelta(days=d['date'].weekday()))
            weekly_map[week_monday.strftime('%Y-%m-%d')] += d['seconds']
        weekly_data = [
            {
                'week_start': datetime.strptime(k, '%Y-%m-%d').date(),
                'seconds': v,
                'hours': round(v / 3600, 2)
            } for k, v in sorted(weekly_map.items())
        ]
        # hourly distribution
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''SELECT date, start_time, duration FROM work_sessions WHERE date >= ? AND is_active = 0''', (start_date.strftime('%Y-%m-%d'),))
        sessions = cursor.fetchall()
        conn.close()
        hourly_distribution: Dict[int, float] = defaultdict(float)
        for date_str, start_time_str, dur in sessions:
            try:
                st = datetime.strptime(start_time_str, '%H:%M:%S')
            except ValueError:
                continue
            hour = st.hour
            hourly_distribution[hour] += dur / 3600
        # productivity vs goal
        daily_goal = int(self.get_setting('daily_goal') or 8)
        productivity_data = []
        for d in daily_data:
            prod = (d['hours'] / daily_goal) * 100 if daily_goal else 0
            productivity_data.append({'date': d['date'], 'productivity': round(prod, 1)})
        return {
            'daily_data': daily_data,
            'weekly_data': weekly_data,
            'hourly_distribution': dict(hourly_distribution),
            'productivity_data': productivity_data
        }

    def get_monthly_hours(self, months: int = 12) -> List[Tuple[str, float]]:
        """Return list of (YYYY-MM, hours) for the last `months` months including current."""
        end = datetime.now().date().replace(day=1)
        # Build month keys from oldest to newest
        keys: List[str] = []
        cur = end
        for _ in range(months):
            keys.append(cur.strftime('%Y-%m'))
            # go to previous month first day
            year = cur.year
            month = cur.month - 1
            if month == 0:
                month = 12
                year -= 1
            cur = cur.replace(year=year, month=month)
        keys.reverse()
        # aggregate
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        start_date = datetime.strptime(keys[0] + '-01', '%Y-%m-%d').date()
        cursor.execute('SELECT date, duration FROM work_sessions WHERE date >= ? AND is_active = 0', (start_date.strftime('%Y-%m-%d'),))
        rows = cursor.fetchall(); conn.close()
        agg: Dict[str, int] = defaultdict(int)
        for d, dur in rows:
            key = d[:7]
            agg[key] += int(dur or 0)
        return [(k, round(agg.get(k, 0)/3600, 2)) for k in keys]

    def get_yearly_hours(self, years: int = 5) -> List[Tuple[str, float]]:
        """Return list of (YYYY, hours) for the last `years` years including current."""
        cur_year = datetime.now().year
        keys = [str(cur_year - i) for i in range(years - 1, -1, -1)]
        start_date = f"{keys[0]}-01-01"
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT date, duration FROM work_sessions WHERE date >= ? AND is_active = 0', (start_date,))
        rows = cursor.fetchall(); conn.close()
        agg: Dict[str, int] = defaultdict(int)
        for d, dur in rows:
            key = d[:4]
            agg[key] += int(dur or 0)
        return [(k, round(agg.get(k, 0)/3600, 2)) for k in keys]

    def is_daily_goal_reached(self, date_str: Optional[str] = None) -> bool:
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        goal_h = self.get_int_setting('daily_goal', 8)
        return self.get_daily_time_seconds(date_str) >= goal_h * 3600

    def consecutive_goal_days(self) -> int:
        """Compute streak ending today: consecutive days where daily goal reached."""
        today = datetime.now().date()
        streak = 0
        for i in range(365):  # cap to 1 year back for performance
            day = today - timedelta(days=i)
            if self.is_daily_goal_reached(day.strftime('%Y-%m-%d')):
                streak += 1
            else:
                break
        return streak
