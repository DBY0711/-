"""控制按钮面板：开始 / 暂停 / 重置 / 跳过"""
import tkinter as tk
from typing import Callable


class ControlPanel(tk.Frame):
    """开始、暂停、重置、跳过按钮"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg="#fafafa")

        btn_frame = tk.Frame(self, bg="#fafafa")
        btn_frame.pack(pady=10)

        btn_style = {
            "font": ("Microsoft YaHei", 11),
            "width": 8,
            "relief": "flat",
            "cursor": "hand2",
        }

        self.start_btn = tk.Button(
            btn_frame, text="▶ 开始", bg="#27ae60", fg="white",
            activebackground="#2ecc71", activeforeground="white",
            **btn_style,
        )
        self.start_btn.pack(side="left", padx=4)

        self.pause_btn = tk.Button(
            btn_frame, text="⏸ 暂停", bg="#f39c12", fg="white",
            activebackground="#f1c40f", activeforeground="white",
            state="disabled", **btn_style,
        )
        self.pause_btn.pack(side="left", padx=4)

        self.reset_btn = tk.Button(
            btn_frame, text="↺ 重置", bg="#95a5a6", fg="white",
            activebackground="#bdc3c7", activeforeground="white",
            **btn_style,
        )
        self.reset_btn.pack(side="left", padx=4)

        self.skip_btn = tk.Button(
            btn_frame, text="⏭ 跳过", bg="#7f8c8d", fg="white",
            activebackground="#95a5a6", activeforeground="white",
            state="disabled", **btn_style,
        )
        self.skip_btn.pack(side="left", padx=4)

    def bind_start(self, callback: Callable):
        self.start_btn.config(command=callback)

    def bind_pause(self, callback: Callable):
        self.pause_btn.config(command=callback)

    def bind_reset(self, callback: Callable):
        self.reset_btn.config(command=callback)

    def bind_skip(self, callback: Callable):
        self.skip_btn.config(command=callback)

    def set_running_state(self, running: bool):
        """更新按钮状态"""
        if running:
            self.start_btn.config(state="disabled")
            self.pause_btn.config(state="normal")
            self.skip_btn.config(state="normal")
        else:
            self.start_btn.config(state="normal")
            self.pause_btn.config(state="disabled")
            self.skip_btn.config(state="disabled")

    def set_idle_state(self):
        """空闲状态下的按钮状态"""
        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled")
        self.skip_btn.config(state="disabled")
