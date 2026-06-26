import pytest
from app.analysis.engine import FactorScore, calculate_composite

def test_composite_score_calculation():
    # Test valid scores
    factors = [
        FactorScore(factor="pop_density", score=80, raw_value=1000, data_source="test", confidence="high"),
        FactorScore(factor="income", score=90, raw_value=50000, data_source="test", confidence="high"),
        FactorScore(factor="transit", score=70, raw_value=1.5, data_source="test", confidence="high"),
        FactorScore(factor="road", score=60, raw_value=2.0, data_source="test", confidence="high"),
        FactorScore(factor="competitor_gap", score=100, raw_value=10.0, data_source="test", confidence="high")
    ]
    weights = {
        "pop_density": 0.30,
        "income": 0.25,
        "transit": 0.15,
        "road": 0.15,
        "competitor_gap": 0.15
    }
    
    score, has_partial, partial_factors = calculate_composite(factors, weights)
    
    expected = (80 * 0.30) + (90 * 0.25) + (70 * 0.15) + (60 * 0.15) + (100 * 0.15)
    assert score == pytest.approx(expected, 0.01)
    assert has_partial is False
    assert len(partial_factors) == 0

def test_composite_score_with_partial_data():
    factors = [
        FactorScore(factor="pop_density", score=80, raw_value=1000, data_source="test", confidence="high", partial=True, partial_reason="Fallback"),
        FactorScore(factor="income", score=90, raw_value=50000, data_source="test", confidence="high"),
    ]
    weights = {"pop_density": 0.5, "income": 0.5}
    
    score, has_partial, partial_factors = calculate_composite(factors, weights)
    
    expected = (80 * 0.5) + (90 * 0.5)
    assert score == pytest.approx(expected, 0.01)
    assert has_partial is True
    assert "pop_density" in partial_factors

def test_composite_score_with_missing_score():
    factors = [
        FactorScore(factor="pop_density", score=80, raw_value=1000, data_source="test", confidence="high"),
        FactorScore(factor="income", score=None, raw_value=None, data_source="test", confidence="unknown"),
    ]
    weights = {"pop_density": 0.5, "income": 0.5}
    
    score, has_partial, partial_factors = calculate_composite(factors, weights)
    assert score is None
    assert "income" in partial_factors

def test_composite_score_missing_weight():
    factors = [
        FactorScore(factor="pop_density", score=80, raw_value=1000, data_source="test", confidence="high"),
    ]
    weights = {"income": 1.0}  # missing pop_density
    
    score, has_partial, partial_factors = calculate_composite(factors, weights)
    assert score is None
    assert "pop_density" in partial_factors
