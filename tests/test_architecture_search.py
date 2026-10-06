from intelligence.architecture_search import ArchitectureCandidate, ArchitectureSearch


def test_rank_is_deterministic_and_prefers_verified_quality():
    search = ArchitectureSearch()
    candidates = [
        ArchitectureCandidate("A", ("claude", "mcp"), .9, .8, .9, .7, .8, .9),
        ArchitectureCandidate("B", ("gpt", "codex"), .95, .95, .95, .8, .8, .95),
    ]
    first = search.rank(candidates)
    second = search.rank(list(reversed(candidates)))
    assert first == second
    assert first[0].candidate_id == "B"


def test_promotion_requires_proof_and_independent_verification():
    search = ArchitectureSearch()
    candidate = ArchitectureCandidate("B", ("gpt", "codex"), 1, 1, 1, 1, 1, 1)
    fitness = search.evaluate(candidate)

    assert search.promote(fitness, proof_present=False,
                          independent_verification=True).promoted is False
    assert search.promote(fitness, proof_present=True,
                          independent_verification=False).promoted is False
    assert search.promote(fitness, proof_present=True,
                          independent_verification=True).promoted is True
