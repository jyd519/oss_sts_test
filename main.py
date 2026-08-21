from aliyun_sts import AliyunSTSService, STSAssumeRoleResult
from dotenv import load_dotenv
import json
import os
import time
import datetime
import base64
import hmac
from hashlib import sha1 as sha

def generate_expiration(seconds: int) -> str:
    """
    通过指定有效的时长（秒）生成过期时间。
    :param seconds: 有效时长（秒）。
    :return: ISO8601 时间字符串，如："2014-12-01T12:00:00.000Z"。
    """
    now = int(time.time())
    expiration_time = now + seconds
    gmt = datetime.datetime.utcfromtimestamp(expiration_time).isoformat()
    gmt += 'Z'
    return gmt

def generate_signature(access_key_secret: str, expiration: str, conditions: str, policy_extra_props=None) -> str:
    """
    生成签名字符串Signature。
    :param access_key_secret: 有权限访问目标Bucket的AccessKeySecret。
    :param expiration: 签名过期时间，按照ISO8601标准表示，并需要使用UTC时间，格式为yyyy-MM-ddTHH:mm:ssZ。示例值："2014-12-01T12:00:00.000Z"。
    :param conditions: 策略条件，用于限制上传表单时允许设置的值。
    :param policy_extra_props: 额外的policy参数，后续如果policy新增参数支持，可以在通过dict传入额外的参数。
    :return: signature，签名字符串。
    """
    policy_dict = {
        'expiration': expiration,
        'conditions': conditions
    }
    if policy_extra_props is not None:
        policy_dict.update(policy_extra_props)
    policy = json.dumps(policy_dict).strip()
    policy_encode = base64.b64encode(policy.encode())
    h = hmac.new(access_key_secret.encode(), policy_encode, sha)
    sign_result = base64.b64encode(h.digest()).strip()
    return sign_result.decode()


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


def use_temp_credentials(credentials: STSAssumeRoleResult):
    """
    使用临时凭证的示例
    """
    # 这里可以展示如何使用临时凭证
    import oss2

    # 使用临时凭证创建OSS客户端
    auth = oss2.StsAuth(
        credentials.access_key_id,
        credentials.access_key_secret,
        credentials.security_token,
    )

    # 创建Bucket实例
    bucket = oss2.Bucket(auth, "https://oss-cn-shanghai.aliyuncs.com", "joytest-test")

    # 使用示例
    print("可以使用临时凭证进行OSS操作")
    # url = "62a7e7edf9a4db0a0b338a1e/forms/13836b2c-8008-40a3-8fb1-05debb934863.zip"
    # print(bucket.sign_url("GET", url, 600))

    policy = {
        "expiration": generate_expiration(600), # 有效期
        # 约束条件
        "conditions": [
            # 未指定success_action_redirect时，上传成功后的返回状态码，默认为 204。
            ["eq", "$success_action_status", "200"],
            ["starts-with", "$key", "test/"],
            ["content-length-range", 0, 1000000],
        ]
    }
    signature = generate_signature(credentials.access_key_secret, policy.get('expiration', ''), policy.get('conditions', ''))
    response = {
        'policy': base64.b64encode(json.dumps(policy).encode('utf-8')).decode(),
        'ossAccessKeyId': credentials.access_key_id,
        'signature': signature,
        'securityToken': credentials.security_token,
        'host': "https://joytest-test.oss-cn-shanghai.aliyuncs.com",
        'dir':"test/" 
        # 可以在这里再自行追加其他参数
    }

    with open("token.json", "w") as f:
        f.write(json.dumps(response, indent=2,  ensure_ascii=False))
    print(json.dumps(response, indent=2,  ensure_ascii=False))



if __name__ == "__main__":
    load_dotenv(".env", override=True)
    main()
