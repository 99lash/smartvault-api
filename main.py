from fastapi import FastAPI;

app = FastAPI(title='smartvault_api')

@app.get('/')
def hello():
  return {"msg": "hello from smartvault-api"}