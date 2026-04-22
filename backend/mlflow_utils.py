"""
MLflow integration for experiment tracking and model registry.

Wraps MLflow lifecycle:
- Experiment tracking (log params, metrics, artifacts)
- Model registry (log model, register, transition stages)
- Run lifecycle management (start/run/end)

All operations degrade gracefully: if MLflow is unavailable or
misconfigured, calls become no-ops with a warning log.
"""

import logging
import os
from contextlib import contextmanager
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Lazy import — mlflow is an optional dependency.
_mlflow = None


def _get_mlflow():
    """Lazily import mlflow, return None on failure."""
    global _mlflow
    if _mlflow is not None:
        return _mlflow
    try:
        import mlflow as _m
        _mlflow = _m
        return _mlflow
    except ImportError:
        logger.warning("mlflow not installed — experiment tracking disabled")
        return None


@contextmanager
def start_mlflow_run(experiment_name: str = "investment-research", run_name: Optional[str] = None,
                     tracking_uri: Optional[str] = None):
    """
    Context manager that starts (or reuses) an MLflow run.

    If a run is already active (e.g. started by graph.run_analysis()),
    yields the existing run instead of creating a duplicate.
    """
    mlflow = _get_mlflow()
    if mlflow is None:
        yield None
        return

    # Fix #1: Reuse existing run if one is already active
    if mlflow.active_run() is not None:
        yield mlflow.active_run()
        return

    if tracking_uri:
        mlflow.set_tracking_uri(tracking_uri)

    mlflow.set_experiment(experiment_name)

    run_kwargs = {}
    if run_name:
        run_kwargs["run_name"] = run_name

    run = mlflow.start_run(**run_kwargs)
    try:
        yield run
    finally:
        mlflow.end_run()


def log_param(key: str, value: Any) -> None:
    """Log a single parameter to the active MLflow run."""
    mlflow = _get_mlflow()
    if mlflow is None:
        return
    try:
        mlflow.log_param(key, value)
    except Exception as e:
        logger.warning("mlflow.log_param(%s=%s) failed: %s", key, value, e)


def log_params(params: dict) -> None:
    """Log a dict of parameters to the active MLflow run."""
    mlflow = _get_mlflow()
    if mlflow is None:
        return
    try:
        mlflow.log_params(params)
    except Exception as e:
        logger.warning("mlflow.log_params failed: %s", e)


def log_metric(key: str, value: float, step: Optional[int] = None) -> None:
    """Log a single metric to the active MLflow run."""
    mlflow = _get_mlflow()
    if mlflow is None:
        return
    try:
        mlflow.log_metric(key, value, step=step)
    except Exception as e:
        logger.warning("mlflow.log_metric(%s=%s) failed: %s", key, value, e)


def log_metrics(metrics: dict, step: Optional[int] = None) -> None:
    """Log a dict of metrics to the active MLflow run."""
    mlflow = _get_mlflow()
    if mlflow is None:
        return
    try:
        mlflow.log_metrics(metrics, step=step)
    except Exception as e:
        logger.warning("mlflow.log_metrics failed: %s", e)


def log_artifact(local_path: str, artifact_path: Optional[str] = None) -> None:
    """Log a local file as an artifact to the active MLflow run."""
    mlflow = _get_mlflow()
    if mlflow is None:
        return
    try:
        mlflow.log_artifact(local_path, artifact_path=artifact_path)
    except Exception as e:
        logger.warning("mlflow.log_artifact(%s) failed: %s", local_path, e)


def log_text(text: str, artifact_file: str) -> None:
    """Log a text string as an artifact file. Cleanly removes temp file even on failure."""
    mlflow = _get_mlflow()
    if mlflow is None:
        return
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(text)
            tmp_path = f.name
        try:
            mlflow.log_artifact(tmp_path, artifact_path=artifact_file)
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        logger.warning("mlflow.log_text(%s) failed: %s", artifact_file, e)


def register_model(model, model_name: str, artifact_path: str = "model",
                   flavor: str = "sklearn") -> Optional[str]:
    """
    Log a trained model to MLflow and register it in the Model Registry.

    Returns the model URI if successful, None otherwise.
    """
    mlflow = _get_mlflow()
    if mlflow is None:
        return None

    try:
        if flavor == "sklearn":
            mlflow.sklearn.log_model(model, artifact_path=artifact_path,
                                     registered_model_name=model_name)
        else:
            logger.warning("Unsupported model flavor: %s", flavor)
            return None
        uri = mlflow.get_artifact_uri(artifact_path)
        logger.info("Registered model '%s' at %s", model_name, uri)
        return uri
    except Exception as e:
        logger.warning("register_model('%s') failed: %s", model_name, e)
        return None


def transition_model_stage(model_name: str, version: str, stage: str) -> None:
    """Transition a registered model to a new stage (Staging/Production/Archived)."""
    mlflow = _get_mlflow()
    if mlflow is None:
        return
    try:
        client = mlflow.tracking.MlflowClient()
        client.transition_model_version_stage(model_name, int(version), stage)
        logger.info("Model %s v%s -> %s", model_name, version, stage)
    except Exception as e:
        logger.warning("transition_model_stage('%s' v%s -> %s) failed: %s",
                       model_name, version, stage, e)


def get_latest_model_version(model_name: str) -> Optional[str]:
    """Get the latest version number of a registered model."""
    mlflow = _get_mlflow()
    if mlflow is None:
        return None
    try:
        client = mlflow.tracking.MlflowClient()
        versions = client.search_model_versions(f"name='{model_name}'")
        if not versions:
            return None
        return max(versions, key=lambda v: int(v.version)).version
    except Exception as e:
        logger.warning("get_latest_model_version('%s') failed: %s", model_name, e)
        return None


def load_registered_model(model_name: str, version: Optional[str] = None):
    """Load a registered model by name and optional version (defaults to latest)."""
    mlflow = _get_mlflow()
    if mlflow is None:
        return None

    if version is None:
        version = get_latest_model_version(model_name)
    if version is None:
        return None

    try:
        model_uri = f"models:/{model_name}/{version}"
        return mlflow.sklearn.load_model(model_uri)
    except Exception as e:
        logger.warning("load_registered_model('%s' v%s) failed: %s", model_name, version, e)
        return None
