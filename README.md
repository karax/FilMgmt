# Filament Command Center

Aplicação self-hosted e local-first para gerenciamento de filamentos de
impressoras 3D. O projeto possui API FastAPI com persistência SQLite, CRUD de
catálogos e spools, e um frontend React para acompanhar o inventário.

## Documentation

- [Manual do usuário](docs/user-guide/README.md)
- [Production Runbook](docs/operations/production-runbook.md)

## Estado atual

- `/` redireciona para o inventário; o Dashboard permanece disponível em
  `/dashboard`.
- Inventário operacional em `/inventory`, com Grid/Table, persistência da
  preferência de visualização, busca, filtros e fluxo completo de Spool.
- CRUD backend para Manufacturer, Material e Spool, além do Print Tracker,
  análise de G-code e identificação de Spool por QR.
- Registro atômico de peso em `POST /api/spools/{code}/weight`, incluindo
  histórico de peso e status derivado no backend.
- Spools arquivados não são retornados pelo `GET /api/spools` padrão.

## Requisitos

- Python 3.11 ou superior
- Node.js 24.15 ou superior na linha 24.x
- npm 11 ou superior
- Shell compatível com POSIX em Linux ou macOS; os comandos abaixo foram
  validados em Linux. O setup equivalente para Windows não está documentado.

O frontend declara esse requisito em `package.json#engines`. Node 20 não é
compatível com o jsdom/undici do lockfile atual. A validação da Wave 2 usa
Node 24.20.0; instale uma versão suportada no seu ambiente, sem depender de
binários temporários usados durante a validação.

Para validar onboarding e mobile com banco descartável, execute no frontend
`npm run test:e2e:wave2`. O comando cria um SQLite temporário, aplica as migrações
existentes e inicia API/Vite nas portas 18002/15173, recusando servidores já em
uso. Os cadastros são feitos pelo Chromium. Depois, executa os testes de smoke
existentes no mesmo ambiente isolado. Para somente os cenários da Wave 2, use
`npm run test:e2e:wave2 -- --project=wave2`. Nenhum comando acessa o banco normal.

## Backend

Crie um ambiente virtual, instale as dependências e inicie a API:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
alembic upgrade head
python -m app.scripts.seed_manufacturers
python -m app.scripts.seed_materials
uvicorn app.main:app --reload
```

As duas seeds são o bootstrap suportado do catálogo em um banco vazio e são
necessárias antes de criar o primeiro Spool.

A API estará disponível em `http://localhost:8000`. O health check poderá ser acessado em `http://localhost:8000/api/health` e a documentação interativa do FastAPI estará em `http://localhost:8000/docs`.

Os principais recursos HTTP disponíveis são:

- `GET /api/health`
- CRUD em `/api/manufacturers` e `/api/materials`
- CRUD em `/api/spools`, além de `POST /api/spools/{code}/weight` e
  `POST /api/spools/{code}/archive`
- CRUD e ciclo start/finish em `/api/prints`
- upload e análise em `/api/gcode/uploads`

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
python -m pip install -r requirements-dev.txt
python -m pytest
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
npm ci
npm run dev
```

O Vite exibirá no terminal o endereço local da aplicação, normalmente
`http://localhost:5173`. O frontend usa URLs relativas em `/api`; durante o
desenvolvimento, o Vite encaminha essas requisições para
`http://127.0.0.1:8000`. Mantenha o backend em execução nesse endereço.

### Páginas disponíveis

| Rota | Estado |
| --- | --- |
| `/` | Redireciona para `/inventory`. |
| `/inventory` | Inventário de spools em Grid ou Table. |
| `/dashboard` | Totais, materiais e spools que precisam de atenção. |
| `/prints` | Criação e acompanhamento de impressões. |
| `/gcode`, `/scan`, `/settings` | G-code, scanner QR e configurações/manual. |
| `/analytics` | Placeholder, ainda sem analytics operacional. |

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

Os testes visuais usam um Chromium do sistema controlado pelo Playwright. Com o
backend e o frontend em execução, verifique o ambiente e siga as instruções de
[testes headless](docs/headless-browser-testing.md):

```bash
cd frontend
npm run browser:doctor
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

- Manufacturer e Material são administrados por seed/API; ainda não há UI
  de catálogo.
- Analytics ainda é um placeholder.
- Não há autenticação, MQTT, ESP32, sensores ou NFC.
- Produção é suportada apenas em LAN confiável ou Tailnet privada; exposição
  direta à Internet não é suportada enquanto não houver autenticação. Consulte
  o [Production Runbook](docs/operations/production-runbook.md) para serviços,
  HTTPS, backup, restauração, atualização e recuperação.
