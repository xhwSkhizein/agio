"""Mixin class for tools with configuration support."""

import dataclasses
from typing import TypeVar

from agio.tools.builtin.config import filter_config_kwargs

TConfig = TypeVar("TConfig")


class ConfigurableToolMixin:
    """Mixin class for tools that use configuration objects.

    This mixin provides a unified way to handle configuration:
    1. Config object (highest priority)
    2. Keyword arguments (medium priority)
    3. Default values (lowest priority)

    Note: This is a mixin class, not a base class. It should be used with
    multiple inheritance alongside BaseTool or its subclasses.
    """

    def _init_config(
        self,
        config_class: type[TConfig],
        config: TConfig | None = None,
        **kwargs,
    ) -> TConfig:
        """Initialize configuration object from config, kwargs, or defaults.

        Args:
            config_class: The configuration dataclass type
            config: Optional configuration object
            **kwargs: Keyword arguments that can override config values

        Returns:
            Initialized configuration object
        """
        if config is None:
            # Filter invalid parameters before creating config object
            filtered_kwargs = filter_config_kwargs(config_class, kwargs)
            return config_class(**filtered_kwargs)
        else:
            # Allow kwargs to override config values
            config_dict = dataclasses.asdict(config)
            # Filter invalid parameters
            filtered_kwargs = filter_config_kwargs(config_class, kwargs)
            config_dict.update(filtered_kwargs)
            return config_class(**config_dict)
