# OTLP Export Setup Guide

本指南说明如何配置 Agio 将 Trace 导出到 OpenTelemetry 兼容的后端（Jaeger、Zipkin、SkyWalking 等）。

## 配置方式

### 环境变量

在 `.env` 文件或环境中设置：

```bash
# 启用 OTLP 导出
AGIO_OTLP_ENABLED=true

# OTLP 端点（根据后端选择）
AGIO_OTLP_ENDPOINT=http://localhost:4317

# 协议：grpc 或 http
AGIO_OTLP_PROTOCOL=grpc

# 可选：自定义 Headers（用于认证等）
# AGIO_OTLP_HEADERS='{"Authorization": "Bearer token"}'
```

---

## 后端配置示例

### 1. Jaeger

#### 使用 Docker 启动 Jaeger

```bash
docker run -d --name jaeger \
  -e COLLECTOR_OTLP_ENABLED=true \
  -p 16686:16686 \
  -p 4317:4317 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest
```

#### Agio 配置

```bash
AGIO_OTLP_ENABLED=true
AGIO_OTLP_ENDPOINT=http://localhost:4317
AGIO_OTLP_PROTOCOL=grpc
```

#### 访问 Jaeger UI

打开浏览器访问：`http://localhost:16686`

---

### 2. Zipkin

#### 使用 Docker 启动 Zipkin

```bash
docker run -d --name zipkin \
  -p 9411:9411 \
  openzipkin/zipkin:latest
```

#### Agio 配置

```bash
AGIO_OTLP_ENABLED=true
AGIO_OTLP_ENDPOINT=http://localhost:9411/api/v2/spans
AGIO_OTLP_PROTOCOL=http
```

#### 访问 Zipkin UI

打开浏览器访问：`http://localhost:9411`

---

### 3. SkyWalking

#### 使用 Docker Compose 启动 SkyWalking

创建 `docker-compose.yml`：

```yaml
version: '3.8'
services:
  oap:
    image: apache/skywalking-oap-server:latest
    container_name: skywalking-oap
    ports:
      - "11800:11800"  # gRPC
      - "12800:12800"  # HTTP
    environment:
      SW_STORAGE: h2

  ui:
    image: apache/skywalking-ui:latest
    container_name: skywalking-ui
    ports:
      - "8080:8080"
    environment:
      SW_OAP_ADDRESS: http://oap:12800
```

启动：

```bash
docker-compose up -d
```

#### Agio 配置

```bash
AGIO_OTLP_ENABLED=true
AGIO_OTLP_ENDPOINT=http://localhost:11800
AGIO_OTLP_PROTOCOL=grpc
```

#### 访问 SkyWalking UI

打开浏览器访问：`http://localhost:8080`

---

## 依赖安装

OTLP 导出需要安装 OpenTelemetry SDK：

```bash
pip install opentelemetry-exporter-otlp
```

或者安装完整的 OpenTelemetry 包：

```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc
```

---

## 验证导出

### 1. 运行示例

```bash
python examples/trace_example.py
```

### 2. 检查日志

查看是否有 `trace_exported` 日志：

```
INFO - trace_exported trace_id=abc123 span_count=3
```

### 3. 在后端 UI 查看

- **Jaeger**: 搜索 Service Name = `agio`
- **Zipkin**: 查找最近的 Traces
- **SkyWalking**: 在 Trace 页面查看

---

## Span 映射

Agio Span 到 OTLP Span 的映射：

| Agio SpanKind | OTLP SpanKind | 说明 |
|---------------|---------------|------|
| WORKFLOW | INTERNAL | 内部执行 |
| STAGE | INTERNAL | 内部执行 |
| AGENT | INTERNAL | 内部执行 |
| LLM_CALL | CLIENT | 调用外部 LLM API |
| TOOL_CALL | CLIENT | 调用外部工具 |

### Attributes 映射

LLM Call Span 会包含：

```
llm.model = "gpt-4o"
llm.tokens.total = 300
llm.tokens.input = 100
llm.tokens.output = 200
```

Tool Call Span 会包含：

```
tool.name = "web_search"
```

---

## 故障排查

### 1. 导出失败

**检查端点连接**：

```bash
# 测试 gRPC 端点
grpcurl -plaintext localhost:4317 list

# 测试 HTTP 端点
curl http://localhost:4318/v1/traces
```

**检查日志**：

```bash
# 查看 Agio 日志
grep "otlp_exporter" logs/agio.log
```

### 2. Trace 未显示

- 确认后端已启动并监听正确端口
- 检查防火墙/网络配置
- 验证 OTLP 协议匹配（gRPC vs HTTP）

### 3. 依赖缺失

```bash
# 安装缺失的包
pip install opentelemetry-exporter-otlp-proto-grpc
```

---

## 生产环境建议

### 1. 使用采样

避免导出所有 Trace，设置采样率：

```bash
# 10% 采样（随机采样）
AGIO_OTLP_SAMPLING_RATE=0.1

# 100% 采样（默认）
AGIO_OTLP_SAMPLING_RATE=1.0

# 禁用导出
AGIO_OTLP_SAMPLING_RATE=0.0
```

采样策略：
- 使用随机采样
- 采样率范围：0.0 ~ 1.0
- 被采样掉的 Trace 仍会保存到 MongoDB，只是不导出到 OTLP

### 2. 批量导出

使用 BatchSpanProcessor 减少网络开销（未来支持）。

### 3. 认证

生产环境使用 Headers 进行认证：

```bash
AGIO_OTLP_HEADERS='{"Authorization": "Bearer your-token"}'
```

---

## 参考资料

- [OpenTelemetry Specification](https://opentelemetry.io/docs/specs/otel/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [Zipkin Documentation](https://zipkin.io/)
- [SkyWalking Documentation](https://skywalking.apache.org/)
