import os
from dotenv import load_dotenv
import boto3

load_dotenv()

ses = boto3.client(
    "ses",
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)

response = ses.send_email(
    Source=os.getenv("SES_FROM_ADDRESS"),
    Destination={
        "ToAddresses": [
            os.getenv("STREAMSUITES_ADMIN_EMAILS").split(",")[0]
        ]
    },
    Message={
        "Subject": {
            "Data": "StreamSuites SES test",
            "Charset": "UTF-8",
        },
        "Body": {
            "Text": {
                "Data": "This is a transactional test email from StreamSuites.",
                "Charset": "UTF-8",
            }
        },
    },
)

print("SES send OK:", response["MessageId"])
