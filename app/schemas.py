from datetime import datetime
from pydantic import BaseModel, Field
from app.models import TaskStatus

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    work_duration: int = Field(default=5, ge=1, le=60, description="Имитация тяжелой работы (в секундах)")

class TaskResponse(BaseModel):
    id: str
    title: str
    status: TaskStatus
    result: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TaskAcceptedResponse(BaseModel):
    task_id: str
    status: TaskStatus
    message: str