# Phase 3: 配置系统增强

## 目标

1. 抽象配置源，支持 YAML 文件和 MongoDB
2. 完善热重载机制
3. 配置变更实时监听

## 架构设计

### 1. 配置源抽象

```
┌─────────────────────────────────────────────────────┐
│                   ConfigSystem                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │              ConfigSourceManager                 │ │
│  │  ┌─────────────┐  ┌─────────────┐              │ │
│  │  │ YamlSource  │  │ MongoSource │  ...         │ │
│  │  └─────────────┘  └─────────────┘              │ │
│  └─────────────────────────────────────────────────┘ │
│                         ↓                            │
│  ┌─────────────────────────────────────────────────┐ │
│  │           Unified Config Storage                 │ │
│  │         {(type, name): config_dict}             │ │
│  └─────────────────────────────────────────────────┘ │
│                         ↓                            │
│  ┌─────────────────────────────────────────────────┐ │
│  │              Component Builders                  │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 2. ConfigSource 协议

新建 `agio/config/sources/base.py`:

```python
from typing import Protocol, Callable, Awaitable, AsyncIterator
from agio.core.config import ComponentType


class ConfigChange:
    """配置变更事件"""
    
    def __init__(
        self,
        component_type: ComponentType,
        name: str,
        change_type: str,  # 'create' | 'update' | 'delete'
        config: dict | None = None,
    ):
        self.component_type = component_type
        self.name = name
        self.change_type = change_type
        self.config = config


class ConfigSource(Protocol):
    """配置源协议"""
    
    @property
    def name(self) -> str:
        """配置源名称"""
        ...
    
    async def load_all(self) -> dict[tuple[ComponentType, str], dict]:
        """
        加载所有配置。
        
        Returns:
            配置字典 {(component_type, name): config_dict}
        """
        ...
    
    async def watch(self) -> AsyncIterator[ConfigChange]:
        """
        监听配置变更。
        
        Yields:
            ConfigChange: 配置变更事件
        """
        ...
    
    async def save(
        self, 
        component_type: ComponentType, 
        name: str, 
        config: dict
    ) -> None:
        """
        保存配置（可选实现）。
        
        Raises:
            NotImplementedError: 如果配置源只读
        """
        ...
    
    async def delete(
        self, 
        component_type: ComponentType, 
        name: str
    ) -> None:
        """
        删除配置（可选实现）。
        """
        ...
```

### 3. YAML 配置源

`agio/config/sources/yaml_source.py`:

```python
import asyncio
from pathlib import Path
from watchfiles import awatch

from agio.config.sources.base import ConfigSource, ConfigChange
from agio.config.loader import ConfigLoader
from agio.core.config import ComponentType


class YamlConfigSource(ConfigSource):
    """YAML 文件配置源"""
    
    def __init__(self, config_dir: str | Path):
        self._config_dir = Path(config_dir)
        self._loader = ConfigLoader(config_dir)
    
    @property
    def name(self) -> str:
        return f"yaml:{self._config_dir}"
    
    async def load_all(self) -> dict[tuple[ComponentType, str], dict]:
        configs_by_type = await self._loader.load_all_configs()
        result = {}
        for component_type, configs in configs_by_type.items():
            for config in configs:
                name = config.get("name")
                result[(component_type, name)] = config
        return result
    
    async def watch(self) -> AsyncIterator[ConfigChange]:
        """监听文件变更"""
        async for changes in awatch(self._config_dir):
            for change_type, path in changes:
                # 解析变更的配置文件
                # 产生 ConfigChange 事件
                yield await self._parse_file_change(change_type, path)
    
    async def save(self, component_type: ComponentType, name: str, config: dict):
        """保存配置到 YAML 文件"""
        file_path = self._config_dir / f"{component_type.value}s" / f"{name}.yaml"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        import yaml
        with open(file_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)
```

### 4. MongoDB 配置源

`agio/config/sources/mongo_source.py`:

```python
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING
from pymongo.change_stream import CollectionChangeStream

from agio.config.sources.base import ConfigSource, ConfigChange
from agio.core.config import ComponentType


class MongoConfigSource(ConfigSource):
    """MongoDB 配置源"""
    
    COLLECTION_MAP = {
        ComponentType.AGENT: "agents",
        ComponentType.MODEL: "models",
        ComponentType.TOOL: "tools",
        ComponentType.MEMORY: "memories",
        ComponentType.KNOWLEDGE: "knowledges",
        ComponentType.REPOSITORY: "repositories",
        ComponentType.STORAGE: "storages",
    }
    
    def __init__(self, uri: str, db_name: str = "agio_config"):
        self._client = AsyncIOMotorClient(uri)
        self._db = self._client[db_name]
    
    @property
    def name(self) -> str:
        return f"mongo:{self._db.name}"
    
    async def load_all(self) -> dict[tuple[ComponentType, str], dict]:
        result = {}
        
        for component_type, collection_name in self.COLLECTION_MAP.items():
            collection = self._db[collection_name]
            async for doc in collection.find({"enabled": {"$ne": False}}):
                doc.pop("_id", None)  # 移除 MongoDB _id
                name = doc.get("name")
                if name:
                    result[(component_type, name)] = doc
        
        return result
    
    async def watch(self) -> AsyncIterator[ConfigChange]:
        """监听 MongoDB Change Streams"""
        # 需要 MongoDB Replica Set
        pipeline = [
            {"$match": {"operationType": {"$in": ["insert", "update", "delete"]}}}
        ]
        
        for component_type, collection_name in self.COLLECTION_MAP.items():
            collection = self._db[collection_name]
            
            async with collection.watch(pipeline) as stream:
                async for change in stream:
                    yield self._parse_change(component_type, change)
    
    async def save(self, component_type: ComponentType, name: str, config: dict):
        collection_name = self.COLLECTION_MAP[component_type]
        collection = self._db[collection_name]
        
        config["name"] = name
        config["type"] = component_type.value
        
        await collection.update_one(
            {"name": name},
            {"$set": config},
            upsert=True
        )
    
    async def delete(self, component_type: ComponentType, name: str):
        collection_name = self.COLLECTION_MAP[component_type]
        collection = self._db[collection_name]
        await collection.delete_one({"name": name})
    
    def _parse_change(self, component_type: ComponentType, change: dict) -> ConfigChange:
        op = change["operationType"]
        doc = change.get("fullDocument", {})
        name = doc.get("name") or change.get("documentKey", {}).get("name")
        
        change_type_map = {
            "insert": "create",
            "update": "update",
            "delete": "delete",
        }
        
        return ConfigChange(
            component_type=component_type,
            name=name,
            change_type=change_type_map.get(op, "update"),
            config=doc if op != "delete" else None,
        )
