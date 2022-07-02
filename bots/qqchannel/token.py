import qqbot

from config import Config

token = qqbot.Token(Config('qqchannel_appid'), Config('qqchannel_token'))
