"""FastAPI server: exposes run_agent() over HTTP with SSE log streaming."""
import asyncio
import json
import tempfile
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel

app = FastAPI(title="Testing Autonomy")

_UI_PATH = Path(__file__).parent / "ui.html"


class GenerateRequest(BaseModel):
    url: str
    journey: str
    max_steps: int = 12


@app.get("/")
async def serve_ui() -> HTMLResponse:
    return HTMLResponse(_UI_PATH.read_text(encoding="utf-8"))


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/generate")
async def api_generate(req: GenerateRequest) -> StreamingResponse:
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()

    def _put(item) -> None:
        loop.call_soon_threadsafe(q.put_nowait, item)

    def _log_sink(message) -> None:
        r = message.record
        _put({"type": "log", "level": r["level"].name, "msg": r["message"]})

    sink_id = logger.add(_log_sink, format="{message}")

    def _worker() -> None:
        from testing_autonomy.agent import run_agent  # lazy import

        try:
            tmp = tempfile.mkdtemp(prefix="ta_")
            outcome = run_agent(
                url=req.url,
                journey=req.journey,
                output_dir=Path(tmp),
                max_exploration_steps=req.max_steps,
            )
            if outcome.test_code.strip():
                _put({"type": "emit", "code": outcome.test_code})
            _put({
                "type": "done",
                "success": outcome.success,
                "summary": outcome.summary,
            })
        except Exception as exc:
            _put({"type": "done", "success": False, "summary": f"Agent error: {exc}"})
        finally:
            logger.remove(sink_id)
            _put(None)  # sentinel — signals end of stream

    threading.Thread(target=_worker, daemon=True).start()

    async def _event_stream():
        # Flush response headers immediately so the browser starts receiving
        yield ": connected\n\n"
        while True:
            item = await q.get()
            if item is None:
                return
            yield f"event: {item['type']}\ndata: {json.dumps(item)}\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
