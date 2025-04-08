import requests

url = "https://api.hyperbolic.xyz/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJraW5nMjI4NjY2QGdtYWlsLmNvbSIsImlhdCI6MTczMTUyMDIzM30.nQLMovda2N0X5U1dH2yJ_sJaYczHIMIzyte1onDdNm8"
}
data = {
    "messages": [{
      "role": "user",
      "content": "What can I do in SF?"
    }],
    "model": "deepseek-ai/DeepSeek-V3-0324",
    "max_tokens": 512,
    "temperature": 0.1,
    "top_p": 0.9
}
  
response = requests.post(url, headers=headers, json=data)
print(response.json()) 