# Jenkins CI/CD Pipeline 文档

本文档描述了 Vito's Pizza Cafe 应用程序的 Jenkins CI/CD 流水线配置。

## 概述

该流水线自动化了完整的部署工作流程：
1. **构建** - 从源代码创建 Docker 镜像
2. **扫描** - 使用 Prisma Cloud 进行安全扫描
3. **推送** - 上传镜像到 Harbor 镜像仓库
4. **部署** - 部署到生产服务器

## 前置要求

### Jenkins 凭据

在 Jenkins 中配置以下凭据：

| 凭据 ID | 类型 | 描述 |
|--------------|------|-------------|
| `gitlab` | 用户名/密码 | GitLab 仓库访问权限 |
| `harbor-credentials` | 用户名/密码 | Harbor 镜像仓库认证 |
| `deploy-server-ssh` | SSH 私钥 | 部署服务器 SSH 访问权限 |
| `openai-key` | 密文文本 | OpenAI-compatible API 密钥 |
| `openai-embedding-key` | 密文文本 | OpenAI-compatible Embedding 模型 API 密钥 |
| `panw-airs-token` | 密文文本 | Palo Alto Networks AIRS API 令牌 |

### Jenkins 插件

必需插件：
- **Git Plugin** - 源代码检出
- **Prisma Cloud Plugin** - 容器镜像安全扫描
- **SSH Agent Plugin** - SSH 部署
- **Docker Pipeline Plugin** - Docker 命令支持

### 基础设施要求

- **Jenkins Agent**：必须安装 Docker 客户端并能访问 `https://docker:2376` 的 Docker 守护进程
- **Docker 证书**：位于 `/certs/client/` 的 TLS 证书(证书由 Jenkins 部署时 Docker in Docker 容器产生)，用于安全的 Docker 守护进程通信
- **Harbor 镜像仓库**：私有镜像仓库 `harbor.halfcoffee.com`
- **部署服务器**：SSH 访问 `10.10.50.16`

## Pipeline 配置

### 环境变量

```groovy
REGISTRY_HOST = 'harbor.halfcoffee.com'           # Harbor 镜像仓库 URL
IMAGE_NAME = "vitos-pizza-cafe"                    # Docker 镜像名称
IMAGE_TAG = "${BUILD_NUMBER}"                      # 镜像标签（Jenkins 构建号）
DEPLOY_HOST = "10.10.50.16"                        # 部署服务器 IP
DEPLOY_PATH = "/root/vitos-pizza-cafe-deploy"     # 部署目录
BACKEND_API_URL = "http://10.10.50.16:8000"       # 后端 API 端点
```

### LLM 配置

```groovy
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_MODEL = "qwen2.5-14b-instruct"
OPENAI_EMBEDDING_BASE_URL = "https://api.siliconflow.cn/v1"
EMBEDDING_MODEL = "BAAI/bge-large-zh-v1.5"
```

### 安全配置

```groovy
AIRS_ENABLED = "true"
X_PAN_INPUT_CHECK_PROFILE_NAME = "matt"
X_PAN_OUTPUT_CHECK_PROFILE_NAME = "matt"
```

## Pipeline 阶段

### 1. Checkout（代码检出）

从 GitLab 仓库克隆源代码。

```groovy
git branch: 'master', 
    credentialsId: 'gitlab', 
    url: 'https://gitlab.halfcoffee.com/root/vitos-pizza-cafe.git'
```

**成功标准**：仓库成功克隆

---

### 2. Build Image（构建镜像）

构建 Docker 镜像并使用构建号打标签。

**步骤**：
1. 创建临时 Docker 配置目录
2. 登录 Harbor 镜像仓库
3. 构建 Docker 镜像，标签为 `harbor.halfcoffee.com/modelscan/vitos-pizza-cafe:${BUILD_NUMBER}`

**输出**：准备好进行扫描的 Docker 镜像

---

### 3. Scan Image（扫描镜像）

使用 Prisma Cloud 执行安全扫描。

