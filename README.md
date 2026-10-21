# URL Shortener (FastAPI + Redis + Celery)

Сервис сокращения ссылок: хранение в Redis, счётчик переходов, ежедневные отчёты через Celery.

## Запуск

1. Поднять Redis (Docker):

   ```bash
   docker run -d --name redis -p 6379:6379 redis:7
   ```

2. Установить зависимости (uv):

   ```bash
   uv sync
   ```

3. Запустить Celery worker (в отдельном терминале):

   ```bash
   celery -A celery_worker worker --pool=solo --loglevel=info
   ```

4. Запустить API:

   ```bash
   uvicorn main:app --reload --port 8000
   ```

## API

| Метод | Путь | Описание |
|---|---|---|
| POST | `/shorten` | Создать короткую ссылку. Тело: `{"url": "https://google.com"}` |
| GET | `/{short_code}` | Перенаправить на оригинальный URL (307), увеличить счётчик |
| GET | `/stats/{short_code}` | Статистика: `{"short_code", "clicks", "ttl"}` |
| POST | `/reports/daily` | Запустить отчёт. Тело: `{"date": "2026-10-22"}` → `task_id` |
| GET | `/reports/{task_id}` | Получить готовый отчёт из Celery Result Backend |

- Код короткой ссылки — 5–8 случайных символов; при совпадении кодов старая ссылка не перезаписывается (`SET ... NX`).
- Ссылка живёт 24 часа (`SET ... EX 86400`), после чего удаляется автоматически.
- Отчёты сохраняются в `reports/otchet_<дата>.txt`.

## Проверка

С сервисом и worker, запущенными в фоне:

```bash
python test_e2e.py
```
# RedisAndSelery
