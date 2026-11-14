import boto3

from jobalerts import config  # importing this also loads .env

client = boto3.client("bedrock-runtime", region_name=config.aws_region())
response = client.converse(
    modelId=config.bedrock_model_id(),
    messages=[{"role": "user", "content": [{"text": "Reply with OK only."}]}],
)
print(response["output"]["message"]["content"][0]["text"])