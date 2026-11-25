# Dashboard de peliculas con la API de TMDB
# Herramientas de Visualizacion
# API: TMDB (The Movie Database) - https://developer.themoviedb.org/docs
#
#     pip install -r requirements.txt
#     streamlit run dashboard_tmdb.py
#
# Los datos salen de respuesta.json (no son en vivo).
# Si se borra ese archivo, se vuelve a consultar la API con el token.
# El token NO va aqui, va en .streamlit/secrets.toml:
#     tmdb_token = "tu-token"

import json
import os
import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import streamlit as st


GRIS = "#B9C3D1"
AZUL = "#1C4C9A"

URL_PELICULAS = "https://api.themoviedb.org/3/discover/movie"
URL_GENEROS = "https://api.themoviedb.org/3/genre/movie/list"
PAGINAS = 30  # cada pagina trae 20 peliculas -> 600

st.set_page_config(page_title="Dashboard TMDB", layout="wide")


# 1. Leer el token (solo se usa si no existe respuesta.json)
def leer_token():
    try:
        token = st.secrets["tmdb_token"].strip()
    except Exception:
        raise ValueError("Falta el token. Crea .streamlit/secrets.toml con: tmdb_token = \"tu-token\"")

    # el token de TMDB es largo y empieza con eyJ
    if not token.startswith("eyJ") or len(token) < 100:
        raise ValueError("El token parece incompleto o no es el 'API Read Access Token'")

    return token


# 2. Hacer una peticion y revisarla
def pedir(url, token, params):
    encabezados = {"Authorization": "Bearer " + token}
    respuesta = requests.get(url, headers=encabezados, params=params, timeout=20)

    if respuesta.status_code == 401:
        raise ValueError("Error 401: el token no sirve")
    if respuesta.status_code == 429:
        raise ValueError("Error 429: me pase del limite de peticiones, hay que esperar")
    if respuesta.status_code != 200:
        raise ValueError("Error " + str(respuesta.status_code))
    if "json" not in (respuesta.headers.get("Content-Type") or ""):
        raise ValueError("La API no devolvio JSON")

    return respuesta.json()


