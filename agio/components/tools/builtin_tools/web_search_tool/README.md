# WebSearchTool

网页搜索工具，使用 Serper API 进行 Google 搜索。

## ✨ 优化特性（v2.0）

- **Token 优化**：搜索结果隐藏 URL，减少 60-70% token 消耗
- **数字索引**：使用 0, 1, 2... 最小化 token 占用
- **持久化存储**：搜索结果存储到 MongoDB，支持 TTL 自动清理
- **无缝集成**：与 web_fetch 工具配合，通过索引获取完整内容

## 功能说明

### 搜索能力
- 使用 Google Serper API 进行网页搜索
- 自动检测查询语言（中文/英文）并设置对应地区
- 返回标题、摘要、发布日期、来源等信息
- 支持单个或多个查询

### 优化机制
1. **URL 隐藏**：搜索结果不包含 URL，只显示索引编号
2. **MongoDB 存储**：结果存储到 MongoDB，24小时 TTL 自动清理
3. **索引映射**：每个结果分配数字索引（0, 1, 2...）
4. **降级支持**：存储失败时自动降级到原始格式（包含 URL）

## 使用示例

### 基本搜索
```python
# LLM 调用
web_search(query="Python 函数定义教程")

# 返回结果（隐藏 URL）
"""
A Google search for 'Python 函数定义教程' found 5 results:

## Web Results

0. Python Functions Tutorial
Date published: 2024-01-15
Source: Python.org
This tutorial covers how to define functions in Python...

1. Defining Functions in Python
Date published: 2024-01-10
Learn about function definitions, parameters, and return values...

**Note**: To fetch full content from any result, use: web_fetch(index=N)
"""
```

### 配合 web_fetch 使用
```python
# 1. 搜索
web_search(query="Python async programming")

# 2. 获取第一个结果的完整内容
web_fetch(index=0)

# 3. 获取第三个结果的完整内容
web_fetch(index=2)
```

## 配置项

在 `config/schema/tool.py` 中配置：

```python
class ToolSettings(BaseModel):
    # 搜索超时时间（秒）
    web_search_tool_timeout_seconds: int = 30
    
    # 最大搜索结果数
    web_search_max_results: int = 10
    
    # 搜索结果缓存过期时间（小时）
    web_search_result_ttl_hours: int = 24
    
    # 每个 session 最多存储的搜索结果数
    web_search_result_max_per_session: int = 1000
```

环境变量：
```bash
# Serper API Key（必需）
export SERPER_API_KEY="your_api_key_here"
```

## 架构设计

### 数据流
```
LLM → web_search → Serper API → 原始结果
                                    ↓
                            SearchResultRaw 模型
                                    ↓
                            MongoDB 存储（带索引）
                                    ↓
                            SearchResultSimplified
                                    ↓
                            返回给 LLM（隐藏 URL）
```

### 存储结构
```python
# MongoDB 文档
{
    "session_id": "sess_123",
    "query": "Python tutorial",
    "index": 0,  # 数字索引
    "url": "https://...",  # 隐藏，不返回给 LLM
    "title": "Python Tutorial",
    "snippet": "...",
    "date_published": "2024-01-15",
    "source": "Python.org",
    "created_at": ISODate("2024-11-06T00:00:00Z")  # TTL 索引
}
```

## Token 节省对比

### 优化前（包含 URL）
```
1. [Python Tutorial](https://docs.python.org/3/tutorial/)
Date published: 2024-01-15
Source: Python.org
This tutorial introduces...
```
**Token 数**：约 60 tokens

### 优化后（隐藏 URL）
```
0. Python Tutorial
Date published: 2024-01-15
Source: Python.org
This tutorial introduces...
```
**Token 数**：约 20 tokens

**节省**：约 67% ✨

## 错误处理

### API 错误
- SERPER_API_KEY 未设置：返回错误提示
- API 超时：自动重试 5 次
- 无搜索结果：返回友好提示

### 存储错误
- MongoDB 连接失败：自动降级到原始格式（包含 URL）
- 存储超时：记录日志，返回原始格式
- 索引创建失败：记录警告，继续运行

## 性能优化

### MongoDB TTL 索引
- 自动清理 24 小时前的搜索结果
- 减少存储空间占用
- 后台任务每小时手动清理一次

### 批量操作
- 批量插入搜索结果（insert_many）
- 批量查询简化结果
- 减少数据库往返次数

## 监控指标

日志事件：
- `search_results_stored_and_simplified`：成功存储
- `search_result_store_failed`：存储失败（降级）
- `search_results_cleaned`：定期清理
- `search_results_cleanup_failed`：清理失败

## 相关工具

- **web_fetch**：通过索引获取完整网页内容
- **web_search（旧版）**：包含 URL 的原始格式（已废弃）

## 迁移指南

从旧版本迁移：
1. 无需修改 Agent 代码
2. 自动使用新的优化格式
3. 存储失败时自动降级到旧格式
4. 向后兼容，无破坏性变更
