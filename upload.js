const fs = require("fs");
const path = require("path");

async function uploadFileToOSS(filePath) {
  // 1. 请求业务服务端接口获取签名参数
  const params = JSON.parse(fs.readFileSync("./token.json", "utf-8"));
  console.log(params);

  // 2. 读取本地文件并构建 FormData
  const fileName = path.basename(filePath);
  const fileBuffer = fs.readFileSync(filePath);
  const blob = new Blob([fileBuffer]);

  const formData = new FormData();
  formData.append("key", params.dir + fileName);
  formData.append("policy", params.policy);
  formData.append("OSSAccessKeyId", params.ossAccessKeyId);
  if (params.callback) {
    formData.append("callback", params.callback);
  }
  formData.append("success_action_status", "200");
  formData.append("signature", params.signature);
  if (params.securityToken) {
    formData.append("x-oss-security-token", params.securityToken);
  }

  // 注意：file 表单域必须放在最后一个追加
  formData.append("file", blob, fileName);

  // 3. 发送 POST 请求将文件直接上传至 OSS
  const uploadRes = await fetch(params.host, {
    method: "POST",
    body: formData,
  });

  if (uploadRes.status === 200) {
    console.log(
      "上传成功！文件 URL:",
      `${params.host}/${params.dir}${fileName}`,
    );
  } else {
    const errorText = await uploadRes.text();
    console.error("上传失败，状态码:", uploadRes.status, errorText);
  }
}

// 调用示例
uploadFileToOSS("./README.md");
