from fastapi import FastAPI
from database import create_db_and_tables
from routes.users import router

create_db_and_tables()

app = FastAPI()

app.include_router(router)

@app.get("/")
def read_root():
    return {"Hello": "World"}


