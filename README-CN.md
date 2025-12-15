<img src="diagrams/logo.png" width="150" height="150">


# Vito's Pizza Cafe - AI客户服务应用程序

一个披萨咖啡厅客户服务应用程序，演示AI安全漏洞及其使用Palo Alto Networks AI运行时安全(AIRS)的缓解措施。使用LangGraph和RAG(检索增强生成)构建，这个项目作为实施AI安全最佳实践的实用示例。

## 概述

这个应用程序演示了生成式AI应用程序中的常见攻击向量，特别是在基于RAG的系统中，并展示了如何使用Palo Alto Networks AI运行时安全API来保护免受这些攻击。

## 先决条件

- Python 3.12或更高版本
- pip包管理器
- **uv** (推荐): 快速Python包管理器和工具运行器
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Node.js和npm** (可选): 如果你想使用AMAP-STDIO MCP传输，则需要
  - `npx`命令(包含在npm中)用于运行AMAP MCP服务器
- Docker和Docker Compose (LiteLLM代理所需)
- API密钥:
  - **OpenAI API密钥**: RAG系统中的文本嵌入和LLM响应所需
  - **其他LLM提供商选项** (如果不使用OpenAI进行LLM):
    - DeepSeek API密钥
    - OpenRouter API密钥
    - 或使用LiteLLM代理统一访问多个提供商
  - **Palo Alto Networks AIRS API密钥**: AI安全功能所需
- Palo Alto Networks AI运行时安全(AIRS) API配置文件，用于输入和输出检查

## 应用程序架构

### 系统概述
    
![应用程序架构](diagrams/vitos_airs.png)

### 消息处理流程

应用程序使用**LangGraph React代理模式**，其中LLM自主决定使用哪些工具:

1. 用户通过聊天机器人Web UI提交查询
2. 聊天机器人Web UI安全地将查询转发给应用程序
3. 基于查询从向量存储中检索相关文档(始终执行)
4. 应用程序使用可用工具(数据库、MCP)创建React代理并发送带有上下文的查询
5. LLM分析查询并**有条件地**根据需要调用工具:
   - 客户信息查询的数据库工具
   - 位置相关查询的MCP工具(如AMAP)
6. 使用检索的上下文和工具结果(如果有)生成响应
7. 响应发送给用户

**注意:** 步骤5-6因查询而异 - 并非每个请求都会调用所有工具。

### 核心组件

应用程序由以下组件组成:
- 用于信息检索的RAG系统
    - 基于markdown标签的分块
    - FAISS向量存储
    - 基于OpenAI嵌入的相似性搜索(`text-embedding-3-small`)
- LangGraph React代理基础对话流程
- SQLite数据库
- 使用LangChain绑定工具的数据库集成
- MCP与LangChain
- LiteLLM集成
- MCP中继

## 安装指南

1. 克隆存储库:
```bash
git clone https://github.com/leonhanl/vitos-pizza-cafe
cd vitos-pizza-cafe
```

2. 创建并激活虚拟环境:
```bash
python -m venv .venv
# 在Windows上:
.venv\Scripts\activate
# 在Unix或MacOS上:
source .venv/bin/activate
```

3. 安装依赖项:
```bash
pip install -e .
```

4. 配置环境变量:
```bash
cp .env.example .env
# 使用您的API密钥和配置编辑.env
# 查看.env.example了解所有可用的LLM提供商选项
```

## 运行应用程序

1. 启动后端:
   ```bash
   ./start_backend.sh
   # 或
   ./restart_backend.sh
   ```

   要验证后端API:
   ```bash
   python tests/test_basic_api.py
   ```

   要运行完整的后端API测试套件:
   ```bash
   python tests/test_api_integration.py
   ```

2. 启动Web界面:
   ```bash
   ./start_frontend.sh
   # 或
   ./restart_frontend.sh
   ```

   打开Web浏览器并导航到: http://localhost:5500

3. 使用常见问题测试应用程序:
   ```
   What's on the menu?
   Do you deliver?
   ```

4. 完成后停止服务器:
   ```bash
   ./stop_backend.sh
   ./stop_frontend.sh
   ```

**注意**: 启动脚本在后台运行服务器。日志存储在`logs/`目录中。

### 不同域的前端配置

