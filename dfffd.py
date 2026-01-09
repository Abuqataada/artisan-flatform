import requests
url = "https://v3.api.termii.com/api/sms/number/send"
payload = {
           "to": "2347065894127",
           "sms": "Hi there, testing Termii",
           "api_key": "TLcnqBFggqTtPqgzxHHZyXoQGbxlAjytxUGKZPzbgVwQzWmyXdtXMXNzGwsvaa"
       }
headers = {
'Content-Type': 'application/json',
}
response = requests.request("POST", url, headers=headers, json=payload)
print(response.text)