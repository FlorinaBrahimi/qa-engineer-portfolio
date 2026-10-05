"""Lambda entry point for the Submission Service.

A Lambda Function URL sends HTTP events; apig-wsgi translates them to WSGI calls so the
exact same Flask app that runs locally runs on AWS. Configure with:

    STORAGE_BACKEND=dynamodb  SUBMISSIONS_TABLE=<table>  SUBMISSION_API_KEY=<key>
"""
from apig_wsgi import make_lambda_handler

from app.server import app

handler = make_lambda_handler(app, binary_support=True)
