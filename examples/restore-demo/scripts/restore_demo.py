"""Deterministic offline restore engine for three provider-shaped profiles."""

from __future__ import annotations

import hashlib
import json
import math
import stat
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, cast

Record = dict[str, Any]

ASSETS = (
    "policies",
    "prompts",
    "memory",
    "audit_history",
    "cost_history",
    "ontology",
    "embeddings",
)
MAX_MANIFEST_BYTES = 64 * 1024
MAX_ASSET_BYTES = 2 * 1024 * 1024
MAX_HTTP_BYTES = 2 * 1024 * 1024
ZERO_HASH = "0" * 64
TRANSFER_LABEL = "vectors copied (same model), not re-embedded"


class RestoreError(RuntimeError):
    """Raised when portable content or restored behavior fails a gate."""


def canonical_json(value: object) -> bytes:
    """Return deterministic JSON bytes used by fixture digests."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unique(pairs: list[tuple[str, Any]]) -> Record:
    result: Record = {}
    for key, value in pairs:
        if key in result:
            raise RestoreError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def parse_json(data: bytes, label: str) -> Record:
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RestoreError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise RestoreError(f"{label} must contain a JSON object")
    return value


def _portable_path(name: object) -> PurePosixPath:
    if not isinstance(name, str) or not name or "\\" in name or len(name) > 240:
        raise RestoreError("Bundle paths must be bounded portable relative paths")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise RestoreError("Bundle paths must not be absolute or contain traversal")
    return path


def _reject_links(root: Path, relative: PurePosixPath) -> Path:
    current = root
    for part in relative.parts:
        current /= part
        info = current.lstat()
        attributes = getattr(info, "st_file_attributes", 0)
        if stat.S_ISLNK(info.st_mode) or attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise RestoreError(f"Linked bundle path is unsupported: {relative}")
    return current


def read_bounded(root: Path, name: object, limit: int) -> bytes:
    relative = _portable_path(name)
    path = _reject_links(root, relative)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise RestoreError(f"Bundle file is not a bounded regular file: {relative}")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise RestoreError(f"Bundle file exceeds its size limit: {relative}")
    return data


@dataclass(frozen=True)
class Asset:
    name: str
    path: PurePosixPath
    digest: str


@dataclass(frozen=True)
class Bundle:
    root: Path
    manifest_bytes: bytes
    assets: dict[str, Asset]
    task_path: PurePosixPath
    task_digest: str

    @classmethod
    def load(cls, root: Path) -> Bundle:
        root = root.absolute()
        manifest_bytes = read_bounded(root, "manifest.json", MAX_MANIFEST_BYTES)
        document = parse_json(manifest_bytes, "bundle manifest")
        if set(document) != {"schema_version", "assets", "task"}:
            raise RestoreError("Bundle manifest fields are invalid")
        if document["schema_version"] != "restore-bundle.v1":
            raise RestoreError("Unsupported restore bundle schema")
        raw_assets = document["assets"]
        if not isinstance(raw_assets, dict) or set(raw_assets) != set(ASSETS):
            raise RestoreError("Bundle must declare every supported restore asset")
        assets: dict[str, Asset] = {}
        for name in ASSETS:
            entry = raw_assets[name]
            if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
                raise RestoreError(f"Invalid manifest entry for {name}")
            path = _portable_path(entry["path"])
            digest = entry["sha256"]
            if not isinstance(digest, str) or len(digest) != 64:
                raise RestoreError(f"Invalid SHA-256 for {name}")
            data = read_bounded(root, str(path), MAX_ASSET_BYTES)
            if sha256(data) != digest:
                raise RestoreError(f"Digest mismatch for {name}")
            assets[name] = Asset(name=name, path=path, digest=digest)
        task = document["task"]
        if not isinstance(task, dict) or set(task) != {"path", "sha256"}:
            raise RestoreError("Invalid task entry")
        task_path = _portable_path(task["path"])
        task_digest = task["sha256"]
        if not isinstance(task_digest, str) or len(task_digest) != 64:
            raise RestoreError("Invalid task SHA-256")
        if sha256(read_bounded(root, str(task_path), MAX_ASSET_BYTES)) != task_digest:
            raise RestoreError("Digest mismatch for task")
        return cls(root, manifest_bytes, assets, task_path, task_digest)

    @property
    def bundle_digest(self) -> str:
        return sha256(self.manifest_bytes)

    def asset_bytes(self, name: str) -> bytes:
        return read_bounded(self.root, str(self.assets[name].path), MAX_ASSET_BYTES)

    def task(self) -> Record:
        return parse_json(
            read_bounded(self.root, str(self.task_path), MAX_ASSET_BYTES),
            "scripted task",
        )

    def content_digests(self) -> dict[str, str]:
        return {name: sha256(self.asset_bytes(name)) for name in ASSETS}


@dataclass(frozen=True)
class Profile:
    name: str
    native_embedding_dimension: int
    input_tokens: int
    output_tokens: int


AZURE = Profile("mock-azure", 4, 41, 13)
AWS = Profile("mock-aws", 6, 43, 15)
OLLAMA = Profile("local-ollama", 8, 47, 17)
PROFILES = (AZURE, AWS, OLLAMA)


class ProviderBackend(Protocol):
    profile: Profile

    def invoke(self, payload: Record) -> Record:
        """Return one provider-shaped completion."""

    def embed(self, text: str) -> Record:
        """Return one provider-shaped native embedding response."""


EXPECTED_RESULT: Record = {
    "action": "draft_support_response",
    "final_response_id": "password-reset-draft-v1",
    "human_review": True,
    "ontology_id": "customer-service",
    "policy_decision": "draft_with_human_review",
    "procedure_id": "procedure-password-reset",
}


class FakeBackend:
    """Strict fake that rejects envelopes belonging to another profile."""

    def __init__(self, profile: Profile) -> None:
        self.profile = profile

    def invoke(self, payload: Record) -> Record:
        if self.profile == AZURE:
            return self._azure(payload)
        if self.profile == AWS:
            return self._aws(payload)
        if self.profile == OLLAMA:
            return self._ollama(payload)
        raise RestoreError("Unknown fake provider profile")

    def embed(self, text: str) -> Record:
        if not isinstance(text, str) or not text:
            raise RestoreError("Native embedding input must not be empty")
        vector = [
            float(index + 1) / 10
            for index in range(self.profile.native_embedding_dimension)
        ]
        if self.profile == AZURE:
            return {"data": [{"embedding": vector}], "usage": {"prompt_tokens": 3}}
        if self.profile == AWS:
            return {"embedding": vector, "inputTextTokenCount": 4}
        return {"embeddings": [vector], "prompt_eval_count": 5}

    def _azure(self, payload: Record) -> Record:
        if set(payload) != {"api_version", "input", "tools"}:
            raise RestoreError("mock-azure rejected a non-Azure request envelope")
        stage = cast(Record, payload["input"]).get("stage")
        message: Record
        finish_reason: str
        if stage == "tool":
            message = {
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_procedure",
                            "arguments": '{"procedure_id":"procedure-password-reset"}',
                        },
                    }
                ]
            }
            finish_reason = "tool_calls"
        elif stage == "final":
            message = {"content": json.dumps(EXPECTED_RESULT, sort_keys=True)}
            finish_reason = "stop"
        else:
            raise RestoreError("mock-azure request omitted its stage")
        return {
            "choices": [{"message": message, "finish_reason": finish_reason}],
            "usage": {
                "prompt_tokens": self.profile.input_tokens,
                "completion_tokens": self.profile.output_tokens,
            },
        }

    def _aws(self, payload: Record) -> Record:
        if set(payload) != {"inferenceConfig", "messages", "toolConfig"}:
            raise RestoreError("mock-aws rejected a non-AWS request envelope")
        messages = cast(list[Record], payload["messages"])
        stage = cast(list[Record], messages[0]["content"])[0].get("stage")
        content: Record
        stop_reason: str
        if stage == "tool":
            content = {
                "toolUse": {
                    "name": "lookup_procedure",
                    "input": {"procedure_id": "procedure-password-reset"},
                }
            }
            stop_reason = "tool_use"
        elif stage == "final":
            content = {"text": json.dumps(EXPECTED_RESULT, sort_keys=True)}
            stop_reason = "end_turn"
        else:
            raise RestoreError("mock-aws request omitted its stage")
        return {
            "output": {"message": {"content": [content]}},
            "stopReason": stop_reason,
            "usage": {
                "inputTokens": self.profile.input_tokens,
                "outputTokens": self.profile.output_tokens,
            },
        }

    def _ollama(self, payload: Record) -> Record:
        if set(payload) != {"messages", "model", "stream", "tools"}:
            raise RestoreError("local-ollama rejected a non-Ollama request envelope")
        messages = cast(list[Record], payload["messages"])
        stage = messages[0].get("stage")
        message: Record
        done_reason: str
        if stage == "tool":
            message = {
                "tool_calls": [
                    {
                        "function": {
                            "name": "lookup_procedure",
                            "arguments": {"procedure_id": "procedure-password-reset"},
                        }
                    }
                ]
            }
            done_reason = "tool_calls"
        elif stage == "final":
            message = {"content": json.dumps(EXPECTED_RESULT, sort_keys=True)}
            done_reason = "stop"
        else:
            raise RestoreError("local-ollama request omitted its stage")
        return {
            "message": message,
            "done_reason": done_reason,
            "prompt_eval_count": self.profile.input_tokens,
            "eval_count": self.profile.output_tokens,
        }


class LiveOllamaBackend:
    """Explicit loopback-only Ollama backend with no fake fallback."""

    profile = OLLAMA

    def __init__(self, endpoint: str, model: str) -> None:
        parsed = urllib.parse.urlparse(endpoint)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise RestoreError("Live Ollama requires an explicit loopback endpoint")
        if not model.strip():
            raise RestoreError("Live Ollama requires a model")
        self.endpoint = endpoint.rstrip("/")
        self.model = model

    def _post(self, route: str, payload: Record) -> Record:
        request = urllib.request.Request(
            f"{self.endpoint}{route}",
            data=canonical_json(payload),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            # The constructor rejects every non-loopback host and unsupported scheme.
            with urllib.request.urlopen(request, timeout=15) as response:  # nosec B310
                data = response.read(MAX_HTTP_BYTES + 1)
        except OSError as exc:
            raise RestoreError(f"Live Ollama request failed: {exc}") from exc
        if len(data) > MAX_HTTP_BYTES:
            raise RestoreError("Live Ollama response exceeded its size limit")
        return parse_json(data, "live Ollama response")

    def invoke(self, payload: Record) -> Record:
        outbound = dict(payload)
        outbound["model"] = self.model
        return self._post("/api/chat", outbound)

    def embed(self, text: str) -> Record:
        response = self._post("/api/embed", {"model": self.model, "input": text})
        return response


class Adapter(Protocol):
    profile: Profile

    def request_tool(self, prompt: str, message: str) -> tuple[str, Record, Record]:
        """Run and normalize a tool-selection turn."""

    def final_response(self, prompt: str, procedure: str) -> tuple[Record, Record]:
        """Run and normalize the final-answer turn."""

    def native_embedding(self, text: str) -> list[float]:
        """Normalize one provider-native embedding response."""


class AzureAdapter:
    profile = AZURE
    portable_embedding_dimensions = (8,)

    def __init__(self, backend: ProviderBackend) -> None:
        self.backend = backend

    def _call(self, stage: str, prompt: str, content: str) -> Record:
        return self.backend.invoke(
            {
                "api_version": "2024-10-01",
                "input": {"stage": stage, "system": prompt, "content": content},
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_procedure",
                            "parameters": {"procedure_id": "string"},
                        },
                    }
                ],
            }
        )

    def request_tool(self, prompt: str, message: str) -> tuple[str, Record, Record]:
        response = self._call("tool", prompt, message)
        choice = cast(list[Record], response["choices"])[0]
        if choice.get("finish_reason") != "tool_calls":
            raise RestoreError("mock-azure stop reason did not request a tool")
        call = cast(list[Record], cast(Record, choice["message"])["tool_calls"])[0]
        function = cast(Record, call["function"])
        args = parse_json(str(function["arguments"]).encode(), "Azure tool arguments")
        usage = cast(Record, response["usage"])
        return (
            str(function["name"]),
            args,
            {
                "input_tokens": usage["prompt_tokens"],
                "output_tokens": usage["completion_tokens"],
            },
        )

    def final_response(self, prompt: str, procedure: str) -> tuple[Record, Record]:
        response = self._call("final", prompt, procedure)
        choice = cast(list[Record], response["choices"])[0]
        if choice.get("finish_reason") != "stop":
            raise RestoreError("mock-azure final stop reason is invalid")
        content = cast(Record, choice["message"])["content"]
        usage = cast(Record, response["usage"])
        return parse_json(str(content).encode(), "Azure final response"), {
            "input_tokens": usage["prompt_tokens"],
            "output_tokens": usage["completion_tokens"],
        }

    def native_embedding(self, text: str) -> list[float]:
        response = self.backend.embed(text)
        return cast(list[float], cast(list[Record], response["data"])[0]["embedding"])


class AwsAdapter:
    profile = AWS
    portable_embedding_dimensions = (8,)

    def __init__(self, backend: ProviderBackend) -> None:
        self.backend = backend

    def _call(self, stage: str, content: str) -> Record:
        return self.backend.invoke(
            {
                "inferenceConfig": {"maxTokens": 128},
                "messages": [
                    {"role": "user", "content": [{"stage": stage, "text": content}]}
                ],
                "toolConfig": {
                    "tools": [
                        {
                            "toolSpec": {
                                "name": "lookup_procedure",
                                "inputSchema": {"json": {"procedure_id": "string"}},
                            }
                        }
                    ]
                },
            }
        )

    def request_tool(self, prompt: str, message: str) -> tuple[str, Record, Record]:
        response = self._call("tool", f"{prompt}\n{message}")
        if response.get("stopReason") != "tool_use":
            raise RestoreError("mock-aws stop reason did not request a tool")
        output = cast(Record, response["output"])
        message_record = cast(Record, output["message"])
        tool = cast(Record, cast(list[Record], message_record["content"])[0]["toolUse"])
        usage = cast(Record, response["usage"])
        return (
            str(tool["name"]),
            cast(Record, tool["input"]),
            {
                "input_tokens": usage["inputTokens"],
                "output_tokens": usage["outputTokens"],
            },
        )

    def final_response(self, prompt: str, procedure: str) -> tuple[Record, Record]:
        response = self._call("final", f"{prompt}\n{procedure}")
        if response.get("stopReason") != "end_turn":
            raise RestoreError("mock-aws final stop reason is invalid")
        output = cast(Record, response["output"])
        message_record = cast(Record, output["message"])
        content = cast(list[Record], message_record["content"])[0]["text"]
        usage = cast(Record, response["usage"])
        return parse_json(str(content).encode(), "AWS final response"), {
            "input_tokens": usage["inputTokens"],
            "output_tokens": usage["outputTokens"],
        }

    def native_embedding(self, text: str) -> list[float]:
        return cast(list[float], self.backend.embed(text)["embedding"])


class OllamaAdapter:
    profile = OLLAMA
    portable_embedding_dimensions = (8,)

    def __init__(self, backend: ProviderBackend) -> None:
        self.backend = backend

    def _call(self, stage: str, content: str) -> Record:
        return self.backend.invoke(
            {
                "model": "restore-fake",
                "messages": [{"role": "user", "stage": stage, "content": content}],
                "stream": False,
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_procedure",
                            "parameters": {
                                "type": "object",
                                "required": ["procedure_id"],
                            },
                        },
                    }
                ],
            }
        )

    def request_tool(self, prompt: str, message: str) -> tuple[str, Record, Record]:
        response = self._call("tool", f"{prompt}\n{message}")
        if response.get("done_reason") != "tool_calls":
            raise RestoreError("local-ollama stop reason did not request a tool")
        message_record = cast(Record, response["message"])
        call = cast(list[Record], message_record["tool_calls"])[0]
        function = cast(Record, call["function"])
        return (
            str(function["name"]),
            cast(Record, function["arguments"]),
            {
                "input_tokens": response["prompt_eval_count"],
                "output_tokens": response["eval_count"],
            },
        )

    def final_response(self, prompt: str, procedure: str) -> tuple[Record, Record]:
        response = self._call("final", f"{prompt}\n{procedure}")
        if response.get("done_reason") != "stop":
            raise RestoreError("local-ollama final stop reason is invalid")
        content = cast(Record, response["message"])["content"]
        return parse_json(str(content).encode(), "Ollama final response"), {
            "input_tokens": response["prompt_eval_count"],
            "output_tokens": response["eval_count"],
        }

    def native_embedding(self, text: str) -> list[float]:
        return cast(list[list[float]], self.backend.embed(text)["embeddings"])[0]


def make_adapter(
    profile: Profile,
    *,
    live_ollama: bool = False,
    ollama_endpoint: str = "http://127.0.0.1:11434",
    ollama_model: str = "qwen2.5:3b",
) -> Adapter:
    backend: ProviderBackend
    if profile == OLLAMA and live_ollama:
        backend = LiveOllamaBackend(ollama_endpoint, ollama_model)
    else:
        backend = FakeBackend(profile)
    if profile == AZURE:
        return AzureAdapter(backend)
    if profile == AWS:
        return AwsAdapter(backend)
    return OllamaAdapter(backend)


def _records(data: bytes, label: str) -> list[Record]:
    rows = []
    for index, line in enumerate(data.splitlines(), start=1):
        if line.strip():
            rows.append(parse_json(line, f"{label} line {index}"))
    return rows


def _check_audit(data: bytes) -> str:
    previous = ZERO_HASH
    for row in _records(data, "audit history"):
        digest = row.get("hash")
        payload = {key: value for key, value in row.items() if key != "hash"}
        if row.get("previous_hash") != previous or digest != sha256(
            canonical_json(payload)
        ):
            raise RestoreError("Audit history chain verification failed")
        previous = str(digest)
    if previous == ZERO_HASH:
        raise RestoreError("Audit history must not be empty")
    appended = {
        "event_id": "audit-restore-task",
        "kind": "restore_behavior_checked",
        "previous_hash": previous,
    }
    return sha256(canonical_json(appended))


def _check_costs(document: Record) -> str:
    if document.get("schema_version") != "restore-cost-history.v1":
        raise RestoreError("Cost history schema is invalid")
    records = document.get("records")
    if not isinstance(records, list) or not records:
        raise RestoreError("Cost history records are invalid")
    try:
        total = sum(
            (Decimal(str(cast(Record, row)["estimated_cost"])) for row in records),
            Decimal(0),
        )
    except (InvalidOperation, KeyError, TypeError) as exc:
        raise RestoreError("Cost history contains an invalid decimal") from exc
    if total != Decimal("0.0250"):
        raise RestoreError("Cost history total changed")
    return format(total, ".4f")


def _check_embeddings(
    document: Record, supported_dimensions: tuple[int, ...]
) -> tuple[str, str, int]:
    if (
        document.get("schema_version") != "portable-embeddings.v1"
        or document.get("model") != "portable-hash-v1"
        or document.get("transfer") != TRANSFER_LABEL
    ):
        raise RestoreError("Portable embedding metadata is invalid")
    dimension = document.get("dimension")
    items = document.get("items")
    if not isinstance(dimension, int) or dimension <= 0 or not isinstance(items, list):
        raise RestoreError("Portable embedding dimension or items are invalid")
    if dimension not in supported_dimensions:
        raise RestoreError("Profile does not support the copied embedding dimension")
    best_id = ""
    best_score = -math.inf
    query = [1.0, *([0.0] * (dimension - 1))]
    for raw in items:
        if not isinstance(raw, dict) or not isinstance(raw.get("vector"), list):
            raise RestoreError("Portable embedding item is invalid")
        vector = raw["vector"]
        if len(vector) != dimension or any(
            not isinstance(value, (int, float)) for value in vector
        ):
            raise RestoreError("Portable embedding dimension mismatch")
        score = sum(
            float(left) * float(right)
            for left, right in zip(query, vector, strict=True)
        )
        item_id = raw.get("id")
        if not isinstance(item_id, str):
            raise RestoreError("Portable embedding item ID is invalid")
        if score > best_score or (score == best_score and item_id < best_id):
            best_id, best_score = item_id, score
    if best_id != "procedure-password-reset":
        raise RestoreError("Portable embedding retrieval changed")
    return best_id, TRANSFER_LABEL, dimension


def _check_ontology(path: Path) -> str:
    try:
        from open_ontology_lite import (
            json_ld_text,
            load_json_ld,
            ontology_digest,
            ontology_from_json_ld,
        )
    except ImportError as exc:
        raise RestoreError(
            "OpenOntologyLite is required for ontology restore checks"
        ) from exc
    ontology = load_json_ld(path)
    restored = ontology_from_json_ld(json.loads(json_ld_text(ontology)))
    if ontology_digest(restored) != ontology_digest(ontology):
        raise RestoreError("Ontology changed during OpenOntologyLite round trip")
    return ontology.ontology.id


def run_behavior(bundle: Bundle, adapter: Adapter) -> Record:
    policy = parse_json(bundle.asset_bytes("policies"), "policies")
    decisions = policy.get("decisions")
    if (
        not isinstance(decisions, dict)
        or decisions.get("low") != "draft_with_human_review"
    ):
        raise RestoreError("Low-risk policy behavior changed")
    if decisions.get("high") != "blocked":
        raise RestoreError("High-risk policy behavior changed")
    prompt = bundle.asset_bytes("prompts").decode("utf-8")
    if (
        "human review" not in prompt
        or "Never request or expose credentials" not in prompt
    ):
        raise RestoreError("Restored prompt constraints changed")
    memory = parse_json(bundle.asset_bytes("memory"), "memory")
    memory_items = memory.get("items")
    if not isinstance(memory_items, list):
        raise RestoreError("Restored memory is invalid")
    procedures = {
        str(cast(Record, item).get("id")): str(cast(Record, item).get("text"))
        for item in memory_items
    }
    supported_dimensions = getattr(adapter, "portable_embedding_dimensions", ())
    if not isinstance(supported_dimensions, tuple) or any(
        not isinstance(value, int) for value in supported_dimensions
    ):
        raise RestoreError(
            "Provider adapter has invalid portable embedding capabilities"
        )
    retrieved_id, transfer, copied_dimension = _check_embeddings(
        parse_json(bundle.asset_bytes("embeddings"), "embeddings"),
        supported_dimensions,
    )
    procedure = procedures.get(retrieved_id)
    if procedure is None or "never request or expose credentials" not in procedure:
        raise RestoreError("Restored memory lookup changed")
    audit_append_hash = _check_audit(bundle.asset_bytes("audit_history"))
    cost_total = _check_costs(
        parse_json(bundle.asset_bytes("cost_history"), "cost history")
    )
    ontology_id = _check_ontology(bundle.root / bundle.assets["ontology"].path)
    if ontology_id != "customer-service":
        raise RestoreError("Restored ontology concept changed")
    task = bundle.task()
    expected = task.get("expected")
    if not isinstance(expected, dict):
        raise RestoreError("Scripted task expected result is invalid")
    tool_name, arguments, tool_usage = adapter.request_tool(
        prompt, str(task.get("message"))
    )
    if tool_name != "lookup_procedure" or arguments != {"procedure_id": retrieved_id}:
        raise RestoreError(
            f"{adapter.profile.name} adapter normalized the wrong tool call"
        )
    actual, final_usage = adapter.final_response(prompt, procedure)
    if actual != expected:
        raise RestoreError(f"{adapter.profile.name} scripted task result changed")
    native = adapter.native_embedding(str(task.get("message")))
    if len(native) != adapter.profile.native_embedding_dimension:
        raise RestoreError(f"{adapter.profile.name} native embedding dimension changed")
    return {
        "status": "passed",
        "expected_result_sha256": sha256(canonical_json(expected)),
        "actual_result_sha256": sha256(canonical_json(actual)),
        "tool_call": tool_name,
        "tool_usage": tool_usage,
        "final_usage": final_usage,
        "native_embedding_dimension": len(native),
        "native_embedding_input": "task text only",
        "portable_embedding_transfer": transfer,
        "portable_embedding_model": "portable-hash-v1",
        "portable_embedding_dimension": copied_dimension,
        "retrieval_engine": "portable vector store",
        "retrieved_procedure": retrieved_id,
        "ontology_id": ontology_id,
        "audit_append_hash": audit_append_hash,
        "cost_history_total": cost_total,
        "asset_checks": {name: "passed" for name in ASSETS},
    }


def _write_bundle(source: Bundle, destination: Path) -> Bundle:
    if destination.exists():
        raise RestoreError(f"Restore destination already exists: {destination.name}")
    destination.mkdir(parents=True)
    for asset in source.assets.values():
        target = destination.joinpath(*asset.path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.asset_bytes(asset.name))
    task_target = destination.joinpath(*source.task_path.parts)
    task_target.parent.mkdir(parents=True, exist_ok=True)
    task_target.write_bytes(
        read_bounded(source.root, str(source.task_path), MAX_ASSET_BYTES)
    )
    (destination / "manifest.json").write_bytes(source.manifest_bytes)
    return Bundle.load(destination)


def _compare(reference: Bundle, candidate: Bundle, gate: str) -> dict[str, str]:
    results: dict[str, str] = {}
    for name in ASSETS:
        if reference.assets[name].digest != candidate.assets[name].digest:
            raise RestoreError(f"{gate} digest mismatch for {name}")
        results[name] = "matched"
    if reference.task_digest != candidate.task_digest:
        raise RestoreError(f"{gate} digest mismatch for task")
    return results


def migrate_once(
    source: Bundle,
    original: Bundle,
    profile: Profile,
    directory: Path,
    *,
    live_ollama: bool,
    ollama_endpoint: str,
    ollama_model: str,
) -> tuple[Record, Bundle]:
    restored = _write_bundle(source, directory / "restored")
    import_digests = _compare(source, restored, f"{profile.name} import")
    original_digests = _compare(
        original, restored, f"{profile.name} original comparison"
    )
    adapter = make_adapter(
        profile,
        live_ollama=live_ollama and profile == OLLAMA,
        ollama_endpoint=ollama_endpoint,
        ollama_model=ollama_model,
    )
    behavior = run_behavior(restored, adapter)
    exported = _write_bundle(restored, directory / "exported")
    reexport_digests = _compare(restored, exported, f"{profile.name} re-export")
    original_reexport = _compare(original, exported, f"{profile.name} re-export origin")
    return (
        {
            "profile": profile.name,
            "provider_mode": "live" if live_ollama and profile == OLLAMA else "fake",
            "input_bundle_sha256": source.bundle_digest,
            "output_bundle_sha256": exported.bundle_digest,
            "content_gate": import_digests,
            "original_content_gate": original_digests,
            "reexport_gate": reexport_digests,
            "original_reexport_gate": original_reexport,
            "behavior_gate": behavior,
            "status": "passed",
        },
        exported,
    )


def _write_json(path: Path, document: Record) -> bytes:
    data = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def _write_profile_record(
    output: Path,
    record_path: PurePosixPath,
    *,
    run_kind: str,
    hop_index: int,
    profile: Profile,
    input_path: PurePosixPath,
    migration_path: PurePosixPath,
    migration: Record,
    source_digest: str,
) -> Record:
    document: Record = {
        "schema_version": "restore-profile-record.v1",
        "run_kind": run_kind,
        "hop_index": hop_index,
        "profile": profile.name,
        "provider_mode": migration["provider_mode"],
        "source_bundle_sha256": source_digest,
        "input_bundle": {
            "path": str(input_path),
            "sha256": migration["input_bundle_sha256"],
        },
        "restored_bundle": {
            "path": str(migration_path / "restored"),
            "sha256": migration["output_bundle_sha256"],
        },
        "exported_bundle": {
            "path": str(migration_path / "exported"),
            "sha256": migration["output_bundle_sha256"],
        },
        "migration": migration,
        "machine_signoff": {
            "producer": "linux-ai-restore-demo",
            "status": "passed",
            "checks": ["content", "behavior", "re-export"],
            "identity_claim": "none",
        },
    }
    data = _write_json(output.joinpath(*record_path.parts), document)
    return {
        "profile": profile.name,
        "hop_index": hop_index,
        "path": str(record_path),
        "sha256": sha256(data),
    }


def run_demo(
    bundle_root: Path,
    output: Path,
    *,
    live_ollama: bool = False,
    ollama_endpoint: str = "http://127.0.0.1:11434",
    ollama_model: str = "qwen2.5:3b",
) -> Record:
    if output.exists():
        raise RestoreError("Output directory already exists")
    external_source = Bundle.load(bundle_root)
    output.mkdir(parents=True)
    source_path = PurePosixPath("evidence/source-bundle")
    original = _write_bundle(external_source, output.joinpath(*source_path.parts))
    fanout: list[Record] = []
    fanout_records: list[Record] = []
    for profile in PROFILES:
        migration_path = PurePosixPath("fanout") / profile.name
        result, _ = migrate_once(
            original,
            original,
            profile,
            output.joinpath(*migration_path.parts),
            live_ollama=live_ollama,
            ollama_endpoint=ollama_endpoint,
            ollama_model=ollama_model,
        )
        fanout.append(result)
        record_path = PurePosixPath("records/fanout") / f"{profile.name}.json"
        fanout_records.append(
            _write_profile_record(
                output,
                record_path,
                run_kind="fanout",
                hop_index=0,
                profile=profile,
                input_path=source_path,
                migration_path=migration_path,
                migration=result,
                source_digest=original.bundle_digest,
            )
        )
    chain: list[Record] = []
    chain_records: list[Record] = []
    current = original
    current_path = source_path
    for index, profile in enumerate(PROFILES, start=1):
        migration_path = PurePosixPath("chain") / f"{index:02d}-{profile.name}"
        result, current = migrate_once(
            current,
            original,
            profile,
            output.joinpath(*migration_path.parts),
            live_ollama=live_ollama,
            ollama_endpoint=ollama_endpoint,
            ollama_model=ollama_model,
        )
        chain.append(result)
        record_path = (
            PurePosixPath("records/chain") / f"{index:02d}-{profile.name}.json"
        )
        chain_records.append(
            _write_profile_record(
                output,
                record_path,
                run_kind="chain",
                hop_index=index,
                profile=profile,
                input_path=current_path,
                migration_path=migration_path,
                migration=result,
                source_digest=original.bundle_digest,
            )
        )
        current_path = migration_path / "exported"
    summary: Record = {
        "schema_version": "restore-summary.v1",
        "verifier_contract": "linux-ai-restore-demo.v1",
        "provider_mode": "live-ollama" if live_ollama else "fake-only",
        "source_bundle": {
            "path": str(source_path),
            "sha256": original.bundle_digest,
        },
        "fanout": fanout_records,
        "chain": chain_records,
        "status": "passed",
    }
    summary_data = _write_json(output / "restore-summary.json", summary)
    report: Record = {
        "schema_version": "restore-demo-result.v1",
        "source_bundle_sha256": original.bundle_digest,
        "provider_mode": "live-ollama" if live_ollama else "fake-only",
        "fanout": fanout,
        "chain": chain,
        "chain_order": [profile.name for profile in PROFILES],
        "embedding_transfer": TRANSFER_LABEL,
        "restore_summary": {
            "path": "restore-summary.json",
            "sha256": sha256(summary_data),
        },
        "status": "passed",
    }
    _write_json(output / "restore-demo-result.json", report)
    return report