# 3. Traer las peliculas
# si ya existe respuesta.json se lee de ahi, si no, se consulta la API y se guarda
def traer_datos():
    if os.path.exists("respuesta.json"):
        with open("respuesta.json", encoding="utf-8") as f:
            return json.load(f)

    token = leer_token()

    # los generos vienen como numeros, esta lista dice el nombre de cada uno
    generos = pedir(URL_GENEROS, token, {"language": "es-MX"})["genres"]

    parametros = {
        "primary_release_date.gte": "2010-01-01",
        "primary_release_date.lte": "2024-12-31",
        "sort_by": "popularity.desc",
        "vote_count.gte": 100,
        "include_adult": "false",
        "language": "es-MX",
    }
    peliculas = []
    for pagina in range(1, PAGINAS + 1):
        parametros["page"] = pagina
        peliculas += pedir(URL_PELICULAS, token, parametros)["results"]
        time.sleep(0.25)

    datos = {"generos": generos, "results": peliculas}
    with open("respuesta.json", "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    return datos


try:
    with st.spinner("Cargando datos..."):
        datos = traer_datos()
except ValueError as e:
    st.error(str(e))
    st.stop()
except requests.exceptions.RequestException:
    st.error("No se pudo conectar con TMDB, revisa tu internet")
    st.stop()


# 4. Limpieza (la misma de mi practica 12)
nombres_generos = {}
for g in datos["generos"]:
    nombres_generos[g["id"]] = g["name"]

filas = []
for p in datos["results"]:
    if len(p["genre_ids"]) > 0:
        genero = p["genre_ids"][0]  # me quedo con el primer genero
    else:
        genero = None
    filas.append({
        "titulo": p["title"],
        "estreno": p["release_date"],
        "calificacion": p["vote_average"],
        "votos": p["vote_count"],
        "genero": genero,
    })

df = pd.DataFrame(filas)
df = df.drop_duplicates(subset="titulo")
df["calificacion"] = pd.to_numeric(df["calificacion"], errors="coerce")
df["votos"] = pd.to_numeric(df["votos"], errors="coerce")
df["estreno"] = pd.to_datetime(df["estreno"], errors="coerce")
df["genero"] = df["genero"].map(nombres_generos)
df = df.dropna()
df["anio"] = df["estreno"].dt.year


# 5. Filtros
with st.sidebar:
    st.header("Filtros")
    anios = st.slider("Año de estreno", 2010, 2024, (2010, 2024))
    elegidos = st.multiselect("Género", sorted(df["genero"].unique()),
                              placeholder="Todos los géneros")
    votos_min = st.number_input("Votos mínimos", min_value=100, value=100, step=500)
    st.caption("Fuente: TMDB. This product uses the TMDB API but is not "
               "endorsed or certified by TMDB.")

f = df[df["anio"].between(anios[0], anios[1]) & (df["votos"] >= votos_min)]
if len(elegidos) > 0:
    f = f[f["genero"].isin(elegidos)]


# 6. Encabezado e indicadores
st.title("Dashboard de películas TMDB")
st.caption("Películas populares de 2010 a 2024 · datos de la API de TMDB guardados en respuesta.json")

if len(f) == 0:
    st.warning("No hay películas con esos filtros")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Películas", len(f))
c2.metric("Calificación promedio", round(f["calificacion"].mean(), 2))
c3.metric("Mediana de votos", f"{f['votos'].median():,.0f}")
c4.metric("Género más común", f["genero"].value_counts().index[0])

st.divider()


# 7. Graficas
# los titulos son neutrales porque los datos cambian con los filtros
izq1, der1 = st.columns(2)
izq2, der2 = st.columns(2)

# Grafica 1: distribucion
with izq1:
    st.subheader("Cómo se reparten las calificaciones")
    mediana = f["calificacion"].median()
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.hist(f["calificacion"], bins=20, color=GRIS, edgecolor="white")
    ax.axvline(mediana, color=AZUL, linewidth=2, label="mediana = " + str(round(mediana, 1)))
    ax.set_xlabel("Calificación (puntos, de 0 a 10)")
    ax.set_ylabel("Número de películas")
    ax.legend(frameon=False)
    st.pyplot(fig)
    plt.close(fig)

# Grafica 2: comparacion
with der1:
    st.subheader("Calificación por género")
    top8 = f["genero"].value_counts().head(8).index
    por_genero = f[f["genero"].isin(top8)].groupby("genero")["calificacion"].median().sort_values()

    # los dos mejores en azul y los demas en gris
    colores = [GRIS] * len(por_genero)
    colores[-2:] = [AZUL] * len(colores[-2:])

    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.barh(por_genero.index, por_genero.values, color=colores)
    for i, valor in enumerate(por_genero.values):
        ax.text(valor + 0.05, i, str(round(valor, 2)), va="center")
    ax.set_xlim(0, 10)
    ax.set_xlabel("Calificación mediana (puntos, de 0 a 10)")
    ax.set_ylabel("Género")
    st.pyplot(fig)
    plt.close(fig)
    st.caption("Los 8 géneros con más películas según los filtros.")

# Grafica 3: relacion
with izq2:
    st.subheader("Votos contra calificación")
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.scatter(f["votos"], f["calificacion"], s=15, color=AZUL, alpha=0.5)
    ax.set_xscale("log")  # los votos van de 100 a miles, con log se ven mejor
    ax.set_xlabel("Número de votos (escala logarítmica)")
    ax.set_ylabel("Calificación (de 0 a 10)")
    st.pyplot(fig)
    plt.close(fig)

    # con muy pocas peliculas la correlacion no dice nada
    if len(f) >= 10:
        r = np.corrcoef(np.log10(f["votos"]), f["calificacion"])[0, 1]
        st.caption("Correlación r = " + str(round(r, 2)))
    else:
        st.caption("Hay muy pocas películas para calcular la correlación.")

# Grafica 4: evolucion
with der2:
    st.subheader("Calificación promedio por año")
    por_anio = f.groupby("anio")["calificacion"].mean()
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.plot(por_anio.index, por_anio.values, color=AZUL, marker="o", linewidth=2)
    ax.axhline(f["calificacion"].mean(), color=GRIS, linestyle="--", label="promedio general")
    ax.set_ylim(0, 10)  # escala completa para no exagerar cambios chiquitos
    ax.set_xticks(por_anio.index)
    ax.tick_params(axis="x", rotation=45)
    ax.set_xlabel("Año de estreno")
    ax.set_ylabel("Calificación (de 0 a 10)")
    ax.legend(frameon=False)
    st.pyplot(fig)
    plt.close(fig)


# 8. Datos
with st.expander("Ver y descargar los datos"):
    st.dataframe(f.drop(columns="anio"), hide_index=True)
    st.download_button("Descargar CSV", f.to_csv(index=False).encode("utf-8-sig"),
                       file_name="peliculas_tmdb.csv", mime="text/csv")
