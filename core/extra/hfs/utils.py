import random

CHARACTERS = 'abcdefghijklmnopqrstuvwxyz0123456789'


def generate_random_string(length: int = 8):
    return ''.join(random.choices(CHARACTERS, k=length))
