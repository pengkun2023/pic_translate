from openai import OpenAI
import httpx

client = OpenAI(
    api_key="sk-906b97091638488f86988b15926e810b",
    base_url="https://api.deepseek.com",
    http_client=httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, content=b""))
    )
)
try:
    response = client.chat.completions.create(model="deepseek-v4-pro", messages=[{"role": "user", "content": "Hello"}])
    print(response)
except Exception as e:
    print(type(e), e)
