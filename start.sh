#!/bin/bash
# ============================================================
# 年度财税顾问项目拆分工作台 - 启动脚本
# 同时启动后端(FastAPI)和前端(Vite)
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 检查 .env 文件
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "[INFO] 未找到 .env 文件，正在从 .env.example 创建..."
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    echo "[INFO] .env 文件已创建，默认使用 Mock 模式。"
fi

# 检查并创建虚拟环境
VENV_DIR="$SCRIPT_DIR/api/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "[INFO] 正在创建 Python 虚拟环境..."
    env -u PYTHONHOME -u PYTHONPATH python3 -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python3"

# 检查依赖
if ! env -u PYTHONHOME -u PYTHONPATH "$VENV_PYTHON" -c "import fastapi" 2>/dev/null; then
    echo "[INFO] 正在安装后端依赖..."
    env -u PYTHONHOME -u PYTHONPATH "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/api/requirements.txt"
fi

# 检查前端依赖
if [ ! -d "$SCRIPT_DIR/app/node_modules" ]; then
    echo "[INFO] 正在安装前端依赖..."
    cd "$SCRIPT_DIR/app" && npm install
fi

# 启动后端
echo "[INFO] 启动 FastAPI 后端服务..."
echo "[INFO] API文档地址: http://localhost:8000/docs"
cd "$SCRIPT_DIR/api"
env -u PYTHONHOME -u PYTHONPATH "$VENV_PYTHON" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "[INFO] 后端 PID: $BACKEND_PID"

# 启动前端
echo "[INFO] 启动 Vite 前端服务..."
cd "$SCRIPT_DIR/app"
npm run dev &
FRONTEND_PID=$!
echo "[INFO] 前端 PID: $FRONTEND_PID"

echo ""
echo "============================================================"
echo "  年度财税顾问项目拆分工作台 已启动"
echo "  前端地址: http://localhost:3131"
echo "  后端API:  http://localhost:8000"
echo "  API文档:  http://localhost:8000/docs"
echo "============================================================"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 捕获退出信号
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM EXIT

wait
