# Agio Configuration System

## Overview

The Agio configuration system provides a powerful, YAML-based approach to defining and managing Agent components. This allows you to:

- 📝 Define components declaratively in YAML
- 🔄 Hot-reload configurations without restarting
- 🔗 Reference and compose components
- ✅ Validate configurations with Pydantic
- 🌍 Manage environment-specific settings

## Quick Start

### 1. Create a Model Configuration

Create `configs/models/gpt4.yaml`:

```yaml
type: model
name: gpt4
description: "GPT-4 Turbo Preview"

provider: openai
model: gpt-4-turbo-preview
api_key: ${OPENAI_API_KEY}

temperature: 0.7
max_tokens: 4096

tags:
  - openai
  - production
```

### 2. Create an Agent Configuration

Create `configs/agents/assistant.yaml`:

```yaml
type: agent
name: assistant
description: "Helpful assistant"

model: gpt4  # Reference to model
system_prompt: "You are a helpful assistant."

tags:
  - general
```

### 3. Load and Use

```python
from agio.registry import load_from_config, get_registry

# Load all configurations
load_from_config("./configs")

# Get components from registry
registry = get_registry()
agent = registry.get("assistant")

# Use the agent
async for chunk in agent.arun("Hello!"):
    print(chunk, end="", flush=True)
```

## Configuration Types

### Model Configuration

```yaml
type: model
name: gpt4
provider: openai  # openai, deepseek, anthropic, custom
model: gpt-4-turbo-preview

# API Configuration
api_key: ${OPENAI_API_KEY}
api_base: https://api.openai.com/v1

# Parameters
temperature: 0.7
max_tokens: 4096
top_p: 0.9

# Advanced
timeout: 120
max_retries: 3
```

### Agent Configuration

```yaml
type: agent
name: my_agent
model: gpt4  # Model reference

# Optional components
tools:
  - search_tool
  - calculator
memory: redis_memory
knowledge: product_docs

# Configuration
system_prompt: "You are helpful"
max_steps: 10
```

### Tool Configuration

```yaml
type: tool
name: search_tool
tool_type: function  # function, class, mcp

# Function Tool
function_path: "mypackage.search_function"

# OR Class Tool
# class_path: "mypackage.SearchTool"
# class_params:
#   api_key: ${SEARCH_API_KEY}
```

## Features

### Environment Variables

Use `${ENV_VAR}` syntax to reference environment variables:

```yaml
api_key: ${OPENAI_API_KEY}
database_url: ${DATABASE_URL}
```

### Configuration Inheritance

Extend existing configurations:

```yaml
# configs/models/gpt4-creative.yaml
extends: gpt4
temperature: 0.9
tags:
  - creative
```

### Component References

Reference other components by name:

```yaml
model: gpt4  # Direct reference
model: ref:gpt4  # Explicit reference
```

## API Reference

### Loading Configurations

```python
from agio.registry import load_from_config, get_registry

# Load from directory
registry = load_from_config("./configs")

# Get component
agent = registry.get("my_agent")
```

### Manual Registration

```python
from agio.registry import ComponentRegistry, ModelConfig

registry = ComponentRegistry()

# Create config
config = ModelConfig(
    name="gpt4",
    provider="openai",
    model="gpt-4-turbo-preview",
    api_key="sk-..."
)

# Create and register component
from agio.models.openai import OpenAIModel
model = OpenAIModel(...)
registry.register("gpt4", model, config)
```

### Query Components

```python
# Get by name
agent = registry.get("my_agent")

# List by type
from agio.registry import ComponentType
models = registry.list_by_type(ComponentType.MODEL)

# List by tag
prod_agents = registry.list_by_tag("production")
```

## Best Practices

1. **Organize by Type**: Keep configurations in type-specific directories
   ```
   configs/
     models/
     agents/
     tools/
   ```

2. **Use Environment Variables**: Never commit secrets
   ```yaml
   api_key: ${OPENAI_API_KEY}  # ✅ Good
   api_key: "sk-actual-key"     # ❌ Bad
   ```

3. **Tag Appropriately**: Use tags for filtering
   ```yaml
   tags:
     - production
     - v2
     - customer-support
   ```

4. **Document Configs**: Add descriptions
   ```yaml
   description: "Production GPT-4 model with optimized settings"
   ```

## Examples

See the `configs/` directory for complete examples:
- `configs/models/gpt4.yaml` - OpenAI GPT-4 configuration
- `configs/models/deepseek.yaml` - DeepSeek configuration
- `configs/agents/simple_assistant.yaml` - Simple agent

## Testing

Run the configuration system tests:

```bash
pytest tests/test_registry.py -v
```

## Next Steps

- Check out `agio/registry/DESIGN.md` for detailed design documentation
- Explore dynamic configuration management (hot reload, API updates)
- Learn about the execution control system for checkpoints and time-travel debugging
