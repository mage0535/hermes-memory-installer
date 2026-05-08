#!/usr/bin/env python3
"""
OpenAI-compatible local embedding server.
Replaces api.openai.com/v1/embeddings for gbrain.
Model: BAAI/bge-small-zh-v1.5 (512d, Chinese optimized, 33MB)

Fully supports encoding_format: 'float' (JSON array) and 'base64' (binary).
OpenAI SDK v4.104+ defaults to base64 for performance — we support both.
"""
import base64
import json
import os
import struct
import sys
import traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Lazy-load model (takes ~2s on first call)
model = None
model_name = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")


def get_model():
    global model
    if model is None:
        print(f"[embedding] Loading model: {model_name}...", flush=True)
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(model_name)
        dim = model.get_sentence_embedding_dimension()
        print(f"[embedding] Model loaded. Dim={dim}", flush=True)
    return model


def float32_to_base64(arr):
    """Convert a list/array of floats to a base64-encoded float32 binary string."""
    buf = struct.pack(f"<{len(arr)}f", *arr)
    return base64.b64encode(buf).decode("ascii")


class EmbeddingHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        try:
            path = urlparse(self.path).path
            if path != "/v1/embeddings":
                self._json({"error": "Not found"}, 404)
                return

            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            body = json.loads(raw)

            requested_model = body.get("model", model_name)
            encoding_format = body.get("encoding_format", "float")
            input_data = body.get("input", [])
            if isinstance(input_data, str):
                input_data = [input_data]

            texts = [t.strip() for t in input_data if t.strip()]

            if not texts:
                self._json({
                    "object": "list",
                    "data": [],
                    "model": requested_model,
                    "usage": {"prompt_tokens": 0, "total_tokens": 0},
                })
                return

            emb_model = get_model()
            embeddings = emb_model.encode(texts, normalize_embeddings=True)

            full_dim = embeddings.shape[1]
            requested_dims = body.get("dimensions", None)
            if requested_dims is not None and requested_dims < full_dim:
                embeddings = embeddings[:, :requested_dims]

            data = []
            for i in range(len(texts)):
                vec = embeddings[i].tolist()
                if encoding_format == "base64":
                    data.append({
                        "object": "embedding",
                        "index": i,
                        "embedding": float32_to_base64(vec),
                    })
                else:
                    data.append({
                        "object": "embedding",
                        "index": i,
                        "embedding": vec,
                    })

            total_chars = sum(len(t) for t in texts)
            estimated_tokens = max(1, total_chars // 2)

            self._json({
                "object": "list",
                "data": data,
                "model": requested_model,
                "usage": {
                    "prompt_tokens": estimated_tokens,
                    "total_tokens": estimated_tokens,
                },
            })

        except json.JSONDecodeError:
            self._json({"error": "Invalid JSON body"}, 400)
        except Exception as e:
            traceback.print_exc()
            self._json({"error": str(e)}, 500)

    def _json(self, data, status=200):
        try:
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, fmt, *args):
        status = args[2] if len(args) >= 3 else ""
        if status != "200":
            sys.stderr.write(f"[embedding] {args[0]} {args[1]} -> {status}\n")


if __name__ == "__main__":
    port = int(os.environ.get("EMBEDDING_PORT", 8766))

    print(f"[embedding] Loading model: {model_name}...", flush=True)
    get_model()
    print(f"[embedding] Server ready on http://127.0.0.1:{port}/v1/embeddings", flush=True)

    server = ThreadingHTTPServer(("127.0.0.1", port), EmbeddingHandler)
    server.serve_forever()
