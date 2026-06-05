"""番茄钟主应用 — 组装所有面板，连接计时器与 UI"""
import tkinter as tk
from datetime import date
from typing import List

from .config import (
    DEFAULT_FOCUS_SECONDS, DEFAULT_SHORT_BREAK_SECONDS,
    DEFAULT_LONG_BREAK_SECONDS, DEFAULT_LONG_BREAK_INTERVAL,
    WINDOW_TITLE, WINDOW_WIDTH, WINDOW_HEIGHT,
    TASKS_FILE, STATS_FILE,
)
from .timer import PomodoroTimer, TimerState
from .models.task import Task
from .models.stats import DailyStats
from .utils.storage import load_json, save_json
from .utils.notification import play_alarm, show_notification
from .ui.timer_display import TimerDisplay
from .ui.control_panel import ControlPanel
from .ui.task_panel import TaskPanel
from .ui.stats_panel import StatsPanel
from .ui.settings_dialog import SettingsDialog


class PomodoroApp:
    """番茄钟主应用"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.configure(bg="#fafafa")

        # ── 计时器 ────────────────────────────────────
        self.timer = PomodoroTimer(
            focus_seconds=DEFAULT_FOCUS_SECONDS,
            short_break_seconds=DEFAULT_SHORT_BREAK_SECONDS,
            long_break_seconds=DEFAULT_LONG_BREAK_SECONDS,
            long_break_interval=DEFAULT_LONG_BREAK_INTERVAL,
        )
        self._setup_timer_callbacks()

        # ── UI 面板 ────────────────────────────────────
        self._build_ui()

        # ── 数据加载 ───────────────────────────────────
        self._load_data()

        # ── 窗口关闭处理 ──────────────────────────────
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI 构建 ────────────────────────────────────────

    def _build_ui(self):
        """构建全部 UI 面板"""

        # 标题栏
        title_bar = tk.Frame(self.root, bg="#e74c3c", height=50)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        tk.Label(
            title_bar, text="🍅 番茄钟", font=("Microsoft YaHei", 16, "bold"),
            fg="white", bg="#e74c3c",
        ).pack(expand=True)

        # 计时器显示
        self.timer_display = TimerDisplay(self.root)
        self.timer_display.pack(fill="x", padx=20)

        # 控制按钮
        self.control_panel = ControlPanel(self.root)
        self.control_panel.pack(fill="x", padx=20)
        self._bind_controls()

        # 今日统计
        self.stats_panel = StatsPanel(self.root)
        self.stats_panel.pack(fill="x", padx=16, pady=(12, 4))

        # 任务列表
        self.task_panel = TaskPanel(self.root)
        self.task_panel.pack(fill="both", expand=True, padx=16, pady=(4, 4))
        self.task_panel.on_task_change = self._save_tasks

        # 底部设置按钮
        bottom = tk.Frame(self.root, bg="#fafafa")
        bottom.pack(fill="x", pady=(4, 12))
        tk.Button(
            bottom, text="⚙ 设置", font=("Microsoft YaHei", 10),
            bg="#ecf0f1", fg="#333333", relief="flat", cursor="hand2",
            activebackground="#dfe6e9", command=self._open_settings,
        ).pack()

    def _bind_controls(self):
        """绑定控制按钮事件"""
        self.control_panel.bind_start(self._on_start)
        self.control_panel.bind_pause(self._on_pause)
        self.control_panel.bind_reset(self._on_reset)
        self.control_panel.bind_skip(self._on_skip)

    # ── 计时器回调设置 ────────────────────────────────

    def _setup_timer_callbacks(self):
        """设置计时器的回调，所有 UI 更新通过 root.after 抛回主线程"""

        def on_tick(remaining: int, state: TimerState):
            self.root.after(0, lambda: self.timer_display.update_display(remaining, state))

        def on_state_change(state: TimerState):
            def _update():
                is_running = state not in (TimerState.IDLE, TimerState.PAUSED)
                self.control_panel.set_running_state(is_running)
                if state == TimerState.IDLE:
                    self.control_panel.set_idle_state()
                self.timer_display.update_display(self.timer.remaining, state)
            self.root.after(0, _update)

        def on_complete(state: TimerState):
            def _handle():
                play_alarm()
                if state == TimerState.FOCUS:
                    # 刚刚结束的是专注阶段
                    self.stats_panel.add_pomodoro()
                    self.stats_panel.add_focus_minutes(self.timer.focus_seconds // 60)
                    self.task_panel.increment_current_task_pomodoro()
                    self._save_stats()
                    self._save_tasks()
                    show_notification("🍅 番茄钟", "专注时间结束！休息一下吧～")
                elif state == TimerState.SHORT_BREAK:
                    show_notification("☕ 休息结束", "短休息结束，开始新的番茄！")
                elif state == TimerState.LONG_BREAK:
                    show_notification("🌟 休息结束", "长休息结束，继续加油！")
                # 自动开始下一阶段
                self.timer.start()
            self.root.after(0, _handle)

        self.timer.on_tick = on_tick
        self.timer.on_state_change = on_state_change
        self.timer.on_complete = on_complete

    # ── 按钮事件 ──────────────────────────────────────

    def _on_start(self):
        self.timer.start()

    def _on_pause(self):
        self.timer.pause()
        self.control_panel.set_idle_state()

    def _on_reset(self):
        self.timer.reset()
        self.control_panel.set_idle_state()
        self.timer_display.update_display(self.timer.remaining, self.timer.state)

    def _on_skip(self):
        self.timer.skip()

    def _open_settings(self):
        result = SettingsDialog.open(
            self.root,
            focus=self.timer.focus_seconds,
            short_break=self.timer.short_break_seconds,
            long_break=self.timer.long_break_seconds,
            interval=self.timer.long_break_interval,
        )
        if result:
            focus, short_b, long_b, interval = result
            self.timer.update_settings(focus, short_b, long_b, interval)
            self.timer_display.update_display(self.timer.remaining, self.timer.state)

    # ── 数据持久化 ────────────────────────────────────

    def _load_data(self):
        """加载任务和统计数据"""
        # 加载任务
        task_dicts = load_json(TASKS_FILE, [])
        tasks = [Task.from_dict(d) for d in task_dicts]
        self.task_panel.load_tasks(tasks)

        # 加载今日统计
        stat_dicts = load_json(STATS_FILE, [])
        today = date.today().isoformat()
        for sd in stat_dicts:
            if sd.get("date") == today:
                self.stats_panel.load_stats(DailyStats.from_dict(sd))
                return
        # 没有今日数据，从零开始
        self.stats_panel.load_stats(DailyStats(date=today))

    def _save_tasks(self):
        """保存任务列表"""
        tasks = self.task_panel.get_tasks()
        save_json(TASKS_FILE, [t.to_dict() for t in tasks])

    def _save_stats(self):
        """保存今日统计"""
        stats = self.stats_panel.get_today_stats()
        # 读取全部统计，更新今日条目
        all_stats = load_json(STATS_FILE, [])
        today = date.today().isoformat()
        found = False
        for i, s in enumerate(all_stats):
            if s.get("date") == today:
                all_stats[i] = stats.to_dict()
                found = True
                break
        if not found:
            all_stats.append(stats.to_dict())
        save_json(STATS_FILE, all_stats)

    def _on_close(self):
        """窗口关闭时保存数据并退出"""
        self.timer.reset()
        self._save_tasks()
        self._save_stats()
        self.root.destroy()

    # ── 启动 ──────────────────────────────────────────

    def run(self):
        self.root.mainloop()
