import uuid
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from arq import create_pool
from arq.connections import RedisSettings

from app.config import settings
from app.database import engine, Base, get_db
from app.models import Task, TaskStatus
from app.schemas import TaskCreate, TaskResponse, TaskAcceptedResponse
from app.websocket_manager import ws_manager, redis_pubsub_listener

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Автоматически создаем таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Подключаем пул задач Arq
    app.state.arq_redis = await create_pool(
        RedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
    )

    # Запускаем фоновый слушатель Redis Pub/Sub
    listener_task = asyncio.create_task(redis_pubsub_listener())

    yield

    listener_task.cancel()
    await app.state.arq_redis.close()
    await engine.dispose()

app = FastAPI(
    title="Real-Time Notification & Task Broker",
    version="1.0.0",
    lifespan=lifespan,
)

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await ws_manager.connect(client_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)

@app.post(
    "/tasks/{client_id}",
    response_model=TaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_task(
    client_id: str,
    payload: TaskCreate,
    db: AsyncSession = Depends(get_db),
):
    task_id = str(uuid.uuid4())
    
    # 1. Записываем задачу в PostgreSQL
    new_task = Task(id=task_id, title=payload.title, status=TaskStatus.PENDING)
    db.add(new_task)
    await db.commit()

    # 2. Отправляем в очередь воркеров
    await app.state.arq_redis.enqueue_job(
        "run_heavy_task", task_id, client_id, payload.work_duration
    )

    return TaskAcceptedResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        message="Задача поставлена в очередь на выполнение",
    )

@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task