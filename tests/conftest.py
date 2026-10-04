import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_ROOT = Path("/tmp/versionweaver-tests")
TEST_ROOT.mkdir(parents=True, exist_ok=True)
os.environ["VERSIONWEAVER_ENVIRONMENT"] = "test"
os.environ["VERSIONWEAVER_DATABASE_URL"] = f"sqlite:///{TEST_ROOT / 'test.sqlite3'}"
os.environ["VERSIONWEAVER_API_TOKEN"] = "test-token"
os.environ["VERSIONWEAVER_ARTIFACT_BACKEND"] = "local"
os.environ["VERSIONWEAVER_ARTIFACT_DIR"] = str(TEST_ROOT / "artifacts")

from versionweaver.api.app import app  # noqa: E402
from versionweaver.persistence.database import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}
