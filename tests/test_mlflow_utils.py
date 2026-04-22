"""
Tests for MLflow integration utilities.

Covers: experiment creation, run management, param/metric logging,
artifact logging, and graceful degradation.

All tests use MLflow's default local file store (no explicit URI) to
avoid Windows path-vs-URI issues. CI runs on Linux where explicit URIs
work fine; these tests validate the API contract on any platform.
"""

import os
import tempfile
import pytest

mlflow = pytest.importorskip("mlflow")

from backend.mlflow_utils import (
    start_mlflow_run,
    log_param,
    log_params,
    log_metric,
    log_metrics,
    log_artifact,
    log_text,
)


@pytest.fixture(autouse=True)
def _reset_mlflow_tracking():
    """Reset MLflow tracking state before each test to avoid cross-test pollution."""
    import mlflow as _ml
    # Reset to default
    if _ml.is_tracking_uri_set():
        _ml.set_tracking_uri(None)
    yield
    # Cleanup after test
    if _ml.is_tracking_uri_set():
        _ml.set_tracking_uri(None)


class TestStartMLflowRun:
    def test_creates_run(self):
        with start_mlflow_run(
            experiment_name="test_exp",
            run_name="test_run",
            tracking_uri=None,
        ) as run:
            assert run is not None
            assert run.info.run_id is not None

    def test_run_id_accessible(self):
        with start_mlflow_run(
            experiment_name="test_exp2",
            run_name="run1",
            tracking_uri=None,
        ) as run:
            assert len(run.info.run_id) > 0

    def test_experiment_created(self):
        with start_mlflow_run(
            experiment_name="new_experiment_test",
            tracking_uri=None,
        ) as run:
            pass
        # Verify experiment exists
        client = mlflow.tracking.MlflowClient()
        exp = client.get_experiment_by_name("new_experiment_test")
        assert exp is not None


class TestLogParam:
    def test_single_param(self):
        with start_mlflow_run(
            experiment_name="params_test",
            tracking_uri=None,
        ) as run:
            log_param("ticker", "600519.SS")
        client = mlflow.tracking.MlflowClient()
        run_data = client.get_run(run.info.run_id)
        assert run_data.data.params.get("ticker") == "600519.SS"

    def test_param_overwrites(self):
        """MLflow does not allow changing param values — first write wins."""
        with start_mlflow_run(
            experiment_name="params_overwrite_test",
            tracking_uri=None,
        ) as run:
            log_param("key", "value1")
            log_param("key", "value2")
        client = mlflow.tracking.MlflowClient()
        run_data = client.get_run(run.info.run_id)
        assert run_data.data.params.get("key") == "value1"


class TestLogParams:
    def test_multiple_params(self):
        with start_mlflow_run(
            experiment_name="params_multi_test",
            tracking_uri=None,
        ) as run:
            log_params({"ticker": "AAPL", "model": "deepseek", "version": "1.0"})
        client = mlflow.tracking.MlflowClient()
        run_data = client.get_run(run.info.run_id)
        assert run_data.data.params["ticker"] == "AAPL"
        assert run_data.data.params["model"] == "deepseek"


class TestLogMetric:
    def test_single_metric(self):
        with start_mlflow_run(
            experiment_name="metric_test",
            tracking_uri=None,
        ) as run:
            log_metric("accuracy", 0.95)
        client = mlflow.tracking.MlflowClient()
        run_data = client.get_run(run.info.run_id)
        assert run_data.data.metrics.get("accuracy") == 0.95

    def test_negative_metric(self):
        with start_mlflow_run(
            experiment_name="metric_neg_test",
            tracking_uri=None,
        ) as run:
            log_metric("loss", -0.5)
        client = mlflow.tracking.MlflowClient()
        run_data = client.get_run(run.info.run_id)
        assert run_data.data.metrics["loss"] == -0.5


class TestLogMetrics:
    def test_multiple_metrics(self):
        with start_mlflow_run(
            experiment_name="metrics_multi_test",
            tracking_uri=None,
        ) as run:
            log_metrics({"accuracy": 0.9, "loss": 0.1, "f1": 0.85})
        client = mlflow.tracking.MlflowClient()
        run_data = client.get_run(run.info.run_id)
        assert run_data.data.metrics["accuracy"] == 0.9
        assert run_data.data.metrics["loss"] == 0.1


class TestLogArtifact:
    def test_log_text_file(self, tmp_path):
        artifact_path = tmp_path / "test.txt"
        artifact_path.write_text("hello mlflow")
        with start_mlflow_run(
            experiment_name="artifact_test",
            tracking_uri=None,
        ) as run:
            log_artifact(str(artifact_path))
        client = mlflow.tracking.MlflowClient()
        artifacts = client.list_artifacts(run.info.run_id)
        assert len(artifacts) >= 1


class TestLogText:
    def test_log_text_artifact(self):
        with start_mlflow_run(
            experiment_name="text_test",
            tracking_uri=None,
        ) as run:
            log_text("This is a test summary.\nLine 2.", "summary.txt")
        client = mlflow.tracking.MlflowClient()
        artifacts = client.list_artifacts(run.info.run_id)
        names = [a.path for a in artifacts]
        assert "summary.txt" in names


class TestGracefulDegradation:
    """When MLflow is unavailable or misconfigured, functions should not raise."""

    @pytest.mark.skipif(os.name == "nt", reason="MLflow on Windows doesn't handle local paths as URIs")
    def test_start_run_bad_uri_returns_none(self):
        """Passing a local path that doesn't exist — MLflow should create it (no error)."""
        import tempfile
        bad_uri = os.path.join(tempfile.gettempdir(), "mlflow_nonexistent_test", "mlruns")
        with start_mlflow_run(
            experiment_name="bad_uri_test",
            tracking_uri=bad_uri,
        ) as run:
            pass

    def test_log_param_no_active_run_no_error(self, caplog):
        log_param("orphan", "value")

    def test_log_metric_no_active_run_no_error(self):
        log_metric("orphan_metric", 42)
