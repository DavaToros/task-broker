import asyncio
import json
from datetime import datetime
from arq.connections import RedisSettings
from sqlalchemy import select
import redis.asyncio as aioredis

from app.config import settings
from app.database import async_session_maker
from app.models import Task, TaskStatus

async def run_heavy_task(ctx, task_id: str, client_id: str, duration: int):
    redis_conn = aioredis.from_url(
        f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}", decode_responses=True
    )

    # Меняем статус на PROCESSING
    async with async_session_maker() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task:
            task.status = TaskStatus.PROCESSING
            await session.commit()

    # Пушим уведомление о старте клиенту
    await redis_conn.publish(
        "task_updates",
        json.dumps({"client_id": client_id, "task_id": task_id, "status": "processing", "progress": 10})
    )

    # Имитация полезной вычислительной нагрузки
    await asyncio.sleep(duration)

    # Завершаем задачу, пишем результат в БД
    async with async_session_maker() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task:
            task.status = TaskStatus.COMPLETED
            task.result = f"Task completed successfully in {duration} seconds"
            task.updated_at = datetime.utcnow()
            await session.commit()

    # Пушим финальное уведомление клиенту
    await redis_conn.publish(
        "task_updates",
        json.dumps({
            "client_id": client_id,
            "task_id": task_id,
            "status": "completed",
            "result": f"Task completed in {duration}s"
        })
    )
    await redis_conn.aclose()

class WorkerSettings:
    functions = [run_heavy_task]
    redis_settings = RedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT)