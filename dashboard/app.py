"""Dashboard Streamlit para a API Amazon Best Sellers.

Lê a API (URL configurável via env var API_URL) e renderiza a visão analítica.
"""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(
    page_title="Mais vendidos da Amazon - Análise",
    page_icon="📚",
    layout="wide",
)


@st.cache_data(ttl=60)
def fetch(path: str, **params):
    resp = requests.get(f"{API_URL}{path}", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fmt_date(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return iso


# ------------------------------ Sidebar ------------------------------

st.sidebar.title("📚 Best Sellers")
st.sidebar.caption(f"API: `{API_URL}`")

try:
    health = fetch("/health")
    st.sidebar.success(f"API ok · {health['books_in_cache']} livros em cache")
    st.sidebar.caption(f"Coletado em: {fmt_date(health.get('fetched_at'))}")
except Exception as exc:  # noqa: BLE001
    st.sidebar.error(f"API indisponível: {exc}")
    st.stop()

if st.sidebar.button("Forçar refresh (scrape Amazon)"):
    try:
        with st.spinner("Disparando refresh na API..."):
            r = requests.post(f"{API_URL}/admin/refresh", timeout=60)
            if r.ok:
                st.sidebar.success(f"Refresh ok: {r.json()['books_fetched']} livros")
                fetch.clear()
            else:
                st.sidebar.warning(f"Refresh falhou: {r.status_code} — cache mantido")
    except Exception as exc:  # noqa: BLE001
        st.sidebar.error(f"Erro: {exc}")

st.sidebar.markdown("---")
st.sidebar.caption(
    "MBA Machine Learning Engineering · FIAP\n\n"
    "Prova Substitutiva — Fase 1\n\n"
    "Thiago Pagotto - RM361741"
)


# ------------------------------ Header -------------------------------

st.title("Amazon Best Sellers — Visão Analítica")
st.caption(
    "Análise descritiva sobre a lista de best sellers em livros da Amazon. "
    "Dados servidos pela API (FastAPI) que consome a fonte "
    "`amazon.com/gp/bestsellers/books/`."
)


# ------------------------------ KPIs ---------------------------------

ov = fetch("/analytics/overview")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Livros no ranking", ov["total_books"])
c2.metric("Avaliação média", f"{ov['avg_rating']:.2f} ⭐" if ov["avg_rating"] else "—")
c3.metric("Preço médio", f"US$ {ov['avg_price']:.2f}" if ov["avg_price"] else "—")
c4.metric("Faixa de preço",
          f"US$ {ov['min_price']:.2f} – {ov['max_price']:.2f}"
          if ov["min_price"] is not None else "—")
c5.metric("Autores únicos", ov["unique_authors"])


# ------------------------------ Charts -------------------------------

books = fetch("/books", limit=100)
df = pd.DataFrame(books)

tab_overview, tab_authors, tab_price, tab_table = st.tabs(
    ["Top avaliados", "Autores", "Preços", "Lista completa"]
)

with tab_overview:
    st.subheader("Top 10 best sellers por avaliação")
    top = fetch("/analytics/top-rated", limit=10)
    top_df = pd.DataFrame(top)
    if not top_df.empty:
        top_df["rating"] = top_df["rating"].fillna(0)
        fig = px.bar(
            top_df.sort_values("rating"),
            x="rating",
            y="title",
            orientation="h",
            color="rating",
            color_continuous_scale="Blues",
            hover_data=["author", "reviews", "price"],
            labels={"rating": "Avaliação", "title": "Livro"},
        )
        fig.update_layout(height=500, yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Avaliação × Preço")
    scatter_df = df.dropna(subset=["rating", "price"])
    if not scatter_df.empty:
        fig = px.scatter(
            scatter_df,
            x="price",
            y="rating",
            size=scatter_df["reviews"].fillna(1).clip(lower=1),
            color="rating",
            hover_data=["title", "author"],
            labels={"price": "Preço (US$)", "rating": "Avaliação"},
        )
        st.plotly_chart(fig, use_container_width=True)

with tab_authors:
    st.subheader("Autores com mais livros no ranking")
    authors = fetch("/analytics/by-author")
    auth_df = pd.DataFrame(authors).head(15)
    if not auth_df.empty:
        fig = px.bar(
            auth_df.sort_values("books"),
            x="books",
            y="author",
            orientation="h",
            color="avg_rating",
            color_continuous_scale="Viridis",
            labels={"books": "Livros no ranking", "author": "Autor", "avg_rating": "Avaliação média"},
        )
        fig.update_layout(height=500, yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Total de autores únicos: **{ov['unique_authors']}**")

with tab_price:
    st.subheader("Distribuição de preço (US$)")
    buckets = fetch("/analytics/price-ranges")
    bk_df = pd.DataFrame(buckets)
    if not bk_df.empty:
        fig = px.bar(
            bk_df,
            x="bucket",
            y="books",
            color="books",
            color_continuous_scale="Teal",
            labels={"bucket": "Faixa de preço (US$)", "books": "Quantidade de livros"},
        )
        st.plotly_chart(fig, use_container_width=True)

    if "price" in df.columns and df["price"].notna().any():
        st.subheader("Histograma de preços")
        fig = px.histogram(df.dropna(subset=["price"]), x="price", nbins=20,
                           labels={"price": "Preço (US$)"})
        st.plotly_chart(fig, use_container_width=True)

with tab_table:
    st.subheader("Lista completa de best sellers")
    search = st.text_input("Buscar por título ou autor")
    view = df.copy()
    if search:
        s = search.lower()
        view = view[
            view["title"].str.lower().str.contains(s, na=False)
            | view["author"].str.lower().str.contains(s, na=False)
        ]
    cols = ["id", "title", "author", "rating", "reviews", "price", "currency", "product_url"]
    cols = [c for c in cols if c in view.columns]
    st.dataframe(
        view[cols].rename(columns={
            "id": "Rank",
            "title": "Título",
            "author": "Autor",
            "rating": "Avaliação",
            "reviews": "Reviews",
            "price": "Preço",
            "currency": "Moeda",
            "product_url": "URL",
        }),
        use_container_width=True,
        hide_index=True,
    )
