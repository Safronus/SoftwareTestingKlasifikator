"""Testy single-instance soft-locku (QLockFile nad datovou složkou)."""

from __future__ import annotations

from softwaretestingklasifikator.app import (
    LOCK_FILENAME,
    acquire_lock,
    force_lock,
)


def test_acquire_lock_succeeds_on_fresh_dir(tmp_path):
    lock, holder = acquire_lock(tmp_path)
    try:
        assert holder is None  # nikdo jiný nedrží
        assert (tmp_path / LOCK_FILENAME).exists()
    finally:
        lock.unlock()


def test_second_acquire_is_blocked(tmp_path):
    first, holder1 = acquire_lock(tmp_path)
    try:
        assert holder1 is None
        # Druhá "instance" nad stejnou složkou narazí na držený zámek.
        second, holder2 = acquire_lock(tmp_path)
        assert holder2 is not None
        pid, host, _appname = holder2
        assert isinstance(pid, int) and pid > 0
        assert isinstance(host, str)
        # second zámek se nepodařilo získat — netřeba unlock, ale pro jistotu.
        second.unlock()
    finally:
        first.unlock()


def test_lock_released_allows_reacquire(tmp_path):
    first, _ = acquire_lock(tmp_path)
    first.unlock()
    # Po uvolnění musí jít zamknout znovu (čistý restart instance).
    second, holder = acquire_lock(tmp_path)
    try:
        assert holder is None
    finally:
        second.unlock()


def test_force_lock_takes_over(tmp_path):
    first, _ = acquire_lock(tmp_path)
    try:
        second, holder = acquire_lock(tmp_path)
        assert holder is not None  # blokováno
        # Uživatel zvolil „Přesto otevřít" → force převezme zámek.
        assert force_lock(second, tmp_path) is True
        assert (tmp_path / LOCK_FILENAME).exists()
        second.unlock()
    finally:
        first.unlock()


def test_acquire_lock_creates_missing_data_dir(tmp_path):
    target = tmp_path / "data"  # ještě neexistuje
    assert not target.exists()
    lock, holder = acquire_lock(target)
    try:
        assert holder is None
        assert target.is_dir()
    finally:
        lock.unlock()
