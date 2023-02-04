from .message import *
from core.elements.message import FetchTarget


class Bot:
    MessageSession = MessageSession
    FetchTarget = FetchTarget


__all__ = ['Bot']
