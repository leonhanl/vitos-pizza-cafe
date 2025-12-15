# Jenkins CI/CD Pipeline Documentation

This document describes the Jenkins CI/CD pipeline configuration for the Vito's Pizza Cafe application.

## Overview

The pipeline automates the complete deployment workflow:
1. **Build** - Create Docker image from source code
2. **Scan** - Security scanning with Prisma Cloud
3. **Push** - Upload image to Harbor registry
4. **Deploy** - Deploy to production server

## Prerequisites

### Jenkins Credentials

Configure the following credentials in Jenkins:

| Credential ID | Type | Description |
|--------------|------|-------------|
| `gitlab` | Username/Password | GitLab repository access |
| `harbor-credentials` | Username/Password | Harbor registry authentication |
| `deploy-server-ssh` | SSH Private Key | SSH access to deployment server |
| `openai-key` | Secret Text | OpenAI API key |
| `openai-embedding-key` | Secret Text | OpenAI embedding API key |
| `panw-airs-token` | Secret Text | Palo Alto Networks AIRS API token |

### Jenkins Plugins

Required plugins:
- **Git Plugin** - Source code checkout
- **Prisma Cloud Plugin** - Container image security scanning
- **SSH Agent Plugin** - SSH deployment
- **Docker Pipeline Plugin** - Docker commands

### Infrastructure Requirements

- **Jenkins Agent**: Must have Docker client and access to Docker daemon at `https://docker:2376`
- **Docker Certificates**: TLS certificates at `/certs/client/` (Align with Jenkins+Docker Deployment) for secure Docker daemon communication
- **Harbor Registry**: Private registry at `harbor.halfcoffee.com`
- **Deployment Server**: SSH access to `10.10.50.16`

## Pipeline Configuration

### Environment Variables

```groovy
REGISTRY_HOST = 'harbor.halfcoffee.com'           # Harbor registry URL
IMAGE_NAME = "vitos-pizza-cafe"                    # Docker image name
IMAGE_TAG = "${BUILD_NUMBER}"                      # Image tag (Jenkins build number)
DEPLOY_HOST = "10.10.50.16"                        # Deployment server IP
DEPLOY_PATH = "/root/vitos-pizza-cafe-deploy"     # Deployment directory
BACKEND_API_URL = "http://10.10.50.16:8000"       # Backend API endpoint
```

### LLM Configuration

```groovy
OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_MODEL = "qwen2.5-14b-instruct"
OPENAI_EMBEDDING_BASE_URL = "https://api.siliconflow.cn/v1"
EMBEDDING_MODEL = "BAAI/bge-large-zh-v1.5"
```

### Security Configuration

```groovy
AIRS_ENABLED = "true"
X_PAN_INPUT_CHECK_PROFILE_NAME = "matt"
X_PAN_OUTPUT_CHECK_PROFILE_NAME = "matt"
```

## Pipeline Stages

### 1. Checkout

Clones the source code from GitLab repository.

```groovy
git branch: 'master', 
    credentialsId: 'gitlab', 
    url: 'https://gitlab.halfcoffee.com/root/vitos-pizza-cafe.git'
```

**Success Criteria**: Repository cloned successfully

---

### 2. Build Image

Builds Docker image and tags it with the build number.

**Steps**:
1. Create temporary Docker config directory
2. Login to Harbor registry
3. Build Docker image with tag `harbor.halfcoffee.com/modelscan/vitos-pizza-cafe:${BUILD_NUMBER}`

**Output**: Docker image ready for scanning

---

### 3. Scan Image

Performs security scanning using Prisma Cloud.

**Configuration**:
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

**What is Scanned**:
- Vulnerabilities (CVEs)
- Compliance violations
- Malware
- Secrets in image layers
- Base image risks

**Behavior**: 
- Stage marked as `FAILURE` if critical issues found
- Build continues to next stage (non-blocking)

---

### 4. Publish Result

Publishes scan results to Prisma Cloud dashboard.

**Output**: Results viewable in Prisma Cloud console

---

### 5. Verify

Checks scan results and fails build if critical issues detected.

```groovy
if (currentBuild.currentResult == 'FAILURE') {
    error "Scan result is failed!"
}
```

**Behavior**: Pipeline stops if security scan failed

---

### 6. Push Image

Pushes the Docker image to Harbor registry.

**Steps**:
1. Login to Harbor
2. Push image: `docker push harbor.halfcoffee.com/modelscan/vitos-pizza-cafe:${BUILD_NUMBER}`

**Success Criteria**: Image available in Harbor

---

### 7. Deploy

Deploys the application to production server via SSH.

**Steps**:

1. **Copy `docker-compose.yml`** to deployment server:
   ```bash
   scp docker-compose.yml root@10.10.50.16:/root/vitos-pizza-cafe-deploy/
   ```

2. **SSH to server and execute deployment**:
   ```bash
   cd /root/vitos-pizza-cafe-deploy
   docker login harbor.halfcoffee.com
   export IMAGE_TAG=${BUILD_NUMBER}
   export APP_VERSION=${BUILD_NUMBER}
   export BACKEND_API_URL=http://10.10.50.16:8000
   # ... (all environment variables)
   docker compose pull
   docker compose down
   docker compose up -d
   docker compose ps
   ```

