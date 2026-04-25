#!/usr/bin/env python3
"""
Hermes Memory Installer - 环境检测模块
检查当前环境是否满足安装条件，返回详细报告。
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


class EnvChecker:
    """环境检测器"""
    
    REQUIRED_PYTHON = (3, 9)
    
    def __init__(self):
        self.issues: List[str] = []
        self.warnings: List[str] = []
        self.info: Dict[str, str] = {}
    
    def check_all(self) -> bool:
        """运行所有检测，返回是否通过"""
        checks = [
            self._check_python_version,
            self._check_hermes_installation,
            self._check_config_yaml,
            self._check_skills_directory,
            self._check_sqlite,
            self._check_cron,
            self._check_disk_space,
        ]
        
        for check in checks:
            try:
                check()
            except Exception as e:
                self.issues.append(f"{check.__name__}: {e}")
        
        return len(self.issues) == 0
    
    def _check_python_version(self):
        """检查 Python 版本"""
        version = sys.version_info
        self.info["python"] = f"{version.major}.{version.minor}.{version.micro}"
        
        if (version.major, version.minor) < self.REQUIRED_PYTHON:
            self.issues.append(
                f"Python 版本过低: 需要 >= {'.'.join(map(str, self.REQUIRED_PYTHON))}, "
                f"当前 {version.major}.{version.minor}"
            )
    
    def _check_hermes_installation(self):
        """检查 Hermes 安装"""
        hermes_dir = Path.home() / ".hermes"
        if not hermes_dir.exists():
            self.issues.append("Hermes 未安装: 未找到 ~/.hermes 目录")
            return
        
        self.info["hermes_dir"] = str(hermes_dir)
        
        # 检查关键文件
        config_file = hermes_dir / "config.yaml"
        if not config_file.exists():
            self.issues.append("Hermes 配置不完整: 未找到 config.yaml")
    
    def _check_config_yaml(self):
        """检查 config.yaml 可读写"""
        config_file = Path.home() / ".hermes" / "config.yaml"
        if not config_file.exists():
            return  # 已在上一步报告
        
        if not os.access(config_file, os.R_OK):
            self.issues.append(f"无法读取 config.yaml: {config_file}")
        if not os.access(config_file, os.W_OK):
            self.issues.append(f"无法写入 config.yaml: {config_file}")
    
    def _check_skills_directory(self):
        """检查 Skill 目录"""
        skills_dir = Path.home() / ".hermes" / "skills"
        if skills_dir.exists():
            self.info["skills_dir"] = str(skills_dir)
            # 检查是否已有冲突的 Skill
            conflicts = []
            for name in ["memory-starter-kit", "memory-archivist", "memory-proactive"]:
                if (skills_dir / name).exists():
                    conflicts.append(name)
            if conflicts:
                self.warnings.append(
                    f"检测到已有的 Skill 可能冲突: {', '.join(conflicts)}"
                )
        else:
            self.info["skills_dir"] = "将创建"
    
    def _check_sqlite(self):
        """检查 SQLite 可用性"""
        try:
            import sqlite3
            version = sqlite3.sqlite_version
            self.info["sqlite"] = version
            # 检查 FTS5 支持
            conn = sqlite3.connect(":memory:")
            conn.execute("CREATE VIRTUAL TABLE test USING fts5(content)")
            conn.close()
        except ImportError:
            self.issues.append("Python 未编译 sqlite3 模块")
        except Exception as e:
            self.issues.append(f"SQLite 不支持 FTS5: {e}")
    
    def _check_cron(self):
        """检查 cron 可用性"""
        if shutil.which("crontab"):
            self.info["cron"] = "可用"
        else:
            self.warnings.append("未找到 crontab，自动化任务需要手动配置")
    
    def _check_disk_space(self):
        """检查磁盘空间"""
        hermes_dir = Path.home() / ".hermes"
        if hermes_dir.exists():
            stat = shutil.disk_usage(hermes_dir)
            free_mb = stat.free // (1024 * 1024)
            self.info["disk_free_mb"] = str(free_mb)
            if free_mb < 100:
                self.warnings.append(f"磁盘空间余量仅 {free_mb}MB，建议至少 100MB")
    
    def report(self) -> str:
        """生成检测报告"""
        lines = [
            "=" * 50,
            "Hermes Memory Installer - 环境检测报告",
            "=" * 50,
            "",
            "【环境信息】",
        ]
        for key, value in self.info.items():
            lines.append(f"  {key}: {value}")
        
        if self.warnings:
            lines.extend(["", "【警告】"])
            for w in self.warnings:
                lines.append(f"  ⚠️  {w}")
        
        if self.issues:
            lines.extend(["", "【问题】"])
            for i in self.issues:
                lines.append(f"  ❌  {i}")
            lines.extend(["", "⚠️  检测未通过，请先解决上述问题"])
        else:
            lines.extend(["", "✅  检测通过，可以继续安装"])
        
        lines.append("")
        return "\n".join(lines)


def main():
    checker = EnvChecker()
    passed = checker.check_all()
    print(checker.report())
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
