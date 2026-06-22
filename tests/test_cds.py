import pytest
import src.cds.engine as cds_engine

def test_initial_priors():
    priors = cds_engine.get_initial_priors()
    assert len(priors) == 20
    for sp in priors:
        assert priors[sp]["mu"] == 0.5
        assert priors[sp]["sigma"] == 0.5

def test_bayesian_update():
    prior_mu = 0.5
    prior_sigma = 0.5
    
    # Positive response
    post_mu, post_sigma = cds_engine.bayesian_update(prior_mu, prior_sigma, 1.0)
    assert post_mu > 0.5
    assert post_sigma < 0.5
    
    # Negative response
    post_mu_neg, post_sigma_neg = cds_engine.bayesian_update(prior_mu, prior_sigma, 0.0)
    assert post_mu_neg < 0.5
    assert post_sigma_neg < 0.5

def test_compute_axis_scores():
    priors = cds_engine.get_initial_priors()
    # Set all N sub-pillars to 0.8
    priors["N1"]["mu"] = 0.8
    priors["N2"]["mu"] = 0.8
    priors["N3"]["mu"] = 0.8
    priors["N4"]["mu"] = 0.8
    
    scores = cds_engine.compute_axis_scores(priors)
    assert scores["N"] == 0.8
    assert scores["C"] == 0.5  # default unchanged

def test_determine_strategic_mode():
    priors = cds_engine.get_initial_priors()
    axis_scores = cds_engine.compute_axis_scores(priors)
    
    # Default should be CONSOLIDATION or PROGRESSION depending on scores
    mode = cds_engine.determine_strategic_mode(priors, axis_scores, 0.5, 0.5)
    assert mode in ["CONSOLIDATION", "PROGRESSION"]
    
    # Low N sub-pillar -> STABILIZATION
    priors["N1"]["mu"] = 0.2
    mode = cds_engine.determine_strategic_mode(priors, axis_scores, 0.5, 0.5)
    assert mode == "STABILIZATION"
    
    # Reset N1, low M1 -> RECOVERY
    priors["N1"]["mu"] = 0.8
    priors["M1"]["mu"] = 0.2
    mode = cds_engine.determine_strategic_mode(priors, axis_scores, 0.5, 0.5)
    assert mode == "RECOVERY"
    
    # High scores -> PROGRESSION
    priors["M1"]["mu"] = 0.8
    mode = cds_engine.determine_strategic_mode(priors, axis_scores, 0.8, 0.8)
    assert mode == "PROGRESSION"
    
    # Very high -> PEAK
    mode = cds_engine.determine_strategic_mode(priors, axis_scores, 0.95, 0.9)
    assert mode == "PEAK"

def test_compute_proximity_scores():
    axis_scores = {"N": 0.8, "C": 0.8, "M": 0.8, "E": 0.8, "S": 0.8}
    
    # First session history is empty
    p_local, p_global = cds_engine.compute_proximity_scores(axis_scores, [])
    assert p_local == 1.0
    assert p_global == 0.8
    
    # Second session history has personal best = 0.9
    history = [
        {"axis_scores_snapshot": {"N": 0.9, "C": 0.9, "M": 0.9, "E": 0.9, "S": 0.9}}
    ]
    p_local, p_global = cds_engine.compute_proximity_scores(axis_scores, history)
    # distance is 0.1 for all axes, so average distance = 0.1. p_local = 1.0 - 0.1 = 0.9
    assert p_local == 0.9
    # best is 0.9, so p_global = 0.9
    assert p_global == 0.9
