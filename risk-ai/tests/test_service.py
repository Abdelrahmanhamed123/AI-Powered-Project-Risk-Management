"""Unit tests - AI Risk Prediction Service (FR13-FR16). Docstring = FR | description | input | expected."""
from unittest.mock import MagicMock
import pytest
from service import (DelayPredictor, ExplainabilityService, RiskAggregator, ModelTrainerEvaluator,
                     RiskPredictionFacade, classify)

FEATURES = {"remaining_effort_hours": 6, "blocking_issue": 5, "workload_utilization": 3}

def predictor(prob):
    store = MagicMock(); store.load.return_value = MagicMock(predict_proba=MagicMock(return_value=prob))
    return DelayPredictor(store), store

def test_AI01_predict_delay_high():
    """FR13.1 | Predict task delay | features, model 1.2.0, model says 0.78 | probability 0.78, HIGH, model loaded once"""
    p, store = predictor(0.78)
    r = p.predict(FEATURES, "1.2.0")
    assert r["delay_probability"] == 0.78 and r["risk_level"] == "HIGH" and r["model_version"] == "1.2.0"
    store.load.assert_called_once_with("1.2.0")

def test_AI02_predict_empty_features_rejected():
    """FR13.1 | Predict with no features | {} | ValueError, model not loaded"""
    p, store = predictor(0.5)
    with pytest.raises(ValueError):
        p.predict({}, "1.2.0")
    store.load.assert_not_called()

@pytest.mark.parametrize("prob,level", [(0.0, "LOW"), (0.32, "LOW"), (0.33, "MEDIUM"), (0.65, "MEDIUM"), (0.66, "HIGH"), (1.0, "HIGH")])
def test_AI03_classify_risk_boundaries(prob, level):
    """FR13.2 | Classify risk level | probability at boundaries | LOW <0.33, MEDIUM <0.66, HIGH otherwise"""
    assert classify(prob) == level

def test_AI04_classify_invalid_probability_rejected():
    """FR13.2 | Classify invalid probability | 1.5 and -0.1 | ValueError"""
    for bad in (1.5, -0.1):
        with pytest.raises(ValueError):
            classify(bad)

def test_AI05_assess_task_risk_score():
    """FR14.1 | Assess task risk | delay 0.78, impact 0.80 | risk score 0.624"""
    assert RiskAggregator.task_risk(0.78, 0.80) == 0.624

def test_AI06_aggregate_project_risk():
    """FR14.2 | Aggregate project risk | 3 tasks, scores 0.9/0.6/0.3 | score 0.6, MEDIUM, 1 high-risk task"""
    repo = MagicMock()
    repo.find_latest.side_effect = [{"risk_score": 0.9, "risk_level": "HIGH"},
                                    {"risk_score": 0.6, "risk_level": "MEDIUM"},
                                    {"risk_score": 0.3, "risk_level": "LOW"}]
    r = RiskAggregator(repo).assess("p1", ["a", "b", "c"])
    assert r["aggregate_risk_score"] == 0.6 and r["risk_status"] == "MEDIUM" and r["high_risk_task_count"] == 1

def test_AI07_aggregate_project_without_predictions():
    """FR14.2 | Aggregate with no predictions | tasks have no prediction | score 0, LOW"""
    repo = MagicMock(); repo.find_latest.return_value = None
    r = RiskAggregator(repo).assess("p1", ["a", "b"])
    assert r["aggregate_risk_score"] == 0.0 and r["risk_status"] == "LOW"

def test_AI08_display_factors_ranked():
    """FR15.1 | Display risk factors | 3 features | Sorted by contribution, rank 1 = remaining_effort_hours (0.43)"""
    f = ExplainabilityService().rank_factors(FEATURES)
    assert [x["name"] for x in f][0] == "remaining_effort_hours" and f[0]["rank"] == 1 and f[0]["contribution"] == 0.43
    assert [x["rank"] for x in f] == [1, 2, 3]

def test_AI09_build_explanation_text():
    """FR15.1 | Build explanation | ranked factors | Text names top 3 factors; empty list handled"""
    e = ExplainabilityService(); f = e.rank_factors(FEATURES)
    assert e.build_explanation(f).startswith("Main risk factors: remaining_effort_hours")
    assert e.build_explanation([]) == "No contributing factors found."
    assert e.rank_factors({"a": 0}) == []

@pytest.mark.parametrize("conf,word", [(0.86, "high"), (0.5, "medium"), (0.1, "low")])
def test_AI10_explain_confidence(conf, word):
    """FR15.2 | Explain confidence | 0.86 / 0.5 / 0.1 | high / medium / low"""
    assert word in ExplainabilityService().explain_confidence(conf)

def test_AI11_explain_confidence_invalid():
    """FR15.2 | Explain invalid confidence | 1.2 | ValueError"""
    with pytest.raises(ValueError):
        ExplainabilityService().explain_confidence(1.2)

def test_AI12_train_model_saves_artifact():
    """FR16.1 | Train model | 100 rows, random_forest | Artifact saved in model store"""
    store = MagicMock(); store.save.side_effect = lambda m: m
    m = ModelTrainerEvaluator(store).train([1] * 100, "random_forest")
    assert m["algorithm"] == "random_forest" and m["rows"] == 100; store.save.assert_called_once()

@pytest.mark.parametrize("ds,alg", [([], "random_forest"), ([1], "magic")])
def test_AI13_train_invalid_input_rejected(ds, alg):
    """FR16.1 | Train with empty dataset / unsupported algorithm | [] or magic | ValueError, nothing saved"""
    store = MagicMock()
    with pytest.raises(ValueError):
        ModelTrainerEvaluator(store).train(ds, alg)
    store.save.assert_not_called()

def test_AI14_evaluate_metrics():
    """FR16.2 | Compare metrics - compute | y_true 1,1,0,0,1 / y_pred 1,0,0,1,1 | precision 0.67, recall 0.67, f1 0.67"""
    m = ModelTrainerEvaluator(MagicMock()).evaluate([1, 1, 0, 0, 1], [1, 0, 0, 1, 1])
    assert m == {"precision": 0.67, "recall": 0.67, "f1": 0.67}

def test_AI15_evaluate_edge_cases():
    """FR16.2 | Evaluate invalid / all-zero predictions | mismatched lengths; no positives | ValueError; metrics 0"""
    t = ModelTrainerEvaluator(MagicMock())
    with pytest.raises(ValueError):
        t.evaluate([1], [1, 0])
    assert t.evaluate([1, 1], [0, 0]) == {"precision": 0.0, "recall": 0.0, "f1": 0.0}

def test_AI16_compare_models_by_f1():
    """FR16.2 | Compare two models | f1 0.8 vs 0.7 | Model A is better"""
    t = ModelTrainerEvaluator(MagicMock())
    assert t.compare_metrics({"f1": 0.8}, {"f1": 0.7}) == "A" and t.compare_metrics({"f1": 0.5}, {"f1": 0.7}) == "B"

def test_AI17_facade_predict_task_end_to_end():
    """FR13.1 | Facade coordinates predictor, explainer, repo | task t1 | Prediction with factors and explanation saved"""
    p, _ = predictor(0.78); reader, repo = MagicMock(), MagicMock()
    reader.get_task_features.return_value = FEATURES; repo.save.side_effect = lambda x: x
    r = RiskPredictionFacade(p, ExplainabilityService(), reader, repo).predict_task("t1")
    assert r["risk_level"] == "HIGH" and r["task_id"] == "t1" and len(r["factors"]) == 3 and "Main risk factors" in r["explanation"]
    repo.save.assert_called_once()
