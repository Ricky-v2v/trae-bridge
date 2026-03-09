#!/bin/bash
# Trae Bridge 开发监控脚本
# 每10分钟检查一次 Claude Code 进度

SESSION="trae-bridge"
LOG_FILE="/Users/rzhu/Documents/GitHub/trae-bridge/monitor.log"
LAST_CHECK_FILE="/Users/rzhu/Documents/GitHub/trae-bridge/.last_check"
FEISHU_CHAT="ou_aa727e433c0f6ccf3187578c6a0dedb3"

# 确保日志文件存在
touch "$LOG_FILE"

# 获取当前时间
NOW=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$NOW] ===== 监控检查开始 =====" >> "$LOG_FILE"

# 检查 tmux 会话是否存在
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "[$NOW] ⚠️ tmux 会话 $SESSION 不存在，尝试重启..." >> "$LOG_FILE"
    
    # 重启会话
    cd /Users/rzhu/Documents/GitHub/trae-bridge
    tmux new-session -d -s "$SESSION"
    sleep 1
    tmux send-keys -t "$SESSION" 'cd /Users/rzhu/Documents/GitHub/trae-bridge && claude --permission-mode bypassPermissions --print "Continue implementing trae-bridge from where we left off. Check current progress in the codebase and continue development."' Enter
    
    echo "[$NOW] ✅ Claude Code 已重启" >> "$LOG_FILE"
    
    # 发送飞书通知
    curl -s -X POST "http://localhost:8080/message" \
        -H "Content-Type: application/json" \
        -d "{\"channel\":\"feishu\",\"target\":\"$FEISHU_CHAT\",\"message\":\"[Trae Bridge] Claude Code 进程已死亡，已自动重启\"}" 2>/dev/null || true
    
    exit 0
fi

# 捕获最近输出
echo "[$NOW] 捕获 Claude Code 输出..." >> "$LOG_FILE"
tmux capture-pane -t "$SESSION" -p -S -100 > /tmp/trae_bridge_output.txt 2>&1

# 获取最后几行关键信息
TAIL_OUTPUT=$(tail -50 /tmp/trae_bridge_output.txt)

# 检测进度关键词
if echo "$TAIL_OUTPUT" | grep -qi "error\|failed\|exception"; then
    STATUS="⚠️ 可能遇到错误"
elif echo "$TAIL_OUTPUT" | grep -qi "complete\|finished\|done\|success"; then
    STATUS="✅ 可能有阶段性完成"
elif echo "$TAIL_OUTPUT" | grep -qi "research\|investigate\|inspect"; then
    STATUS="🔍 调研阶段"
elif echo "$TAIL_OUTPUT" | grep -qi "implement\|coding\|writing"; then
    STATUS="💻 编码阶段"
elif echo "$TAIL_OUTPUT" | grep -qi "test\|debug"; then
    STATUS="🧪 测试阶段"
else
    STATUS="⏳ 进行中"
fi

# 提取最近的动作（如果有明确的动作描述）
RECENT_ACTION=$(echo "$TAIL_OUTPUT" | grep -E "(Created|Modified|Writing|Implementing|Researching|Testing)" | tail -3)

# 统计代码文件数量
FILE_COUNT=$(find /Users/rzhu/Documents/GitHub/trae-bridge -type f -name "*.py" 2>/dev/null | wc -l)
FILE_COUNT=$((FILE_COUNT))

echo "[$NOW] 状态: $STATUS" >> "$LOG_FILE"
echo "[$NOW] Python文件数: $FILE_COUNT" >> "$LOG_FILE"

# 生成进度报告
REPORT="[Trae Bridge 进度报告]
时间: $NOW
状态: $STATUS
Python文件数: $FILE_COUNT

最近活动:
$RECENT_ACTION

最近输出片段:
$(tail -20 /tmp/trae_bridge_output.txt)"

# 保存报告
echo "$REPORT" >> "$LOG_FILE"
echo "[$NOW] ===== 监控检查结束 =====" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# 发送飞书通知 (通过 OpenClaw 系统)
# 使用 process 日志方式

# 输出到 stdout 供调用者捕获
echo "$REPORT"
