# Dashboard Reverse Proxy Examples

`metrics_dashboard_server.py` binds to `127.0.0.1` by default and requires a token. Keep that default unless you intentionally publish the dashboard behind a hardened reverse proxy.

## Required Controls

- Serve only over HTTPS.
- Keep the dashboard server bound to localhost.
- Require the dashboard token with `Authorization: Bearer <token>`.
- Add an IP allowlist when possible.
- Do not log query-string tokens. Prefer the Authorization header.

## Caddy Example

```caddyfile
metrics.example.com {
  tls you@example.com

  @allowed remote_ip 203.0.113.10 2001:db8::/32
  handle @allowed {
    reverse_proxy 127.0.0.1:9500
  }

  respond "forbidden" 403
}
```

Use:

```bash
curl -H "Authorization: Bearer $(cat $AGENT_HOME/private/dashboard-token)" \
  https://metrics.example.com/dashboard
```

## Nginx Example

```nginx
server {
    listen 443 ssl http2;
    server_name metrics.example.com;

    ssl_certificate /etc/letsencrypt/live/metrics.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/metrics.example.com/privkey.pem;

    allow 203.0.113.10;
    allow 2001:db8::/32;
    deny all;

    location / {
        proxy_pass http://127.0.0.1:9500;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

## Operational Note

The public repository intentionally does not include real hostnames, IP addresses, tokens, or certificates. Treat this file as a template.
