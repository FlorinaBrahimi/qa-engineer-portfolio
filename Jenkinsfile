// Continuous Testing pipeline for the Submission Service.
//
// Runs on a plain Jenkins agent with Python 3.12, Java 17+, Maven and JMeter on the PATH. It needs no Docker and only core pipeline plugins: Pipeline, Git, JUnit,
// Timestamper. Create it as a "Pipeline" job with "Pipeline script from SCM" pointing at this
// repository; see docs/10_jenkins_setup.md.
pipeline {
  agent any

  options {
    timestamps()
    timeout(time: 30, unit: 'MINUTES')
    buildDiscarder(logRotator(numToKeepStr: '30'))
    disableConcurrentBuilds()
  }

  parameters {
    booleanParam(name: 'RUN_CODEBUILD', defaultValue: true,
                 description: 'Also build this commit in AWS CodeBuild (about 3 billable build minutes)')
  }

  triggers {
    cron('H 2 * * *')        // nightly run, which also enables the performance stage
    pollSCM('H/15 * * * *')  // pick up pushes without needing a webhook into a local Jenkins
  }

  environment {
    // Jenkins started as a macOS service has a minimal PATH; add Homebrew and python.org Python.
    PATH = "/opt/homebrew/bin:/Library/Frameworks/Python.framework/Versions/3.12/bin:/usr/local/bin:${env.PATH}"
    PY = "${env.WORKSPACE}/.venv/bin/python"
    SUBMISSION_API_KEY = 'qa-demo-key'
    PYTHONDONTWRITEBYTECODE = '1'
  }

  stages {
    stage('Install') {
      steps {
        sh '''
          python3 -m venv .venv
          "$PY" -m pip install -q --upgrade pip
          "$PY" -m pip install -q -r requirements.txt
          "$PY" -m playwright install chromium
          mkdir -p reports
        '''
      }
    }

    stage('Smoke') {
      steps {
        sh '"$PY" -m pytest -m smoke --junitxml=reports/smoke.xml'
      }
    }

    stage('Test') {
      parallel {
        stage('Unit + API + security + AWS') {
          steps {
            sh '"$PY" -m pytest tests/unit tests/api tests/security tests/aws -n auto --junitxml=reports/api.xml --html=reports/api.html --self-contained-html'
          }
        }
        stage('UI + a11y + mobile') {
          steps {
            sh '"$PY" -m pytest -m "ui or a11y or mobile" --junitxml=reports/ui.xml --html=reports/ui.html --self-contained-html'
          }
        }
        stage('Integration + scale') {
          steps {
            sh '"$PY" -m pytest -m "integration or scale" --junitxml=reports/integration.xml'
          }
        }
        stage('Security scans') {
          steps {
            sh '''
              "$PY" -m pip_audit -r requirements.txt
              "$PY" -m bandit -q -c security/bandit.yaml -r app aws -ll
              "$WORKSPACE/.venv/bin/cfn-lint" infra/template.yaml infra/github-oidc-role.yaml infra/pipeline.yaml
              if command -v gitleaks > /dev/null; then gitleaks detect --source . --no-banner --redact; else echo "gitleaks not installed on this agent; secret scan runs in GitHub Actions"; fi
            '''
          }
        }
        stage('Java API suite') {
          steps {
            // Start the app, run Maven against it, and always stop the app, all in one shell
            // so the background process cannot outlive the step.
            sh '''
              PORT=5011 "$PY" -m app.server > reports/java-sut.log 2>&1 &
              SUT_PID=$!
              trap 'kill $SUT_PID 2>/dev/null || true' EXIT
              for _ in $(seq 1 20); do curl -sf http://localhost:5011/health > /dev/null && break; sleep 1; done
              cd java-api-tests && mvn -B -q clean test -Dbase.url=http://localhost:5011
            '''
          }
        }
      }
    }

    stage('AWS CodeBuild') {
      // Jenkins orchestrates; AWS CodeBuild does the work. The same commit is built and
      // tested on a clean AWS Linux machine, and its log is streamed back into this console.
      // Uses the AWS credentials of the account Jenkins runs under (default provider chain).
      when { expression { return params.RUN_CODEBUILD } }
      steps {
        awsCodeBuild projectName: 'submission-service-pipeline-jenkins',
                     region: 'eu-west-2',
                     credentialsType: 'keys',
                     sourceControlType: 'project',
                     sourceVersion: env.GIT_COMMIT
      }
    }

    stage('Predictive analysis') {
      steps {
        sh '"$PY" ai_testing/predict_flaky.py ai_testing/test_history.csv --out reports/flakiness.md'
      }
    }

    stage('Performance') {
      // Short load test on every build; the nightly timer run is longer and heavier.
      steps {
        script {
          def nightly = currentBuild.getBuildCauses('hudson.triggers.TimerTrigger$TimerTriggerCause').size() > 0
          withEnv(nightly ? ['USERS=50', 'RAMP=30', 'DURATION=120'] : ['USERS=20', 'RAMP=5', 'DURATION=30']) {
            sh 'performance/run.sh'
          }
        }
      }
    }
  }

  post {
    always {
      junit allowEmptyResults: true, testResults: 'reports/*.xml, java-api-tests/target/surefire-reports/*.xml'
      archiveArtifacts artifacts: 'reports/**', allowEmptyArchive: true
    }
    failure {
      echo "Build ${env.BUILD_NUMBER} failed. See the test report and archived artifacts: ${env.BUILD_URL}"
    }
  }
}
