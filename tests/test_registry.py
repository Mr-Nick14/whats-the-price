"""Реестр закрепляется за конкретной версией на время жизни пода."""

import sys
from types import SimpleNamespace

from what_s_price.service.app import Features, load_registered_model


def test_alias_resolves_once_and_loads_exact_version(monkeypatch) -> None:
    loaded_uris: list[str] = []
    model = SimpleNamespace(metadata=SimpleNamespace(metadata={
        "input_features": list(Features.model_fields),
    }))

    class Client:
        def get_model_version_by_alias(self, name, alias):
            assert (name, alias) == ("what-s-price", "champion")
            return SimpleNamespace(version="7")

    monkeypatch.setitem(
        sys.modules,
        "mlflow",
        SimpleNamespace(
            MlflowClient=Client,
            pyfunc=SimpleNamespace(load_model=lambda uri: loaded_uris.append(uri) or model),
        ),
    )

    loaded, metadata = load_registered_model("what-s-price", "champion")

    assert loaded is model
    assert loaded_uris == ["models:/what-s-price/7"]
    assert metadata["model_version"] == "7"
