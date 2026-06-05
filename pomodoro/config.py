"""默认配置"""

# 计时器默认值（秒）
DEFAULT_FOCUS_SECONDS = 25 * 60       # 25 分钟
DEFAULT_SHORT_BREAK_SECONDS = 5 * 60  # 5 分钟
DEFAULT_LONG_BREAK_SECONDS = 15 * 60  # 15 分钟
DEFAULT_LONG_BREAK_INTERVAL = 4       # 4 个番茄后进入长休息

# 窗口
WINDOW_WIDTH = 420
WINDOW_HEIGHT = 600
WINDOW_TITLE = "🍅 番茄钟"

# 数据目录
DATA_DIR = "data"
TASKS_FILE = "data/tasks.json"
STATS_FILE = "data/stats.json"
