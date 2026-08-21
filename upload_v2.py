import json
import sys
from pathlib import Path

import requests


def upload_file_to_oss(file_path: str | Path) -> None:
    """使用 token.json 中的 V4 签名信息，将本地文件直传至 OSS。"""
    params = json.loads(Path("./token.json").read_text(encoding="utf-8"))
    print(params)

    file_path = Path(file_path)
    file_name = file_path.name

    form_fields = [
        ("key", params["dir"] + file_name),
        ("policy", params["policy"]),
        ("x-oss-signature-version", params["x_oss_signature_version"]),
        ("x-oss-credential", params["x_oss_credential"]),
        ("x-oss-date", params["x_oss_date"]),
        ("x-oss-signature", params["x_oss_signature"]),
    ]
    if params.get("x_oss_security_token"):
        form_fields.append(("x-oss-security-token", params["x_oss_security_token"]))
    if params.get("callback"):
        form_fields.append(("callback", params["callback"]))

    # requests 先编码 data 字段，file 字段始终位于最后。
    with file_path.open("rb") as file:
        upload_res = requests.post(
            params["host"],
            data=form_fields,
            files=[("file", (file_name, file))],
        )

    # OSS PostObject 默认成功返回 204（No Content），未设置 success_action_status 时即为 204。
    if upload_res.status_code // 100 == 2:
        file_url = f'{params["host"]}/{params["dir"]}{file_name}'
        print("上传成功！文件 URL:", file_url, upload_res.status_code)
    else:
        print(
            "上传失败，状态码:",
            upload_res.status_code,
            upload_res.text,
            file=sys.stderr,
        )


if __name__ == "__main__":
    upload_file_to_oss("./README.md")
