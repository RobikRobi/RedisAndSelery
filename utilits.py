import random
import secrets
import string


def generate_random_code(min_length=5, max_length=8):
    """Генерирует случайный код из 5–8 символов (латиница + цифры)."""
    alphabet = string.ascii_letters + string.digits  # 62 символа
    length = random.randint(min_length, max_length)
    return "".join(secrets.choice(alphabet) for _ in range(length))
