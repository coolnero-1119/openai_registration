"""
对已注册成功但未获取到 Token 的账号，单独执行登录换取 Token。
"""
import logging
from openai_registration import (
    create_session,
    generate_proxy_url,
    perform_oauth_login,
    save_token_json
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("login_only")

# ====== 填入账号信息 ======
EMAIL    = "esiom0gmloamr@dev-group.engineer"
PASSWORD = "Au3Zi#RGEJEI%ckX"
# ==========================

def main():
    logger.info(f"开始为 {EMAIL} 单独登录获取 Token...")
    proxy_url = generate_proxy_url()
    session = create_session(proxy_url)

    tokens = perform_oauth_login(session, EMAIL, PASSWORD, account_data={"email": EMAIL})

    if tokens and tokens.get("access_token"):
        saved = save_token_json(
            EMAIL,
            tokens["access_token"],
            tokens.get("refresh_token"),
            tokens.get("id_token"),
        )
        logger.info(f"✅ Token 获取成功，已保存: {saved}")
    else:
        logger.error("❌ Token 获取失败，请查看上方日志")

if __name__ == "__main__":
    main()
