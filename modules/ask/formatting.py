import aiohttp
import ujson as json


async def generate_latex(formula: str):
    async with aiohttp.ClientSession() as session:
        async with session.post(url='https://wikimedia.org/api/rest_v1/media/math/check/inline-tex', data=json.dumps({
            'q': formula
        }), headers={'content-type': 'application/json'}) as req:
            headers = req.headers
            location = headers.get('x-resource-location')

        async with session.get(url=f'https://wikimedia.org/api/rest_v1/media/math/render/png/{location}') as img:
            return await img.read()


async def generate_code_snippet(code: str, language: str):
    async with aiohttp.ClientSession() as session:
        async with session.post(url='https://sourcecodeshots.com/api/image', data=json.dumps({
            'code': code,
            'settings': {
                'language': language,
                'theme': 'night-owl',
            }
        }), headers={'content-type': 'application/json'}) as req:
            return await req.read()
