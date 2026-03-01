import logging
import time
from openai_registration import (
    generate_cf_email,
    generate_random_password,
    generate_proxy_url,
    ProtocolRegistrar
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("run_test")

# 连续失败多少次后自动退出
MAX_CONSECUTIVE_FAILURES = 3
# 每次注册之间的等待秒数
INTERVAL_SECONDS = 2


def register_one():
    """执行一次完整的注册流程，返回 (success, full_success, reason)。"""
    email    = generate_cf_email()
    password = generate_random_password()
    logger.info(f"▶ 开始注册: {email}")

    proxy_url = generate_proxy_url()
    registrar = ProtocolRegistrar(proxy_url=proxy_url)
    success, reason = registrar.register(account_data={"email": email}, password=password)
    return success, reason


def main():
    total         = 0
    success_full  = 0   # 注册 + Token 均成功
    success_reg   = 0   # 仅注册成功，Token 失败
    failures      = 0
    consecutive_failures = 0

    logger.info("========== 持续注册模式启动，按 Ctrl+C 停止 ==========")

    while True:
        total += 1
        logger.info(f"\n======== 第 {total} 次注册 ========")
        try:
            success, reason = register_one()

            if success and reason == "Success":
                success_full += 1
                consecutive_failures = 0
                logger.info(f"🎉 完全成功！累计成功获取 Token: {success_full} 个")

            elif success:
                success_reg += 1
                consecutive_failures = 0
                logger.warning(f"⚠️  注册成功，Token 失败（已存入待重试队列）: {reason}")

            else:
                failures += 1
                consecutive_failures += 1
                logger.error(f"❌ 注册失败 [{consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}]: {reason}")

        except KeyboardInterrupt:
            logger.info("\n用户手动停止。")
            break
        except Exception as e:
            failures += 1
            consecutive_failures += 1
            logger.error(f"❌ 异常 [{consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}]: {e}")

        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            logger.error(f"\n连续失败 {MAX_CONSECUTIVE_FAILURES} 次，自动退出。")
            break

        logger.info(f"统计 → 全成功: {success_full} | 仅注册: {success_reg} | 失败: {failures}")
        logger.info(f"等待 {INTERVAL_SECONDS} 秒后继续...")
        time.sleep(INTERVAL_SECONDS)

    logger.info(f"\n========== 运行结束 ==========")
    logger.info(f"总次数: {total} | 全成功: {success_full} | 仅注册: {success_reg} | 失败: {failures}")


if __name__ == "__main__":
    main()