**Environment Variables Passed**:
- `IMAGE_TAG` - Docker image version
- `APP_VERSION` - Application version
- `BACKEND_API_URL` - Backend API URL
- `OPENAI_API_KEY` - OpenAI API credentials
- `OPENAI_BASE_URL` - LLM provider endpoint
- `LLM_MODEL` - LLM model name
- `OPENAI_EMBEDDING_API_KEY` - Embedding API credentials
- `OPENAI_EMBEDDING_BASE_URL` - Embedding provider endpoint
- `EMBEDDING_MODEL` - Embedding model name
- `AIRS_ENABLED` - Enable AIRS security
- `X_PAN_TOKEN` - AIRS API token
- `X_PAN_INPUT_CHECK_PROFILE_NAME` - Input security profile
- `X_PAN_OUTPUT_CHECK_PROFILE_NAME` - Output security profile

**Deployment Process**:
1. Pull latest image from Harbor
2. Stop running containers
3. Start new containers with updated image
4. Display container status

**Success Criteria**: Application running on deployment server

---

## Post-Build Actions

### Cleanup

Removes temporary files after build completion:
```groovy
sh 'rm -rf *.json || true'
```

---

## Usage

### Trigger Pipeline

**Manual Trigger**:
1. Navigate to Jenkins job
2. Click "Build Now"

**Automatic Trigger** (if configured):
- Git webhook on push to `master` branch

### Monitor Build

1. **Console Output**: View real-time build logs
2. **Prisma Cloud Results**: Check security scan report
3. **Deployment Status**: Verify containers running on deployment server

### Verify Deployment

```bash
# SSH to deployment server
ssh root@10.10.50.16

# Check deployment directory
cd /root/vitos-pizza-cafe-deploy
docker compose ps

# Check backend health
curl http://10.10.50.16:8000/api/v1/health

# Check frontend
curl http://10.10.50.16:5500
```

---

## Troubleshooting

### Build Stage Fails

**Issue**: Docker build fails

**Solutions**:
- Check Dockerfile syntax
- Verify base image availability
- Review build logs for dependency errors

### Scan Stage Fails

**Issue**: Prisma Cloud scan detects critical vulnerabilities

**Solutions**:
- Review scan results in `prisma-cloud-scan-results.json`
- Update base image to patched version
- Apply security fixes to application code
- Update dependencies in `pyproject.toml`

### Push Stage Fails

**Issue**: Cannot push to Harbor registry

**Solutions**:
- Verify `harbor-credentials` are correct
- Check Harbor registry availability
- Ensure network connectivity to `harbor.halfcoffee.com`

### Deploy Stage Fails

**Issue**: SSH deployment fails

**Solutions**:
- Verify `deploy-server-ssh` credentials
- Check SSH connectivity: `ssh root@10.10.50.16`
- Ensure deployment directory exists: `/root/vitos-pizza-cafe-deploy`
- Check Docker Compose file syntax

### Application Not Starting

**Issue**: Containers fail to start after deployment

**Solutions**:
1. SSH to deployment server
2. Check container logs:
   ```bash
   cd /root/vitos-pizza-cafe-deploy
   docker compose logs backend
   docker compose logs frontend
   ```
3. Verify environment variables are set correctly
4. Check `docker-compose.yml` configuration

---

## Security Considerations

### Secrets Management

- **Never commit credentials** to Git repository
- **Use Jenkins credentials** for all sensitive data
- **Rotate credentials** regularly
- **Use SSH keys** instead of passwords

### Image Security

- **Scan all images** before deployment
- **Update base images** regularly
- **Remove unnecessary packages** from Dockerfile
- **Use minimal base images** (e.g., `python:3.12-slim`)

### AIRS Protection

The pipeline deploys with AI Runtime Security enabled:
- **Input scanning**: Blocks malicious prompts
- **Output scanning**: Prevents data leakage
- **Streaming protection**: Progressive content scanning

See `README.md` for AIRS details.

---

## Maintenance

### Update LLM Model

To change the LLM model:

1. Update pipeline environment variables:
   ```groovy
   LLM_MODEL = "new-model-name"
   OPENAI_BASE_URL = "https://new-provider.com/v1"
   ```

2. Update Jenkins credentials if API keys changed

3. Run pipeline to deploy new configuration

### Update AIRS Profiles

To change security profiles:

```groovy
X_PAN_INPUT_CHECK_PROFILE_NAME = "new-input-profile"
X_PAN_OUTPUT_CHECK_PROFILE_NAME = "new-output-profile"
```

### Scale Deployment

To deploy to multiple servers:

1. Add new deployment stages
2. Configure separate credentials for each server
3. Update `DEPLOY_HOST` and `DEPLOY_PATH` for each stage

---

## Related Documentation

- `README.md` - Application overview and setup
- `CLAUDE.md` - Developer guide
- `Dockerfile` - Container build configuration
- `docker-compose.yml` - Deployment configuration
- `design/STREAMING_AIRS_PROTECTION.md` - Security implementation

---

## Support

For pipeline issues:
1. Check Jenkins console output for detailed error messages
2. Review relevant documentation above
3. Contact DevOps team or open an issue in the repository
