"""
批量重试 Token 获取脚本。

从 tokens/pending_accounts.json 读取所有注册成功但未获取到 Token 的账号，
逐一尝试登录获取 Token，成功后从队列中移除。
"""
import json
import logging
import os
import time
from openai_registration import (
    create_session,
    generate_proxy_url,
    perform_oauth_login,
    save_token_json,
    TOKENS_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("retry_tokens")

PENDING_FILE = os.path.join(TOKENS_DIR, "pending_accounts.json")


def load_pending():
    if not os.path.exists(PENDING_FILE):
        return []
    with open(PENDING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_pending(pending):
    os.makedirs(TOKENS_DIR, exist_ok=True)
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)


def main():
    pending = load_pending()
    if not pending:
        logger.info("✅ 没有待处理的账号，队列为空。")
        return

    logger.info(f"共有 {len(pending)} 个账号待重试获取 Token...")
    remaining = []

    for i, account in enumerate(pending, 1):
        email    = account.get("email", "")
        password = account.get("password", "")
        logger.info(f"\n[{i}/{len(pending)}] 正在处理: {email}")

        try:
            proxy_url = generate_proxy_url()
            session   = create_session(proxy_url)
            tokens    = perform_oauth_login(
                session, email, password, account_data={"email": email}
            )

            if tokens and tokens.get("access_token"):
                saved = save_token_json(
                    email,
                    tokens["access_token"],
                    tokens.get("refresh_token"),
                    tokens.get("id_token"),
                )
                logger.info(f"✅ Token 获取成功，已保存: {saved}")
                # 成功则不加入 remaining，相当于从队列移除
            else:
                logger.warning(f"⚠️  Token 获取失败，保留在队列中: {email}")
                remaining.append(account)

        except Exception as e:
            logger.error(f"❌ 处理 {email} 时出现异常: {e}")
            remaining.append(account)

        # 每个账号之间等 3 秒规避限速
        if i < len(pending):
            logger.info("等待 3 秒再处理下一个账号...")
            time.sleep(3)

    save_pending(remaining)
    success_count = len(pending) - len(remaining)
    logger.info(f"\n========== 处理完成 ==========")
    logger.info(f"成功: {success_count}  |  剩余待重试: {len(remaining)}")
    if remaining:
        logger.info(f"失败账号已保留在: {PENDING_FILE}")


if __name__ == "__main__":
    main()
