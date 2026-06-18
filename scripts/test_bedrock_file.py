# First, start your FastAPI emulator
# uvicorn bedrock_emulator:app --reload --port 8000

# Then run your Lambda with local mode enabled
# export IS_LOCAL=true
# export TABLE_NAME=your-table
# export BUCKET_NAME=your-bucket

# Invoke your Lambda
# python -c "
import os
import sys


os.environ["IS_LOCAL"] = "true"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from processor.lambda_bedrock_narrative import lambda_handler
result = lambda_handler({'action': 'generate_daily', 'user_id': 'test-user', 'date': '2026-06-13'}, None)
print(result)
# "