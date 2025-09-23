from jose import jwt
token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJzaGFya3MiLCJleHAiOjE3NTgyMjc3OTd9.liciCjlZg9NAAy1h9jiFuWtfvHA56dJ0xyMySuUy0lo'
SECRET_KEY = 'a699f178b8b83de7721314c70f2fdcd78f58a1a793a7c7ed1ce32c5e2dea348f'
ALGORITHM = 'HS256'
try:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    print('Decode successful:', payload)
except Exception as e:
    print('Decode failed:', str(e))