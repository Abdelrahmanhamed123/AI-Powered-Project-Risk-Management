"""AI Risk Prediction Service (FR13-FR16)."""
import uuid


def classify(probability):
    if probability < 0 or probability > 1:
        raise ValueError("Probability must be between 0 and 1")
    if probability < 0.33: return "LOW"
    if probability < 0.66: return "MEDIUM"
    return "HIGH"


class DelayPredictor:
    def __init__(self, model_store):
        self.model_store = model_store

    def predict(self, features, model_version):
        if not features:
            raise ValueError("Features are required")
        model = self.model_store.load(model_version)
        prob = model.predict_proba(features)
        return {"delay_probability": prob, "confidence": abs(prob - 0.5) * 2,
                "risk_level": classify(prob), "model_version": model_version}


class ExplainabilityService:
    def rank_factors(self, features):
        total = sum(abs(v) for v in features.values())
        if total == 0: return []
        factors = [{"name": k, "contribution": round(abs(v) / total, 2)} for k, v in features.items()]
        factors.sort(key=lambda f: f["contribution"], reverse=True)
        for i, f in enumerate(factors, 1): f["rank"] = i
        return factors

    def build_explanation(self, factors, top=3):
        if not factors: return "No contributing factors found."
        return "Main risk factors: " + ", ".join(f["name"] for f in factors[:top]) + "."

    def explain_confidence(self, confidence):
        if confidence < 0 or confidence > 1:
            raise ValueError("Confidence must be between 0 and 1")
        level = "high" if confidence >= 0.75 else "medium" if confidence >= 0.4 else "low"
        return f"Model confidence is {level} ({confidence:.0%})."


class RiskAggregator:
    def __init__(self, predictions):
        self.predictions = predictions

    @staticmethod
    def task_risk(delay_probability, impact_score):
        return round(delay_probability * impact_score, 3)

    def assess(self, project_id, task_ids):
        preds = [p for p in (self.predictions.find_latest(t) for t in task_ids) if p is not None]
        if not preds:
            return {"project_id": project_id, "aggregate_risk_score": 0.0, "risk_status": "LOW", "high_risk_task_count": 0}
        score = round(sum(p["risk_score"] for p in preds) / len(preds), 3)
        high = sum(1 for p in preds if p["risk_level"] == "HIGH")
        return {"project_id": project_id, "aggregate_risk_score": score,
                "risk_status": classify(score), "high_risk_task_count": high}


class ModelTrainerEvaluator:
    def __init__(self, model_store):
        self.model_store = model_store

    def train(self, dataset, algorithm):
        if not dataset: raise ValueError("Dataset is empty")
        if algorithm not in ("random_forest", "logistic_regression"):
            raise ValueError("Unsupported algorithm")
        return self.model_store.save({"algorithm": algorithm, "version": "1.0.0", "rows": len(dataset)})

    def evaluate(self, y_true, y_pred):
        if len(y_true) != len(y_pred) or not y_true:
            raise ValueError("Invalid evaluation data")
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        return {"precision": round(prec, 2), "recall": round(rec, 2), "f1": round(f1, 2)}

    def compare_metrics(self, a, b):
        return "A" if a["f1"] >= b["f1"] else "B"


class RiskPredictionFacade:
    def __init__(self, predictor, explainer, reader, repo):
        self.predictor, self.explainer, self.reader, self.repo = predictor, explainer, reader, repo

    def predict_task(self, task_id, model_version="1.2.0"):
        features = self.reader.get_task_features(task_id)
        out = self.predictor.predict(features, model_version)
        factors = self.explainer.rank_factors(features)
        out.update({"task_id": task_id, "factors": factors,
                    "explanation": self.explainer.build_explanation(factors)})
        return self.repo.save(out)
