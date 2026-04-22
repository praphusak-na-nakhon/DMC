from __future__ import annotations

import json

from dmc_sidecar.rpc import RpcServer


def test_ping_rpc() -> None:
    server = RpcServer(emit_notification=lambda payload: None)
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "req-1",
            "method": "ping",
            "params": {},
        }
    )

    response = json.loads(server.handle_text(payload))

    assert response["result"]["value"] == "pong"
    assert response["result"]["sidecar_version"] == "0.1.0"
