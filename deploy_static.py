import boto3
import os
import time
from pathlib import Path
import mimetypes

AWS_REGION = 'us-east-1'
S3_BUCKET_NAME = 'zoharbabintest'
CLOUDFRONT_DISTRIBUTION_ID = 'E1EJTL378WS6GY'
LOCAL_STATIC_DIR = './static'

s3_client = boto3.client('s3', region_name=AWS_REGION)
cloudfront_client = boto3.client('cloudfront', region_name=AWS_REGION)

def upload_files_to_s3():
    for root, dirs, files in os.walk(LOCAL_STATIC_DIR):
        for file in files:
            file_path = os.path.join(root, file)
            s3_key = str(Path(file_path).relative_to(LOCAL_STATIC_DIR))
            content_type, _ = mimetypes.guess_type(file_path)
            if content_type is None:
                content_type = 'binary/octet-stream'  # default fallback

            print(f'Uploading {file_path} to s3://{S3_BUCKET_NAME}/{s3_key} with ContentType {content_type}')
            s3_client.upload_file(
                file_path,
                S3_BUCKET_NAME,
                s3_key,
                ExtraArgs={'ContentType': content_type}
            )

def invalidate_cloudfront_cache():
    invalidation = cloudfront_client.create_invalidation(
        DistributionId=CLOUDFRONT_DISTRIBUTION_ID,
        InvalidationBatch={
            'Paths': {
                'Quantity': 1,
                'Items': ['/*']
            },
            'CallerReference': str(time.time())
        }
    )
    print(f'Invalidation ID: {invalidation["Invalidation"]["Id"]}')

if __name__ == "__main__":
    upload_files_to_s3()
    invalidate_cloudfront_cache()
