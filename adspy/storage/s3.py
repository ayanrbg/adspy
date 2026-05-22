import io

import boto3

from adspy.config.settings import S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET, S3_PUBLIC_URL


def _get_s3_client():
    kwargs = {}
    if S3_ENDPOINT:
        kwargs["endpoint_url"] = S3_ENDPOINT
    if S3_ACCESS_KEY:
        kwargs["aws_access_key_id"] = S3_ACCESS_KEY
        kwargs["aws_secret_access_key"] = S3_SECRET_KEY
    return boto3.client("s3", **kwargs)


def upload_file(data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
    client = _get_s3_client()
    client.upload_fileobj(
        io.BytesIO(data),
        S3_BUCKET,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return f"{S3_PUBLIC_URL}/{key}"
