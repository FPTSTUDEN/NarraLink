# First, start your FastAPI emulator
# uvicorn bedrock_emulator:app --reload --port 8000

# Then run your Lambda with local mode enabled
# export IS_LOCAL=true
# export TABLE_NAME=your-table
# export BUCKET_NAME=your-bucket

# Invoke your Lambda
# python -c "
import os


os.environ["IS_LOCAL"] = "true"
from lambda_bedrock_narrative import lambda_handler
result = lambda_handler({'action': 'generate_daily', 'user_id': 'test-user-20260613', 'date': '2026-06-13'}, None)
print(result)
# "