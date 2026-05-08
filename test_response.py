from openai import OpenAI
import os
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''
client = OpenAI(api_key="sk-906b97091638488f86988b15926e810b", base_url="https://api.deepseek.com")
print(client.base_url)
