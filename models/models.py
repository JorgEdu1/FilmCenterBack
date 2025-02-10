from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel

# Tabela users
class User_Film(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True)
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relacionamento com Streamings e Movies
    streamings: List["Streaming"] = Relationship(back_populates="user_film")
    movies: List["Movie"] = Relationship(back_populates="user_film")


# Tabela streamings
class Streaming(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user_film.id")
    name: str
    price: float
    billing_date: date
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relacionamento com User
    user_film: User_Film = Relationship(back_populates="streamings")


# Tabela movies
class Movie(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user_film.id")
    tmdb_id: int = Field(unique=True)
    genre_id: int
    title: str
    status: str
    release_date: date
    runtime: int
    rating: Optional[float] = None  # Não é obrigatório
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relacionamento com User
    user_film: User_Film = Relationship(back_populates="movies")


class MovieFilters(BaseModel):
    min_date: date
    max_date: date
    genre_id: int
    vote_average: int
    streaming_providers: List[str]
