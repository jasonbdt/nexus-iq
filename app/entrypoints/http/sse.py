"""Public SSE formatting and cancellation-safe stream entrypoints."""
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from anyio import CancelScope
from .dependencies import CurrentUser, ServicesDep

router = APIRouter()
HEADERS = {'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}


def parse_pubsub_message(
    raw_data: bytes | str | dict
) -> tuple[str, dict | str]:
    """
    Parse published messages from a subscribed redis channel.

    Args:
        raw_data (bytes|str|dict): Raw message data sent by Redis.

    Returns:
        tuple[str, dict|str]: A tuple with an event name and data payload.
    """
    if isinstance(raw_data, bytes):
        raw_data = raw_data.decode("utf8")

    if isinstance(raw_data, dict):
        obj = raw_data
    elif isinstance(raw_data, str):
        try:
            obj = json.loads(raw_data)
        except json.JSONDecodeError:
            return "update", raw_data
    else:
        return "update", str(raw_data)

    if not isinstance(obj, dict):
        return "update", obj

    event = obj.get("event") or "update"

    if "payload" in obj:
        payload = obj["payload"]
    else:
        payload = {k: v for k, v in obj.items() if k != "event"}

    return event, payload


def build_sse(
    data: dict | str | bytes,
    event: str | None = None,
    event_id: str | None = None,
    retry: int | None = None
) -> str:
    """
    Prebuild the event message for server-sent events.

    Args:
        data (dict|str|bytes): Data field for the event message.
        event (str|None): Describes the type of event.
        event_id (str|None): (Optional) Last event id.
        retry (int|None): (Optional) Reconnection time in milliseconds.

    Returns:
        str: The prebuilt message as a string to send as a server event.
    """
    if isinstance(data, bytes):
        data = data.decode('utf8').replace("'", '"')
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    lines = []
    if event:
        lines.append(f"event: {event}")

    if event_id:
        lines.append(f"id: {event_id}")

    if retry is not None:
        lines.append(f"retry: {retry}")

    lines.append(f"data: {payload}")

    return "\n".join(lines) + "\n\n"


async def token_events(iterator):
    """Close the underlying SDK iterator on disconnect and emit DONE only on success."""
    sentinel = object()
    try:
        while True:
            delta = await run_in_threadpool(next, iterator, sentinel)
            if delta is sentinel:
                break
            yield f"data: {json.dumps({'delta': delta})}\n\n"
        yield 'data: [DONE]\n\n'
    finally:
        close = getattr(iterator, 'close', None)
        if close:
            with CancelScope(shield=True):
                await run_in_threadpool(close)


@router.get('/subscribe/{puuid}', tags=['Summoners'])
async def subscribe(puuid: str, request: Request, services: ServicesDep):
    """Forward the existing named Redis update events and keepalives."""
    async def generate():
        channel = f'nexus_iq:summoner_profile:{puuid}'
        yield build_sse({'status': 'connected', 'channel': channel}, event='connected')
        source = services.updates.subscribe(puuid)
        try:
            async for message in source:
                if await request.is_disconnected():
                    break
                if message is None:
                    yield ': keepalive\n\n'
                else:
                    event, payload = parse_pubsub_message(message)
                    yield build_sse(payload, event=event)
        finally:
            await source.aclose()
    return StreamingResponse(generate(), media_type='text/event-stream',
                             headers={**HEADERS, 'Connection': 'keep-alive'})


@router.post('/query/stream', tags=['RAG'])
async def query_stream(question: str, services: ServicesDep, top_k: int = 5):
    """Stream stateless retrieval deltas with the existing sentinel."""
    context = await services.retrieval.context(question, top_k)
    iterator = services.retrieval.ai.stream(question, context, [])
    return StreamingResponse(token_events(iterator), media_type='text/event-stream', headers=HEADERS)


@router.post('/coach/sessions/{session_id}/chat', tags=['Coach'])
async def chat(session_id: int, question: str, user: CurrentUser, services: ServicesDep):
    """Stream a question after its first transaction has completed."""
    iterator = await services.coaching.chat(session_id, user.id, question)
    return StreamingResponse(token_events(iterator), media_type='text/event-stream', headers=HEADERS)