如果您的前端和后端部署在不同的域上(例如，前端在`vitos.lianglab.net`，后端在`vitos-api.lianglab.net`)，您可以使用`BACKEND_API_URL`环境变量配置后端API URL。

**选项1: 与start_frontend.sh内联**
```bash
BACKEND_API_URL="https://vitos-api.lianglab.net" ./start_frontend.sh
```

**选项2: 与restart_frontend.sh内联**
```bash
BACKEND_API_URL="https://vitos-api.lianglab.net" ./restart_frontend.sh
```

**选项3: 对多个命令使用export**
```bash
export BACKEND_API_URL="https://vitos-api.lianglab.net"
./start_frontend.sh  # 或 ./restart_frontend.sh
```

**注意**:
- 不要包含`/api/v1`后缀 - 它将自动添加
- 如果未设置`BACKEND_API_URL`，前端默认为`http://localhost:8000`
- 配置在启动时自动生成到`frontend/config.js`中

## LiteLLM代理 (可选)

LiteLLM是一个统一的API网关，通过单一接口访问多个LLM提供商。它特别适用于:

- **多提供商支持**: 在OpenAI、DeepSeek、Qwen和其他模型之间切换，无需更改代码
- **内置护栏**: 在代理级别可选的AIRS安全扫描
- **成本跟踪**: 监控不同提供商的API使用和成本
- **负载均衡**: 在多个模型或API密钥之间分配请求

### 设置

1. 导航到litellm目录并启动代理:
   ```bash
   cd litellm
   docker-compose up -d
   ```

   打开浏览器访问Web UI: http://localhost:4000/ui/

2. 通过更新`.env`配置您的应用程序使用代理:
   ```bash
   OPENAI_BASE_URL="http://localhost:4000"
   OPENAI_API_KEY=your_litellm_master_key_here
   LLM_MODEL=deepseek-chat  # 或在litellm_config.yaml中配置的任何模型
   ```

### 支持的模型

LiteLLM代理预配置了:

- **OpenAI**: `gpt-5`, `gpt-5-mini`, `gpt-5-nano`
- **DeepSeek**: `deepseek-chat`, `deepseek-reasoner`
- **阿里巴巴Qwen**: `qwen-max`, `qwen-plus`

您可以通过编辑`litellm/litellm_config.yaml`添加更多模型。

### AIRS集成

配置中的某些模型启用了可选的AIRS护栏。这些在请求到达您的应用程序之前在代理级别提供输入/输出过滤。

要停止LiteLLM代理:
```bash
cd litellm
docker-compose down
```

要拆除LiteLLM代理:
```bash
cd litellm
docker-compose down -v
```

## MCP集成 (可选)

模型上下文协议(MCP)通过标准化工具集成扩展应用程序的附加功能。这个项目演示了两种不同的MCP集成方法。

### 集成方法

**重要**: 选择一种方法 - 它们是互斥的:

| 方法 | 配置 | 用例 |
|----------|--------------|----------|
| **直接连接** | 仅`.env` | 简单设置，直接访问MCP服务器 |
| **代理模式** | `mcp-relay.yaml` | 使用AIRS的安全扫描，集中化网关 |

### 直接MCP连接 (AMAP)

