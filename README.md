# OpenAI 自动化注册 & Token 获取工具

一个基于纯 HTTP 协议的 OpenAI 账号自动注册脚本，无需 Selenium，所有注册逻辑在内存中完成。

## 功能特点

- ✅ 持续批量注册 OpenAI 账号（含邮箱验证码与账号创建）
- ✅ 注册成功后自动登录并提取 `access_token` / `refresh_token` / `id_token`
- ✅ Token 保存为本地 JSON 文件（`tokens/<email>.json`）
- ✅ 支持动态住宅代理（IPRoyal 等）
- ✅ 完全绕过 Sentinel 反爬指纹验证（纯 Python 逆向实现）
- ✅ 自动存档失败账号，支持批量补回漏掉的 Token


## 依赖

- Python 3.10+
- IPRoyal 动态住宅代理账号（或其他兼容代理）
- Cloudflare Temp Email 收件后端：[dreamhunter2333/cloudflare_temp_email](https://github.com/dreamhunter2333/cloudflare_temp_email)


## 安装

```bash
git clone https://github.com/coolnero-1119/openai_registration.git
cd openai_registration
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```


## 配置

修改 `openai_registration.py` 顶部的以下常量：

```python
# 你的 Cloudflare 收信域名（不能是 .top，OpenAI 不支持）
CF_EMAIL_DOMAIN = "your-domain.engineer"

# 你部署的 cloudflare_temp_email worker 地址
MAIL_API_BASE = "https://apimail.your-domain.com"
MAIL_API_ADMIN_AUTH = "你的管理员密码"   # 对应 worker 环境变量 ADMIN_PASSWORDS
```

修改 `openai_registration.py` 中的 `generate_proxy_url()` 函数，填入你的代理账号信息：

```python
proxy_host = "geo.iproyal.com:12321"   # 你的代理网关
auth_user  = "你的用户名"
auth_pass  = "你的密码"
```

### Cloudflare 邮箱收件配置

1. 将域名托管到 Cloudflare
2. Email → Email Routing → Catch-all → **Send to a Worker**，绑定你的 `worker.js`


## 使用

### 持续批量注册（主程序）

```bash
source venv/bin/activate
python run_test.py
```

- 自动循环注册，每次完成后打印统计
- 连续失败 **3 次**自动退出（可在文件顶部修改 `MAX_CONSECUTIVE_FAILURES`）
- 随时按 `Ctrl+C` 手动停止

### 批量补回漏掉的 Token

注册成功但 Token 获取失败的账号会自动存入 `tokens/pending_accounts.json`，运行以下命令批量补回：

```bash
python retry_tokens.py
```

### 对单个账号单独获取 Token

```bash
# 修改 login_only.py 里的 EMAIL / PASSWORD，然后运行：
python login_only.py
```


## Token 文件格式

保存路径：`../tokens/<email>.json`（项目目录的上一层）

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "id_token": "...",
  "email": "xxx@your-domain.engineer"
}
```


## 项目结构

```
openai_registration/
├── openai_registration.py   # 核心注册逻辑（Sentinel 逆向 + OAuth 流程）
├── run_test.py              # 持续批量注册入口
├── retry_tokens.py          # 批量补回漏掉的 Token
├── login_only.py            # 单账号手动登录获取 Token
├── requirements.txt         # 依赖列表
└── README.md
```


## 注意事项

- 本项目**仅供学习和个人研究**，请勿违反 OpenAI 服务条款
- 避免使用 `.top`、`.xyz` 等被 OpenAI 拉黑的域名后缀
- 代理 IP 质量直接影响注册成功率，推荐住宅代理
- OpenAI 会定期更新 Sentinel 算法，若成功率下降请检查 `SentinelTokenGenerator`
