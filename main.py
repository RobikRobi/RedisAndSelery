import json
import time

import redis
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from celery_worker import generate_report
from utilits import generate_random_code

TTL_SECONDS = 86_400  # 24 часа
BASE_URL = "http://localhost:8000"

app = FastAPI(title="URL Shortener")
r = redis.Redis(
    "localhost",
    port=6379,
    db=0,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)


class ShortenRequest(BaseModel):
    url: str


class ReportRequest(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


@app.post("/shorten")
def shorten_url(body: ShortenRequest):
    long_url = body.url.strip()
    if not long_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL должен начинаться с http:// или https://")

    for _ in range(10):
        short_code = generate_random_code()  # длина 5–8, см. реализацию
        payload = json.dumps({
            "long_url": long_url,
            "short_code": short_code,
            "short_url": f"{BASE_URL}/{short_code}",
            "created_at": time.time(),
            "clicks": 0,
        })
        # nx=True — запись только если ключа нет (старые ссылки не перезаписываем);
        # ex=TTL_SECONDS — ссылка удаляется автоматически через 24 часа
        if r.set(short_code, payload, ex=TTL_SECONDS, nx=True):
            return json.loads(r.get(short_code))
    raise HTTPException(status_code=500, detail="Не удалось сгенерировать уникальный код")


@app.get("/{short_code}")
def redirect_to_url(short_code: str):
    raw = r.get(short_code)
    if raw is None:
        raise HTTPException(status_code=404, detail="Ссылка не найдена или срок её действия истёк")

    data = json.loads(raw)
    data["clicks"] += 1

    # Обновляем JSON со счётчиком, сохраняя оставшийся TTL
    ttl_ms = r.pttl(short_code)
    if ttl_ms > 0:
        r.set(short_code, json.dumps(data), px=ttl_ms)
    else:
        r.set(short_code, json.dumps(data))

    # Накапливаем переходы по дням — это источник данных для отчёта
    r.zincrby(f"clicks:day:{time.strftime('%Y-%m-%d')}", 1, short_code)

    return RedirectResponse(data["long_url"], status_code=307)


@app.get("/stats/{short_code}")
def get_stats(short_code: str):
    raw = r.get(short_code)
    if raw is None:
        raise HTTPException(status_code=404, detail="Ссылка не найдена или срок её действия истёк")

    data = json.loads(raw)
    return {
        "short_code": short_code,
        "clicks": data["clicks"],
        "ttl": r.ttl(short_code),  # секунд до автоматического удаления
    }


@app.post("/reports/daily")
def run_daily_report(body: ReportRequest):
    task = generate_report.delay(body.date)
    return {"task_id": task.id, "status": "started"}


@app.get("/reports/{task_id}")
def get_report(task_id: str):
    result = generate_report.AsyncResult(task_id)
    if result.state == "PENDING":
        raise HTTPException(status_code=404, detail="Задача не найдена или ещё выполняется")
    if result.state == "FAILURE":
        raise HTTPException(status_code=500, detail=str(result.result))
    return result.result
