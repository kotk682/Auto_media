#!/usr/bin/env python3.12
"""一键启动 AutoMedia 前后端"""
import subprocess
import sys
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def run(cmd, cwd=None, check=True):
    print(f"  $ {cmd}")
    return subprocess.run(cmd, shell=True, cwd=cwd, check=check)


def check_env():
    env_file = BACKEND / ".env"
    if not env_file.exists():
        shutil.copy(BACKEND / ".env.example", env_file)
        print("  已创建 .env，请填入 API keys 后重新运行")
        sys.exit(1)


def setup_backend():
    print("\n[后端] 安装依赖...")
    run("uv sync", cwd=BACKEND)


def setup_frontend():
    print("\n[前端] 安装依赖...")
    run("npm install", cwd=FRONTEND)


def start():
    check_env()
    setup_backend()
    setup_frontend()

    print("\n[启动] 后端 :8000  前端 :5173\n")

    backend_proc = subprocess.Popen(
        "uv run uvicorn app.main:app --reload",
        shell=True, cwd=BACKEND,
    )
    frontend_proc = subprocess.Popen(
        "npm run dev",
        shell=True, cwd=FRONTEND,
    )

    try:
        backend_proc.wait()
        frontend_proc.wait()
    except KeyboardInterrupt:
        print("\n正在关闭...")
        backend_proc.terminate()
        frontend_proc.terminate()


if __name__ == "__main__":
    start()