[AMAP (高德)](https://lbs.amap.com/api/mcp-server/gettingstarted)是中国领先的基于位置的服务提供商，通过其MCP服务器集成提供地图和地理编码功能。

**用例**: 这个MCP工具使AI助手能够回答配送相关问题，如"你们配送到[位置]吗？"，通过计算客户位置与Vito's Pizza Cafe之间的距离。该工具提供地理编码、距离计算和路线规划功能，帮助根据配送半径确定服务可用性。

**集成**: 直接连接到AMAP服务，无需安全代理(对于基于代理的安全扫描，请参见下面的PAN MCP Relay部分)。

**支持的传输**:
- **AMAP-SSE** (服务器发送事件): 基于HTTP的流式传输
- **AMAP-STDIO** (标准I/O): 通过`npx`的本地子进程

**在`.env`中配置**:
```bash
AMAP_API_KEY=your_amap_api_key_here

# 启用一种传输类型
AMAP_SSE_ENABLED=true   # 用于SSE传输
AMAP_STDIO_ENABLED=false

# 或
AMAP_SSE_ENABLED=false
AMAP_STDIO_ENABLED=true  # 用于stdio传输(需要npx)
```

**重要**: 当使用PAN MCP Relay时，禁用直接AMAP连接(两者都设置为`false`)。

### PAN MCP Relay (集中安全代理)

[PAN MCP Relay](https://github.com/PaloAltoNetworks/pan-mcp-relay)是Palo Alto Networks的安全增强MCP中继服务器，作为所有MCP工具的集中网关。它通过扫描工具交互提供实时AI威胁保护:

- 提示注入和越狱尝试
- 恶意URL和有毒内容
- 敏感数据泄露(PII/PCI)
- AI代理威胁和不安全输出

**关键架构**: 中继位于您的应用程序和所有上游MCP服务器之间，通过AIRS安全配置文件扫描工具描述、参数和响应。

```
Vito's Backend → PAN MCP Relay (端口 8800) → 上游MCP服务器 (AMAP等)
                      ↓ AIRS安全检查
```

**设置**:

1. **在`pan-mcp-relay/mcp-relay.yaml`中配置所有MCP服务器**:
   ```yaml
   mcpRelay:
     apiKey: <AIRS_API_KEY>
     aiProfile: Demo-Profile-for-Input

   mcpServers:
     amap:
       command: npx
       args:
         - -y
         - "@amap/amap-maps-mcp-server"
       env:
         AMAP_MAPS_API_KEY: <API_KEY>
   ```

2. **启动中继服务器**:
   ```bash
   cd pan-mcp-relay
   ./start_pan_mcp_relay.sh
   ```

   中继将监听http://localhost:8800

3. **在`.env`中的应用程序中启用**:
   ```bash
   # 启用PAN MCP Relay
   PAN_MCP_RELAY_ENABLED=true
   PAN_MCP_RELAY_URL=http://127.0.0.1:8800/mcp/

   # 禁用直接MCP连接
   AMAP_SSE_ENABLED=false
   AMAP_STDIO_ENABLED=false
   ```

4. **启动您的应用程序**:
   ```bash
   ./start_backend.sh
   ```

**要求**:
- 有效的Palo Alto Networks AIRS API密钥
- 在Strata Cloud Manager中配置的AI安全配置文件
- 安装Node.js和npm(`npx`命令可用)

**重要**: 所有MCP服务器必须在`mcp-relay.yaml`中定义 - 中继充当所有工具集成的单一访问点。

要停止中继:
```bash
# 找到并停止中继进程
pkill -f pan-mcp-relay
```

## 红队API使用

后端API支持有状态和无状态模式:

### 无状态模式 (红队推荐)

对于批量测试和红队场景，使用无状态模式以防止内存泄漏:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What pizzas do you have?", "stateless": true}'
```

**无状态模式的优点**:
- 内存中不存储对话历史
- 不需要对话ID管理
- 适合运行数百或数千个测试用例
- 每个请求的内存占用为零

### 有状态模式 (默认)

用于测试多轮对话:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What pizzas do you have?", "conversation_id": "test-123"}'
```

### Python API客户端

对于编程访问，使用`tests/api_client.py`中的Python客户端:

```python
from tests.api_client import VitosApiClient

with VitosApiClient(base_url="http://localhost:8000") as client:
    # 红队的无状态模式
    response = client.chat("What's on the menu?", stateless=True)
    print(response)

    # 带对话跟踪的有状态模式
    response = client.chat("What's your special today?", conversation_id="test-123")
```

有关两种模式的全面示例，请参见`tests/test_api_integration.py`。

## AI运行时安全(AIRS) - 流式保护

应用程序实现**渐进式流式AIRS保护**，在AI响应生成期间实时检测和阻止恶意内容。这提供了对提示注入、PII泄露和其他安全威胁的即时保护，无需等待完整响应。

### 架构

**双层安全扫描**:

1. **输入扫描** (在API端点级别 - `backend/api.py`)
   - 在处理开始前扫描用户提示
   - 立即阻止恶意请求(HTTP 403)
   - 向用户返回清理过的错误消息

2. **输出扫描** (在聊天服务级别 - `backend/chat_service.py`)
   - **渐进扫描**: 在流式传输期间每50个块扫描累积内容
   - **最终扫描**: 流式传输完成后始终扫描完整响应
   - **内容撤回**: 检测到违规时立即停止流式传输并清除显示的内容

### 关键功能

**渐进内容扫描**:
- 每50个内容块扫描累积响应(通过`AIRS_STREAM_SCAN_CHUNK_INTERVAL`可配置)
- 在其出现的约50个块内检测恶意内容
- 同步扫描(扫描期间短暂阻塞，通常200-500ms)

**内容撤回用户体验**:
- 收到`security_violation`事件时，前端立即清除所有显示的内容
- 显示用户友好的错误消息，不暴露安全详情
- 防止用户看到任何恶意内容

**失败开放行为**:
- 如果AIRS API失败，流式传输继续(优先考虑可用性)
- 所有失败都会记录以供监控和审计

**对话历史**:
- 内容被阻止时记录用户输入以供审计
- 被阻止的响应不存储在对话历史中
- 为下一条消息维护干净状态

### 配置

添加到`.env`:

```bash
# 启用AIRS扫描
AIRS_ENABLED=true

# AIRS API凭据和配置文件
X_PAN_TOKEN=your_xpan_token_here
X_PAN_INPUT_CHECK_PROFILE_NAME='Demo-Profile-for-Input'
X_PAN_OUTPUT_CHECK_PROFILE_NAME='Demo-Profile-for-Output'

# 渐进扫描间隔(每N个内容块扫描)
AIRS_STREAM_SCAN_CHUNK_INTERVAL=50
```

### 流式模式

有状态和无状态流式模式都支持渐进AIRS保护:

**有状态模式** (带对话历史):
```bash
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What pizzas do you have?",
    "conversation_id": "test-123"
  }'
```

**无状态模式** (无对话历史):
```bash
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What pizzas do you have?",
    "stateless": true
  }'
```

### 事件类型

流式端点产生服务器发送事件(SSE):

- `start`: 流式传输开始
- `kb_search`: 知识库搜索进行中
- `tool_call`: 工具调用(数据库、MCP)
- `tool_result`: 工具执行结果
- `token`: LLM文本生成块
- `security_violation`: 检测到恶意内容，流式传输停止
- `error`: 处理期间发生错误

### 性能影响

**AIRS API调用计数** (500块响应):
- 1次输入扫描(在API级别)
- 10次渐进输出扫描(在块50、100、...、500)
- 1次最终输出扫描(流式传输完成后)
- **总计: 12次AIRS API调用**

**典型延迟**:
- 每次扫描: 200-500ms
- 渐进扫描期间每50块短暂暂停
- 用户感知影响: 对良性内容影响最小

### 测试

**单元测试** (`tests/unit/test_streaming_airs.py`):
```bash
pytest tests/unit/test_streaming_airs.py -v
```

测试涵盖:
- 输入扫描阻止恶意提示
- 渐进扫描在块间隔检测内容
- 最终扫描捕获剩余恶意块
- 安全违规事件格式
- AIRS API错误时的失败开放行为
- 被阻止内容的对话历史处理

**集成测试** (`tests/test_streaming_airs_integration.py`):
```bash
pytest tests/test_streaming_airs_integration.py -v
```

测试涵盖:
- 带恶意内容检测的端到端流式传输
- AIRS API调用计数验证
- 性能影响测量
- 有状态与无状态模式对等

### 实现详情

**修改的文件**:
- `backend/config.py`: 添加了`AIRS_STREAM_SCAN_CHUNK_INTERVAL`配置
- `backend/security/airs_scanner.py`: 增强了流式上下文的日志记录
- `backend/api.py`: 向`/api/v1/chat/stream`端点添加了输入扫描
- `backend/chat_service.py`: 在两种流式方法中实现了渐进和最终扫描
- `frontend/script.js`: 添加了带内容撤回的`security_violation`事件处理器
- `frontend/style.css`: 添加了安全错误样式
- `.env.example`: 记录了流式配置

**设计文档**:
请参见`design/STREAMING_AIRS_PROTECTION.md`了解全面的架构、设计决策和实现原理。

## 贡献

欢迎通过标准GitHub fork和pull request工作流程进行贡献。

## 许可证

此项目根据MIT许可证授权 - 有关详情请参见[LICENSE](LICENSE)文件。

## 支持

如需支持，请在GitHub存储库中开启issue或联系维护者。