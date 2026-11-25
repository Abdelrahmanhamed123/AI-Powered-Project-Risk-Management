pipeline {
    agent any

    environment {
        PYTHONPATH = 'access-service'
        REGISTRY   = 'ghcr.io'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Unit Tests & Coverage') {
            steps {
                sh '''
                    python3 -m pip install --upgrade pip
                    if [ -f access-service/requirements.txt ]; then
                        pip install -r access-service/requirements.txt
                    fi
                    pip install pytest pytest-cov httpx fastapi
                    python3 -m pytest access-service/tests --cov=access-service --cov-report=term-missing --cov-report=xml:coverage.xml
                '''
            }
        }

        stage('SonarCloud Quality Gate') {
            steps {
                echo "Run SonarCloud scanner using SONAR_TOKEN and coverage.xml, then verify Quality Gate status."
            }
        }

        stage('Docker Build') {
            when {
                branch 'main'
            }
            steps {
                sh '''
                    for svc in access-service dependency-service project-service reports-service risk-ai; do
                        echo "Building Docker image for ${svc}..."
                        docker build -t ${REGISTRY}/abdelrahmanhamed123/${svc}:latest ./${svc}
                    done
                '''
            }
        }
    }

    post {
        success {
            echo "CI/CD pipeline completed successfully."
        }
        failure {
            echo "CI/CD pipeline failed; inspect stage logs for details."
        }
    }
}
