from fastapi import FastAPI
from database import create_db_and_tables
from routes.users import router
from fastapi.middleware.cors import CORSMiddleware

create_db_and_tables()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite requisições de qualquer origem (para desenvolvimento)
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos os métodos (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Permite todos os headers
)

app.include_router(router)

@app.get("/")
def read_root():
    return {"Hello": "World"}