```

### 5. ConfigSystem 增强

修改 `agio/config/system.py`:

```python
class ConfigSystem:
    def __init__(self):
        # ... 现有初始化
        self._sources: list[ConfigSource] = []
        self._watch_tasks: list[asyncio.Task] = []
    
    def add_source(self, source: ConfigSource) -> None:
        """添加配置源"""
        self._sources.append(source)
    
    async def load_from_sources(self) -> dict[str, int]:
        """从所有配置源加载"""
        stats = {"loaded": 0, "failed": 0}
        
        for source in self._sources:
            try:
                configs = await source.load_all()
                for (ct, name), config in configs.items():
                    self._configs[(ct, name)] = config
                    stats["loaded"] += 1
            except Exception as e:
                logger.error(f"Failed to load from {source.name}: {e}")
                stats["failed"] += 1
        
        return stats
    
    async def start_watching(self) -> None:
        """启动所有配置源的监听"""
        for source in self._sources:
            task = asyncio.create_task(self._watch_source(source))
            self._watch_tasks.append(task)
    
    async def stop_watching(self) -> None:
        """停止所有监听"""
        for task in self._watch_tasks:
            task.cancel()
        self._watch_tasks.clear()
    
    async def _watch_source(self, source: ConfigSource) -> None:
        """监听单个配置源的变更"""
        try:
            async for change in source.watch():
                await self._handle_source_change(change)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Watch error for {source.name}: {e}")
    
    async def _handle_source_change(self, change: ConfigChange) -> None:
        """处理配置变更"""
        key = (change.component_type, change.name)
        
        if change.change_type == "delete":
            await self.delete_config(change.component_type, change.name)
        else:
            self._configs[key] = change.config
            if change.name in self._instances:
                await self._handle_config_change(change.name, change.change_type)
            else:
                await self._build_component(change.component_type, change.name)
```

### 6. 初始化 API 更新

```python
async def init_config_system(
    yaml_dir: str | Path | None = None,
    mongo_uri: str | None = None,
    mongo_db: str = "agio_config",
) -> ConfigSystem:
    """
    初始化配置系统。
    
    Args:
        yaml_dir: YAML 配置目录（可选）
        mongo_uri: MongoDB 连接 URI（可选）
        mongo_db: MongoDB 数据库名
    
    Returns:
        ConfigSystem 实例
    """
    system = get_config_system()
    
    # 添加配置源
    if yaml_dir:
        system.add_source(YamlConfigSource(yaml_dir))
    
    if mongo_uri:
        system.add_source(MongoConfigSource(mongo_uri, mongo_db))
    
    # 加载所有配置
    await system.load_from_sources()
    
    # 构建组件
    await system.build_all()
    
    # 启动监听
    await system.start_watching()
    
    return system
```

## 使用示例

### YAML 配置

```yaml
# configs/agents/my_agent.yaml
type: agent
name: my_agent
model: gpt4
tools:
  - search
  - calculator
```

### MongoDB 配置

```javascript
// MongoDB: agio_config.agents
{
  "name": "my_agent",
  "type": "agent",
  "model": "gpt4",
  "tools": ["search", "calculator"],
  "enabled": true
}
```

### 热重载

```python
# 配置变更自动生效
# 1. 修改 YAML 文件 -> 自动检测并重载
# 2. 更新 MongoDB 文档 -> Change Stream 触发重载
```

## 文件变更

### 新增
```
agio/config/sources/
  ├── __init__.py
  ├── base.py           # ConfigSource 协议
  ├── yaml_source.py    # YAML 文件源
  └── mongo_source.py   # MongoDB 源
```

### 修改
```
agio/config/system.py   # 支持多配置源
agio/config/__init__.py # 导出新类
requirements.txt        # 添加 watchfiles, motor
```

## 依赖

```
# requirements.txt
watchfiles>=0.21.0      # 文件监听
motor>=3.3.0            # MongoDB 异步驱动
```

## 测试

```python
# tests/config/test_sources.py

@pytest.mark.asyncio
async def test_yaml_source_load():
    source = YamlConfigSource("configs/")
    configs = await source.load_all()
    assert len(configs) > 0


@pytest.mark.asyncio
async def test_mongo_source_load():
    source = MongoConfigSource("mongodb://localhost:27017")
    configs = await source.load_all()
    # 验证加载结果


@pytest.mark.asyncio
async def test_hot_reload():
    system = await init_config_system(yaml_dir="configs/")
    
    # 修改配置文件
    # 等待重载
    # 验证组件已更新
```
