# Filament Command Center

Aplicação self-hosted e local-first para gerenciamento de filamentos de
impressoras 3D. O projeto possui API FastAPI com persistência SQLite, CRUD de
catálogos e spools, e um frontend React para acompanhar o inventário.

## Documentation

- [Manual do usuário](docs/user-guide/README.md)

## Estado atual

- Dashboard operacional em `/`, com resumo de estoque, materiais e spools que
  precisam de atenção.
- Inventário operacional em `/inventory`, com Grid/Table, persistência da
  preferência de visualização e estados loading, error e empty.
- CRUD backend para Manufacturer, Material, Location e Spool.
- Registro atômico de peso em `POST /api/spools/{code}/weight`, incluindo
  histórico de peso e status derivado no backend.
- Spools arquivados não são retornados pelo `GET /api/spools` padrão.

Ainda não há filtros, busca, formulário de spool, detalhes de spool,
autenticação ou integrações de hardware.

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
alembic upgrade head
uvicorn app.main:app --reload
```

A API estará disponível em `http://localhost:8000`. O health check poderá ser acessado em `http://localhost:8000/api/health` e a documentação interativa do FastAPI estará em `http://localhost:8000/docs`.

Os principais recursos HTTP disponíveis são:

- `GET /api/health`
- CRUD em `/api/manufacturers`, `/api/materials` e `/api/locations`
- CRUD em `/api/spools`, além de `POST /api/spools/{code}/weight` e
  `POST /api/spools/{code}/archive`

`GET /api/spools` retorna apenas spools ativos por padrão e aceita filtros
estruturados já suportados pelo backend. O Dashboard e Inventory usam essa
mesma fonte de dados; não existe endpoint específico de dashboard.

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

Os testes de backend usam bancos isolados em memória ou em diretórios
temporários e não devem alterar o banco local de desenvolvimento.

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

## Seed manufacturers

Para inserir uma seleção inicial de fabricantes de filamento sem sobrescrever
websites já configurados pelo usuário, execute:

```bash
cd backend
source .venv/bin/activate
python -m app.scripts.seed_manufacturers
```

O comando usa a mesma configuração `DATABASE_URL` da aplicação, é idempotente
e não cria spools ou materiais.

## Seed materials

Para inserir o catálogo técnico canônico de materiais, execute:

```bash
cd backend
source .venv/bin/activate
python -m app.scripts.seed_materials
```

O seed é idempotente e preserva valores já configurados. Materiais representam
perfis técnicos reutilizáveis; nomes comerciais pertencem ao `product_name` do
spool. Veja também [a cobertura do catálogo](docs/material-catalog-coverage.md).

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

### Páginas disponíveis

| Rota | Estado |
| --- | --- |
| `/` | Dashboard com totais, materiais e spools críticos. |
| `/inventory` | Inventário de spools em Grid ou Table. |
| `/prints`, `/analytics`, `/settings` | Módulos disponíveis na aplicação. |

O frontend usa TanStack Query para `GET /api/spools`. A preferência Grid/Table
é local ao dispositivo e fica em `localStorage` na chave `fcc-inventory-view`.
Os valores de status e percentuais vêm do backend; o frontend não reproduz
regras de LOW.

Para gerar a compilação de produção:

```bash
cd frontend
npm run build
```

Os arquivos gerados ficarão em `frontend/dist/`.

Para executar os testes unitários e de componentes:

```bash
cd frontend
npm test
```

Não há script de lint configurado atualmente.

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

Os cenários cobrem Dashboard em desktop claro e mobile escuro, Inventory em
tabela desktop escura, Inventory em grid mobile com drawer e a persistência da
visualização após refresh. O relatório HTML é salvo em
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

## Idiomas

O frontend oferece Português (Brasil) (`pt-BR`) e English (`en`). O idioma
inicial é `pt-BR`; a preferência é armazenada localmente na chave
`fcc-language` e pode ser alterada em **Configurações → Idioma**. Para incluir
novas traduções, adicione as chaves correspondentes em
`frontend/src/i18n/locales/`.

## Limitações atuais

- Não há filtros ou busca no frontend do Inventory.
- Não há criação, edição, arquivamento ou atualização de peso via interface.
- Não há página de detalhes de spool.
- Autenticação, MQTT, ESP32, sensores, QR/NFC, upload de G-code e PrintJobs
  ainda não foram implementados.
