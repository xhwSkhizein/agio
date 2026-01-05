## 🔧 开发与发布

### 自动发布（GitHub Actions）

项目配置了 GitHub Actions 工作流，可以自动发布到 PyPI。

#### 配置 GitHub Secrets

在 GitHub 仓库设置中添加以下 Secrets：

1. **PYPI_API_TOKEN**（必需）：PyPI API Token
   - 访问 [PyPI 账户设置](https://pypi.org/manage/account/) 创建 API Token
   - 在 GitHub 仓库 Settings → Secrets and variables → Actions 中添加

2. **TEST_PYPI_API_TOKEN**（可选）：TestPyPI API Token（用于测试发布）
   - 访问 [TestPyPI 账户设置](https://test.pypi.org/manage/account/) 创建 API Token

#### 发布方式

**方式 1：通过 Release 发布（推荐）**

1. 更新版本号：在 `pyproject.toml` 和 `agio/__init__.py` 中同步更新版本号
2. 提交并推送代码
3. 在 GitHub 创建 Release：
   - 点击 "Releases" → "Create a new release"
   - 选择或创建新的 tag（例如 `v0.1.0`）
   - 填写 Release 标题和描述
   - 点击 "Publish release"
4. GitHub Actions 会自动构建并发布到 PyPI

**方式 2：手动触发**

1. 在 GitHub Actions 页面选择 "发布到 PyPI" 工作流
2. 点击 "Run workflow" 手动触发
3. 工作流会发布到 TestPyPI（如果配置了 TEST_PYPI_API_TOKEN）

### 手动发布

#### 发布前准备

1. **更新版本号**：在 `pyproject.toml` 和 `agio/__init__.py` 中同步更新版本号

2. **运行预发布检查**：
```bash
./scripts/prepare_release.sh
```

### 构建包

```bash
./scripts/build_package.sh
```

构建完成后，会在 `dist/` 目录生成以下文件：
- `agio-X.X.X-py3-none-any.whl` - 轮子文件（推荐）
- `agio-X.X.X.tar.gz` - 源码分发包

### 检查包

```bash
./scripts/check_package.sh
```

### 本地测试安装

在发布前，建议先本地测试安装：

```bash
pip install dist/agio-*.whl
# 或
pip install dist/agio-*.tar.gz
```

测试命令行工具：
```bash
agio-server --help
```

### 发布到 TestPyPI（测试）

首次发布建议先发布到 TestPyPI 进行测试：

```bash
./scripts/publish_package.sh testpypi
```

测试安装：
```bash
pip install --index-url https://test.pypi.org/simple/ agio
```

### 发布到 PyPI（生产）

测试通过后，发布到正式 PyPI：

```bash
./scripts/publish_package.sh pypi
```

### PyPI 凭证配置

发布前需要配置 PyPI 凭证，推荐使用 API Token：

1. **使用 API Token（推荐）**：
   - 在 [PyPI 账户设置](https://pypi.org/manage/account/) 创建 API Token
   - 设置环境变量：
     ```bash
     export TWINE_USERNAME=__token__
     export TWINE_PASSWORD=pypi-你的token
     ```

2. **使用 ~/.pypirc 文件**：
   ```ini
   [pypi]
   username = __token__
   password = pypi-你的token

   [testpypi]
   username = __token__
   password = pypi-你的testpypi-token
   ```

3. **使用传统用户名密码**（不推荐）：
   ```bash
     export TWINE_USERNAME=你的用户名
     export TWINE_PASSWORD=你的密码
   ```
