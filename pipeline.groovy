pipeline {
    agent none
    environment {
        REGISTRY_HOST = 'harbor.halfcoffee.com'
        IMAGE_NAME = "vitos-pizza-cafe"
        IMAGE_TAG = "${BUILD_NUMBER}"
        FULL_IMAGE = "${REGISTRY_HOST}/modelscan/${IMAGE_NAME}:${IMAGE_TAG}"
        BACKEND_API_URL = "http://10.10.50.16:8000"
        DEPLOY_HOST = "10.10.50.16"
        DEPLOY_PATH = "/root/vitos-pizza-cafe-deploy"
        OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        LLM_MODEL = "qwen2.5-14b-instruct"
        OPENAI_EMBEDDING_BASE_URL = "https://api.siliconflow.cn/v1"
        EMBEDDING_MODEL = "BAAI/bge-large-zh-v1.5"  
        AIRS_ENABLED = "true"
        OPENAI_API_KEY = credentials('openai-key')
        OPENAI_EMBEDDING_API_KEY = credentials('openai-embedding-key')
        X_PAN_TOKEN = credentials('panw-airs-token')
        X_PAN_INPUT_CHECK_PROFILE_NAME = "matt"
        X_PAN_OUTPUT_CHECK_PROFILE_NAME = "matt"

    }

    stages {
        stage('Checkout') {
            agent any
            steps {
                // gitlab username/password credentials stored in Jenkins credentials with ID 'gitlab'
                git branch: 'master', 
                    credentialsId: 'gitlab', 
                    url: 'https://gitlab.halfcoffee.com/root/vitos-pizza-cafe.git'
                script {
                    sh 'ls -l'
                }
            }
        }
        stage('Build Image') {
            agent any
            environment {
                // create tmp docker config to avoid permission issues
                DOCKER_CONFIG = "${WORKSPACE}/.docker_tmp"
            }
            steps {
                script {
                    // create docker config dir
                    sh "mkdir -p ${DOCKER_CONFIG}"
                    
                    withCredentials([usernamePassword(credentialsId: 'harbor-credentials', usernameVariable: 'HARBOR_USER', passwordVariable: 'HARBOR_PWD')]) {
                        
                        // 1. login
                        sh 'echo $HARBOR_PWD | docker login ${REGISTRY_HOST} -u $HARBOR_USER --password-stdin'
                        
                        // 2. build image
                        echo "Building image: ${FULL_IMAGE}"
                        sh "docker build -t ${FULL_IMAGE} ."
                    }
                }
            }
        }
        stage('Scan Image') {
            agent any
            steps {
            catchError(buildResult: 'FAILURE', stageResult: 'FAILURE'){
                // Scan the image
                prismaCloudScanImage ca: '/certs/client/ca.pem',
                cert: '/certs/client/cert.pem',
                dockerAddress: 'https://docker:2376',
                image: "${FULL_IMAGE}",
                key: '/certs/client/key.pem',
                logLevel: 'debug',
                podmanPath: '',
                // The project field below is only applicable if you are using Prisma Cloud Compute Edition and have set up projects (multiple consoles) on Prisma Cloud.
                project: '',
                resultsFile: 'prisma-cloud-scan-results.json',
                ignoreImageBuildTime:true
            }
            }
        }
        stage('Publish Result') {
        agent any
        steps {
            script {
                sh 'cat prisma-cloud-scan-results.json'
                }
            prismaCloudPublish resultsFilePattern: 'prisma-cloud-scan-results.json'
            }
        }
    stage('Verify'){
        agent any
        steps {
            script {                                   
            if (currentBuild.currentResult == 'FAILURE') {
                error "Scan result is failed!"     
            } else {
                echo "Scan finished and success!"
                }
            }
        }
    }
        stage('Push Image') {
            agent any
            environment {
                DOCKER_CONFIG = "${WORKSPACE}/.docker_tmp"
            }
            steps {
                script {
                    sh "mkdir -p ${DOCKER_CONFIG}"
                    
                    withCredentials([usernamePassword(credentialsId: 'harbor-credentials', usernameVariable: 'HARBOR_USER', passwordVariable: 'HARBOR_PWD')]) {
                        // 1. login
                        sh 'echo $HARBOR_PWD | docker login ${REGISTRY_HOST} -u $HARBOR_USER --password-stdin'
                        
                        // 2. push image
                        echo "Pushing image to Harbor..."
                        sh "docker push ${FULL_IMAGE}"
                    }
                }
            }
        }

        stage('Deploy') {
            agent any
            steps {
                script {
                    // SSH credentials stored in Jenkins with ID 'deploy-server-ssh'
                    withCredentials([
                        sshUserPrivateKey(credentialsId: 'deploy-server-ssh', keyFileVariable: 'SSH_KEY', usernameVariable: 'SSH_USER'),
                        usernamePassword(credentialsId: 'harbor-credentials', usernameVariable: 'HARBOR_USER', passwordVariable: 'HARBOR_PWD'),
                        ]) {
                        def DEPLOY_HOST = "${DEPLOY_HOST}"
                        def DEPLOY_PATH = "${DEPLOY_PATH}"
                        
                        // 1. copy docker-compose.yaml to remote server
                        sh """
                            scp -i ${SSH_KEY} -o StrictHostKeyChecking=no \
                                docker-compose.yml ${SSH_USER}@${DEPLOY_HOST}:${DEPLOY_PATH}/
                        """
                    
                        // 2. SSH to remote server and execute deployment
                        sh """
                            ssh -i ${SSH_KEY} -o StrictHostKeyChecking=no \
                                ${SSH_USER}@${DEPLOY_HOST} \
                                'cd ${DEPLOY_PATH} && \
                                echo ${HARBOR_PWD} | docker login ${REGISTRY_HOST} -u ${HARBOR_USER} --password-stdin && \
                                export IMAGE_TAG=${IMAGE_TAG} && \
                                export APP_VERSION=${IMAGE_TAG} && \
                                export BACKEND_API_URL=${BACKEND_API_URL} && \
                                export OPENAI_API_KEY=${OPENAI_API_KEY} && \
                                export OPENAI_BASE_URL=${OPENAI_BASE_URL} && \
                                export LLM_MODEL=${LLM_MODEL} && \
                                export OPENAI_EMBEDDING_API_KEY=${OPENAI_EMBEDDING_API_KEY} && \
                                export OPENAI_EMBEDDING_BASE_URL=${OPENAI_EMBEDDING_BASE_URL} && \
                                export EMBEDDING_MODEL=${EMBEDDING_MODEL} && \
                                export AIRS_ENABLED=${AIRS_ENABLED} && \
                                export X_PAN_TOKEN=${X_PAN_TOKEN} && \
                                export X_PAN_INPUT_CHECK_PROFILE_NAME=${X_PAN_INPUT_CHECK_PROFILE_NAME} &&
                                export X_PAN_OUTPUT_CHECK_PROFILE_NAME=${X_PAN_OUTPUT_CHECK_PROFILE_NAME} && \
                                docker compose pull && \
                                docker compose down && \
                                docker compose up -d && \
                                docker compose ps'
                        """
                        
                        echo "Deployment completed successfully!"
                    }
                }
            }
        }

    }

    post {
        cleanup {
            node('') {
                sh 'rm -rf *.json || true'
            }
        }
    }
}