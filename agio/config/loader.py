"""Configuration loader for cold start from YAML files."""

import logging
from pathlib import Path
from typing import Any

import yaml

from agio.config.exceptions import ConfigError
from agio.config.schema import ComponentType

logger = logging.getLogger(__name__)


class ConfigLoader:
    """从 YAML 文件加载配置并按依赖顺序初始化
    
    职责：
    - 扫描配置目录
    - 解析 YAML 文件
    - 构建依赖图
    - 按拓扑顺序加载配置
    """

    def __init__(self, config_dir: str | Path):
        """初始化配置加载器
        
        Args:
            config_dir: 配置文件根目录
        """
        self.config_dir = Path(config_dir)
        if not self.config_dir.exists():
            raise ValueError(f"Config directory not found: {config_dir}")

    async def load_all_configs(self) -> dict[ComponentType, list[dict[str, Any]]]:
        """加载所有配置文件
        
        Returns:
            按类型分组的配置字典: {ComponentType: [config_dict, ...]}
        """
        configs_by_type: dict[ComponentType, list[dict[str, Any]]] = {
            ComponentType.MODEL: [],
            ComponentType.TOOL: [],
            ComponentType.MEMORY: [],
            ComponentType.KNOWLEDGE: [],
            ComponentType.STORAGE: [],
            ComponentType.REPOSITORY: [],
            ComponentType.AGENT: [],
        }

        # 扫描各个子目录
        type_dir_mapping = {
            "models": ComponentType.MODEL,
            "tools": ComponentType.TOOL,
            "memory": ComponentType.MEMORY,
            "knowledge": ComponentType.KNOWLEDGE,
            "storages": ComponentType.STORAGE,
            "repositories": ComponentType.REPOSITORY,
            "agents": ComponentType.AGENT,
        }

        for dir_name, component_type in type_dir_mapping.items():
            type_dir = self.config_dir / dir_name
            if not type_dir.exists():
                logger.warning(f"Config directory not found: {type_dir}")
                continue

            # 加载该类型的所有 YAML 文件
            for yaml_file in type_dir.glob("*.yaml"):
                try:
                    config_data = self._load_yaml_file(yaml_file)
                    if config_data and config_data.get("enabled", True):
                        configs_by_type[component_type].append(config_data)
                        logger.info(f"Loaded config: {yaml_file.name}")
                except Exception as e:
                    logger.error(f"Failed to load {yaml_file}: {e}")

        return configs_by_type

    def _load_yaml_file(self, file_path: Path) -> dict[str, Any] | None:
        """加载单个 YAML 文件
        
        Args:
            file_path: YAML 文件路径
            
        Returns:
            配置字典或 None
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                
            if not data:
                logger.warning(f"Empty config file: {file_path}")
                return None
                
            # 验证必需字段
            if "type" not in data:
                raise ConfigError(f"Missing 'type' field in {file_path}")
            if "name" not in data:
                raise ConfigError(f"Missing 'name' field in {file_path}")
            
            # 解析环境变量
            data = self._resolve_env_vars(data)
                
            return data
            
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in {file_path}: {e}")
        except ConfigError:
            raise
        except Exception as e:
            raise ConfigError(f"Failed to load {file_path}: {e}")

    def _resolve_env_vars(self, data: dict[str, Any]) -> dict[str, Any]:
        """递归解析配置中的环境变量
        
        支持格式：
        - ${VAR_NAME}
        - ${VAR_NAME:default_value}
        
        Args:
            data: 配置字典
            
        Returns:
            解析后的配置字典
        """
        import os
        import re
        
        def resolve_value(value: Any) -> Any:
            if isinstance(value, str):
                # 匹配 ${VAR_NAME} 或 ${VAR_NAME:default}
                pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'
                
                def replacer(match):
                    var_name = match.group(1)
                    default_value = match.group(2) if match.group(2) is not None else ""
                    return os.getenv(var_name, default_value)
                
                return re.sub(pattern, replacer, value)
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(item) for item in value]
            else:
                return value
        
        return resolve_value(data)

    def get_load_order(
        self, configs_by_type: dict[ComponentType, list[dict[str, Any]]]
    ) -> list[tuple[ComponentType, dict[str, Any]]]:
        """计算配置加载顺序（按依赖关系拓扑排序）
        
        Args:
            configs_by_type: 按类型分组的配置
            
        Returns:
            排序后的配置列表: [(ComponentType, config_dict), ...]
        """
        # 收集所有配置
        all_configs: dict[str, tuple[ComponentType, dict]] = {}

        # 添加所有节点（使用临时的 BaseModel 对象）
        for component_type, configs in configs_by_type.items():
            for config in configs:
                name = config["name"]
                all_configs[name] = (component_type, config)

        # 构建依赖关系
        dependencies: dict[str, set[str]] = {}
        
        for name, (component_type, config) in all_configs.items():
            deps = set()
            
            # Agent 依赖
            if component_type == ComponentType.AGENT:
                if "model" in config:
                    deps.add(config["model"])
                if "tools" in config:
                    deps.update(config["tools"])
                if "memory" in config:
                    deps.add(config["memory"])
                if "knowledge" in config:
                    deps.add(config["knowledge"])
                if "repository" in config:
                    deps.add(config["repository"])
            
            # Tool 依赖
            elif component_type == ComponentType.TOOL:
                if "dependencies" in config:
                    deps.update(config["dependencies"].values())
            
            dependencies[name] = deps

        # 拓扑排序
        sorted_names = self._topological_sort(dependencies)
        
        # 构建结果
        result = []
        for name in sorted_names:
            if name in all_configs:
                result.append(all_configs[name])
        
        return result

    def _topological_sort(self, dependencies: dict[str, set[str]]) -> list[str]:
        """拓扑排序
        
        Args:
            dependencies: 依赖关系字典 {name: {dep1, dep2, ...}}
            
        Returns:
            排序后的名称列表（依赖项在前，被依赖项在后）
        """
        from collections import deque

        # 计算每个节点的依赖数（出度）
        in_degree: dict[str, int] = {name: len(deps) for name, deps in dependencies.items()}
        
        # 从没有依赖的节点开始（出度为 0）
        queue = deque([name for name, degree in in_degree.items() if degree == 0])
        result = []

        while queue:
            name = queue.popleft()
            result.append(name)

            # 找到所有依赖当前节点的其他节点，减少它们的依赖计数
            for other_name, deps in dependencies.items():
                if name in deps:
                    in_degree[other_name] -= 1
                    if in_degree[other_name] == 0:
                        queue.append(other_name)

        return result
