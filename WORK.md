# WORK.md — 阿里云 OSS v1 → v2 迁移记录

> 用途：下次迭代时快速回顾本项目的关键结论与坑点，避免重新查文档。

## 一、项目背景

从阿里云 v1 SDK 升级到 v2，核心链路：**STS AssumeRole 拿临时凭证 → 用临时凭证做 OSS 操作 / 生成表单直传签名**。

约定：**现有 v1 文件不改动**，v2 代码一律新建文件。

| 文件 | 说明 | 状态 |
|---|---|---|
| `aliyun_sts.py` | v1 STS（`aliyunsdkcore`） | 原文件，不改 |
| `main.py` | v1 OSS（`oss2`）+ v1 签名 | 原文件，不改 |
| `upload.py` | v1 表单直传（requests） | 原文件，不改 |
| `aliyun_sts_v2.py` | v2 STS（`alibabacloud_sts20150401`） | 新建 |
| `main_v2.py` | v2 OSS（`alibabacloud_oss_v2`）+ V4 签名 | 新建 |
| `upload_v2.py` | V4 表单直传（requests） | 新建 |

## 二、依赖

`pyproject.toml` 已有：`alibabacloud-credentials`、`alibabacloud-sts20150401`、`alibabacloud-tea-openapi`、`oss2`、`python-dotenv`、`requests`。

```bash
uv add alibabacloud-oss-v2
```

环境变量（`.env`）：`OSS_ACCESS_KEY_ID`、`OSS_ACCESS_KEY_SECRET`、`OSS_REGION_ID`、`OSS_ROLE_ARN`。

## 三、STS v2（`alibabacloud_sts20150401`）

```python
from alibabacloud_sts20150401.client import Client as StsClient
from alibabacloud_sts20150401 import models as sts_models
from alibabacloud_tea_openapi.models import Config as OpenApiConfig

config = OpenApiConfig(access_key_id=..., access_key_secret=..., region_id=..., endpoint="sts.aliyuncs.com")
client = StsClient(config)

request = sts_models.AssumeRoleRequest(role_arn=..., role_session_name=..., duration_seconds=3600)
request.policy = json.dumps(policy)          # 注意：policy 是 JSON 字符串，不是 dict

response = client.assume_role(request)       # 方法名是 assume_role（存在）
body = response.body
body.credentials.access_key_id / .access_key_secret / .security_token / .expiration
body.request_id
```

- v1 `AcsClient`+`CommonRequest`+`do_action_with_exception`+`json.loads` → v2 `StsClient`+`AssumeRoleRequest`+`assume_role()` 直接返回强类型 body。

## 四、OSS v2 客户端（`alibabacloud_oss_v2`）

```python
import alibabacloud_oss_v2 as oss

provider = oss.credentials.StaticCredentialsProvider(
    access_key_id=..., access_key_secret=..., security_token=...)   # STS 用 security_token
cfg = oss.config.load_default()
cfg.region = "cn-shanghai"
cfg.endpoint = "oss-cn-shanghai.aliyuncs.com"   # 不带 https:// 前缀
cfg.credentials_provider = provider
client = oss.Client(cfg)

# 预签名 GET
url = client.presign(oss.PresignRequest(bucket=..., key=..., method="GET", expires_in=600)).url
```

- v1 `oss2.StsAuth`+`oss2.Bucket` → v2 `StaticCredentialsProvider`+`Client`。
- v1 `bucket.sign_url("GET", key, 600)` → v2 `client.presign(...).url`。
- **OSS v2 默认签名版本就是 v4**，`presign` 无需额外配置。

## 五、V4 签名（PostObject 表单直传）— 重点坑点

官方参考：`sample/post_object.py`、文档「Python 表单上传」。

### 算法公式

```
string_to_sign = base64(policy)            # 就是 policy JSON 的 base64，不是别的

signing_key = "aliyun_v4" + access_key_secret
k1 = HMAC-SHA256(signing_key, date)        # date = YYYYMMDD
k2 = HMAC-SHA256(k1, region)               # 如 cn-shanghai
k3 = HMAC-SHA256(k2, "oss")
k4 = HMAC-SHA256(k3, "aliyun_v4_request")
signature = HMAC-SHA256(k4, string_to_sign).hexdigest()   # 输出 hex，不是 base64
```

### policy 结构（V4）

```python
{
  "expiration": "YYYY-MM-DDTHH:MM:SS.000Z",   # 必须带 .000 毫秒
  "conditions": [
    {"bucket": "<bucket>"},
    {"x-oss-signature-version": "OSS4-HMAC-SHA256"},          # 精确匹配
    {"x-oss-credential": "<ak>/<YYYYMMDD>/<region>/oss/aliyun_v4_request"},  # 精确匹配
    {"x-oss-date": "<YYYYMMDDTHHMMSSZ>"},                     # 精确匹配
    {"x-oss-security-token": "<STS token>"},                  # STS 必加
    ["starts-with", "$key", "test/"],
    ["content-length-range", 0, 1000000],
  ]
}
```

### 表单字段（V4，upload_v2.py）

顺序：`key`、`policy`、`x-oss-signature-version`、`x-oss-credential`、`x-oss-date`、`x-oss-signature`、（`x-oss-security-token`）、（`callback`）、`file`（**最后**）。

### 坑点清单

1. **STS 临时凭证必须同时**：`x-oss-credential` 用临时 AK、签名用临时 SK、`conditions` 加 `{"x-oss-security-token": token}`、表单字段加 `x-oss-security-token`。漏了会报 `InvalidAccessKeyId`。
2. **region 必须一致**：签名的 `region`、client 的 `endpoint`、`x-oss-credential` 里的 region 三者要同地域（本项目统一为 `cn-shanghai`，已提取常量 `OSS_REGION`/`OSS_BUCKET`/`OSS_ENDPOINT`）。
3. **时间用 UTC，且同源**：`date`(YYYYMMDD) / `x-oss-date`(YYYYMMDDTHHMMSSZ) / `expiration` 基于同一个 `datetime.utcnow()`。
4. **PostObject 成功返回 204（No Content），不是 200**。判断成功用 `status_code // 100 == 2`，不要用 `== 200`。若想保持 200，需在 conditions 加 `["eq", "$success_action_status", "200"]` 且表单带 `success_action_status=200`（本项目当前用「放宽判断」方案，未加）。
5. V4 签名输出是 **hexdigest**（v1 是 `base64(HMAC-SHA1)`）。

## 六、验证方式

```bash
python main_v2.py       # 生成 V4 版 token.json（先要装好依赖 + 配好 .env）
python upload_v2.py     # 用 token.json 直传，成功返回 204
```
