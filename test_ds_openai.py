import os
for key in ['all_proxy', 'ALL_PROXY', 'http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY']:
    if key in os.environ and os.environ[key].startswith('socks://'):
        os.environ[key] = os.environ[key].replace('socks://', 'socks5://')

from openai import OpenAI
client = OpenAI(
    api_key="sk-906b97091638488f86988b15926e810b",
    base_url="https://api.deepseek.com"
)
try:
    response = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[{"role": "user", "content": "Hello"}],
        stream=False,
        reasoning_effort="high",
        extra_body={"thinking": {"type": "enabled"}}
    )
    print("Response type:", type(response))
    print(response.choices[0].message.content)
except Exception as e:
    import traceback
    traceback.print_exc()
