import json
from datetime import datetime
from pathlib import Path

import redis
from celery import Celery

# Брокер и Result Backend — Redis (логическая БД №1, данные приложения — в №0)
celery_app = Celery(
    "url_shortener",
    broker="redis://localhost:6379/1",
    backend="redis://localhost:6379/1",
)

r = redis.Redis(
    "localhost",
    port=6379,
    db=0,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)

REPORTS_DIR = Path(__file__).parent / "reports"


@celery_app.task(bind=True)
def generate_report(self, date: str):
    # 1. Получаем статистику переходов из Redis (накопленную по дням)
    key = f"clicks:day:{date}"

    # 2. Топ-10 самых популярных ссылок за выбранный день
    top = r.zrevrange(key, 0, 9, withscores=True)
    top_links = []
    for short_code, score in top:
        raw = r.get(short_code)
        long_url = json.loads(raw)["long_url"] if raw else None
        top_links.append({
            "short_code": short_code,
            "url": long_url,
            "clicks": int(score),
        })

    # 3. Суммарное количество переходов за день
    total_clicks = sum(
        int(score) for _, score in r.zrange(key, 0, -1, withscores=True)
    )

    data = {
        "date": date,
        "total_clicks": total_clicks,
        "top_links": top_links,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    # 4. Формируем txt-отчёт
    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / f"otchet_{date}.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2))

    # 5. Возвращаем результат через Celery Result Backend
    return {"report_file": str(report_path), **data}
