# Earthing System — earthing system design to IEEE 80, IEC 60364, IEC 62305 and IEEE 142.
# Copyright (C) 2026 Emad Roshandel
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <https://www.gnu.org/licenses/>.

"""
Independent numerical solutions on several processor cores (1.8.4).

The studies of the numerical page solve many models that do not depend on
each other — the seasonal cases, the soil-uncertainty samples, the
candidate grids of one optimisation round.  On the desktop and in the local
browser application they are spread over a pool of worker processes; in the
in-browser (Pyodide) build, which has one thread, and whenever a pool cannot
be started, they run one after another with identical results.

The number of workers is the number of cores less one (at most 8), and can
be set with the environment variable ES_WORKERS (1 turns the pool off).
Each worker runs its linear algebra on one thread, so the pool does not
oversubscribe the cores.
"""

from __future__ import annotations

import atexit
import os
import sys
import threading

_POOL = None
_POOL_N = 0
_LOCK = threading.Lock()
_BLAS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")


def max_workers() -> int:
    if sys.platform == "emscripten":                  # Pyodide: one thread
        return 1
    env = os.environ.get("ES_WORKERS")
    if env:
        try:
            return max(1, int(env))
        except ValueError:
            return 1
    c = os.cpu_count() or 1
    return max(1, min(8, c - 1 if c > 2 else c))


def _pool(n: int):
    global _POOL, _POOL_N
    with _LOCK:
        if _POOL is not None and _POOL_N >= n:
            return _POOL
        if _POOL is not None:
            _POOL.shutdown(wait=False, cancel_futures=True)
        from concurrent.futures import ProcessPoolExecutor
        import multiprocessing as mp
        saved = {k: os.environ.get(k) for k in _BLAS}
        for k in _BLAS:
            os.environ[k] = "1"                       # inherited by the workers
        try:
            _POOL = ProcessPoolExecutor(max_workers=n, mp_context=mp.get_context("spawn"))
            _POOL_N = n
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        return _POOL


def _shutdown():
    global _POOL
    if _POOL is not None:
        _POOL.shutdown(wait=False, cancel_futures=True)
        _POOL = None


atexit.register(_shutdown)


def pmap(fn, items, min_items: int = 2) -> list:
    """[fn(x) for x in items], on worker processes when that helps.

    `fn` must be a module-level function and `items` picklable.  Any failure
    of the pool itself (not of `fn`) falls back to running in this process.
    """
    global _POOL
    items = list(items)
    n = min(max_workers(), len(items))
    if n <= 1 or len(items) < min_items:
        return [fn(x) for x in items]
    try:
        ex = _pool(n)
        futs = [ex.submit(fn, x) for x in items]
    except Exception:                                  # pool could not start
        return [fn(x) for x in items]
    out = []
    try:
        for f in futs:
            out.append(f.result())
    except Exception as e:
        from concurrent.futures.process import BrokenProcessPool
        if isinstance(e, BrokenProcessPool):
            _POOL = None
            return [fn(x) for x in items]
        raise
    return out
