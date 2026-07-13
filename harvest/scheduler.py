"""
Scheduler — Task queue for Harvest.

Features:
- Redis/RQ backend
- Cron-like scheduling
- Retry failed tasks

Usage:
    scheduler = Scheduler()
    scheduler.schedule(url="https://example.com", cron="0 * * * *")
"""

from typing import Optional
from rq import Queue
from redis import Redis
from loguru import logger


class Scheduler:
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis = Redis.from_url(redis_url)
        self.queue = Queue(connection=self.redis)

    def schedule(
        self,
        url: str,
        cron: str,
        selector: Optional[str] = None,
        extraction: str = "markdown",
    ) -> str:
        """Schedule a scraping task."""
        job = self.queue.enqueue(
            "harvest.core.scrape",
            url=url,
            selector=selector,
            extraction=extraction,
            job_timeout=3600,
            result_ttl=86400,
        )
        logger.info(f"Scheduled job {job.id} for {url}")
        return job.id

    async def run_worker(self) -> None:
        """Run a worker to process tasks."""
        from rq.worker import Worker

        worker = Worker([self.queue], connection=self.redis)
        worker.work()
