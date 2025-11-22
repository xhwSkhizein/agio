# Agio Configuration Files

This directory contains YAML configuration files for all Agio components.

## Directory Structure

```
configs/
├── models/          # LLM model configurations
├── agents/          # Agent configurations
├── tools/           # Tool configurations
├── memory/          # Memory system configurations
├── knowledge/       # Knowledge base configurations
└── hooks/           # Hook configurations
```

## Available Configurations

### Models (4)
- `gpt4.yaml` - OpenAI GPT-4 Turbo (production)
- `gpt35.yaml` - OpenAI GPT-3.5 Turbo (fast, cost-effective)
- `deepseek.yaml` - DeepSeek model (cost-effective)
- `claude.yaml` - Anthropic Claude 3 Opus (disabled by default)

### Agents (4)
- `simple_assistant.yaml` - Simple general-purpose assistant
- `customer_support.yaml` - Customer support agent with knowledge base
- `code_assistant.yaml` - AI coding assistant
- `research_agent.yaml` - Research agent with web search

### Tools (10)
- `web_search.yaml` - Web search functionality
- `calculator.yaml` - Mathematical calculations
- `search_knowledge.yaml` - Knowledge base search
- `create_ticket.yaml` - Support ticket creation
- `send_email.yaml` - Email notifications
- `code_search.yaml` - Codebase search
- `run_tests.yaml` - Test runner
- `format_code.yaml` - Code formatter
- `scrape_webpage.yaml` - Web scraping
- `summarize_text.yaml` - Text summarization

### Memory (2)
- `conversation_memory.yaml` - Simple conversation memory
- `semantic_memory.yaml` - Semantic memory with vectors (disabled)

### Knowledge (2)
- `product_docs.yaml` - Product documentation
- `research_database.yaml` - Research database

### Hooks (2)
- `logging_hook.yaml` - Event logging
- `metrics_hook.yaml` - Metrics collection (disabled)

## Environment Variables

The following environment variables are used in configurations:

```bash
# Model API Keys
export OPENAI_API_KEY="your-openai-key"
export DEEPSEEK_API_KEY="your-deepseek-key"
export ANTHROPIC_API_KEY="your-anthropic-key"

# Tool Integrations
export TICKETING_API_URL="https://tickets.example.com/api"
export TICKETING_API_KEY="your-ticketing-key"
export SMTP_SERVER="smtp.example.com"
export SMTP_USERNAME="your-smtp-username"
export SMTP_PASSWORD="your-smtp-password"

# Development
export REPO_PATH="/path/to/your/repo"
```

## Usage

### Load All Configurations

```python
from agio.registry import load_from_config

# Load all configurations
load_from_config("./configs")
```

### Load Specific Component Type

```python
from agio.registry import ConfigLoader, ComponentType

loader = ConfigLoader("./configs")
models = loader.load_directory(ComponentType.MODEL)
agents = loader.load_directory(ComponentType.AGENT)
```

### Get Component from Registry

```python
from agio.registry import get_registry

registry = get_registry()

# Get agent
agent = registry.get("customer_support")

# Get model
model = registry.get("gpt4")
```

## Configuration Features

### Environment Variable Resolution

Use `${ENV_VAR}` syntax to reference environment variables:

```yaml
api_key: ${OPENAI_API_KEY}
api_base: ${CUSTOM_API_BASE}
```

### Configuration Inheritance

Extend existing configurations:

```yaml
type: agent
name: my_agent
extends: simple_assistant  # Inherit from simple_assistant
model: gpt4  # Override model
```

### Tags for Organization

Use tags to organize and filter components:

```yaml
tags:
  - production
  - customer-service
  - high-priority
```

### Enable/Disable Components

Control which components are active:

```yaml
enabled: true  # or false
```

## Best Practices

1. **Use Environment Variables** for sensitive data (API keys, passwords)
2. **Tag Configurations** for easy filtering and organization
3. **Disable Unused Components** to avoid unnecessary resource usage
4. **Document Configurations** with clear descriptions
5. **Version Control** configuration files (but not secrets!)

## Validation

Test your configurations:

```bash
# Run configuration tests
uv run pytest tests/test_registry.py -v

# Validate specific config
uv run python -c "from agio.registry import ConfigValidator; ConfigValidator().validate('configs/agents/customer_support.yaml')"
```
