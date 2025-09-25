import datetime


class MinuteTempCounter:
    value = 0
    value_before = 0
    ts = datetime.datetime.now().timestamp()

    @classmethod
    def add(cls):
        now = datetime.datetime.now().timestamp()
        if now > cls.ts + 60:
            cls.value_before = cls.value
            cls.value = 0
        cls.value += 1
        return cls.value
