#!/usr/bin/env python3
"""
Hermes Memory Installer - 主安装器
用户执行: curl ... | bash 或 python3 install.py

安装流程：
1. 环境检测
2. 备份
3. 创建目录结构
4. 初始化数据库
5. 安装 Skills
6. 修改配置
7. 验证 + 报告
"""

import os
import sys
import shutil
import argparse
from pathlib import Path
from typing import Optional

# 导入本地模块
sys.path.insert(0, str(Path(__file__).parent))
from check_env import EnvChecker
from config_patch import ConfigPatcher


class Installer:
    """一键安装器主类"""
    
    VERSION = "0.1.0"
    
    # 目录结构
    ARCHIVE_DIRS = [
        "archives/people",
        "archives/projects", 
        "archives/knowledge",
        "archives/_index",
    ]
    
    def __init__(self, dry_run: bool = False, skip_backup: bool = False):
        self.dry_run = dry_run
        self.skip_backup = skip_backup
        self.hermes_dir = Path.home() / ".hermes"
        self.report = []
    
    def log(self, msg: str, level: str = "info"):
        """记录日志"""
        prefix = {"info": "ℹ️ ", "ok": "✅ ", "warn": "⚠️ ", "error": "❌ "}.get(level, "  ")
        self.report.append(f"{prefix}{msg}")
        if not self.dry_run or level in ["error", "warn"]:
            print(f"{prefix}{msg}")
    
    def run(self) -> bool:
        """执行完整安装流程"""
        self.log(f"Hermes Memory Installer v{self.VERSION}")
        self.log("模式: " + ("演示模式" if self.dry_run else "真实安装"))
        self.log("")
        
        steps = [
            ("环境检测", self._step_check_env),
            ("备份现有配置", self._step_backup),
            ("创建目录结构", self._step_create_dirs),
            ("初始化数据库", self._step_init_db),
            ("安装 Skill 套件", self._step_install_skills),
            ("修改配置文件", self._step_patch_config),
            ("验证安装", self._step_verify),
        ]
        
        for name, step_func in steps:
            self.log(f"步骤: {name}...")
            try:
                success = step_func()
                if not success:
                    self.log(f"步骤失败: {name}", "error")
                    self._print_report(False)
                    return False
            except Exception as e:
                self.log(f"步骤异常: {name} - {e}", "error")
                self._print_report(False)
                return False
        
        self._print_report(True)
        return True
    
    def _step_check_env(self) -> bool:
        """步骤1: 环境检测"""
        checker = EnvChecker()
        passed = checker.check_all()
        for warning in checker.warnings:
            self.log(warning, "warn")
        return passed
    
    def _step_backup(self) -> bool:
        """步骤2: 备份"""
        if self.skip_backup:
            self.log("跳过备份")
            return True
        
        # 备份 config.yaml
        config = self.hermes_dir / "config.yaml"
        if config.exists():
            backup = config.with_suffix(".yaml.pre-memory-install")
            if not self.dry_run:
                shutil.copy2(config, backup)
            self.log(f"已备份: {backup.name}")
        
        return True
    
    def _step_create_dirs(self) -> bool:
        """步骤3: 创建目录"""
        for dir_path in self.ARCHIVE_DIRS:
            full_path = self.hermes_dir / dir_path
            if not self.dry_run:
                full_path.mkdir(parents=True, exist_ok=True)
            self.log(f"创建: {dir_path}")
        return True
    
    def _step_init_db(self) -> bool:
        """步骤4: 初始化数据库"""
        db_path = self.hermes_dir / "pool.db"
        if db_path.exists():
            self.log("pool.db 已存在，跳过初始化")
            return True
        
        if not self.dry_run:
            # 执行数据库初始化脚本
            script = Path(__file__).parent.parent / "scripts" / "init_db.py"
            if script.exists():
                os.system(f"python3 {script} {db_path}")
            else:
                self.log("未找到 init_db.py，数据库未初始化", "warn")
                return False
        
        self.log(f"初始化: {db_path}")
        return True
    
    def _step_install_skills(self) -> bool:
        """步骤5: 安装 Skills"""
        skills_src = Path(__file__).parent.parent / "skills"
        skills_dst = self.hermes_dir / "skills"
        
        for skill_name in ["memory-starter-kit", "memory-archivist"]:
            src = skills_src / skill_name
            dst = skills_dst / skill_name
            
            if dst.exists():
                self.log(f"Skill 已存在: {skill_name}")
                continue
            
            if not self.dry_run:
                if src.exists():
                    shutil.copytree(src, dst)
                else:
                    self.log(f"未找到 Skill 源: {skill_name}", "warn")
                    continue
            
            self.log(f"安装 Skill: {skill_name}")
        
        return True
    
    def _step_patch_config(self) -> bool:
        """步骤6: 修改配置"""
        patcher = ConfigPatcher()
        
        if self.dry_run:
            # 演示模式只显示修改内容，不应用
            self.log("演示模式: 仅展示修改，不应用")
            return True
        
        success, msg = patcher.patch_and_apply()
        self.log(msg, "ok" if success else "error")
        return success
    
    def _step_verify(self) -> bool:
        """步骤7: 验证"""
        # 简单检查关键目录是否存在
        checks = [
            self.hermes_dir / "archives",
            self.hermes_dir / "pool.db",
            self.hermes_dir / "skills" / "memory-starter-kit",
        ]
        
        all_ok = True
        for check in checks:
            exists = check.exists()
            status = "✅" if exists else "❌"
            self.log(f"{status} {check}")
            if not exists:
                all_ok = False
        
        return all_ok
    
    def _print_report(self, success: bool):
        """打印最终报告"""
        print("\n" + "=" * 50)
        if success:
            print("✅ 安装成功！")
            print("\n下一步:")
            print("  1. 重启 Hermes Gateway")
            print("  2. 运行: hermes-memory new person --name '你的名字'")
            print("  3. 查看指南: ~/.hermes/skills/memory-starter-kit/SKILL.md")
        else:
            print("❌ 安装失败")
            print("\n请检查上述错误，或手动执行回滚")
        print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Hermes Memory Installer")
    parser.add_argument("--dry-run", action="store_true", help="演示模式，不会真正修改系统")
    parser.add_argument("--skip-backup", action="store_true", help="跳过备份（不推荐）")
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    args = parser.parse_args()
    
    installer = Installer(dry_run=args.dry_run, skip_backup=args.skip_backup)
    success = installer.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
