"""Canonical persistence-layer errors."""

class PersistenceError(RuntimeError):
    """Base error for durable persistence failures."""


class ConcurrentWriteError(PersistenceError):
    """Raised when optimistic concurrency detects a stale write."""


class DuplicatePersistenceRecordError(PersistenceError):
    """Raised when a durable uniqueness invariant is violated."""
