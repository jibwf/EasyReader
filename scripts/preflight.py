#!/usr/bin/env python3
"""环境体检脚本"""

import os
import sys
import subprocess
from pathlib import Path


def check_env_file():
    """检查 .env 文件是否配置"""
    env_example = Path(".env.example")
    env_file = Path(".env")
    env_local = Path(".env.local")

    if env_example.exists() and not env_file.exists() and not env_local.exists():
        print("⚠️  发现 .env.example 但未找到 .env 或 .env.local，请配置环境变量")
        return False
    return True


def check_git_status():
    """检查 git 状态"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return True

        result = subprocess.run(
            ["git", "stash", "list"],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            stash_count = len(result.stdout.strip().split("\n"))
            print(f"📌 有 {stash_count} 个 stash 未处理")

        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            changed = len(result.stdout.strip().split("\n"))
            print(f"📝 有 {changed} 个文件有未提交的变更")

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return True


def check_python_venv():
    """检查 Python 虚拟环境"""
    if Path("backend/requirements.txt").exists() or Path("backend/pyproject.toml").exists():
        if not hasattr(sys, 'real_prefix') and sys.base_prefix == sys.prefix:
            if Path(".venv").exists() or Path("venv").exists():
                print("⚠️  发现虚拟环境目录但未激活，建议先激活")
                return False
    return True


def check_node_modules():
    """检查前端依赖"""
    if Path("frontend/package.json").exists() and not Path("frontend/node_modules").exists():
        print("⚠️  frontend/package.json 存在但 node_modules 未安装，请运行 cd frontend && npm install")
        return False
    return True


def check_docker():
    """检查 Docker 是否可用"""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            print("⚠️  Docker 未运行或不可用")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("⚠️  未安装 Docker")
        return False
    return True


def main():
    checks = [
        ("环境变量", check_env_file),
        ("Git 状态", check_git_status),
        ("Python 虚拟环境", check_python_venv),
        ("前端依赖", check_node_modules),
        ("Docker", check_docker),
    ]

    warnings = []
    for name, check_fn in checks:
        if not check_fn():
            warnings.append(name)

    if warnings:
        print(f"\n⚠️  {len(warnings)} 项需注意：{', '.join(warnings)}")
    else:
        print("✅ 环境就绪")


if __name__ == "__main__":
    main()
