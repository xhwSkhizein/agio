"""Configuration loader for cold start from YAML files."""

from pathlib import Path
from typing import Any

import yaml

from agio.config.exceptions import ConfigError
from agio.config.schema import ComponentType
from agio.utils.logging import get_logger

logger = get_logger(__name__)


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
            ComponentType.SESSION_STORE: [],
            ComponentType.TRACE_STORE: [],
            ComponentType.AGENT: [],
            ComponentType.WORKFLOW: [],
        }

        # 扫描各个子目录
        type_dir_mapping = {
            "models": ComponentType.MODEL,
            "tools": ComponentType.TOOL,
            # "memory": ComponentType.MEMORY,
            # "knowledge": ComponentType.KNOWLEDGE,
            "storages": ComponentType.SESSION_STORE,
            "observability": ComponentType.TRACE_STORE,
            "agents": ComponentType.AGENT,
            "workflows": ComponentType.WORKFLOW,
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
                    if not config_data:
                        continue
                    if config_data.get("enabled", True):
                        configs_by_type[component_type].append(config_data)
                        logger.info(f"Loaded config: {yaml_file.name}")
                    else:
                        logger.info(
                            f"Skipped disabled config: {yaml_file.name} "
                            f"(type={component_type.value}, name={config_data.get('name')})"
                        )
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
                pattern = r"\$\{([^}:]+)(?::([^}]*))?\}"

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

