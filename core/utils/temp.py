class TempCounter:
    value = 0

    @classmethod
    def add(cls):
        cls.value += 1
        return cls.value
