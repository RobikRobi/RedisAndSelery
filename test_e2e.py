"""Сквозной тест сервиса: сокращение, редирект, статистика, отчёт."""
import json
import time
import urllib.request
import urllib.error

BASE = "http://localhost:8000"


def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def redirect(method, path):
    """Запрос без follow-redirect, чтобы увидеть 307."""
    req = urllib.request.Request(BASE + path, method=method)
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(req) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


# 1. Создание коротких ссылок
s1, link1 = api("POST", "/shorten", {"url": "https://google.com"})
assert s1 == 200, (s1, link1)
code1 = link1["short_code"]
assert 5 <= len(code1) <= 8, code1
print("POST /shorten ->", link1)

s2, link2 = api("POST", "/shorten", {"url": "https://github.com"})
assert s2 == 200, (s2, link2)
code2 = link2["short_code"]

# 2. Переходы по ссылкам
import redis
redis.Redis("localhost", 6379, db=0, decode_responses=True).delete(
    f"clicks:day:{time.strftime('%Y-%m-%d')}"
)
for _ in range(3):
    st, hdr = redirect("GET", f"/{code1}")
    assert st == 307 and hdr.get("location") == "https://google.com", (st, hdr)
for _ in range(7):
    st, hdr = redirect("GET", f"/{code2}")
    assert st == 307 and hdr.get("location") == "https://github.com", (st, hdr)
print("GET /{code} -> 307 редирект на оригинальный URL: OK")

# 3. Несуществующий код -> 404
st, _ = redirect("GET", "/noSuch1")
assert st == 404, st
st, _ = api("GET", "/stats/noSuch1")
assert st == 404, st
print("404 для несуществующих кодов: OK")

# 4. Статистика
st, stats = api("GET", f"/stats/{code1}")
assert st == 200, (st, stats)
assert stats["short_code"] == code1 and stats["clicks"] == 3, stats
assert 0 < stats["ttl"] <= 86400, stats
print("GET /stats ->", stats)

# 5. Отчёт через Celery
today = time.strftime("%Y-%m-%d")
st, started = api("POST", "/reports/daily", {"date": today})
assert st == 200 and started.get("task_id"), (st, started)
task_id = started["task_id"]
print("POST /reports/daily ->", started)

result = None
for _ in range(30):
    st, result = api("GET", f"/reports/{task_id}")
    if st == 200:
        break
    time.sleep(1)
assert st == 200, (st, result)
assert result["total_clicks"] == 10, result
assert len(result["top_links"]) == 2, result
assert result["top_links"][0]["short_code"] == code2, result
print("GET /reports/{task_id} ->", json.dumps(result, ensure_ascii=False, indent=2))

print("\nВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")
