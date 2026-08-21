import base64
import datetime
import hashlib
import hmac
import json
import os

import alibabacloud_oss_v2 as oss

from aliyun_sts_v2 import AliyunSTSService, STSAssumeRoleResult
from dotenv import load_dotenv

# OSS V4 签名与访问所需的 Bucket 信息，需与 STS 临时凭证授权的资源保持一致。
OSS_REGION = "cn-shanghai"
OSS_BUCKET = "joytest-test"
OSS_ENDPOINT = "oss-cn-shanghai.aliyuncs.com"


def generate_v4_signature(
    access_key_secret: str,
    date: str,
    region: str,
    string_to_sign: str,
) -> str:
    """
    生成 OSS V4 签名（OSS4-HMAC-SHA256）。

    :param access_key_secret: 有权限访问目标 Bucket 的 AccessKeySecret（STS 临时凭证的 secret）。
    :param date: 签名日期，格式 yyyyMMdd。
    :param region: Bucket 所在地域，如 cn-shanghai。
    :param string_to_sign: 待签名内容，即 base64 编码后的 Post Policy。
    :return: 十六进制签名字符串。
    """
    signing_key = "aliyun_v4" + access_key_secret
    k_date = hmac.new(signing_key.encode(), date.encode(), hashlib.sha256).digest()
    k_region = hmac.new(k_date, region.encode(), hashlib.sha256).digest()
    k_service = hmac.new(k_region, "oss".encode(), hashlib.sha256).digest()
    k_signing = hmac.new(k_service, "aliyun_v4_request".encode(), hashlib.sha256).digest()
    return hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()


def main():
    # 配置参数
    ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID", "")
    ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET", "")
    REGION_ID = os.getenv("OSS_REGION_ID", "")

    ROLE_ARN = os.getenv("OSS_ROLE_ARN", "")
    ROLE_SESSION_NAME = "default-session"

    if not ACCESS_KEY_ID or not ACCESS_KEY_SECRET or not REGION_ID or not ROLE_ARN:
        print("请设置环境变量：")
        print("OSS_ACCESS_KEY_ID")
        print("OSS_ACCESS_KEY_SECRET")
        print("OSS_REGION_ID")
        print("OSS_ROLE_ARN")
        return

    # 创建STS服务
    sts_service = AliyunSTSService(ACCESS_KEY_ID, ACCESS_KEY_SECRET, REGION_ID)

    # 可选：自定义权限策略
    policy = {
        "Version": "1",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["oss:GetObject", "oss:PutObject"],
                "Resource": "acs:oss:*:*:joytest-test/*",
            }
        ],
    }

    try:
        # 获取临时凭证
        credentials = sts_service.assume_role(
            role_arn=ROLE_ARN,
            role_session_name=ROLE_SESSION_NAME,
            duration_seconds=3600,
            policy=policy,
        )

        print("STS临时凭证获取成功：")
        print(credentials.__dict__)
        print()

        # 使用临时凭证的示例
        use_temp_credentials(credentials)

    except Exception as e:
        print(f"错误：{e}")


def build_oss_client(credentials: STSAssumeRoleResult) -> oss.Client:
    """
    使用 STS 临时凭证创建 OSS v2 客户端。
    """
    credentials_provider = oss.credentials.StaticCredentialsProvider(
        access_key_id=credentials.access_key_id,
        access_key_secret=credentials.access_key_secret,
        security_token=credentials.security_token,
    )

    cfg = oss.config.load_default()
    cfg.region = OSS_REGION
    cfg.endpoint = OSS_ENDPOINT
    cfg.credentials_provider = credentials_provider

    return oss.Client(cfg)


def use_temp_credentials(credentials: STSAssumeRoleResult):
    """
    使用临时凭证的示例
    """
    # 使用临时凭证创建 OSS v2 客户端
    client = build_oss_client(credentials)

    # 使用示例
    print("可以使用临时凭证进行OSS操作")

    # 生成 GET 预签名 URL 示例（对应 v1 的 bucket.sign_url("GET", url, 600)）
    # 注意：alibabacloud_oss_v2 的 presign 接收的是具体操作请求模型（如 GetObjectRequest），
    # 没有 oss.PresignRequest；expires 需传 datetime.timedelta。
    url = "62a7e7edf9a4db0a0b338a1e/forms/13836b2c-8008-40a3-8fb1-05debb934863.zip"
    result = client.presign(
        oss.GetObjectRequest(bucket=OSS_BUCKET, key=url),
        expires=datetime.timedelta(seconds=600),
    )
    print(result.url)

    # 生成表单直传（PostObject）所需的 V4 签名信息。
    # 时间需为 UTC，签名与表单字段都基于同一个时间点。
    utc_now = datetime.datetime.utcnow()
    date = utc_now.strftime("%Y%m%d")
    x_oss_date = utc_now.strftime("%Y%m%dT%H%M%SZ")
    expiration = (utc_now + datetime.timedelta(seconds=600)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    x_oss_credential = f"{credentials.access_key_id}/{date}/{OSS_REGION}/oss/aliyun_v4_request"

    policy_map = {
        "expiration": expiration,  # 有效期
        # 约束条件（V4 签名版本）
        "conditions": [
            {"bucket": OSS_BUCKET},
            {"x-oss-signature-version": "OSS4-HMAC-SHA256"},
            {"x-oss-credential": x_oss_credential},
            {"x-oss-date": x_oss_date},
            {"x-oss-security-token": credentials.security_token},
            ["starts-with", "$key", "test/"],
            ["content-length-range", 0, 1000000],
        ],
    }
    policy = json.dumps(policy_map)
    policy_base64 = base64.b64encode(policy.encode("utf-8")).decode()

    signature = generate_v4_signature(
        credentials.access_key_secret,
        date,
        OSS_REGION,
        policy_base64,
    )

    response = {
        "policy": policy_base64,
        "x_oss_signature_version": "OSS4-HMAC-SHA256",
        "x_oss_credential": x_oss_credential,
        "x_oss_date": x_oss_date,
        "x_oss_signature": signature,
        "x_oss_security_token": credentials.security_token,
        "host": f"https://{OSS_BUCKET}.{OSS_ENDPOINT}",
        "dir": "test/",
        # 可以在这里再自行追加其他参数
    }

    with open("token.json", "w") as f:
        f.write(json.dumps(response, indent=2, ensure_ascii=False))
    print(json.dumps(response, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    load_dotenv(".env", override=True)
    main()
