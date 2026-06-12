import os
import json
import boto3

# Set environment variables
os.environ['AWS_REGION'] = 'us-east-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'test'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'test'

# Configure boto3 client for LocalStack
lambda_client = boto3.client(
    'lambda',
    region_name='us-east-1',
    endpoint_url='http://localhost:4566',  # Default LocalStack endpoint
    aws_access_key_id='test',
    aws_secret_access_key='test',
    aws_session_token=None  # Not needed for LocalStack
)

# Prepare the payload
payload = {
    "action": "generate_daily_narrative",
    "user_id": "test-user"
}

print("\n3. Generating story...")

# Invoke the Lambda function
try:
    response = lambda_client.invoke(
        FunctionName='narrative-generator',
        InvocationType='RequestResponse',  # Synchronous invocation
        Payload=json.dumps(payload)
    )
    
    # Read and save the response
    response_payload = json.loads(response['Payload'].read())
    
    # Save to response.json file
    with open('response.json', 'w') as f:
        json.dump(response_payload, f, indent=2)
    
    print(f"Lambda invocation completed. Status code: {response['StatusCode']}")
    print(f"Response saved to response.json")
    
    # Optional: Print the response
    print("\nResponse content:")
    print(json.dumps(response_payload, indent=2))
    
except Exception as e:
    print(f"Error invoking Lambda: {e}")