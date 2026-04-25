#!/usr/bin/env python3
"""
Hermes Memory Installer - Config 安全修改器
安全地修改 ~/.hermes/config.yaml，不损坏现有配置。

原则：
1. 使用 YAML 解析器读写，不做文本替换
2. 保留现有配置，只追加
3. 先写临时文件，验证通过后原子替换
4. API Key 绝不触碰
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple

# 使用 ruamel.yaml 或标准 yaml
# 如果不存在 ruamel.yaml，回退到标准 yaml（可能丢失注释）
try:
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap
    HAS_RUAMEL = True
except ImportError:
    import yaml
    HAS_RUAMEL = False


class ConfigPatcher:
    """安全的 config.yaml 修改器"""
    
    # 默认需要追加的 Skill
    DEFAULT_SKILLS = [
        "memory-starter-kit",
        "memory-archivist",
        # "memory-proactive"  # 选装，不默认加入
    ]
    
    # 默认需要追加的 memory 条目
    DEFAULT_MEMORY_ENTRIES = [
        "你拥有一个综合记忆管理系统，使用 ~/.hermes/archives/ 存储档案，",
        "pool.db 存储归档数据，FTS5 全文检索。",
    ]
    
    def __init__(self, config_path: str = None):
        self.config_path = Path(config_path) if config_path else (Path.home() / ".hermes" / "config.yaml")
        self.backup_path = self.config_path.with_suffix(".yaml.backup")
        self.temp_path = None
        
        if HAS_RUAMEL:
            self.yaml = YAML()
            self.yaml.preserve_quotes = True
            self.yaml.default_flow_style = False
    
    def backup(self) -> bool:
        """备份现有配置"""
        if not self.config_path.exists():
            return False
        
        shutil.copy2(self.config_path, self.backup_path)
        return True
    
    def load(self) -> Any:
        """加载 YAML"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        if HAS_RUAMEL:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return self.yaml.load(f)
        else:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
    
    def patch(self, data: Any) -> Any:
        """修改配置数据（不修改原有内容，只追加）"""
        if data is None:
            data = {} if not HAS_RUAMEL else CommentedMap()
        
        # 1. 追加 skills 列表
        if "skills" not in data:
            data["skills"] = [] if not HAS_RUAMEL else CommentedMap()
        
        # Hermes config.yaml 中 skills 是一个字典，包含 external_dirs 等键
        if isinstance(data["skills"], dict):
            if "external_dirs" not in data["skills"]:
                data["skills"]["external_dirs"] = [] if not HAS_RUAMEL else []
            existing_skills = set(data["skills"].get("external_dirs", []))
            for skill in self.DEFAULT_SKILLS:
                if skill not in existing_skills:
                    data["skills"]["external_dirs"].append(skill)
        else:
            # 兼容旧版/自定义格式
            existing_skills = set(data["skills"]) if isinstance(data["skills"], list) else set()
            for skill in self.DEFAULT_SKILLS:
                if skill not in existing_skills:
                    data["skills"].append(skill)
        
        # 2. 追加 memory 条目（如果存在 memory 配置）
        # 注：memory 配置存储方式因 Hermes 版本而异，
        # 这里只做最安全的追加
        
        return data
    
    def save(self, data: Any) -> str:
        """保存修改后的配置到临时文件，返回路径"""
        fd, temp_path = tempfile.mkstemp(
            suffix=".yaml",
            prefix="config_",
            dir=self.config_path.parent
        )
        
        try:
            if HAS_RUAMEL:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    self.yaml.dump(data, f)
            else:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
            
            self.temp_path = Path(temp_path)
            return str(self.temp_path)
        except Exception:
            os.close(fd)
            raise
    
    def validate(self, temp_path: str = None) -> bool:
        """验证临时配置是否有效"""
        path = Path(temp_path) if temp_path else self.temp_path
        if not path or not path.exists():
            return False
        
        try:
            if HAS_RUAMEL:
                with open(path, "r", encoding="utf-8") as f:
                    data = self.yaml.load(f)
            else:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            
            # 基础验证：是否能够解析
            if data is None:
                return False
            
            # 检查是否成功追加了 skills
            if "skills" not in data or not isinstance(data["skills"], (list, dict)):
                return False
            
            # 处理字典格式（Hermes V7+）
            if isinstance(data["skills"], dict):
                dirs = data["skills"].get("external_dirs", [])
                for skill in self.DEFAULT_SKILLS:
                    if skill not in dirs:
                        return False
            else:
                # 列表格式
                for skill in self.DEFAULT_SKILLS:
                    if skill not in data["skills"]:
                        return False
            
            return True
        except Exception:
            return False
    
    def apply(self, temp_path: str = None) -> bool:
        """原子替换：临时文件 -> 正式配置"""
        path = Path(temp_path) if temp_path else self.temp_path
        if not path or not path.exists():
            return False
        
        # 确保备份存在
        if not self.backup_path.exists():
            self.backup()
        
        # 原子替换
        os.replace(path, self.config_path)
        self.temp_path = None
        return True
    
    def rollback(self) -> bool:
        """回滚到备份"""
        if not self.backup_path.exists():
            return False
        
        shutil.copy2(self.backup_path, self.config_path)
        return True
    
    def patch_and_apply(self) -> Tuple[bool, str]:
        """一键修改并应用，返回 (是否成功, 消息)"""
        try:
            # 1. 备份
            self.backup()
            
            # 2. 加载
            data = self.load()
            
            # 3. 修改
            data = self.patch(data)
            
            # 4. 保存到临时文件
            temp_path = self.save(data)
            
            # 5. 验证
            if not self.validate(temp_path):
                return False, "配置验证失败，已自动回滚"
            
            # 6. 应用
            if not self.apply(temp_path):
                return False, "应用配置失败"
            
            return True, "配置修改成功"
            
        except Exception as e:
            # 出错时尝试回滚
            try:
                self.rollback()
            except Exception:
                pass
            return False, f"修改失败: {e}"


def main():
    """独立运行测试"""
    patcher = ConfigPatcher()
    success, msg = patcher.patch_and_apply()
    print(f"{'✅' if success else '❌'} {msg}")
    if not success:
        exit(1)


if __name__ == "__main__":
    main()
