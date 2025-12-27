# app/modules/orchestrator/dag.py
from typing import List, Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class ResearchTask(BaseModel):
    id: str
    description: str
    dependencies: List[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    
    # 🟢 新增：关联的大纲章节 (用于追踪任务属于哪个部分)
    related_section: Optional[str] = None 

class DAGManager:
    def __init__(self, tasks: List[Dict] = None):
        self.tasks: Dict[str, ResearchTask] = {}
        if tasks:
            self.load_from_state(tasks)

    def load_from_state(self, task_list: List[Dict]):
        for t_data in task_list:
            # Pydantic 会自动处理 extra fields，但最好显式定义
            task = ResearchTask(**t_data)
            self.tasks[task.id] = task

    def to_state(self) -> List[Dict]:
        return [task.model_dump(mode='json') for task in self.tasks.values()]

    def add_task(self, id: str, description: str, dependencies: List[str] = None, related_section: str = None):
        if id in self.tasks:
            if self.tasks[id].status == TaskStatus.PENDING:
                 self.tasks[id].description = description
                 self.tasks[id].dependencies = dependencies or []
                 # 🟢 支持更新关联章节
                 if related_section:
                     self.tasks[id].related_section = related_section
            return
        
        deps = dependencies or []
        # 🟢 传入 related_section
        self.tasks[id] = ResearchTask(
            id=id, 
            description=description, 
            dependencies=deps,
            related_section=related_section
        )

    def get_ready_tasks(self) -> List[ResearchTask]:
        """获取可执行任务"""
        ready_tasks = []
        for task in self.tasks.values():
            if task.status != TaskStatus.PENDING:
                continue
            
            dependencies_met = True
            for dep_id in task.dependencies:
                dep_task = self.tasks.get(dep_id)
                if not dep_task or dep_task.status not in [TaskStatus.COMPLETED]:
                    dependencies_met = False
                    if dep_task and dep_task.status in [TaskStatus.FAILED, TaskStatus.SKIPPED]:
                        self.skip_task(task.id, reason=f"Dependency {dep_id} failed/skipped")
                    break
            
            if dependencies_met:
                ready_tasks.append(task)
        
        return ready_tasks

    def set_task_running(self, task_id: str):
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.RUNNING

    def complete_task(self, task_id: str, result: str):
        if task_id in self.tasks:
            t = self.tasks[task_id]
            t.status = TaskStatus.COMPLETED
            t.result = result
            t.completed_at = datetime.now()

    def fail_task(self, task_id: str, error: str):
        if task_id in self.tasks:
            t = self.tasks[task_id]
            t.status = TaskStatus.FAILED
            t.error = error
            t.completed_at = datetime.now()
            print(f"❌ [DAG] Task {task_id} FAILED: {error}")

    def skip_task(self, task_id: str, reason: str):
        if task_id in self.tasks:
            t = self.tasks[task_id]
            t.status = TaskStatus.SKIPPED
            t.result = f"SKIPPED: {reason}"
            t.completed_at = datetime.now()
            print(f"⏭️ [DAG] Task {task_id} SKIPPED: {reason}")

    def is_all_completed(self) -> bool:
        return all(t.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED] 
                   for t in self.tasks.values())