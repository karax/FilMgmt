# Filament Command Center

Aplicação self-hosted e local-first para gerenciamento inteligente de filamentos de impressoras 3D. Esta versão contém a base executável do backend e do frontend e a infraestrutura inicial de persistência, ainda sem modelos de domínio.

## Requisitos

- Python 3.11 ou superior
- Node.js 20.19 ou superior
- npm 10 ou superior

## Backend

Crie um ambiente virtual, instale as dependências e inicie a API:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```

A API estará disponível em `http://localhost:8000`. O health check poderá ser acessado em `http://localhost:8000/api/health` e a documentação interativa do FastAPI estará em `http://localhost:8000/docs`.

Por padrão, o backend utiliza SQLite em `data/filament.db`. A URL pode ser substituída ao iniciar a aplicação por meio da variável de ambiente `DATABASE_URL`:

```bash
cd backend
DATABASE_URL="sqlite+pysqlite:////caminho/absoluto/filament.db" uvicorn app.main:app --reload
```

Para instalar as dependências de desenvolvimento e executar os testes:

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

## Migrations do banco de dados

O schema é versionado com Alembic. Tanto a aplicação quanto as migrations usam
a mesma resolução de `DATABASE_URL`; sem essa variável, ambas apontam para o
arquivo absoluto `data/filament.db` na raiz do projeto.

Para aplicar todas as migrations pendentes:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

Para consultar a revisão aplicada ou desfazer todas as migrations:

```bash
alembic current
alembic downgrade base
```

Após alterar os models SQLAlchemy em tarefas futuras, uma migration poderá ser
gerada com:

```bash
alembic revision --autogenerate -m "description"
```

Revise sempre o conteúdo gerado por `--autogenerate` antes de aplicar a
migration. Depois da revisão, aplique-a com `alembic upgrade head`. Mudanças de
schema da aplicação devem ser versionadas por Alembic, sem usar
`Base.metadata.create_all()` como substituto permanente.

Para validar migrations sem alterar o banco de desenvolvimento, defina uma URL
para um arquivo SQLite temporário:

```bash
DATABASE_URL="sqlite+pysqlite:////tmp/filament-migration-test.db" alembic upgrade head
```

## Frontend

Instale as dependências e inicie o servidor de desenvolvimento:

```bash
cd frontend
npm install
npm run dev
```

O Vite exibirá no terminal o endereço local da aplicação, normalmente `http://localhost:5173`.

O frontend usa `VITE_API_BASE_URL` para localizar a API. Sem essa variável, o
valor padrão é `http://localhost:8000`:

```bash
VITE_API_BASE_URL="http://localhost:8000" npm run dev
```

Para o desenvolvimento local, o backend aceita leituras CORS originadas pelo
Vite em `localhost` ou `127.0.0.1`, nas portas `5173` e `4173`. Outras origens
não são liberadas por padrão.

Para gerar a compilação de produção:

```bash
cd frontend
npm run build
```

Os arquivos gerados ficarão em `frontend/dist/`.

### Testes visuais

Os testes visuais usam o Chromium controlado pelo Playwright. Após instalar as
dependências do frontend, instale o navegador uma vez:

```bash
cd frontend
npm run test:visual:install
```

Execute a suíte e compare a interface com as imagens de referência:

```bash
npm run test:visual
```

Os cenários cobrem o dashboard desktop em tema claro, o inventário desktop em
tema escuro e o inventário móvel com o menu aberto. O relatório HTML é salvo em
`frontend/playwright-report/` e evidências de falha em
`frontend/test-results/playwright/`.

Quando uma mudança visual for intencional e revisada, atualize as imagens de
referência com:

```bash
npm run test:visual:update
```

## Estrutura do projeto

```text
.
├── backend/          # API FastAPI e testes do backend
│   ├── alembic/      # Ambiente e histórico de migrations
│   ├── alembic.ini
│   ├── app/
│   └── tests/
├── frontend/         # Aplicação React, TypeScript e Vite
│   └── src/
├── hardware/
│   └── esp32/        # Espaço reservado para firmware futuro
├── scripts/          # Scripts auxiliares futuros
├── docs/             # Documentação adicional
└── data/             # Dados locais gerados em tempo de execução
```

O projeto ainda não implementa modelos ou tabelas de domínio, inventário de filamentos, autenticação ou integrações de hardware.
