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
    SKIPPED = "skipped" # 🟢 新增：跳过状态

class ResearchTask(BaseModel):
    id: str
    description: str
    dependencies: List[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None # 🟢 新增：错误信息
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    retry_count: int = 0 # 🟢 新增：重试计数（预留给 Graph 用）

class DAGManager:
    def __init__(self, tasks: List[Dict] = None):
        self.tasks: Dict[str, ResearchTask] = {}
        if tasks:
            self.load_from_state(tasks)

    def load_from_state(self, task_list: List[Dict]):
        for t_data in task_list:
            task = ResearchTask(**t_data)
            self.tasks[task.id] = task

    def to_state(self) -> List[Dict]:
        return [task.model_dump(mode='json') for task in self.tasks.values()]

    def add_task(self, id: str, description: str, dependencies: List[str] = None):
        if id in self.tasks:
            # 允许更新已存在的任务（只要不是运行中）
            if self.tasks[id].status == TaskStatus.PENDING:
                 self.tasks[id].description = description
                 self.tasks[id].dependencies = dependencies or []
            return
        
        deps = dependencies or []
        self.tasks[id] = ResearchTask(id=id, description=description, dependencies=deps)

    def get_ready_tasks(self) -> List[ResearchTask]:
        """获取可执行任务"""
        ready_tasks = []
        for task in self.tasks.values():
            if task.status != TaskStatus.PENDING:
                continue
            
            dependencies_met = True
            for dep_id in task.dependencies:
                dep_task = self.tasks.get(dep_id)
                # 🟢 逻辑增强：如果依赖的任务失败或跳过，当前任务也不能执行
                if not dep_task or dep_task.status not in [TaskStatus.COMPLETED]:
                    dependencies_met = False
                    
                    # 🛡️ 熔断传导：如果依赖挂了，自己也设为跳过
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
        """🟢 标记任务失败"""
        if task_id in self.tasks:
            t = self.tasks[task_id]
            t.status = TaskStatus.FAILED
            t.error = error
            t.completed_at = datetime.now()
            print(f"❌ [DAG] Task {task_id} FAILED: {error}")

    def skip_task(self, task_id: str, reason: str):
        """🟢 标记任务跳过"""
        if task_id in self.tasks:
            t = self.tasks[task_id]
            t.status = TaskStatus.SKIPPED
            t.result = f"SKIPPED: {reason}"
            t.completed_at = datetime.now()
            print(f"⏭️ [DAG] Task {task_id} SKIPPED: {reason}")

    def is_all_completed(self) -> bool:
        """检查是否所有任务都已处理（完成、失败或跳过都算结束）"""
        return all(t.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED] 
                   for t in self.tasks.values())