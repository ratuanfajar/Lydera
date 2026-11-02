from __future__ import annotations

RRF_K = 60


def reciprocal_rank_fusion(rankings: list[list[int]], weights: list[float] | None = None, limit: int | None = None) -> list[int]:
    weights = weights or [1.0] * len(rankings)
    scores: dict[int, float] = {}
    for ranking, weight in zip(rankings, weights):
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + weight / (RRF_K + rank)
    ordered = sorted(scores, key=lambda item: -scores[item])
    return ordered if limit is None else ordered[:limit]
