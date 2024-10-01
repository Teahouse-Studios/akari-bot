from config import Config
from aiohttp import ClientSession
from retrying import retry
from core.exceptions import FaildToQueryWeather

import asyncio
import ujson as json

key = Config('qweather_api_key',cfg_type=str)
# key = "a5e3446eeec3419e91a08fdcfc19fb52"


class QweatherApi():
    @staticmethod
    @retry(wait_exponential_multiplier=1000, wait_exponential_max=10)
    async def query_url(url:str):
        async with ClientSession() as session:
            async with session.get(url) as response_:
                result = json.loads(await response_.text())
                if response_.status == 200:
                    return dict(result)
                else:
                    raise FaildToQueryWeather

    async def geo_ip(self,city):
        """
        获取城市信息
        :param city: 城市名称，支持中英文、汉语拼音
        :return: 返回数据JSON格式，参考https://dev.qweather.com/docs/api/geoapi/city-lookup/
        """
        url = f'https://geoapi.qweather.com/v2/city/lookup?location={city}&key={key}&lang=zh'
        return await self.query_url(url)

    async def get_lon_lat(self,city):
        location = await self.geo_ip(city)
        weathers_locate = {}
        for location_ in location["location"]:
            weathers_locate[location_['name']] = {'lon': location_['lon'], 'lat': location_['lat']}
        return weathers_locate

    async def weather_now(self,city):
        """
        获取中国3000+市县区和海外20万个城市实时天气数据，
        包括实时温度、体感温度、风力风向、相对湿度、大气压强、降水量、能见度、露点温度、云量等。
        :param city: 城市名称，支持中英文、汉语拼音
        """
        weathers = []
        weathers_locate = await self.get_lon_lat(city)
        for _city_ in weathers_locate:
            url = f"https://devapi.qweather.com/v7/weather/now?location={str(weathers_locate[_city_]['lon'])+','+str(weathers_locate[_city_]['lat'])}&key={key}&lang=zh"
            weather_ = (await self.query_url(url))['now']
            weathers.append({'city': _city_,
                             'time': weather_['obsTime'],
                             'temp': weather_['temp'],
                             'feelsLike': weather_['feelsLike'],
                             'wind': [weather_['windDir'],weather_['windScale'],weather_['windSpeed']],
                             'others': {"humidity": weather_['humidity'],
                                        "precip": weather_['precip'],
                                        "pressure": weather_['pressure'],
                                        "vis": weather_['vis']
                                        }
                             }
                            )
        return weathers

    async def weather_7d(self,city):
        weathers_locate = list(await self.get_lon_lat(city))[0]
        lonlat = (await self.get_lon_lat(city))[weathers_locate]
        url = f"https://devapi.qweather.com/v7/weather/7d?key={key}&lang=zh&location={str(lonlat['lon'])+','+str(lonlat['lat'])}"
        _7days = (await self.query_url(url))['daily']
        return {'city': weathers_locate,'7days':_7days}

if __name__ == '__main__':
    text = asyncio.run(QweatherApi().weather_now('beijing'))
    print(text)
