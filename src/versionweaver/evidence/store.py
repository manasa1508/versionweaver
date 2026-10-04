import hashlib
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, cast

import boto3  # type: ignore[import-untyped]

from versionweaver.config import Settings, get_settings


def canonical_json(document: dict[str, Any]) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), default=str).encode()


def digest_document(document: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(document)).hexdigest()


class ArtifactStore(ABC):
    @abstractmethod
    def put_json(self, key: str, document: dict[str, Any]) -> str:
        """Store a document and return its URI."""

    @abstractmethod
    def get_json(self, uri: str) -> dict[str, Any]:
        """Retrieve a document by URI."""


class LocalArtifactStore(ArtifactStore):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, key: str) -> Path:
        target = (self.root / key).resolve()
        if self.root not in target.parents:
            raise ValueError("artifact key escapes configured root")
        return target

    def put_json(self, key: str, document: dict[str, Any]) -> str:
        path = self._safe_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical_json(document))
        return path.as_uri()

    def get_json(self, uri: str) -> dict[str, Any]:
        path = Path(uri.removeprefix("file://")).resolve()
        if self.root not in path.parents:
            raise ValueError("artifact URI escapes configured root")
        return cast(dict[str, Any], json.loads(path.read_text()))


class S3ArtifactStore(ArtifactStore):
    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

    def put_json(self, key: str, document: dict[str, Any]) -> str:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=canonical_json(document),
            ContentType="application/json",
        )
        return f"s3://{self.bucket}/{key}"

    def get_json(self, uri: str) -> dict[str, Any]:
        prefix = f"s3://{self.bucket}/"
        if not uri.startswith(prefix):
            raise ValueError("artifact URI is outside configured bucket")
        response = self.client.get_object(Bucket=self.bucket, Key=uri.removeprefix(prefix))
        return cast(dict[str, Any], json.loads(response["Body"].read()))


def build_artifact_store(settings: Settings | None = None) -> ArtifactStore:
    config = settings or get_settings()
    if config.artifact_backend == "s3":
        return S3ArtifactStore(config)
    return LocalArtifactStore(config.artifact_dir)
