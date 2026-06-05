"""今日统计面板"""
import tkinter as tk
from datetime import date

from ..models.stats import DailyStats


class StatsPanel(tk.LabelFrame):
    """显示今日番茄完成数、总专注时长"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="📊 今日统计", font=("Microsoft YaHei", 11, "bold"),
                         bg="#fafafa", fg="#333333", **kwargs)

        self._stats = DailyStats()

        # 番茄图标行
        self.tomato_row = tk.Label(
            self, text="", font=("Segoe UI Emoji", 18),
            bg="#fafafa", fg="#e74c3c",
        )
        self.tomato_row.pack(pady=(6, 2))

        # 文字统计
        self.stats_label = tk.Label(
            self, text="", font=("Microsoft YaHei", 10),
            bg="#fafafa", fg="#666666",
        )
        self.stats_label.pack(pady=(0, 8))

        self._refresh_display()

    # ── 公开方法 ──────────────────────────────────────

    def add_pomodoro(self):
        """记录一个完成的番茄"""
        today = date.today().isoformat()
        if self._stats.date != today:
            self._stats = DailyStats(date=today)
        self._stats.completed_pomodoros += 1
        self._stats.total_focus_minutes += 25  # 默认 25 分钟，可由外部覆盖
        self._refresh_display()

    def add_focus_minutes(self, minutes: int):
        """追加专注分钟数"""
        today = date.today().isoformat()
        if self._stats.date != today:
            self._stats = DailyStats(date=today, completed_pomodoros=self._stats.completed_pomodoros)
        self._stats.total_focus_minutes += minutes

    def record_task_completed(self):
        """记录一个完成的任务"""
        self._stats.tasks_completed += 1
        self._refresh_display()

    def get_today_stats(self) -> DailyStats:
        today = date.today().isoformat()
        if self._stats.date != today:
            self._stats = DailyStats(date=today)
        return self._stats

    def load_stats(self, stats: DailyStats):
        """加载历史统计数据"""
        today = date.today().isoformat()
        if stats.date == today:
            self._stats = stats
        else:
            # 加载的是旧数据，保留
            self._stats = stats
        self._refresh_display()

    def set_focus_minutes(self, minutes: int):
        """设置每次专注的分钟数（用于统计计算）"""
        self._focus_minutes = minutes

    # ── 内部方法 ──────────────────────────────────────

    def _refresh_display(self):
        count = self._stats.completed_pomodoros
        minutes = self._stats.total_focus_minutes
        self.tomato_row.config(text="🍅" * min(count, 20))  # 最多显示 20 个
        self.stats_label.config(
            text=f"已完成 {count} 个番茄 · 专注 {minutes} 分钟"
        )