**配置**：
```groovy
prismaCloudScanImage ca: '/certs/client/ca.pem',
    cert: '/certs/client/cert.pem',
    dockerAddress: 'https://docker:2376',
    image: "${FULL_IMAGE}",
    key: '/certs/client/key.pem',
    logLevel: 'debug',
    resultsFile: 'prisma-cloud-scan-results.json',
    ignoreImageBuildTime: true
```

**扫描内容**：
- 漏洞（CVE）
- 合规性违规
- 恶意软件
- 镜像层中的密钥
- 基础镜像风险

**行为**： 
- 如果发现严重问题，阶段标记为 `FAILURE`
- 构建继续到下一阶段（非阻塞）

---

### 4. Publish Result（发布结果）

将扫描结果发布到 Prisma Cloud 控制台。

**输出**：结果可在 Prisma Cloud 控制台查看

---

### 5. Verify（验证）

检查扫描结果，如果检测到严重问题则构建失败。

```groovy
if (currentBuild.currentResult == 'FAILURE') {
    error "Scan result is failed!"
}
```

**行为**：如果安全扫描失败，流水线停止

---

### 6. Push Image（推送镜像）

将 Docker 镜像推送到 Harbor 镜像仓库。

**步骤**：
1. 登录 Harbor
2. 推送镜像：`docker push harbor.halfcoffee.com/modelscan/vitos-pizza-cafe:${BUILD_NUMBER}`

**成功标准**：镜像在 Harbor 中可用

---

### 7. Deploy（部署）

通过 SSH 将应用程序部署到生产服务器。

**步骤**：

1. **复制 `docker-compose.yml`** 到部署服务器：
   ```bash
   scp docker-compose.yml root@10.10.50.16:/root/vitos-pizza-cafe-deploy/
   ```

2. **SSH 到服务器并执行部署**：
   ```bash
   cd /root/vitos-pizza-cafe-deploy
   docker login harbor.halfcoffee.com
   export IMAGE_TAG=${BUILD_NUMBER}
   export APP_VERSION=${BUILD_NUMBER}
   export BACKEND_API_URL=http://10.10.50.16:8000
   # ... (所有环境变量)
   docker compose pull
   docker compose down
   docker compose up -d
   docker compose ps
   ```

**传递的环境变量**：
- `IMAGE_TAG` - Docker 镜像版本
- `APP_VERSION` - 应用程序版本
- `BACKEND_API_URL` - 后端 API URL
- `OPENAI_API_KEY` - OpenAI API 凭据
- `OPENAI_BASE_URL` - LLM 提供商端点
- `LLM_MODEL` - LLM 模型名称
- `OPENAI_EMBEDDING_API_KEY` - 嵌入 API 凭据
- `OPENAI_EMBEDDING_BASE_URL` - 嵌入提供商端点
- `EMBEDDING_MODEL` - 嵌入模型名称
- `AIRS_ENABLED` - 启用 AIRS 安全防护
- `X_PAN_TOKEN` - AIRS API 令牌
- `X_PAN_INPUT_CHECK_PROFILE_NAME` - 输入安全配置文件
- `X_PAN_OUTPUT_CHECK_PROFILE_NAME` - 输出安全配置文件

**部署过程**：
1. 从 Harbor 拉取最新镜像
2. 停止运行中的容器
3. 使用更新的镜像启动新容器
4. 显示容器状态

**成功标准**：应用程序在部署服务器上运行

---

## 构建后操作

### Cleanup（清理）

构建完成后删除临时文件：
```groovy
sh 'rm -rf *.json || true'
```

---

## 使用方法

### 触发 Pipeline

**手动触发**：
1. 导航到 Jenkins 任务
2. 点击 "Build Now"

**自动触发**（如果已配置）：
- 推送到 `master` 分支时的 Git webhook

### 监控构建

1. **控制台输出**：查看实时构建日志
2. **Prisma Cloud 结果**：检查安全扫描报告
3. **部署状态**：验证部署服务器上的容器运行状态

