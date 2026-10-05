// Continuous Testing pipeline for the Submission Service.
// Stages fan out so UI, API and Java suites run in parallel; the pipeline fails fast on smoke.
pipeline {
  agent { dockerfile true }

  options {
    timestamps()
    timeout(time: 30, unit: 'MINUTES')
    buildDiscarder(logRotator(numToKeepStr: '30'))
  }

  environment {
    SUBMISSION_API_KEY = credentials('submission-api-key')
    PYTHONDONTWRITEBYTECODE = '1'
  }

  stages {
    stage('Install') {
      steps {
        sh 'python --version && pip list | grep -i playwright'
      }
    }

    stage('Smoke') {
      steps {
        sh 'pytest -m smoke --junitxml=reports/smoke.xml'
      }
    }

    stage('Test') {
      parallel {
        stage('API + security + AWS') {
          steps { sh 'pytest -m "api or security or aws" -n auto --junitxml=reports/api.xml --html=reports/api.html --self-contained-html' }
        }
        stage('UI + a11y + mobile') {
          steps { sh 'pytest -m "ui or a11y or mobile" --junitxml=reports/ui.xml --html=reports/ui.html --self-contained-html' }
        }
        stage('Integration + scale') {
          steps { sh 'pytest -m "integration or scale" --junitxml=reports/integration.xml' }
        }
        stage('Security scans') {
          steps {
            sh 'pip install pip-audit bandit && pip-audit -r requirements.txt && bandit -c security/bandit.yaml -r app aws -lll'
          }
        }
        stage('Java API suite') {
          agent { docker { image 'maven:3.9-eclipse-temurin-17' } }
          steps {
            sh 'python -m app.server & sleep 2'
            dir('java-api-tests') { sh 'mvn -B clean test -Dbase.url=http://localhost:5001' }
          }
        }
      }
    }

    stage('Predictive analysis') {
      steps {
        sh 'python ai_testing/predict_flaky.py ai_testing/test_history.csv --out reports/flakiness.md'
      }
    }

    stage('Performance (nightly)') {
      when { triggeredBy 'TimerTrigger' }
      steps {
        sh 'jmeter -n -t performance/submissions_load_test.jmx -Jhost=staging.internal -l reports/perf.jtl -e -o reports/perf-html'
      }
    }
  }

  post {
    always {
      junit allowEmptyResults: true, testResults: 'reports/*.xml, java-api-tests/target/surefire-reports/*.xml'
      archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
      publishHTML target: [reportDir: 'reports', reportFiles: 'api.html,ui.html', reportName: 'Test reports', keepAll: true]
    }
    failure {
      slackSend channel: '#qa-alerts', message: "Build ${env.BUILD_NUMBER} failed: ${env.BUILD_URL}"
    }
  }
}
