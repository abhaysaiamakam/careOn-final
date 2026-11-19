"""
CareOn Background Worker Runner Daemon.
Periodically invokes:
1. Transactional outbox relay worker (every 5 seconds)
2. Inter-agency coordination maintenance and expiry sweep (every 30 seconds)
3. Intelligence and positioning maintenance (every 60 seconds)
4. Offline sync recovery and audit maintenance (every 60 seconds)
"""

import time
import logging
import sys
import signal
from app.database import SessionLocal
from app.realtime.event_publisher import relay_pending_outbox_events
from app.coordination.worker import sweep_coordination_expiries
from app.intelligence.worker import execute_intelligence_maintenance_cycle
from app.sync.recovery_worker import run_sync_recovery_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("careon.worker_daemon")

_shutdown_requested = False


def _signal_handler(signum, frame):
    global _shutdown_requested
    logger.info(f"Shutdown signal ({signum}) received. Finishing active cycle and shutting down gracefully...")
    _shutdown_requested = True


def main():
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    logger.info("CareOn Background Worker Daemon initialized.")
    last_5s = 0.0
    last_30s = 0.0
    last_60s = 0.0

    while not _shutdown_requested:
        now = time.time()
        # 1. Outbox relay (every 5s)
        if now - last_5s >= 5.0:
            last_5s = now
            try:
                db = SessionLocal()
                try:
                    relayed = relay_pending_outbox_events(db, limit=50)
                    if relayed > 0:
                        logger.info(f"Relayed {relayed} pending outbox events.")
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"Error in outbox relay: {e}")

        # 2. Coordination sweep (every 30s)
        if now - last_30s >= 30.0:
            last_30s = now
            try:
                db = SessionLocal()
                try:
                    stats = sweep_coordination_expiries(db)
                    db.commit()
                    if any(v > 0 for v in stats.values()):
                        logger.info(f"Coordination sweep completed: {stats}")
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"Error in coordination sweep: {e}")

        # 3. Intelligence & Sync recovery (every 60s)
        if now - last_60s >= 60.0:
            last_60s = now
            try:
                db = SessionLocal()
                try:
                    intel_stats = execute_intelligence_maintenance_cycle(db)
                    db.commit()
                    logger.debug(f"Intelligence cycle: {intel_stats}")
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"Error in intelligence maintenance: {e}")

            try:
                db = SessionLocal()
                try:
                    sync_stats = run_sync_recovery_cycle(db)
                    db.commit()
                    logger.debug(f"Sync recovery cycle: {sync_stats}")
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"Error in sync recovery cycle: {e}")

        time.sleep(1.0)

if __name__ == "__main__":
    main()
