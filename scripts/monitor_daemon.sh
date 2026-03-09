#!/bin/bash
# Trae Bridge 进度监控和汇报系统

PROJECT_DIR="/Users/rzhu/Documents/GitHub/trae-bridge"
LOG_DIR="$PROJECT_DIR/logs"
PID_FILE="$PROJECT_DIR/.monitor.pid"
REPORT_INTERVAL=600  # 10分钟

# 创建日志目录
mkdir -p "$LOG_DIR"

# 检查是否已经在运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Monitor already running (PID: $OLD_PID)"
        exit 1
    fi
fi

# 保存当前 PID
echo $$ > "$PID_FILE"

echo "[$$(date '+%Y-%m-%d %H:%M:%S')] 监控启动 (PID: $$)"

# 清理函数
cleanup() {
    rm -f "$PID_FILE"
    echo "[$$(date '+%Y-%m-%d %H:%M:%S')] 监控停止"
    exit 0
}

trap cleanup EXIT INT TERM

# 主循环
while true; do
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    LOG_FILE="$LOG_DIR/monitor_$(date '+%Y%m%d').log"
    
    echo "[$TIMESTAMP] ===== 进度检查 =====" >> "$LOG_FILE"
    
    # 1. 检查 Claude Code 进程
    CLAUDE_PIDS=$(pgrep -f "claude.*trae-bridge" | tr '\n' ' ')
    if [ -n "$CLAUDE_PIDS" ]; then
        echo "[$TIMESTAMP] ✅ Claude Code 运行中 (PIDs: $CLAUDE_PIDS)" >> "$LOG_FILE"
    else
        echo "[$TIMESTAMP] ⚠️ Claude Code 未运行" >> "$LOG_FILE"
        
        # 尝试重启
        echo "[$TIMESTAMP] 尝试重启 Claude Code..." >> "$LOG_FILE"
        cd "$PROJECT_DIR"
        
        # 确保 tmux 会话存在
        if ! tmux has-session -t trae-bridge 2>/dev/null; then
            tmux new-session -d -s trae-bridge
        fi
        
        # 重启 Claude Code
        tmux send-keys -t trae-bridge C-c
        sleep 1
        tmux send-keys -t trae-bridge 'cd /Users/rzhu/Documents/GitHub/trae-bridge && claude --permission-mode bypassPermissions --print "Continue implementing trae-bridge from current state. Check existing files in src/ and continue development. Focus on: 1) Complete any pending implementations 2) Create api_server.py for REST API 3) Create bridge.py main entry 4) Test integration"' Enter
        
        echo "[$TIMESTAMP] ✅ Claude Code 已重启" >> "$LOG_FILE"
    fi
    
    # 2. 统计代码文件
    PY_COUNT=$(find "$PROJECT_DIR" -name "*.py" -type f 2>/dev/null | wc -l)
    TOTAL_LINES=$(find "$PROJECT_DIR" -name "*.py" -type f -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}')
    echo "[$TIMESTAMP] 📊 Python文件: $PY_COUNT, 总代码行: ${TOTAL_LINES:-0}" >> "$LOG_FILE"
    
    # 3. 检查 Trae 运行状态
    if pgrep -f "Trae.app" > /dev/null; then
        echo "[$TIMESTAMP] ✅ Trae.app 运行中" >> "$LOG_FILE"
    else
        echo "[$TIMESTAMP] ⚠️ Trae.app 未运行" >> "$LOG_FILE"
    fi
    
    # 4. 列出最近修改的文件
    echo "[$TIMESTAMP] 📝 最近修改的文件:" >> "$LOG_FILE"
    ls -lt "$PROJECT_DIR"/*.py "$PROJECT_DIR"/src/*.py "$PROJECT_DIR"/scripts/*.py 2>/dev/null | head -10 >> "$LOG_FILE"
    
    # 5. 检查是否有新的提交
    cd "$PROJECT_DIR"
    if [ -d .git ]; then
        GIT_STATUS=$(git status --short 2>/dev/null | wc -l)
        echo "[$TIMESTAMP] 🔄 Git未提交更改: $GIT_STATUS 个文件" >> "$LOG_FILE"
    fi
    
    # 6. 读取最新代码文件列表
    echo "[$TIMESTAMP] 📁 项目结构:" >> "$LOG_FILE"
    find "$PROJECT_DIR" -type f \( -name "*.py" -o -name "*.sh" -o -name "*.md" -o -name "*.txt" \) ! -path "*/.git/*" ! -path "*/logs/*" | sort >> "$LOG_FILE"
    
    echo "[$TIMESTAMP] ===== 检查完成 =====" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
    
    # 等待下一次检查
    sleep $REPORT_INTERVAL
done
