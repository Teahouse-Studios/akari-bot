import base64
import traceback

import orjson
from e2b_code_interpreter import AsyncSandbox
from e2b_code_interpreter.exceptions import TimeoutException

from core.config import Config
from core.utils.cache import random_cache_path

api_key = Config("e2b_api_key", cfg_type=str, secret=True, table_name="module_ai")

if api_key:
    execute_python_code_desc = {
        "type": "function",
        "function": {
            "name": "execute_python_code",
            "description": "Executes Python code and returns the results. Supports outputting text and PNG/JPEG images. Internet access is not supported.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The Python code that needs to be executed.",
                    },
                },
                "required": ["code"],
            },
        },
    }
else:
    execute_python_code_desc = {}


async def execute_python_code(code: str):
    async with await AsyncSandbox.create(api_key=api_key, allow_internet_access=False) as sandbox:
        try:
            execution = await sandbox.run_code(code, timeout=10)

            if execution.error:
                return execution.error.traceback

            returns = []
            for res in execution.results:
                if res.png:
                    path = f"{random_cache_path()}.png"
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(res.png))
                    returns.append(f"[KE:image,path={path}]")
                if res.jpeg:
                    path = f"{random_cache_path()}.jpg"
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(res.jpeg))
                    returns.append(f"[KE:image,path={path}]")
                if res.text:
                    returns.append(res.text)

            result = {"returns": returns, "stdout": execution.logs.stdout + execution.logs.stderr}
            return orjson.dumps(result).decode("utf-8")
        except TimeoutException:
            return "Request timeout"
        except Exception:
            traceback.print_exc()
            return "Unable to execute Python code, let user connect bot owner."
