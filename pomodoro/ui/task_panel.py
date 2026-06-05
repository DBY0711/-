"""任务列表面板"""
import tkinter as tk
from tkinter import simpledialog, messagebox
from typing import List, Callable

from ..models.task import Task


class TaskPanel(tk.LabelFrame):
    """任务列表：添加 / 完成 / 删除"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, text="📋 任务列表", font=("Microsoft YaHei", 11, "bold"),
                         bg="#fafafa", fg="#333333", **kwargs)

        self._tasks: List[Task] = []
        self._list_frame = tk.Frame(self, bg="#fafafa")
        self._list_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        # 添加任务按钮
        add_btn = tk.Button(
            self, text="＋ 添加新任务", font=("Microsoft YaHei", 10),
            bg="#3498db", fg="white", relief="flat", cursor="hand2",
            activebackground="#5dade2", activeforeground="white",
            command=self._add_task,
        )
        add_btn.pack(fill="x", padx=8, pady=(0, 8))

        # 回调
        self.on_task_change: Callable = lambda: None  # 任务列表变化时通知外部

    # ── 公开方法 ──────────────────────────────────────

    def load_tasks(self, tasks: List[Task]):
        """加载任务列表"""
        self._tasks = tasks
        self._refresh_list()

    def get_tasks(self) -> List[Task]:
        return self._tasks

    def increment_current_task_pomodoro(self):
        """给当前进行中的任务增加一个番茄计数"""
        for task in self._tasks:
            if not task.completed:
                task.pomodoro_count += 1
                self._refresh_list()
                self.on_task_change()
                return

    def get_active_task_title(self) -> str:
        """获取当前进行中的任务标题"""
        for task in self._tasks:
            if not task.completed:
                return task.title
        return ""

    # ── 内部方法 ──────────────────────────────────────

    def _add_task(self):
        title = simpledialog.askstring("添加任务", "请输入任务名称：", parent=self)
        if title and title.strip():
            task = Task(title=title.strip())
            self._tasks.append(task)
            self._refresh_list()
            self.on_task_change()

    def _toggle_task(self, task: Task):
        task.completed = not task.completed
        self._refresh_list()
        self.on_task_change()

    def _delete_task(self, task: Task):
        if messagebox.askyesno("删除任务", f"确定删除「{task.title}」吗？", parent=self):
            self._tasks.remove(task)
            self._refresh_list()
            self.on_task_change()

    def _refresh_list(self):
        """刷新任务列表显示"""
        for widget in self._list_frame.winfo_children():
            widget.destroy()

        if not self._tasks:
            empty_label = tk.Label(
                self._list_frame, text="暂无任务，点击下方按钮添加",
                font=("Microsoft YaHei", 10), fg="#aaaaaa", bg="#fafafa",
            )
            empty_label.pack(pady=20)
            return

        for task in self._tasks:
            self._create_task_row(task)

    def _create_task_row(self, task: Task):
        """创建单个任务行"""
        row = tk.Frame(self._list_frame, bg="#fafafa", pady=3)
        row.pack(fill="x")

        # 完成复选框
        check_text = "☑" if task.completed else "☐"
        check_btn = tk.Button(
            row, text=check_text, font=("Microsoft YaHei", 12),
            bg="#fafafa", fg="#27ae60" if task.completed else "#cccccc",
            relief="flat", cursor="hand2", bd=0,
            activebackground="#f0f0f0",
            command=lambda t=task: self._toggle_task(t),
        )
        check_btn.pack(side="left")

        # 任务标题
        title_style = ("Microsoft YaHei", 10)
        if task.completed:
            title_style = ("Microsoft YaHei", 10, "overstrike")
        title_label = tk.Label(
            row, text=task.title, font=title_style,
            fg="#888888" if task.completed else "#333333",
            bg="#fafafa", anchor="w",
        )
        title_label.pack(side="left", padx=(4, 8), fill="x", expand=True)

        # 番茄计数
        tomato_text = "🍅" * task.pomodoro_count
        if task.pomodoro_count > 0:
            tomato_label = tk.Label(
                row, text=tomato_text, font=("Segoe UI Emoji", 10),
                bg="#fafafa", fg="#e74c3c",
            )
            tomato_label.pack(side="right", padx=(0, 4))

        # 预估番茄数（灰色）
        if task.estimated > 0 and not task.completed:
            estimated_label = tk.Label(
                row, text=f"预计 {task.estimated}🍅", font=("Microsoft YaHei", 8),
                bg="#fafafa", fg="#cccccc",
            )
            estimated_label.pack(side="right", padx=(0, 4))

        # 删除按钮
        del_btn = tk.Button(
            row, text="✕", font=("Microsoft YaHei", 10),
            bg="#fafafa", fg="#e74c3c", relief="flat", cursor="hand2", bd=0,
            activebackground="#f0f0f0", activeforeground="#c0392b",
            command=lambda t=task: self._delete_task(t),
        )
        del_btn.pack(side="right", padx=(0, 2))
