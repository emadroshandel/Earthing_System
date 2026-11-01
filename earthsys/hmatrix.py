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
Compressed (hierarchical) matrices and an iterative solver (version 1.8.7).

The boundary-element matrix of a large earthing grid is dense: every segment
raises the potential of every other.  Stored and factorised as it is, it
costs n² memory and n³ time, which is what limited the numerical solution to
a few thousand segments.  But the coupling between two groups of segments
that are far apart compared with their size is smooth, and such a block of
the matrix is very nearly of low rank: a few products of a column and a row
reproduce it to any stated accuracy.

* cluster tree    the segments are split in two along the longest side of
                  their bounding box, recursively, down to a few dozen per
                  leaf; each cluster is a contiguous range of a permutation
* blocks          a pair of clusters is "admissible" when the horizontal gap
                  between their boxes exceeds the smaller of their diameters
                  (divided by eta) and the near-field reach of the
                  quadrature; it is
                  then compressed, otherwise split or, at the leaves, stored
                  in full
* ACA             adaptive cross approximation with partial pivoting
                  (Bebendorf 2000): one row and one column of the block at
                  a time, stopped when the next cross is below `tol` times
                  the Frobenius norm of the approximation so far, so only
                  O(k (m + n)) entries of a block are ever evaluated
* GMRES           restarted GMRES (Saad and Schultz 1986) with a
                  block-Jacobi preconditioner built from the dense diagonal
                  blocks of the clusters of up to `pc_size` segments

