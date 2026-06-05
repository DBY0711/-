"""系统通知 & 提示音"""
import winsound
import tkinter.messagebox as messagebox


def play_alarm():
    """播放提示音 — 使用 Windows 系统提示音"""
    # 800Hz, 500ms 的蜂鸣声，连续 3 声
    for _ in range(3):
        winsound.Beep(800, 300)
        winsound.Beep(1000, 300)


def show_notification(title: str, message: str):
    """弹出通知对话框"""
    messagebox.showinfo(title, message)
