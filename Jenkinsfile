// Continuous Testing pipeline for the Submission Service.
//
// Runs on a plain Jenkins agent with Python 3.12, Java 17+, Maven and (for the nightly stage)
// JMeter on the PATH. It needs no Docker and only core pipeline plugins: Pipeline, Git, JUnit,
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
              "$PY" -m bandit -q -c security/bandit.yaml -r app aws -lll
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

    stage('Predictive analysis') {
      steps {
        sh '"$PY" ai_testing/predict_flaky.py ai_testing/test_history.csv --out reports/flakiness.md'
      }
    }

    stage('Performance (nightly)') {
      when { triggeredBy 'TimerTrigger' }
      steps {
        sh '''
          PORT=5012 "$PY" -m app.server > reports/perf-sut.log 2>&1 &
          SUT_PID=$!
          trap 'kill $SUT_PID 2>/dev/null || true' EXIT
          for _ in $(seq 1 20); do curl -sf http://localhost:5012/health > /dev/null && break; sleep 1; done
          rm -rf reports/perf-html reports/perf.jtl
          jmeter -n -t performance/submissions_load_test.jmx -Jhost=localhost -Jport=5012 -Jusers=20 -Jramp=5 -Jduration=30 -l reports/perf.jtl -e -o reports/perf-html
        '''
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