Horizontal gaps are used for admissibility because every image of the
Green's function — air image, layer images, the mirror image of a vertical
boundary as far as the clusters do not straddle it — lies at the horizontal
position of its source or further away, so a horizontal gap bounds the
distance to every singularity.  numpy only (the browser build has no scipy).
"""

from __future__ import annotations

import math

try:
    import numpy as np
except ImportError:                                    # pragma: no cover
    np = None


class Cluster:
    __slots__ = ("start", "stop", "lo", "hi", "diam", "children", "level")

    def __init__(self, start, stop, lo, hi, level):
        self.start = int(start)
        self.stop = int(stop)
        self.lo = lo
        self.hi = hi
        self.diam = float(np.linalg.norm(hi - lo))
        self.children = None
        self.level = level

    @property
    def size(self):
        return self.stop - self.start


def cluster_tree(centres, lo, hi, leaf: int = 48):
    """Binary cluster tree.  centres (n, 3) split the clusters; lo, hi (n, 3)
    are the corners of each item's own box (a segment's two ends).  Returns
    (root, perm): cluster ranges index into perm."""
    n = len(centres)
    perm = np.arange(n)
    root = Cluster(0, n, lo.min(axis=0), hi.max(axis=0), 0)
    stack = [root]
    while stack:
        c = stack.pop()
        if c.size <= leaf:
            continue
        idx = perm[c.start:c.stop]
        ext = centres[idx].max(axis=0) - centres[idx].min(axis=0)
        ax = int(np.argmax(ext))
        if ext[ax] <= 0.0:
            continue                       # coincident centres: keep as a leaf
        order = np.argsort(centres[idx, ax], kind="stable")
        perm[c.start:c.stop] = idx[order]
        mid = c.start + c.size // 2
        kids = []
        for a, b in ((c.start, mid), (mid, c.stop)):
            sub = perm[a:b]
            kids.append(Cluster(a, b, lo[sub].min(axis=0), hi[sub].max(axis=0), c.level + 1))
        c.children = kids
        stack.extend(kids)
    return root, perm


def _gap_h(a: Cluster, b: Cluster) -> float:
    """Horizontal (x, y) distance between two cluster boxes."""
    dx = max(0.0, a.lo[0] - b.hi[0], b.lo[0] - a.hi[0])
    dy = max(0.0, a.lo[1] - b.hi[1], b.lo[1] - a.hi[1])
    return math.hypot(dx, dy)


def block_partition(rt: Cluster, ct: Cluster, eta: float = 1.0, reach: float = 0.0,
                    split=None):
    """(far, near) lists of (row cluster, column cluster) pairs.  `split`,
    when given, is a function (a, b) -> True when the pair straddles a
    feature (a vertical soil boundary) that must keep it near."""
    far, near = [], []
    stack = [(rt, ct)]
    while stack:
        a, b = stack.pop()
        g = _gap_h(a, b)
        if g > 0.0 and g >= reach and min(a.diam, b.diam) <= eta * g and \
                (split is None or not split(a, b)):
            far.append((a, b))
            continue
        if a.children is None and b.children is None:
            near.append((a, b))
        elif a.children is None:
            stack.extend((a, c) for c in b.children)
        elif b.children is None:
            stack.extend((c, b) for c in a.children)
        elif a.size >= b.size:
            stack.extend((c, b) for c in a.children)
        else:
            stack.extend((a, c) for c in b.children)
    return far, near


def aca(row, col, m: int, n: int, tol: float = 1e-7, kmax: int | None = None):
    """Adaptive cross approximation with partial pivoting.

    row(i) -> (n,) and col(j) -> (m,) evaluate one row / column of the
    block.  Returns (U (m, k), V (n, k)) with block ≈ U Vᵀ, or None when the
    rank would exceed kmax (the caller then stores the block in full)."""
    if kmax is None:
        kmax = max(1, min(m, n) // 2)
    U, V = [], []
    used = np.zeros(m, bool)
    norm2 = 0.0
    i = 0
    tries = 0
    while len(U) < kmax:
        r = row(i).astype(float, copy=True)
        for u, v in zip(U, V):
            r -= u[i] * v
        used[i] = True
        j = int(np.argmax(np.abs(r)))
        piv = r[j]
        if abs(piv) <= 1e-300 or (norm2 > 0 and abs(piv) <= 1e-14 * math.sqrt(norm2)):
            # an (almost) zero residual row: try another, unused row
            tries += 1
            free = np.nonzero(~used)[0]
            if free.size == 0 or tries > 3:
                break
            i = int(free[0])
            continue
        v = r / piv
        c = col(j).astype(float, copy=True)
        for u, vv in zip(U, V):
            c -= vv[j] * u
        uu = float(c @ c)
        vv2 = float(v @ v)
        cross = 0.0
        for u, vv in zip(U, V):
            cross += float(u @ c) * float(vv @ v)
        norm2 += uu * vv2 + 2.0 * cross
        U.append(c)
        V.append(v)
        if math.sqrt(uu * vv2) <= tol * math.sqrt(max(norm2, 1e-300)):
            break
        cu = np.abs(c)
        cu[used] = -1.0
        i = int(np.argmax(cu))
        if cu[i] < 0:
            break
    else:
        return None
    if not U:
        return np.zeros((m, 0)), np.zeros((n, 0))
    return np.array(U).T, np.array(V).T


class HMatrix:
    """Square H-matrix over one cluster tree, for the boundary-element
    potential-coefficient matrix.

    entries(rows, cols) -> (len(rows), len(cols)) dense entries (global,
    original indices).  sparse = (rows, cols, values) are exact entries that
    replace those of `entries` (the near-field quadrature); every one of
    them must lie in a dense block, which a `reach` at least as long as
    their range guarantees."""

    def __init__(self, entries, centres, lo, hi, *, sparse=None, leaf=64, eta=1.5,
                 reach=0.0, tol=1e-7, split=None, full_eval=None):
        self.n = len(centres)
        self.root, self.perm = cluster_tree(centres, lo, hi, leaf)
        far, near = block_partition(self.root, self.root, eta, reach, split)
        p = self.perm
        fix = None
        if sparse is not None:
            ip = np.empty(self.n, int)
            ip[p] = np.arange(self.n)
            sr, sc, sv = sparse
            pr, pc = ip[np.asarray(sr, int)], ip[np.asarray(sc, int)]
            o = np.lexsort((pr, pc))
            pr, pc, sv = pr[o], pc[o], np.asarray(sv, float)[o]

            def fix(r0, r1, c0, c1, D):
                a, b = np.searchsorted(pc, [c0, c1])
                if a == b:
                    return
                r, c, v = pr[a:b], pc[a:b], sv[a:b]
                k = (r >= r0) & (r < r1)
                D[r[k] - r0, c[k] - c0] = v[k]
        self.far = []
        self.near = []
        self.stats = dict(far_blocks=len(far), near_blocks=len(near), rank_max=0,
                          stored=0, dense_fallback=0)
        for a, b in near:
            R, C = p[a.start:a.stop], p[b.start:b.stop]
            D = entries(R, C)
            if fix is not None:
                fix(a.start, a.stop, b.start, b.stop, D)
            self.near.append((a.start, a.stop, b.start, b.stop, D))
            self.stats["stored"] += D.size
        for a, b in far:
            R, C = p[a.start:a.stop], p[b.start:b.stop]
            if full_eval is not None and full_eval(len(R), len(C)):
                # a small block: one vectorised evaluation of all of it is
                # cheaper than the row and column calls of ACA; it is then
                # compressed by ACA on the array itself
                F = entries(R, C)
                uv = aca(lambda i, F=F: F[i], lambda j, F=F: F[:, j], len(R), len(C), tol)
                if uv is None or uv[0].shape[1] * (len(R) + len(C)) >= F.size:
                    self.near.append((a.start, a.stop, b.start, b.stop, F))
                    self.stats["stored"] += F.size
                    continue
            else:
                uv = aca(lambda i, R=R, C=C: entries(R[i:i + 1], C)[0],
                         lambda j, R=R, C=C: entries(R, C[j:j + 1])[:, 0],
                         len(R), len(C), tol)
            if uv is None:
                D = entries(R, C)
                if fix is not None:
                    fix(a.start, a.stop, b.start, b.stop, D)
                self.near.append((a.start, a.stop, b.start, b.stop, D))
                self.stats["dense_fallback"] += 1
                self.stats["stored"] += D.size
                continue
            U, V = uv
            self.far.append((a.start, a.stop, b.start, b.stop, U, V))
            self.stats["rank_max"] = max(self.stats["rank_max"], U.shape[1])
            self.stats["stored"] += U.size + V.size
        self.stats["compression"] = self.stats["stored"] / float(self.n * self.n)
        self._entries = entries
        self._fix = fix

    # products in the permuted ordering
    def _matvec_p(self, x):
        y = np.zeros_like(x)
        for r0, r1, c0, c1, D in self.near:
            y[r0:r1] += D @ x[c0:c1]
        for r0, r1, c0, c1, U, V in self.far:
            y[r0:r1] += U @ (V.T @ x[c0:c1])
        return y

    def matvec(self, x):
        """P x in the original ordering (x may be (n,) or (n, k))."""
        xp = x[self.perm]
        y = np.empty_like(xp)
        y[self.perm] = self._matvec_p(xp)
        return y

    def diagonal_blocks(self, pc_size: int = 256):
        """Clusters of up to pc_size items covering the index range, each with
        its exact dense diagonal block (for the preconditioner)."""
        out = []
        stack = [self.root]
        while stack:
            c = stack.pop()
            if c.size > pc_size and c.children is not None:
                stack.extend(c.children)
                continue
            R = self.perm[c.start:c.stop]
            D = self._entries(R, R)
            if self._fix is not None:
                self._fix(c.start, c.stop, c.start, c.stop, D)
            out.append((c.start, c.stop, D))
        return out


class BlockJacobi:
    """M⁻¹ ≈ blockdiag(P_cc)⁻¹ in the permuted ordering."""

    def __init__(self, hm: HMatrix, pc_size: int = 256):
        self.perm = hm.perm
        self.blocks = []
        for a, b, D in hm.diagonal_blocks(pc_size):
            try:
                inv = np.linalg.inv(D)
            except np.linalg.LinAlgError:              # pragma: no cover
                inv = np.diag(1.0 / np.where(np.diag(D) != 0, np.diag(D), 1.0))
            self.blocks.append((a, b, inv))

    def apply(self, r):
        rp = r[self.perm]
        z = np.empty_like(rp)
        for a, b, inv in self.blocks:
            z[a:b] = inv @ rp[a:b]
        out = np.empty_like(z)
        out[self.perm] = z
        return out


def gmres(matvec, b, precond=None, tol: float = 1e-10, restart: int = 60,
          maxiter: int = 1000):
    """Right-preconditioned restarted GMRES for one right-hand side.
    Returns (x, iterations, relative residual)."""
    n = len(b)
    M = precond if precond is not None else (lambda v: v)
    x = np.zeros(n)
    bnorm = float(np.linalg.norm(b)) or 1.0
    r = b.copy()
    it = 0
    rel = float(np.linalg.norm(r)) / bnorm
    while it < maxiter and rel > tol:
        beta = float(np.linalg.norm(r))
        Q = np.zeros((restart + 1, n))
        Zs = []
        H = np.zeros((restart + 1, restart))
        Q[0] = r / beta
        g = np.zeros(restart + 1)
        g[0] = beta
        cs = np.zeros(restart)
        sn = np.zeros(restart)
        k_done = 0
        for k in range(restart):
            z = M(Q[k])
            Zs.append(z)
            w = matvec(z)
            for i in range(k + 1):                  # modified Gram-Schmidt
                H[i, k] = float(w @ Q[i])
                w -= H[i, k] * Q[i]
            for i in range(k + 1):                  # re-orthogonalise once
                c = float(w @ Q[i])
                H[i, k] += c
                w -= c * Q[i]
            H[k + 1, k] = float(np.linalg.norm(w))
            if H[k + 1, k] > 0:
                Q[k + 1] = w / H[k + 1, k]
            for i in range(k):                      # apply the rotations so far
                t = cs[i] * H[i, k] + sn[i] * H[i + 1, k]
                H[i + 1, k] = -sn[i] * H[i, k] + cs[i] * H[i + 1, k]
                H[i, k] = t
            den = math.hypot(H[k, k], H[k + 1, k]) or 1.0
            cs[k], sn[k] = H[k, k] / den, H[k + 1, k] / den
            H[k, k] = den
            H[k + 1, k] = 0.0
            g[k + 1] = -sn[k] * g[k]
            g[k] = cs[k] * g[k]
            it += 1
            k_done = k + 1
            if abs(g[k + 1]) / bnorm <= tol or it >= maxiter or H[k, k] == 0:
                break
        y = np.linalg.solve(np.triu(H[:k_done, :k_done]), g[:k_done]) if k_done else []
        for i in range(k_done):
            x += y[i] * Zs[i]
        r = b - matvec(x)
        rel = float(np.linalg.norm(r)) / bnorm
    return x, it, rel
