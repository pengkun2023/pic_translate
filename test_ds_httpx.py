import httpx
import os

for key in ['all_proxy', 'ALL_PROXY', 'http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY']:
    if key in os.environ and os.environ[key].startswith('socks://'):
        os.environ[key] = os.environ[key].replace('socks://', 'socks5://')

try:
    response = httpx.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": "Bearer sk-906b97091638488f86988b15926e810b",
            "Content-Type": "application/json"
        },
        json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "Hello"}]
        },
        timeout=10.0
    )
    print(response.status_code)
    print(response.text)
except Exception as e:
    print("Exception:", type(e), e)
