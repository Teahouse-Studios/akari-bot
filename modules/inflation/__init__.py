from math import isnan
import os
import pandas as pd

from core.builtins import Bot
from core.component import module

cpi = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'consumer_price_index.csv'))

i = module('inflation',
           developers=['Dianliang233'], desc='{inflation.help.desc}', )


@i.command('<price> <country_or_region_name_or_alpha_3_code> <from_year> [<to_year>] {{inflation.help.adjust}}', )
async def _(msg: Bot.MessageSession, price: float, country_or_region_name_or_alpha_3_code: str, from_year: str, to_year: int = 2022):
    row = cpi[cpi['Country Name'] == country_or_region_name_or_alpha_3_code]

    if row.empty:
        row = cpi[cpi['Country Code'] == country_or_region_name_or_alpha_3_code.upper()]
    if row.empty:
        await msg.finish(msg.locale.t('inflation.message.country_not_found'))

    try:
        from_cpi = row[f'{from_year}'].values[0]
    except KeyError:
        await msg.finish(msg.locale.t('inflation.message.from_year_not_found'))
    if isnan(from_cpi):
        await msg.finish(msg.locale.t('inflation.message.from_year_no_data'))

    try:
        to_cpi = row[f'{to_year}'].values[0]
    except KeyError:
        await msg.finish(msg.locale.t('inflation.message.to_year_not_found'))
    if isnan(to_cpi):
        await msg.finish(msg.locale.t('inflation.message.to_year_no_data'))

    res = price / from_cpi * to_cpi
    country_or_region_name = row['Country Name'].values[0]

    await msg.finish(msg.locale.t('inflation.message.result', result=f'{res:.4f}', country_or_region_name=country_or_region_name, from_year=from_year, to_year=to_year, price=f'{price:.4f}'))
