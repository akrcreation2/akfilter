from dataclasses import dataclass, field

@dataclass(frozen=True)
class RankingWeights:
    title: float = 3.0
    person: float = 3.0
    language: float = 1.5
    year: float = 1.5
    quality: float = 1.25
    size: float = 1.0
    season: float = 1.5
    episode: float = 1.5
    semantic: float = 1.0
    confidence: float = .5
