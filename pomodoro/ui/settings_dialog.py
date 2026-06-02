"""设置对话框 — 自定义时长和周期"""
import tkinter as tk
from tkinter import ttk, simpledialog
from typing import Optional, Tuple


class SettingsDialog(tk.Toplevel):
    """番茄钟设置对话框"""

    def __init__(self, parent, focus: int, short_break: int, long_break: int, interval: int):
        super().__init__(parent)
        self.title("⚙ 设置")
        self.geometry("300x280")
        self.resizable(False, False)
        self.configure(bg="#fafafa")

        # 使窗口居中于父窗口
        self.transient(parent)
        self.grab_set()

        self.result = None  # 用户点击确认后设置

        # ── 输入区域 ──────────────────────────────────
        pad = {"padx": 20, "pady": (8, 2), "anchor": "w"}

        tk.Label(self, text="专注时长（分钟）", font=("Microsoft YaHei", 10),
                 bg="#fafafa").pack(**pad)
        self.focus_var = tk.IntVar(value=focus // 60)
        ttk.Spinbox(self, from_=1, to=120, textvariable=self.focus_var,
                   font=("Microsoft YaHei", 12), width=8, justify="center",
                   state="readonly").pack(padx=20, pady=(2, 10))

        tk.Label(self, text="短休息时长（分钟）", font=("Microsoft YaHei", 10),
                 bg="#fafafa").pack(**pad)
        self.short_var = tk.IntVar(value=short_break // 60)
        ttk.Spinbox(self, from_=1, to=30, textvariable=self.short_var,
                   font=("Microsoft YaHei", 12), width=8, justify="center",
                   state="readonly").pack(padx=20, pady=(2, 10))

        tk.Label(self, text="长休息时长（分钟）", font=("Microsoft YaHei", 10),
                 bg="#fafafa").pack(**pad)
        self.long_var = tk.IntVar(value=long_break // 60)
        ttk.Spinbox(self, from_=1, to=60, textvariable=self.long_var,
                   font=("Microsoft YaHei", 12), width=8, justify="center",
                   state="readonly").pack(padx=20, pady=(2, 10))

        tk.Label(self, text="长休息间隔（几个番茄后）", font=("Microsoft YaHei", 10),
                 bg="#fafafa").pack(**pad)
        self.interval_var = tk.IntVar(value=interval)
        ttk.Spinbox(self, from_=1, to=10, textvariable=self.interval_var,
                   font=("Microsoft YaHei", 12), width=8, justify="center",
                   state="readonly").pack(padx=20, pady=(2, 10))

        # ── 按钮 ──────────────────────────────────────
        btn_frame = tk.Frame(self, bg="#fafafa")
        btn_frame.pack(pady=15)

        tk.Button(btn_frame, text="保存", font=("Microsoft YaHei", 10),
                  bg="#27ae60", fg="white", relief="flat", width=8,
                  command=self._on_save).pack(side="left", padx=6)
        tk.Button(btn_frame, text="取消", font=("Microsoft YaHei", 10),
                  bg="#95a5a6", fg="white", relief="flat", width=8,
                  command=self.destroy).pack(side="left", padx=6)

    def _on_save(self):
        self.result = (
            self.focus_var.get() * 60,
            self.short_var.get() * 60,
            self.long_var.get() * 60,
            self.interval_var.get(),
        )
        self.destroy()

    @classmethod
    def open(cls, parent, focus: int, short_break: int, long_break: int, interval: int) -> Optional[Tuple[int, int, int, int]]:
        """打开设置对话框，返回 (focus, short_break, long_break, interval) 或 None"""
        dlg = cls(parent, focus, short_break, long_break, interval)
        dlg.wait_window()
        return dlg.result
