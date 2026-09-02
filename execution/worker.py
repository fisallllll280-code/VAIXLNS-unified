"""
Worker System
Task execution within capability envelopes
"""
from typing import Callable, Dict, Any, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, Future
from enum import Enum
import uuid


class WorkerStatus(str, Enum):
    """Worker status"""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class Job:
    """Unit of work"""
    job_id: str
    task_type: str
    capability: str
    payload: Dict[str, Any]
    worker_id: str = ""
    status: WorkerStatus = WorkerStatus.IDLE
    result: Any = None
    error: Optional[str] = None


class Worker:
    """
    Executes jobs within a specific capability.
    
    A Worker:
    - Owns a specific capability
    - Executes one job at a time
    - Records all work
    - Does not have sovereign authority
    - Cannot exceed its capability envelope
    """
    
    def __init__(self, worker_id: str, capability: str, handler: Callable):
        self.worker_id = worker_id
        self.capability = capability
        self.handler = handler
        self.status = WorkerStatus.IDLE
        self.current_job: Optional[Job] = None
        self.job_history: list[Job] = []
    
    def execute(self, job: Job) -> Any:
        """
        Execute a job.
        Verifies job matches capability.
        """
        if job.capability != self.capability:
            raise ValueError(
                f"Job capability {job.capability} "
                f"does not match worker capability {self.capability}"
            )
        
        job.worker_id = self.worker_id
        job.status = WorkerStatus.RUNNING
        self.current_job = job
        self.status = WorkerStatus.RUNNING
        
        try:
            result = self.handler(job.payload)
            job.result = result
            job.status = WorkerStatus.SUCCESS
            self.status = WorkerStatus.SUCCESS
            return result
        
        except Exception as e:
            job.error = str(e)
            job.status = WorkerStatus.FAILED
            self.status = WorkerStatus.FAILED
            raise
        
        finally:
            self.job_history.append(job)
            self.current_job = None
            self.status = WorkerStatus.IDLE
    
    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics"""
        successful = sum(
            1 for j in self.job_history if j.status == WorkerStatus.SUCCESS
        )
        failed = sum(
            1 for j in self.job_history if j.status == WorkerStatus.FAILED
        )
        
        return {
            "worker_id": self.worker_id,
            "capability": self.capability,
            "status": self.status.value,
            "total_jobs": len(self.job_history),
            "successful_jobs": successful,
            "failed_jobs": failed,
        }


class WorkerPool:
    """
    Manages multiple workers.
    Routes jobs to appropriate workers based on capability.
    """
    
    def __init__(self, max_workers: int = 8):
        self.workers: Dict[str, Worker] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.job_queue: list[Job] = []
    
    def register_worker(
        self,
        capability: str,
        handler: Callable,
    ) -> Worker:
        """Register a new worker"""
        worker_id = str(uuid.uuid4())
        worker = Worker(worker_id, capability, handler)
        self.workers[capability] = worker
        return worker
    
    def submit_job(self, job: Job) -> Future:
        """
        Submit job to appropriate worker.
        Returns a Future for async execution.
        """
        worker = self.workers.get(job.capability)
        if not worker:
            raise ValueError(f"No worker for capability: {job.capability}")
        
        # Submit to thread pool
        future = self.executor.submit(worker.execute, job)
        return future
    
    def get_worker(self, capability: str) -> Optional[Worker]:
        """Get worker by capability"""
        return self.workers.get(capability)
    
    def shutdown(self) -> None:
        """Shutdown worker pool"""
        self.executor.shutdown(wait=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        return {
            "total_workers": len(self.workers),
            "workers": {
                cap: worker.get_stats()
                for cap, worker in self.workers.items()
            },
        }
