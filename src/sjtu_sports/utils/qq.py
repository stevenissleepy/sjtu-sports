"""QQ Bot notifications and recipient OpenID discovery."""

import asyncio
import os

import requests
from dotenv import load_dotenv

from sjtu_sports.utils.paths import HOME


TOKEN_URL = "https://api.bot.qq.com/app/getAppAccessToken"
MESSAGE_URL = "https://api.bot.qq.com/v2/users/{openid}/messages"


def send_qq_bot(app_id, app_secret, openid, message):
    """Return (sent, error) without exposing credentials or the recipient."""
    try:
        with requests.Session() as session:
            session.trust_env = False
            token_response = session.post(
                TOKEN_URL,
                json={"appId": app_id, "clientSecret": app_secret},
                timeout=5,
            )
            if token_response.status_code != 200:
                return False, f"获取访问凭证失败：HTTP {token_response.status_code}"
            try:
                token_result = token_response.json()
            except ValueError:
                return False, "获取访问凭证失败：响应不是 JSON"
            if not isinstance(token_result, dict):
                return False, "获取访问凭证失败：响应格式不正确"
            token = token_result.get("access_token")
            if not token:
                return False, f"获取访问凭证失败：code={token_result.get('code')}"

            response = session.post(
                MESSAGE_URL.format(openid=openid),
                headers={"Authorization": f"QQBot {token}"},
                json={"msg_type": 0, "content": message},
                timeout=5,
            )
    except requests.RequestException:
        return False, "网络请求失败"

    if response.status_code != 200:
        try:
            result = response.json()
        except ValueError:
            return False, f"发送失败：HTTP {response.status_code}"
        if isinstance(result, dict) and result.get("err_code") is not None:
            return False, f"发送失败：err_code={result['err_code']}"
        return False, f"发送失败：HTTP {response.status_code}"
    try:
        result = response.json()
    except ValueError:
        return False, "发送失败：响应不是 JSON"
    if not isinstance(result, dict):
        return False, "发送失败：响应格式不正确"
    if result.get("err_code") is not None:
        return False, f"发送失败：err_code={result['err_code']}"
    if not result.get("id"):
        return False, "发送失败：响应缺少消息 ID"
    return True, ""


def qq_openid_main():
    """Print and reply with the OpenID from the next bot private message."""
    load_dotenv(HOME / ".env", override=False)
    app_id = os.environ.get("QQ_BOT_APP_ID", "").strip()
    app_secret = os.environ.get("QQ_BOT_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        raise SystemExit("请先在 .env 中设置 QQ_BOT_APP_ID 和 QQ_BOT_APP_SECRET")

    import botpy

    class OpenIDClient(botpy.Client):
        def __init__(self):
            super().__init__(
                intents=botpy.Intents(public_messages=True),
                bot_log=False,
                ext_handlers=False,
            )
            self.openid = None
            self.reply_failed = False
            self.received = asyncio.Event()

        async def on_ready(self):
            print("机器人已连接，请在 QQ 私聊机器人发送一条消息。", flush=True)

        async def on_c2c_message_create(self, message):
            openid = message.author.user_openid
            if openid:
                setting = f'QQ_BOT_USER_OPENID="{openid}"'
                try:
                    await self.api.post_c2c_message(
                        openid=openid,
                        msg_type=0,
                        msg_id=message.id,
                        content=setting,
                    )
                except Exception:
                    self.reply_failed = True
                self.openid = openid
                self.received.set()

    async def capture():
        client = OpenIDClient()
        running = asyncio.create_task(client.start(app_id, app_secret))
        received = asyncio.create_task(client.received.wait())
        try:
            done, _ = await asyncio.wait(
                {running, received}, return_when=asyncio.FIRST_COMPLETED
            )
            if running in done:
                await running
                raise RuntimeError("机器人连接已结束，未收到私聊消息")
            print(f'QQ_BOT_USER_OPENID="{client.openid}"', flush=True)
            if client.reply_failed:
                print("QQ 私聊回复失败，请使用终端中的 OpenID。", flush=True)
        finally:
            running.cancel()
            received.cancel()
            await client.close()
            await asyncio.gather(running, received, return_exceptions=True)

    asyncio.run(capture())
