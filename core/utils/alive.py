from datetime import datetime


class Alive:
    values = {}

    @classmethod
    def refresh_alive(cls, client_name: str):
        cls.values[client_name] = datetime.now()

    @classmethod
    def get_alive(cls):
        _v = cls.values.copy()
        for k, v in _v.items():
            if (datetime.now() - v).total_seconds() > 120:
                del _v[k]
        return _v
