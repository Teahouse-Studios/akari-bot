import httpx
import orjson as json


async def generate_latex(formula: str):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url="https://wikimedia.org/api/rest_v1/media/math/check/inline-tex",
            data=json.dumps({"q": formula}),
            headers={"content-type": "application/json"},
        )
        headers = resp.headers
        location = headers.get("x-resource-location")

        img_resp = await client.get(
            url=f"https://wikimedia.org/api/rest_v1/media/math/render/png/{location}"
        )
        return img_resp.content


async def generate_code_snippet(code: str, language: str):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url="https://sourcecodeshots.com/api/image",
            data=json.dumps(
                {
                    "code": code,
                    "settings": {
                        "language": language,
                        "theme": "night-owl",
                    },
                }
            ),
            headers={"content-type": "application/json"},
        )
        return resp.content
