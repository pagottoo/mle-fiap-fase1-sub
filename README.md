# Amazon Best Sellers API

> Entrega da **Prova Substitutiva — Fase 1** do MBA em Machine Learning Engineering (FIAP).

REST API em Python (**FastAPI**) que consulta os **best sellers em livros da Amazon** e expõe os campos exigidos pelo enunciado: **nome, autor, avaliação e preço**. **Dashboard analítico em Streamlit** que consome a API e apresenta a análise descritiva.

- Fonte de dados: <https://www.amazon.com/gp/bestsellers/books/>
- Documentação da API: `/docs` (Swagger UI gerado automaticamente pelo FastAPI)
- Arquitetura: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Deploy: Docker + Kubernetes (manifests em [`k8s/`](k8s/))

## Estrutura do repositório

```
fase1-sub/
├── api/                       # Serviço FastAPI
│   ├── app/
│   │   ├── main.py            # Entrypoint (FastAPI app + lifespan)
│   │   ├── models.py          # Schemas Pydantic
│   │   ├── scraper.py         # Scraper da Amazon (requests + BS4)
│   │   ├── cache.py           # Cache em arquivo JSON
│   │   ├── analytics.py       # Agregações
│   │   ├── routers/           # /books, /analytics, /admin
│   │   └── data/seed.json     # Snapshot inicial
│   ├── requirements.txt
│   └── Dockerfile
├── dashboard/                 # Streamlit
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── k8s/                       # Manifests Kubernetes (Kustomize)
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── api-pvc.yaml
│   ├── api-deployment.yaml · api-service.yaml
│   ├── dashboard-deployment.yaml · dashboard-service.yaml
│   ├── ingress.yaml
│   └── kustomization.yaml
├── docs/ARCHITECTURE.md       # Diagrama e decisões de design
├── docker-compose.yml         # Dev local (sobe API + dashboard)
└── entrega.txt                # Template para a entrega (links)
```

## Endpoints da API

| Método | Path | Descrição |
|---|---|---|
| GET  | `/health`                    | Liveness; mostra `fetched_at` e quantos livros há no cache |
| GET  | `/books`                     | Lista best sellers (paginado, com filtros `min_rating`, `max_price`) |
| GET  | `/books/{rank}`              | Retorna um livro pelo seu rank (1 = topo) |
| GET  | `/books/search?q=...`        | Busca por título ou autor (substring, case-insensitive) |
| GET  | `/analytics/overview`        | KPIs: total, avg rating, avg/min/max price, autores únicos |
| GET  | `/analytics/top-rated`       | Top N livros por avaliação |
| GET  | `/analytics/by-author`       | Autores com mais livros no ranking + média de avaliação |
| GET  | `/analytics/price-ranges`    | Distribuição de livros por faixa de preço |
| POST | `/admin/refresh`             | Dispara novo scrape e atualiza o cache |
| GET  | `/docs`                      | Swagger UI (gerado automaticamente) |
| GET  | `/redoc`                     | ReDoc |

A documentação completa e o schema OpenAPI ficam disponíveis em `/docs` quando a API está rodando.

## Como rodar localmente

### Opção 1 — Docker Compose (recomendado)
```bash
docker compose up --build
```
- API:        <http://localhost:8000/docs>
- Dashboard:  <http://localhost:8501>

### Opção 2 — Python direto

```bash
# API
cd api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Em outro terminal: dashboard
cd dashboard
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
API_URL=http://localhost:8000 streamlit run app.py
```

A API sobe já carregado (30 livros). Para fazer a raspagem de dados ao vivo da Amazon:

```bash
curl -X POST http://localhost:8000/admin/refresh
```

## Deploy em Kubernetes

```bash
# 1. Build das imagens (ajuste a tag/registry conforme seu cluster)
docker build -t bestsellers-api:1.0.0       ./api
docker build -t bestsellers-dashboard:1.0.0 ./dashboard

# 2. (Em caso de registry remoto) push das imagens:
# docker tag bestsellers-api:1.0.0 pagottoo/bestsellers-api:1.0.0
# docker push pagottoo/bestsellers-api:1.0.0
# (Idem para o dashboard, e atualize os campos `image:` nos Deployments.)

# 3. Aplicar manifests
kubectl apply -k k8s/

# 4. Verificar
kubectl -n bestsellers get pods,svc,ingress
kubectl -n bestsellers port-forward svc/api 8000:8000     # acesso local rápido
kubectl -n bestsellers port-forward svc/dashboard 8501:8501
```

Edite `k8s/ingress.yaml` para apontar para o seu domínio antes de aplicar em produção. O `ConfigMap` já configura o dashboard para falar com a API pelo DNS interno do cluster (`api.bestsellers.svc.cluster.local`).

## Visão analítica dos dados

O dashboard Streamlit (`dashboard/app.py`) consome a API e apresenta:

- **KPIs**: total de livros, avaliação média, preço médio, faixa de preço, autores únicos
- **Top 10 por avaliação** (gráfico de barras horizontal)
- **Avaliação × Preço** (scatter, tamanho da bolha = número de reviews)
- **Autores mais presentes no ranking** (top 15)
- **Distribuição por faixa de preço** + histograma
- **Lista completa** com busca por título/autor

Todos os números vêm dos endpoints `/analytics/*` e `/books`, ou seja, o dashboard é apenas a camada de apresentação; a API entrega os agregados prontos.

## Stack

- **Python 3.11** · **FastAPI 0.115** · **Pydantic 2** · **uvicorn**
- **requests** · **BeautifulSoup 4** · **lxml**
- **Streamlit 1.39** · **Plotly** · **Pandas**
- **Docker** · **Kubernetes** (Deployment / Service / Ingress / PVC / ConfigMap, via Kustomize)
