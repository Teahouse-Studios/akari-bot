from bots.aiocqhttp.info import client_name as cq_client_name
from bots.kook.info import client_name as kook_client_name
from bots.matrix.info import client_name as matrix_client_name
from bots.discord.info import client_name as discord_client_name
from bots.aiogram.info import client_name as aiogram_client_name


def get_all_clients_name():
    return [cq_client_name, kook_client_name, matrix_client_name, discord_client_name, aiogram_client_name, 'TEST']
