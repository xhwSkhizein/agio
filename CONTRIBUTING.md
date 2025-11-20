# Contributing to Agio

Thank you for your interest in contributing to Agio! 🎉

This document provides guidelines and instructions for contributing to the project.

---

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)
- [Community](#community)

---

## 📜 Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9 or higher
- Git
- Basic understanding of async/await in Python
- Familiarity with AI agents and LLMs (helpful but not required)

### Find an Issue

1. Browse [open issues](https://github.com/yourusername/agio/issues)
2. Look for issues labeled `good first issue` or `help wanted`
3. Comment on the issue to let others know you're working on it

---

## 💻 Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/agio.git
cd agio

# Add upstream remote
git remote add upstream https://github.com/yourusername/agio.git
```

### 2. Create a Virtual Environment

```bash
# Using venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Or using conda
conda create -n agio python=3.12
conda activate agio
```

### 3. Install Dependencies

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Or install from requirements
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. Set Up Pre-commit Hooks

```bash
pre-commit install
```

### 5. Verify Installation

```bash
# Run tests
pytest

# Check code style
ruff check .

# Type check
mypy agio
```

---

## 🤝 How to Contribute

### Types of Contributions

1. **Bug Reports** - Report bugs via GitHub Issues
2. **Feature Requests** - Suggest new features
3. **Code Contributions** - Fix bugs or implement features
4. **Documentation** - Improve docs, add examples
5. **Tests** - Add or improve test coverage
6. **Reviews** - Review pull requests

### Reporting Bugs

When reporting bugs, please include:

- **Description**: Clear description of the bug
- **Steps to Reproduce**: Minimal code to reproduce the issue
- **Expected Behavior**: What you expected to happen
- **Actual Behavior**: What actually happened
- **Environment**: Python version, OS, Agio version
- **Logs**: Relevant error messages or logs

**Template**:

```markdown
**Bug Description**
A clear description of what the bug is.

**To Reproduce**
```python
# Minimal code to reproduce
```

**Expected Behavior**
What you expected to happen.

**Environment**
- Python version: 3.12
- Agio version: 0.1.0
- OS: macOS 14.0
```

### Suggesting Features

When suggesting features, please include:

- **Use Case**: Why is this feature needed?
- **Proposed Solution**: How should it work?
- **Alternatives**: Other solutions you've considered
- **Examples**: Code examples if applicable

---

## 📝 Coding Standards

### Code Style

We follow **PEP 8** with some modifications:

- **Line Length**: 100 characters (not 79)
- **Quotes**: Double quotes for strings
- **Imports**: Absolute imports, sorted alphabetically
- **Type Hints**: Required for all functions and class attributes

### Type Annotations

```python
# ✅ Good
def process_query(query: str, max_tokens: int = 100) -> str:
    return query[:max_tokens]

# ❌ Bad
def process_query(query, max_tokens=100):
    return query[:max_tokens]
```

### Async/Await

```python
# ✅ Good - Async function with proper typing
async def fetch_data(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

# ❌ Bad - Blocking I/O in async function
async def fetch_data(url: str) -> dict:
    response = requests.get(url)  # Blocking!
    return response.json()
```

### Naming Conventions

- **Modules**: `snake_case` (e.g., `agent_runner.py`)
- **Classes**: `PascalCase` (e.g., `AgentRunner`)
- **Functions/Variables**: `snake_case` (e.g., `run_agent`)
- **Constants**: `UPPER_CASE` (e.g., `MAX_RETRIES`)
- **Private**: Prefix with `_` (e.g., `_internal_method`)

### Documentation

All public APIs must have docstrings:

```python
def create_agent(
    model: Model,
    tools: list[Tool],
    instruction: str | None = None
) -> Agent:
    """
    Create a new Agent instance.
    
    Args:
        model: The language model to use
        tools: List of tools available to the agent
        instruction: System instruction for the agent
        
    Returns:
        Agent: Configured agent instance
        
    Example:
        ```python
        agent = create_agent(
            model=OpenAIModel(),
            tools=[search_tool],
            instruction="You are a helpful assistant"
        )
        ```
    """
    return Agent(model=model, tools=tools, system_prompt=instruction)
```

### Error Handling

```python
# ✅ Good - Specific exceptions with context
try:
    result = await execute_tool(tool_call)
except ToolExecutionError as e:
    log_error(f"Tool {tool_call.name} failed: {e}")
    raise AgentExecutionError(f"Failed to execute {tool_call.name}") from e

# ❌ Bad - Bare except
try:
    result = await execute_tool(tool_call)
except:
    pass
```

---

## 🧪 Testing Guidelines

### Writing Tests

- **Location**: Tests go in `tests/` directory
- **Naming**: Test files start with `test_` (e.g., `test_agent.py`)
- **Structure**: One test file per module
- **Coverage**: Aim for >80% code coverage

### Test Structure

```python
import pytest
from agio import Agent
from agio.models import OpenAIModel

@pytest.fixture
def agent():
    """Fixture for creating a test agent."""
    return Agent(
        model=OpenAIModel(),
        tools=[],
        name="test_agent"
    )

@pytest.mark.asyncio
async def test_agent_basic_query(agent):
    """Test agent can handle a basic query."""
    response = ""
    async for chunk in agent.arun("Hello"):
        response += chunk
    
    assert len(response) > 0
    assert isinstance(response, str)

@pytest.mark.asyncio
async def test_agent_with_tools(agent):
    """Test agent can use tools."""
    # Test implementation
    pass
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_agent.py

# Run with coverage
pytest --cov=agio --cov-report=html

# Run with verbose output
pytest -v

# Run only fast tests
pytest -m "not slow"
```

### Test Categories

Use markers to categorize tests:

```python
@pytest.mark.unit
def test_unit():
    pass

@pytest.mark.integration
async def test_integration():
    pass

@pytest.mark.slow
async def test_slow_operation():
    pass
```

---

## 📝 Commit Guidelines

### Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

### Examples

```bash
# Feature
feat(agent): add support for streaming events

# Bug fix
fix(tools): handle null return values correctly

# Documentation
docs(readme): update installation instructions

# Refactor
refactor(runner): extract event handler to separate class

# Test
test(agent): add tests for error handling
```

### Commit Best Practices

- **Atomic Commits**: One logical change per commit
- **Clear Messages**: Describe what and why, not how
- **Present Tense**: "Add feature" not "Added feature"
- **Reference Issues**: Include issue number if applicable

```bash
# ✅ Good
git commit -m "feat(agent): add memory persistence (#123)"

# ❌ Bad
git commit -m "fixed stuff"
```

---

## 🔄 Pull Request Process

### Before Submitting

1. **Update from upstream**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run tests**:
   ```bash
   pytest
   ```

3. **Check code style**:
   ```bash
   ruff check .
   ruff format .
   ```

4. **Type check**:
   ```bash
   mypy agio
   ```

5. **Update documentation** if needed

### Creating a Pull Request

1. **Push to your fork**:
   ```bash
   git push origin your-branch-name
   ```

2. **Open PR on GitHub**

3. **Fill out the PR template**:
   - Description of changes
   - Related issues
   - Type of change (bug fix, feature, etc.)
   - Testing done
   - Checklist

### PR Template

```markdown
## Description
Brief description of what this PR does.

## Related Issues
Fixes #123

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Added new tests
- [ ] All tests pass
- [ ] Manual testing done

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings
```

### Review Process

1. **Automated Checks**: CI must pass
2. **Code Review**: At least one maintainer approval
3. **Discussion**: Address review comments
4. **Merge**: Maintainer will merge when ready

### After Merge

1. **Delete branch**: Clean up your branch
2. **Update fork**: Sync with upstream
3. **Celebrate**: You're a contributor! 🎉

---

## 👥 Community

### Communication Channels

- **GitHub Discussions**: For questions and discussions
- **Discord**: Real-time chat and support
- **Twitter**: Follow [@AgioFramework](https://twitter.com/AgioFramework)

### Getting Help

- **Documentation**: Check [docs/](docs/)
- **Examples**: Browse [examples/](examples/)
- **Issues**: Search existing issues
- **Discord**: Ask in #help channel

### Recognition

Contributors are recognized in:
- [CONTRIBUTORS.md](CONTRIBUTORS.md)
- Release notes
- Project README

---

## 📚 Resources

### Learning Resources

- [Python Async/Await Tutorial](https://realpython.com/async-io-python/)
- [Type Hints Guide](https://docs.python.org/3/library/typing.html)
- [Pytest Documentation](https://docs.pytest.org/)

### Project Resources

- [Architecture Documentation](docs/architecture/)
- [API Reference](docs/api/)
- [Development Guides](docs/guides/)

---

## ❓ FAQ

### Q: How do I get assigned to an issue?
A: Comment on the issue expressing your interest. Maintainers will assign it to you.

### Q: Can I work on multiple issues at once?
A: Yes, but we recommend focusing on one at a time for better quality.

### Q: How long does PR review take?
A: Usually 1-3 days. Complex PRs may take longer.

### Q: My PR was rejected. What now?
A: Don't worry! Address the feedback and resubmit. We're here to help.

### Q: Can I contribute if I'm a beginner?
A: Absolutely! Look for `good first issue` labels.

---

## 🙏 Thank You!

Your contributions make Agio better for everyone. We appreciate your time and effort!

---

**Questions?** Open an issue or ask in [Discord](https://discord.gg/agio).

**Happy Contributing!** 🚀
