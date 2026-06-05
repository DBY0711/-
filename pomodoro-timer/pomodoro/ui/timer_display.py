"""大号计时器显示区域"""
import tkinter as tk
from ..timer import TimerState, STATE_LABELS


class TimerDisplay(tk.Frame):
    """显示倒计时和当前状态"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg="#fafafa")

        # 倒计时数字（大号）
        self.time_label = tk.Label(
            self,
            text="25:00",
            font=("Helvetica", 48, "bold"),
            fg="#333333",
            bg="#fafafa",
        )
        self.time_label.pack(pady=(40, 10))

        # 状态标签
        self.status_label = tk.Label(
            self,
            text=STATE_LABELS[TimerState.IDLE],
            font=("Microsoft YaHei", 14),
            fg="#888888",
            bg="#fafafa",
        )
        self.status_label.pack(pady=(0, 20))

        # 进度条（占位 — 后续可选实现圆环进度）

    def update_display(self, remaining_seconds: int, state: TimerState):
        """更新显示的倒计时和状态"""
        minutes = remaining_seconds // 60
        seconds = remaining_seconds % 60
        self.time_label.config(text=f"{minutes:02d}:{seconds:02d}")

        status_text = STATE_LABELS.get(state, "")
        self.status_label.config(text=status_text)

        # 根据状态切换颜色
        colors = {
            TimerState.IDLE: "#888888",
            TimerState.FOCUS: "#e74c3c",
            TimerState.SHORT_BREAK: "#2ecc71",
            TimerState.LONG_BREAK: "#3498db",
            TimerState.PAUSED: "#f39c12",
        }
        color = colors.get(state, "#888888")
        self.status_label.config(fg=color)
        self.time_label.config(fg=color)
