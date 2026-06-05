"""番茄钟计时器核心逻辑

状态机:
    IDLE → FOCUS → SHORT_BREAK → FOCUS → ... ×N → LONG_BREAK → FOCUS → ...
    任意阶段可 PAUSE → 恢复回原阶段
"""

import threading
import time
from enum import Enum, auto
from typing import Callable, Optional


class TimerState(Enum):
    IDLE = auto()
    FOCUS = auto()
    SHORT_BREAK = auto()
    LONG_BREAK = auto()
    PAUSED = auto()


STATE_LABELS = {
    TimerState.IDLE: "准备就绪",
    TimerState.FOCUS: "专注中...",
    TimerState.SHORT_BREAK: "短休息",
    TimerState.LONG_BREAK: "长休息",
    TimerState.PAUSED: "已暂停",
}


class PomodoroTimer:
    """番茄钟计时器，在后台线程中运行倒计时"""

    def __init__(
        self,
        focus_seconds: int = 25 * 60,
        short_break_seconds: int = 5 * 60,
        long_break_seconds: int = 15 * 60,
        long_break_interval: int = 4,
    ):
        self.focus_seconds = focus_seconds
        self.short_break_seconds = short_break_seconds
        self.long_break_seconds = long_break_seconds
        self.long_break_interval = long_break_interval

        # 运行时状态
        self._state = TimerState.IDLE
        self._previous_state = TimerState.IDLE  # 暂停前的状态
        self._remaining = focus_seconds
        self._pomodoro_count = 0  # 当前周期完成的番茄数
        self._total_pomodoros = 0  # 总共完成的番茄数

        # 线程控制
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

        # 回调（由 UI 层设置）
        self.on_tick: Optional[Callable[[int, TimerState], None]] = None  # (remaining, state)
        self.on_state_change: Optional[Callable[[TimerState], None]] = None
        self.on_complete: Optional[Callable[[TimerState], None]] = None  # 计时到时

    # ── 属性 ──────────────────────────────────────────

    @property
    def state(self) -> TimerState:
        return self._state

    @property
    def remaining(self) -> int:
        return self._remaining

    @property
    def pomodoro_count(self) -> int:
        return self._pomodoro_count

    @property
    def total_pomodoros(self) -> int:
        return self._total_pomodoros

    @property
    def is_running(self) -> bool:
        return self._running

    # ── 公共方法 ──────────────────────────────────────

    def start(self):
        """开始或恢复计时"""
        with self._lock:
            if self._state == TimerState.IDLE:
                self._transition_to(TimerState.FOCUS)
            elif self._state == TimerState.PAUSED:
                self._transition_to(self._previous_state)
            else:
                return  # 已经在运行中
        self._start_thread()

    def pause(self):
        """暂停计时"""
        with self._lock:
            if self._state in (TimerState.FOCUS, TimerState.SHORT_BREAK, TimerState.LONG_BREAK):
                self._previous_state = self._state
                self._transition_to(TimerState.PAUSED)
                self._running = False

    def reset(self):
        """重置计时器到初始状态"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        with self._lock:
            self._state = TimerState.IDLE
            self._previous_state = TimerState.IDLE
            self._remaining = self.focus_seconds
            self._pomodoro_count = 0
            self._notify_tick()

    def skip(self):
        """跳过当前阶段"""
        self._running = False
        with self._lock:
            self._handle_completion()

    def get_current_duration(self) -> int:
        """返回当前阶段的总时长（秒）"""
        if self._state in (TimerState.IDLE, TimerState.FOCUS):
            return self.focus_seconds
        elif self._state == TimerState.SHORT_BREAK:
            return self.short_break_seconds
        elif self._state == TimerState.LONG_BREAK:
            return self.long_break_seconds
        elif self._state == TimerState.PAUSED:
            if self._previous_state in (TimerState.IDLE, TimerState.FOCUS):
                return self.focus_seconds
            elif self._previous_state == TimerState.SHORT_BREAK:
                return self.short_break_seconds
            else:
                return self.long_break_seconds
        return self.focus_seconds

    def update_settings(
        self,
        focus_seconds: int,
        short_break_seconds: int,
        long_break_seconds: int,
        long_break_interval: int,
    ):
        """更新设置（仅在 IDLE 状态下生效）"""
        self.focus_seconds = focus_seconds
        self.short_break_seconds = short_break_seconds
        self.long_break_seconds = long_break_seconds
        self.long_break_interval = long_break_interval
        if self._state == TimerState.IDLE:
            self._remaining = focus_seconds
            self._notify_tick()

    # ── 内部方法 ──────────────────────────────────────

    def _transition_to(self, new_state: TimerState):
        """状态切换"""
        old_state = self._state
        self._state = new_state

        # 进入新状态时初始化倒计时
        if new_state == TimerState.FOCUS:
            self._remaining = self.focus_seconds
        elif new_state == TimerState.SHORT_BREAK:
            self._remaining = self.short_break_seconds
        elif new_state == TimerState.LONG_BREAK:
            self._remaining = self.long_break_seconds
        # PAUSED 不改变 remaining

        if self.on_state_change and old_state != new_state:
            self.on_state_change(new_state)

    def _handle_completion(self):
        """计时到时，切换到下一阶段"""
        if self._state == TimerState.FOCUS:
            self._pomodoro_count += 1
            self._total_pomodoros += 1
            if self._pomodoro_count % self.long_break_interval == 0:
                self._transition_to(TimerState.LONG_BREAK)
            else:
                self._transition_to(TimerState.SHORT_BREAK)
        elif self._state in (TimerState.SHORT_BREAK, TimerState.LONG_BREAK):
            self._transition_to(TimerState.FOCUS)

        if self.on_complete:
            self.on_complete(self._state)

    def _notify_tick(self):
        """通知 UI 更新（在主线程安全调用）"""
        if self.on_tick:
            self.on_tick(self._remaining, self._state)

    def _start_thread(self):
        """启动后台计时线程"""
        self._running = True
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """后台线程主循环"""
        while self._running:
            time.sleep(1)
            with self._lock:
                if not self._running:
                    break
                self._remaining -= 1
                self._notify_tick()
                if self._remaining <= 0:
                    self._running = False
                    self._handle_completion()
                    self._notify_tick()
                    break
