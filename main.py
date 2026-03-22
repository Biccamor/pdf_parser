from fastapi import FastAPI

app = FastAPI()

@app.post("/parser")
async def main():
    ... 