### 验证部署

```bash
# SSH 到部署服务器
ssh root@10.10.50.16

# 检查部署目录
cd /root/vitos-pizza-cafe-deploy
docker compose ps

# 检查后端健康状态
curl http://10.10.50.16:8000/api/v1/health

# 检查前端
curl http://10.10.50.16:5500
```

---

## 故障排除

### 构建阶段失败

**问题**：Docker 构建失败

**解决方案**：
- 检查 Dockerfile 语法
- 验证基础镜像可用性
- 查看构建日志中的依赖错误

### 扫描阶段失败

**问题**：Prisma Cloud 扫描检测到严重漏洞

**解决方案**：
- 查看 `prisma-cloud-scan-results.json` 中的扫描结果
- 将基础镜像更新到已修补的版本
- 对应用程序代码应用安全修复
- 更新 `pyproject.toml` 中的依赖项

### 推送阶段失败

**问题**：无法推送到 Harbor 镜像仓库

**解决方案**：
- 验证 `harbor-credentials` 是否正确
- 检查 Harbor 镜像仓库可用性
- 确保网络连接到 `harbor.halfcoffee.com`

### 部署阶段失败

**问题**：SSH 部署失败

**解决方案**：
- 验证 `deploy-server-ssh` 凭据
- 检查 SSH 连接：`ssh root@10.10.50.16`
- 确保部署目录存在：`/root/vitos-pizza-cafe-deploy`
- 检查 Docker Compose 文件语法

### 应用程序无法启动

**问题**：部署后容器启动失败

**解决方案**：
1. SSH 到部署服务器
2. 检查容器日志：
   ```bash
   cd /root/vitos-pizza-cafe-deploy
   docker compose logs backend
   docker compose logs frontend
   ```
3. 验证环境变量设置是否正确
4. 检查 `docker-compose.yml` 配置

---

## 安全考虑

### 密钥管理

- **永远不要将凭据提交**到 Git 仓库
- **使用 Jenkins 凭据**管理所有敏感数据
- **定期轮换凭据**
- **使用 SSH 密钥**而非密码

### 镜像安全

- **在部署前扫描所有镜像**
- **定期更新基础镜像**
- **从 Dockerfile 中删除不必要的包**
- **使用最小化基础镜像**（例如 `python:3.12-slim`）

### AIRS 防护

流水线部署时启用了 AI 运行时安全防护：
- **输入扫描**：阻止恶意提示
- **输出扫描**：防止数据泄露
- **流式防护**：渐进式内容扫描

有关 AIRS 的详细信息，请参阅 `README.md`。

---

## 维护

### 更新 LLM 模型

要更改 LLM 模型：

1. 更新流水线环境变量：
   ```groovy
   LLM_MODEL = "new-model-name"
   OPENAI_BASE_URL = "https://new-provider.com/v1"
   ```

2. 如果 API 密钥已更改，则更新 Jenkins 凭据

3. 运行流水线以部署新配置

### 更新 AIRS 配置文件

要更改安全配置文件：

```groovy
X_PAN_INPUT_CHECK_PROFILE_NAME = "new-input-profile"
X_PAN_OUTPUT_CHECK_PROFILE_NAME = "new-output-profile"
```

### 扩展部署

要部署到多个服务器：

1. 添加新的部署阶段
2. 为每个服务器配置单独的凭据
3. 为每个阶段更新 `DEPLOY_HOST` 和 `DEPLOY_PATH`

---

## 相关文档

- `README.md` - 应用程序概述和设置
- `README-CN.md` - 中文版应用程序文档
- `CLAUDE.md` - 开发者指南
- `Dockerfile` - 容器构建配置
- `docker-compose.yml` - 部署配置
- `design/STREAMING_AIRS_PROTECTION.md` - 安全实现文档

---

## 支持

如遇到流水线问题：
1. 检查 Jenkins 控制台输出以获取详细错误消息
2. 查看上面的相关文档
3. 联系 DevOps 团队或在仓库中提出 issue
