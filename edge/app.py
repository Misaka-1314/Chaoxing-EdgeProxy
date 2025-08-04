from typing import Dict, Any
import websockets
import logging
import asyncio
import httpx
import json
import sys
import os

SERVER_WS_URL = os.getenv("SERVER_WS_URL", "ws://localhost:8000/edge/ws/dev")
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", 30))

logging.basicConfig(level=logging.INFO)
TIME_COLOR = "\033[32m"
LEVEL_COLOR = "\033[33m"
RESET = "\033[0m"
logger = logging.getLogger()
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(
    fmt=logging.Formatter(
        f"{TIME_COLOR}%(asctime)s{RESET} - {LEVEL_COLOR}%(levelname)s{RESET} - %(message)s"
    )
)
logger.addHandler(handler)
logging.getLogger("httpx").setLevel(logging.WARNING)


class EdgeAgent:
    def __init__(self):
        self._websocket = None
        self._client = httpx.AsyncClient(http2=True, timeout=HTTP_TIMEOUT)
        self._tasks: set[asyncio.Task] = set()

    async def connect(self):
        """连接到服务端WebSocket"""
        while True:
            logging.info("尝试连接主服务器")
            try:
                self._websocket = await websockets.connect(
                    SERVER_WS_URL,
                    ping_interval=20,
                    ping_timeout=5,
                    close_timeout=10,
                )
                logging.info("连接成功，开始接收代理请求")
                await self.loop()
            except websockets.ConnectionClosed:
                logging.error("连接已关闭，尝试重新连接...")
                await asyncio.sleep(5)
            except Exception as e:
                logging.error(f"连接错误: {e.__class__.__name__} {str(e)}")
                await asyncio.sleep(5)

    async def loop(self):
        """持续接收服务端的代理请求"""
        while self._websocket:
            try:
                message = await self._websocket.recv()
                data: dict = json.loads(message)

                task = asyncio.create_task(self.handle_proxy_request(**data))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
            except json.JSONDecodeError:
                logging.error("接收到无效的JSON数据")
            except KeyError as e:
                logging.error(f"请求数据缺少必要字段: {str(e)}")

    async def handle_proxy_request(
        self,
        request_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """处理具体的代理请求"""
        try:
            response = await self._client.request(
                method=payload["method"],
                url=payload["url"],
                headers=payload["headers"],
                content=payload["body"],
                timeout=HTTP_TIMEOUT,
            )

            remove = {
                "Content-Encoding",
                "Content-Length",
                "Transfer-Encoding",
                "Connection",
                "Keep-Alive",
            }
            headers = {
                k: v
                for k, v in response.headers.items()
                if k.lower() not in {r.lower() for r in remove}
            }

            await self._websocket.send(
                json.dumps(
                    {
                        "request_id": request_id,
                        "payload": {
                            "status_code": response.status_code,
                            "headers": headers,
                            "body": response.text,
                        },
                    }
                )
            )

        except httpx.HTTPError as e:
            await self._websocket.send(
                json.dumps(
                    {
                        "request_id": request_id,
                        "payload": {
                            "status_code": 502,
                            "headers": {},
                            "body": f"HTTP请求失败: {str(e)}",
                        },
                    }
                )
            )


if __name__ == "__main__":
    agent = EdgeAgent()
    asyncio.run(agent.connect())
