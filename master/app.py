from fastapi import FastAPI, WebSocket, Request, HTTPException, Body
from fastapi.responses import Response
from starlette.websockets import WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Literal
import logging
import asyncio
import uvicorn
import random
import sys

app = FastAPI()

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


class AgentResponse(BaseModel):
    body: str
    status_code: int
    headers: dict


class AgentManager:
    def __init__(self):
        self._agents: List[WebSocket] = []
        self._futures: dict[str, asyncio.Future] = {}
        self._tasks: set[asyncio.Task] = set()

    async def add_agent(self, agent: WebSocket):
        """新增代理连接"""
        self._agents.append(agent)
        await self._handle_agent(agent)

    def remove_agent(self, agent: WebSocket):
        """移除代理连接"""
        self._agents.remove(agent)

    def _get_agent(self) -> WebSocket:
        """随机选择一个可用的代理连接"""
        if not len(self._agents):
            raise HTTPException(status_code=400, detail="没有可用的代理连接")
        return random.choice(self._agents)

    async def _handle_agent(self, agent: WebSocket):
        """处理代理连接的消息接收"""
        try:
            while True:
                resp: dict = await agent.receive_json()
                request_id = resp.get("request_id")
                response = AgentResponse.model_validate(resp["payload"])
                logging.info(f"收到响应 {request_id}")
                if request_id in self._futures:
                    self._futures[request_id].set_result(
                        Response(
                            content=response.body,
                            status_code=response.status_code,
                            headers=response.headers,
                            media_type=response.headers.get(
                                "Content-Type", "application/octet-stream"
                            ),
                        )
                    )
        except WebSocketDisconnect:
            logging.info("WebSocket 连接正常断开")
        except Exception as e:
            logging.error(f"连接异常，移除连接 {e.__class__.__name__}: {e}")
        finally:
            if agent in self._agents:
                self.remove_agent(agent)

    async def request(
        self,
        payload: dict,
        timeout: float = 60,
    ) -> Response:
        """请求代理处理"""
        target = self._get_agent()
        request_id = str(random.randint(100000, 999999))

        await target.send_json(
            data={
                "payload": payload,
                "request_id": request_id,
            }
        )

        future = asyncio.get_event_loop().create_future()
        self._futures[request_id] = future
        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            try:
                del self._futures[request_id]
            except KeyError:
                pass


managers = AgentManager()


@app.websocket("/edge/ws/{uuid}")
async def _(
    uuid: str,
    websocket: WebSocket,
):
    await websocket.accept()
    await managers.add_agent(websocket)


class ProxyRequest(BaseModel):
    url: str
    method: Literal["GET", "POST", "PUT", "DELETE"]
    headers: dict[str, str] = {}
    cookies: dict[str, str] = {}
    params: dict[str, str] = {}
    body: str = ""


@app.post("/proxy")
async def proxy_request(
    request: Request,
    proxy_request: ProxyRequest = Body(...),
):
    response = await managers.request(proxy_request.model_dump())
    logging.info(f"代理请求 {response.status_code} {response.headers}")
    return response


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
