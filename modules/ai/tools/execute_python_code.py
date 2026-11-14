import base64
import traceback

import orjson
from e2b_code_interpreter import AsyncSandbox
from e2b_code_interpreter.exceptions import TimeoutException

from modules.ai.config import AiConfigSecret
from core.utils.cache import random_cache_path

api_key = AiConfigSecret.e2b_api_key

if api_key:
    execute_python_code_desc = {
        "type": "function",
        "function": {
            "name": "execute_python_code",
            "description": "Run Python code in an isolated sandbox and return its output. "
            "Use it for calculations that need exact results, data processing, or charts, "
            "or when the user asks you to run code. "
            "The sandbox has no internet access, a 10-second time limit, and keeps no state between calls. "
            "Returns printed output, the value of the last expression, and any PNG or JPEG images "
            "the code displays, such as charts shown with `plt.show()`.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "A complete, self-contained Python script. Use `print()` for text results.",
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
                return f"The code raised an error:\n{execution.error.traceback}"

            returns = []
            images = []
            for res in execution.results:
                if res.png:
                    path = f"{random_cache_path()}.png"
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(res.png))
                    returns.append(f"[KE:image,path={path}]")
                    images.append({"path": path, "data_url": f"data:image/png;base64,{res.png}"})
                if res.jpeg:
                    path = f"{random_cache_path()}.jpg"
                    with open(path, "wb") as f:
                        f.write(base64.b64decode(res.jpeg))
                    returns.append(f"[KE:image,path={path}]")
                    images.append({"path": path, "data_url": f"data:image/jpeg;base64,{res.jpeg}"})
                if res.text:
                    returns.append(res.text)

            result = {"returns": returns, "stdout": execution.logs.stdout + execution.logs.stderr, "images": images}
            return orjson.dumps(result).decode("utf-8")
        except TimeoutException:
            return "Execution timed out after 10 seconds. Simplify the code or reduce the workload before retrying."
        except Exception:
            traceback.print_exc()
            return "Unable to run Python code. Tell the user to contact the bot owner."
