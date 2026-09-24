import aiohttp
import asyncio
from config import ONEC_BASE_URL, ONEC_USERNAME, ONEC_PASSWORD


class OneCClient:

    def __init__(self):
        self.base_url = ONEC_BASE_URL
        self.auth = aiohttp.BasicAuth(ONEC_USERNAME, ONEC_PASSWORD)
        self.timeout = aiohttp.ClientTimeout(total=30)

    async def get_order_tracking(self, track_number: str) -> dict:
        url = f"{self.base_url}/{track_number}"

        try:
            async with aiohttp.ClientSession(
                auth=self.auth, timeout=self.timeout
            ) as session:
                async with session.get(url) as response:

                    if response.status == 200:
                        data = await response.json(content_type=None)
                        return {"success": True, "data": data}

                    elif response.status == 404:
                        data = await response.json(content_type=None)
                        return {
                            "success": False,
                            "error": "not_found",
                            "message": data.get("message", "Заказ не найден"),
                        }

                    elif response.status == 401:
                        return {
                            "success": False,
                            "error": "auth_error",
                            "message": "Ошибка авторизации в 1С",
                        }

                    else:
                        return {
                            "success": False,
                            "error": "server_error",
                            "message": f"Ошибка сервера ({response.status})",
                        }

        except aiohttp.ClientConnectorError:
            return {
                "success": False,
                "error": "connection_error",
                "message": "Не удалось подключиться к 1С",
            }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "timeout",
                "message": "1С не ответила вовремя",
            }
        except Exception as e:
            return {
                "success": False,
                "error": "unknown",
                "message": str(e),
            }