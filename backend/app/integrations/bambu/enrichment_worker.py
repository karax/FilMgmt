"""One-thread bounded retry queue for blocking FTPS enrichment."""

from dataclasses import dataclass, field
import heapq
import logging
from threading import Condition, Thread
import time

from app.integrations.bambu.enrichment import BambuPrintJobEnrichmentService


logger = logging.getLogger(__name__)


@dataclass(order=True)
class _QueuedJob:
    due_at: float
    sequence: int
    print_job_id: int = field(compare=False)
    force: bool = field(compare=False, default=False)


class BambuEnrichmentWorker:
    def __init__(
        self,
        service: BambuPrintJobEnrichmentService,
        *,
        retry_delays_seconds: tuple[float, ...] = (30.0, 300.0),
    ) -> None:
        self._service = service
        self._retry_delays = retry_delays_seconds
        self._condition = Condition()
        self._queue: list[_QueuedJob] = []
        self._scheduled_ids: set[int] = set()
        self._active_id: int | None = None
        self._sequence = 0
        self._stopping = False
        self._thread: Thread | None = None

    def start(self) -> None:
        with self._condition:
            if self._thread is not None:
                return
            self._stopping = False
            self._thread = Thread(target=self._run, name="bambu-ftps-enrichment", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._condition:
            self._stopping = True
            self._condition.notify_all()
            thread = self._thread
        if thread is not None:
            thread.join(timeout=15)
        with self._condition:
            self._thread = None
            self._queue.clear()
            self._scheduled_ids.clear()
            self._active_id = None

    def schedule(self, print_job_id: int, *, force: bool = False) -> bool:
        if print_job_id <= 0:
            return False
        with self._condition:
            if self._stopping or print_job_id in self._scheduled_ids or print_job_id == self._active_id:
                return False
            self._enqueue_locked(print_job_id, force=force, delay=0)
            return True

    def _enqueue_locked(self, print_job_id: int, *, force: bool, delay: float) -> None:
        self._sequence += 1
        self._scheduled_ids.add(print_job_id)
        heapq.heappush(
            self._queue,
            _QueuedJob(time.monotonic() + delay, self._sequence, print_job_id, force),
        )
        self._condition.notify_all()

    def _run(self) -> None:
        while True:
            with self._condition:
                while not self._stopping and not self._queue:
                    self._condition.wait()
                if self._stopping:
                    return
                queued = self._queue[0]
                delay = queued.due_at - time.monotonic()
                if delay > 0:
                    self._condition.wait(timeout=delay)
                    continue
                heapq.heappop(self._queue)
                self._scheduled_ids.discard(queued.print_job_id)
                self._active_id = queued.print_job_id
            outcome = None
            try:
                outcome = self._service.enrich(queued.print_job_id, force=queued.force)
            except Exception as error:
                logger.error(
                    "Bambu enrichment worker failed print_job_id=%s error_type=%s",
                    queued.print_job_id,
                    type(error).__name__,
                )
            with self._condition:
                self._active_id = None
                if (
                    not self._stopping
                    and outcome is not None
                    and outcome.retryable
                    and outcome.attempts <= len(self._retry_delays)
                ):
                    delay = self._retry_delays[outcome.attempts - 1]
                    self._enqueue_locked(queued.print_job_id, force=False, delay=delay)
