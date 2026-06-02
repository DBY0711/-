"""统计数据模型"""
from dataclasses import dataclass, field
from datetime import date


@dataclass
class DailyStats:
    """每日统计"""
    date: str = field(default_factory=lambda: date.today().isoformat())
    completed_pomodoros: int = 0
    total_focus_minutes: int = 0
    tasks_completed: int = 0

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "completed_pomodoros": self.completed_pomodoros,
            "total_focus_minutes": self.total_focus_minutes,
            "tasks_completed": self.tasks_completed,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DailyStats":
        return cls(
            date=d.get("date", date.today().isoformat()),
            completed_pomodoros=d.get("completed_pomodoros", 0),
            total_focus_minutes=d.get("total_focus_minutes", 0),
            tasks_completed=d.get("tasks_completed", 0),
        )
