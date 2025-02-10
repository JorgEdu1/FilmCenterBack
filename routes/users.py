from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlmodel import select
from database import get_session
from models.models import Streaming, Movie, MovieFilters
from dotenv import load_dotenv
import os
import requests
import random
from datetime import date
from schemas.schemas import StreamingCreate

load_dotenv()
MAX_RETRIES = 5

router = APIRouter()

@router.get("/streamings/")
def get_streamings(session: Session = Depends(get_session)):
    try:
        streamings = session.exec(select(Streaming)).all()
        return streamings
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error getting streamings: {str(e)}")
    
@router.post("/streamings/", response_model=Streaming)
def create_streaming(
    streaming_data: StreamingCreate, 
    session: Session = Depends(get_session)
):
    # Criar o objeto Streaming
    new_streaming = Streaming(
        user_id=streaming_data.user_id,
        name=streaming_data.name,
        price=streaming_data.price,
        billing_date=streaming_data.billing_date
    )

    # Adicionar ao banco e salvar
    session.add(new_streaming)
    session.commit()
    session.refresh(new_streaming)

    return new_streaming
    
@router.get("/streamings/{streaming_id}")
def get_streaming(streaming_id: int, session: Session = Depends(get_session)):
    try:
        streaming = session.get(Streaming, streaming_id)
        return streaming
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error getting streaming: {str(e)}")
    
@router.put("/streamings/{streaming_id}")
def update_streaming(streaming_id: int, streaming: StreamingCreate, session: Session = Depends(get_session)):
    try:
        db_streaming = session.get(Streaming, streaming_id)
        if db_streaming:
            for key, value in streaming.dict().items():
                setattr(db_streaming, key, value)
            session.add(db_streaming)
            session.commit()
            session.refresh(db_streaming)
            return db_streaming
        raise HTTPException(status_code=404, detail="Streaming not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error updating streaming: {str(e)}")
    
@router.delete("/streamings/{streaming_id}")
def delete_streaming(streaming_id: int, session: Session = Depends(get_session)):
    try:
        streaming = session.get(Streaming, streaming_id)
        if streaming:
            session.delete(streaming)
            session.commit()
            return {"message": "Streaming deleted"}
        raise HTTPException(status_code=404, detail="Streaming not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error deleting streaming: {str(e)}")


@router.post("/sortMovies/")
def sort_movies(
    filters: MovieFilters,  # Agora os filtros são recebidos no corpo da requisição
    session: Session = Depends(get_session)
):
    try:
        # Pega os filmes já assistidos pelo usuário para evitar recomendar os mesmos
        movies = session.exec(select(Movie)).all()
        watched_movies = [movie.tmdb_id for movie in movies if movie.status == "watched"]

        # Tentativas de encontrar uma página válida com resultados
        for attempt in range(MAX_RETRIES):
            # Fazendo uma requisição para obter filmes populares
            response = requests.get(
                f'{os.getenv("BASE_URL")}/discover/movie',
                params={
                    'api_key': os.getenv("API_KEY"),
                    'sort_by': 'popularity.desc',
                    'primary_release_date.gte': filters.min_date,  # Data mínima de lançamento
                    'primary_release_date.lte': filters.max_date,  # Data máxima de lançamento
                    'with_genres': filters.genre_id,  # Gênero específico
                    'vote_average.gte': filters.vote_average,  # Nota mínima
                },
            )

            # Verifica se a requisição foi bem-sucedida
            if response.status_code != 200:
                raise Exception(f"Erro na API do TMDB: {response.status_code}")

            data = response.json()
            movies = data.get('results', [])

            # Filtra os filmes que o usuário já assistiu
            movies = [movie for movie in movies if movie['id'] not in watched_movies]

            # Se a lista de provedores de streaming estiver vazia, retorna um filme aleatório sem verificar provedores
            if not filters.streaming_providers:
                if movies:
                    return movies
                continue  # Tenta novamente se não houver filmes disponíveis

            # Caso contrário, faz a filtragem por provedores de streaming
            available_movies = []
            for movie in movies:
                movie_id = movie['id']
                
                # Obtém os provedores de streaming para cada filme
                providers_response = requests.get(
                    f'{os.getenv("BASE_URL")}/movie/{movie_id}/watch/providers',
                    params={'api_key': os.getenv("API_KEY")}
                )

                if providers_response.status_code == 200:
                    providers_data = providers_response.json()
                    # Verifica se algum dos provedores desejados está disponível
                    providers = providers_data.get('results', {}).get('US', {}).get('flatrate', [])
                    for provider in providers:
                        if provider['provider_name'] in filters.streaming_providers:
                            available_movies.append(movie)
                            break

            # Se houver filmes disponíveis nas plataformas desejadas, retorna um aleatório
            if available_movies:
                return available_movies

        # Se não encontrar filmes após várias tentativas
        raise Exception("Nenhum filme encontrado com os filtros fornecidos ou nas plataformas desejadas.")

    except Exception as e:
        print(f"Erro ao buscar filme: {e}")
        return {"error": str(e)}

