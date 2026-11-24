import os
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# DB location comes from the environment (set in card-api.env), so the database
# lives outside the code folder and never touches other SQL servers on the VPS.
DB_PATH = os.environ.get("CARDS_DB_PATH", str(Path(__file__).with_name("cards.db")))
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="Card Counter API")


def get_shift(dt: datetime) -> int:
    """Shift 1: 08:00-17:00 | Shift 2: 17:00-24:00 | Shift 3: 00:00-08:00"""
    h = dt.hour
    if 8 <= h < 17:
        return "A"
    if 17 <= h <= 23:
        return "B"
    return "C"



def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")      # fast concurrent writes
    conn.execute("PRAGMA synchronous=NORMAL")    # fast, still safe
    return conn


conn = get_conn()
conn.executescript(Path(__file__).with_name("schema.sql").read_text())
conn.commit()


class CardData(BaseModel):
    count: int
    shift: Optional[int] = None          # na bheje to server khud nikaal lega
    date_time: Optional[str] = None      # 'YYYY-MM-DD HH:MM:SS', na bheje to abhi ka time


lock = threading.Lock()   # ek saath do request aayein to database safe rahe
FMT = "%Y-%m-%d %H:%M:%S"


def parse_dt(s: str) -> datetime:
    """URL ke liye kai formats chalte hain (space ki jagah _ ya T bhi)."""
    s = s.strip().replace("_", " ").replace("T", " ")
    for f in (FMT, "%Y-%m-%d %H:%M", "%Y%m%d%H%M%S", "%Y%m%d%H%M"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            pass
    raise HTTPException(400, "date_time ka format galat hai. Use: 2026-11-17_15:14:00")


def save_card(count: int, shift: Optional[int], dt: Optional[datetime]) -> dict:
    t0 = time.perf_counter()
    now = dt or datetime.now()
    shift = shift or get_shift(now)

    stamp = now.strftime(FMT)
    with lock:
        conn.execute(
            "INSERT INTO card_counts (count, shift, date_time) VALUES (?, ?, ?)",
            (count, shift, stamp),
        )
        conn.commit()
    return {
        "ok": True,
        "count": count,
        "shift": shift,
        "date_time": stamp,
        "response_time": datetime.now().strftime(FMT),                    # server time when reply was made
        "process_time_ms": round((time.perf_counter() - t0) * 1000, 2),  # server processing time
    }


@app.post("/api/card")
def post_card(d: CardData):
    return save_card(d.count, d.shift, parse_dt(d.date_time) if d.date_time else None)


@app.api_route("/api/card/{count}/{shift}/{date_time}", methods=["GET", "POST"])
def add_card_by_url(count: int, shift: str, date_time: str):
    """
    URL se data: /api/card/25/1/2026-11-17_15:14:00
      shift     : 1, 2, 3  (ya 0 / auto = server time se khud nikaal le)
      date_time : YYYY-MM-DD_HH:MM:SS  (ya now = abhi ka time)
    """
    s = None if shift.lower() in ("0", "auto") else (int(shift) if shift.isdigit() else -1)
    dt = None if date_time.lower() == "now" else parse_dt(date_time)
    return save_card(count, s, dt)


@app.get("/api/card")
def list_cards(limit: int = 100, shift: Optional[int] = None):
    q = "SELECT id, count, shift, date_time FROM card_counts"
    args = []
    if shift:
        q += " WHERE shift = ?"
        args.append(shift)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    rows = conn.execute(q, args).fetchall()
    return [dict(zip(("id", "count", "shift", "date_time"), r)) for r in rows]


@app.get("/api/card/summary")
def summary(date: Optional[str] = None):
    date = date or datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT shift, SUM(count) FROM card_counts WHERE date(date_time) = ? GROUP BY shift",
        (date,),
    ).fetchall()
    return {"date": date, "shifts": {f"shift_{s}": t for s, t in rows}}
