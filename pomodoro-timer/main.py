"""番茄钟桌面应用入口"""
from pomodoro.app import PomodoroApp


def main():
    app = PomodoroApp()
    app.run()


if __name__ == "__main__":
    main()