@router.post("/movies/", response_model=Movie)
def create_movie(
    movie_tmdb_id: int,
    status: int,
    session: Session = Depends(get_session)  # Obtém a sessão do banco
):
    try:
        status_tuplas = {
            1: "watchlist",
            2: "watched",
            3: "blacklist"
        }

        # Fazendo uma requisição para obter informações do filme
        response = requests.get(
            f'{os.getenv("BASE_URL")}/movie/{movie_tmdb_id}',
            params={'api_key': os.getenv("API_KEY")}
        )

        if response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Erro ao buscar filme: {response.status_code}")

        # Convertendo os dados para um novo objeto Movie
        movie_data = response.json()
        new_movie = Movie(
            user_id=1,  # Ajuste conforme a lógica do seu sistema (pode vir do token JWT)
            tmdb_id=movie_data['id'],
            title=movie_data['title'],
            status=status_tuplas.get(status, "watchlist"),  # Evita erro se um status inválido for passado
            genre_id=movie_data['genres'][0]['id'],  # Pega o primeiro gênero da lista
            release_date=movie_data['release_date'],
            runtime=movie_data['runtime'],
            rating=movie_data.get('vote_average')  # Usa `.get()` para evitar KeyError caso não exista
        )

        # Salvando no banco de dados
        session.add(new_movie)
        session.commit()
        session.refresh(new_movie)  # Agora o `id` será gerado corretamente

        return new_movie  # Retorna o objeto com ID preenchido
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/movies/")
def get_movies(session: Session = Depends(get_session)):
    try:
        movies = session.exec(select(Movie)).all()
        return movies
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error getting movies: {str(e)}")
    
@router.get("/movies/{movie_id}")
def get_movie(movie_id: int, session: Session = Depends(get_session)):
    try:
        movie = session.get(Movie, movie_id)
        return movie
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error getting movie: {str(e)}")
    
@router.put("/movies/{movie_id}")
def update_movie(movie_id: int, status: int, session: Session = Depends(get_session)):
    try:
        db_movie = session.get(Movie, movie_id)
        if db_movie:
            status_tuplas = {
                1: "watchlist",
                2: "watched",
                3: "blacklist"
            }
            db_movie.status = status_tuplas.get(status, "watchlist")
            session.add(db_movie)
            session.commit()
            session.refresh(db_movie)
            return db_movie
        raise HTTPException(status_code=404, detail="Movie not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error updating movie: {str(e)}")
    
@router.delete("/movies/{movie_id}")
def delete_movie(movie_id: int, session: Session = Depends(get_session)):
    try:
        movie = session.get(Movie, movie_id)
        if movie:
            session.delete(movie)
            session.commit()
            return {"message": "Movie deleted"}
        raise HTTPException(status_code=404, detail="Movie not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error deleting movie: {str(e)}")
    
# gasto com streaming
@router.get("/streamings/gasto/")
def get_gasto(session: Session = Depends(get_session)):
    try:
        streamings = session.exec(select(Streaming)).all()
        total = 0
        for streaming in streamings:
            total += streaming.price
        return {"total": total}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error getting streamings: {str(e)}")
    
# filmes assistidos por ano de lancamento
@router.get("/movies/assistidos/")
def get_movies_assistidos(session: Session = Depends(get_session)):
    try:
        movies = session.exec(select(Movie)).all()
        assistidos = {}
        for movie in movies:
            if movie.status == "watched":
                if movie.release_date.year in assistidos:
                    assistidos[movie.release_date.year] += 1
                else:
                    assistidos[movie.release_date.year] = 1
        return assistidos
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error getting movies: {str(e)}")
    
# numero de filmes assistidos por plataforma de streaming
@router.get("/movies/assistidos/plataforma/")
def get_movies_assistidos_plataforma(session: Session = Depends(get_session)):
    try:
        movies = session.exec(select(Movie)).all()
        assistidos = {}
        for movie in movies:
            # faz a rq para obter os provedores de streaming para cada filme
            providers_response = requests.get(
                f'{os.getenv("BASE_URL")}/movie/{movie.tmdb_id}/watch/providers',
                params={'api_key': os.getenv("API_KEY")}
            )
            if providers_response.status_code == 200:
                providers_data = providers_response.json()
                # faz um contador para cada provedor, a cada filme que foi assistido dele, soma mais 1
                providers = providers_data.get('results', {}).get('US', {}).get('flatrate', [])
                for provider in providers:
                    # Netflix == Netflix Basic with ads
                    if provider['provider_name'] in assistidos:
                        assistidos[provider['provider_name']] += 1
                    else:
                        assistidos[provider['provider_name']] = 1
        return assistidos
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error getting movies: {str(e)}")

@router.get("/movies/assistidos/genero/")
def get_movies_assistidos_genero(session: Session = Depends(get_session)):
    try:
        # inicializa o dicionario de generos
        assistidos = {}

        #pega os filmes assistidos
        movies = session.exec(select(Movie)).all()
        for movie in movies:
            if movie.status == "watched":
                # faz a rq para obter os generos do filme
                response = requests.get(
                    f'{os.getenv("BASE_URL")}/movie/{movie.tmdb_id}',
                    params={'api_key': os.getenv("API_KEY")}
                )
                if response.status_code != 200:
                    raise HTTPException(status_code=400, detail=f"Erro ao buscar filme: {response.status_code}")
                movie_data = response.json()
                # faz um contador para cada genero, a cada filme que foi assistido dele, soma mais 1, coloque o nome do genero
                for genre in movie_data['genres']:
                    if genre['name'] in assistidos:
                        assistidos[genre['name']] += 1
                    else:
                        assistidos[genre['name']] = 1
        return assistidos
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error getting movies: {str(e)}")