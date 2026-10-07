"""Local HTTP adapter wire contract, safe failures and pinned runtime preflight."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from test_m4_mapping import schema, task_for, valid_output

from datapulse.mapping.contracts import MappingTaskOutput
from datapulse.mapping.provider import LocalModelConfig, OllamaProvider, ProviderFailure


@pytest.fixture
def local_server():
    state = {"digest": "a" * 64, "runtime": "fixture-1", "requests": [], "fault": None}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "null")
            state["requests"].append((self.path, body))
            if self.path == "/api/version":
                payload = {"version": state["runtime"]}
            elif self.path == "/api/tags":
                payload = {"models": [{"name": "fixture:1b", "digest": state["digest"]}]}
            elif self.path == "/api/show":
                payload = {"details": {"format": "gguf"}}
                if state["fault"] == "cloud":
                    payload["remote_host"] = "remote.invalid"
            else:
                task = state["task"]
                payload = {
                    "done": True,
                    "done_reason": "stop",
                    "message": {"content": json.dumps(valid_output(task))},
                }
                if state["fault"] == "truncated":
                    payload["done_reason"] = "length"
            if state["fault"] == "redirect":
                self.send_response(302)
                self.send_header("Location", "http://remote.invalid/leak")
                self.end_headers()
                return
            if state["fault"] == "timeout":
                time.sleep(1.2)
            data = json.dumps(payload).encode()
            if state["fault"] == "oversized":
                data = b"x" * 262145
            if state["fault"] == "malformed":
                data = b"{invalid"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                if state["fault"] == "slow_drip":
                    for byte in data:
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        time.sleep(0.2)
                else:
                    self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    config = LocalModelConfig(
        endpoint=f"http://127.0.0.1:{server.server_port}",
        model="fixture:1b",
        model_digest="a" * 64,
        runtime_version="fixture-1",
        timeout_seconds=1,
    )
    _, task = task_for(schema())
    state["task"] = task
    yield state, config, task
    server.shutdown()
    server.server_close()
    worker.join(timeout=2)


def test_http_structured_task_pins_and_bounded_generation(local_server):
    state, config, task = local_server
    provider = OllamaProvider(config)
    assert provider.generate(task) == MappingTaskOutput.model_validate(valid_output(task))
    routes = [path for path, _ in state["requests"]]
    assert routes == ["/api/version", "/api/tags", "/api/show", "/api/chat"]
    payload = state["requests"][-1][1]
    assert payload["stream"] is False and payload["format"] == task.output_schema
    assert payload["options"]["num_predict"] == task.max_output_tokens
    assert payload["options"]["temperature"] == 0
    assert "credential_ref" not in payload["messages"][1]["content"]
    assert provider.metadata()["model_digest"] == "a" * 64


@pytest.mark.parametrize(
    "fault,expected",
    [
        ("cloud", "cloud_model_rejected"),
        ("truncated", "output_truncated"),
        ("redirect", "redirect_rejected"),
        ("oversized", "response_limit"),
        ("malformed", "invalid_output"),
        ("timeout", "timeout"),
        ("slow_drip", "timeout"),
    ],
)
def test_transport_failures_are_bounded_and_safe(local_server, fault, expected, caplog):
    state, config, task = local_server
    state["fault"] = fault
    with pytest.raises(ProviderFailure, match=expected):
        OllamaProvider(config).generate(task)
    assert "message" not in caplog.text


@pytest.mark.parametrize(
    "key,value,expected",
    [
        ("digest", "b" * 64, "model_digest_mismatch"),
        ("runtime", "changed", "runtime_version_mismatch"),
    ],
)
def test_changed_artifacts_fail_before_prompt_is_sent(local_server, key, value, expected):
    state, config, task = local_server
    state[key] = value
    with pytest.raises(ProviderFailure, match=expected):
        OllamaProvider(config).generate(task)
    assert all(path != "/api/chat" for path, _ in state["requests"])


def test_prompt_bound_refuses_without_generation(local_server):
    state, config, task = local_server
    config = config.model_copy(update={"context_tokens": 4096})
    with pytest.raises(ProviderFailure, match="prompt_limit"):
        OllamaProvider(config).generate(task)
    assert all(path != "/api/chat" for path, _ in state["requests"])
