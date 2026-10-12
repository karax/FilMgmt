from threading import Event, Lock

from app.integrations.bambu.enrichment import EnrichmentOutcome
from app.integrations.bambu.enrichment_worker import BambuEnrichmentWorker
from app.models import PrintJobEnrichmentStatus


def test_worker_serializes_deduplicates_and_bounds_retries() -> None:
    completed = Event()

    class FakeService:
        def __init__(self) -> None:
            self.calls: list[tuple[int, bool]] = []
            self.lock = Lock()

        def enrich(self, print_job_id: int, *, force: bool = False) -> EnrichmentOutcome:
            with self.lock:
                self.calls.append((print_job_id, force))
                attempt = len(self.calls)
            if attempt == 3:
                completed.set()
            return EnrichmentOutcome(
                PrintJobEnrichmentStatus.RETRYABLE,
                attempts=attempt,
                retryable=True,
            )

    service = FakeService()
    worker = BambuEnrichmentWorker(service, retry_delays_seconds=(0.01, 0.01))
    assert worker.schedule(42) is True
    assert worker.schedule(42) is False
    worker.start()
    try:
        assert completed.wait(timeout=2)
    finally:
        worker.stop()

    assert service.calls == [(42, False), (42, False), (42, False)]
