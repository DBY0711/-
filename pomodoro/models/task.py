"""任务数据模型"""
from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class Task:
    """单个任务"""
    title: str
    pomodoro_count: int = 0       # 已完成的番茄数
    estimated: int = 1            # 预估番茄数
    completed: bool = False
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "pomodoro_count": self.pomodoro_count,
            "estimated": self.estimated,
            "completed": self.completed,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            title=d["title"],
            pomodoro_count=d.get("pomodoro_count", 0),
            estimated=d.get("estimated", 1),
            completed=d.get("completed", False),
            created_at=d.get("created_at", datetime.now().isoformat()),
        )
