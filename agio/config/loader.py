"""Configuration loader for cold start from YAML files."""

from pathlib import Path
from typing import Any

import yaml

from agio.config.exceptions import ConfigError
from agio.config.schema import ComponentType
from agio.utils.logging import get_logger

logger = get_logger(__name__)


class ConfigLoader:
    """从 YAML 文件加载配置

    职责：
    - 递归扫描配置目录中的所有 YAML 文件
    - 解析 YAML 文件内容
    - 基于配置文件的 type 字段识别组件类型
    - 检测重复配置名称
    - 返回按类型分组的配置字典

    支持任意文件夹组织方式，不限制目录结构。
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

        递归扫描所有 YAML 文件，基于配置文件的 type 字段识别组件类型。

        Returns:
            按类型分组的配置字典: {ComponentType: [config_dict, ...]}
        """
        # 初始化所有类型的列表（动态生成）
        configs_by_type: dict[ComponentType, list[dict[str, Any]]] = {
            ct: [] for ct in ComponentType
        }

        # 用于检测重复配置名称
        seen_configs: dict[tuple[ComponentType, str], Path] = {}

        # 递归扫描所有 YAML 文件
        yaml_files = list(self.config_dir.rglob("*.yaml"))
        logger.info(f"Found {len(yaml_files)} YAML files in {self.config_dir}")

        for yaml_file in yaml_files:
            try:
                config_data = self._load_yaml_file(yaml_file)
                if not config_data:
                    continue

                # 验证必需字段
                if "type" not in config_data:
                    logger.warning(
                        f"Missing 'type' field in {yaml_file.relative_to(self.config_dir)}, skipping"
                    )
                    continue

                if "name" not in config_data:
                    logger.warning(
                        f"Missing 'name' field in {yaml_file.relative_to(self.config_dir)}, skipping"
                    )
                    continue

                # 从配置内容识别类型
                try:
                    component_type = ComponentType(config_data["type"])
                except ValueError:
                    logger.warning(
                        f"Unknown component type '{config_data['type']}' in "
                        f"{yaml_file.relative_to(self.config_dir)}, skipping"
                    )
                    continue

                # 检查是否启用
                if not config_data.get("enabled", True):
                    logger.info(
                        f"Skipped disabled config: {yaml_file.relative_to(self.config_dir)} "
                        f"(type={component_type.value}, name={config_data['name']})"
                    )
                    continue

                # 检测重复配置名称
                config_key = (component_type, config_data["name"])
                if config_key in seen_configs:
                    previous_path = seen_configs[config_key].relative_to(
                        self.config_dir
                    )
                    logger.warning(
                        f"Duplicate config found: {component_type.value}/{config_data['name']} "
                        f"at {yaml_file.relative_to(self.config_dir)}, "
                        f"previous: {previous_path}"
                    )

                seen_configs[config_key] = yaml_file
                configs_by_type[component_type].append(config_data)
                logger.info(
                    f"Loaded config: {yaml_file.relative_to(self.config_dir)} "
                    f"(type={component_type.value}, name={config_data['name']})"
                )

            except Exception as e:
                logger.error(
                    f"Failed to load {yaml_file.relative_to(self.config_dir)}: {e}",
                    exc_info=True,
                )

        # 统计信息
        total = sum(len(configs) for configs in configs_by_type.values())
        logger.info(f"Loaded {total} configs across {len(ComponentType)} types")

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

