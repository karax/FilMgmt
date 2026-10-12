# Filament Command Center

Aplicação local-first e self-hosted para inventário de filamentos de impressão
3D, acompanhamento da Bambu Lab P1S, histórico de impressões, reconciliação de
consumo físico, calibrações, Analytics e exportação CSV.

Este documento é o manual técnico para instalar, configurar e executar o
sistema em Linux, macOS e Windows. O modo de desenvolvimento/local funciona
nas três plataformas. O deploy de produção versionado pelo projeto usa Linux,
systemd e Caddy.

## 1. Arquitetura

```text
Navegador
  -> React 19 + TypeScript + Vite
       -> /api (proxy no desenvolvimento)
  -> FastAPI + SQLAlchemy
       -> SQLite
       -> armazenamento local de G-code e miniaturas
       -> coletor opcional e somente leitura da Bambu Lab P1S
```

Componentes principais:

- backend Python/FastAPI em `backend/`;
- frontend React/Vite em `frontend/`;
- banco SQLite versionado por migrations Alembic;
- dados locais em `data/` por padrão;
- proxy Caddy e unidades systemd em `deploy/` para produção Linux;
- testes backend com Pytest e frontend com Vitest/Playwright.

Não há Dockerfile ou Docker Compose mantido pelo projeto. Não use um schema
criado manualmente: o mecanismo suportado de criação e atualização do banco é
Alembic.

## 2. Suporte por plataforma

| Cenário | Linux | macOS | Windows |
| --- | --- | --- | --- |
| Desenvolvimento local | Suportado | Suportado | Suportado com PowerShell |
| SQLite local | Suportado | Suportado | Suportado |
| Build do frontend | Suportado | Suportado | Suportado |
| Testes unitários | Suportado | Suportado | Suportado |
| Coletor P1S na LAN | Suportado | Suportado | Suportado, sujeito ao firewall local |
| Deploy versionado Caddy + serviço | Suportado com systemd | Não fornecido | Não fornecido |
| Serviço automático no boot | systemd user service | Requer adaptação para launchd | Requer adaptação para Windows Service |

Para uma instalação permanente, o perfil oficialmente documentado é Linux,
incluindo Raspberry Pi OS/Debian ARM64. Em macOS e Windows, os comandos abaixo
são adequados para desenvolvimento, avaliação e uso local supervisionado. O
repositório não inclui unidades launchd, Windows Service ou IIS.

A suíte completa é validada operacionalmente em Linux. O repositório ainda não
possui uma matriz de CI que execute cada release em macOS e Windows; nessas
plataformas, execute a Seção 15 após a instalação para confirmar o ambiente.

## 3. Requisitos

- Python 3.11 ou superior;
- Node.js `>=24.15.0 <25`;
- npm 11 ou superior;
- Git;
- navegador moderno;
- acesso de rede local à impressora apenas se o coletor P1S for utilizado.

O requisito exato do Node está declarado em `frontend/package.json`. Node 20
não é compatível com o lockfile e com a versão atual de jsdom/undici.

Verifique o ambiente antes de instalar:

### Linux e macOS

```bash
python3 --version
node --version
npm --version
git --version
```

### Windows PowerShell

```powershell
py -3 --version
node --version
npm --version
git --version
```

Instale Python, Node e Git pelos instaladores oficiais ou pelo gerenciador de
pacotes da plataforma. Confirme as versões depois da instalação; não dependa da
versão antiga que possa vir instalada pelo sistema operacional.

## 4. Obter o código

O runbook de produção usa o remoto SSH abaixo:

```bash
git clone git@github.com:karax/FilMgmt.git
cd FilMgmt
```

Se o seu acesso ao repositório usa HTTPS, substitua a URL pelo remoto HTTPS
fornecido pelo GitHub. Todos os comandos seguintes partem da raiz `FilMgmt`.

## 5. Inicialização do banco

Uma instalação nova precisa executar todas as migrations e os dois seeds de
catálogo. Os seeds são idempotentes: podem ser executados novamente sem criar
duplicatas nem sobrescrever personalizações suportadas.

Ordem obrigatória:

1. instalar as dependências Python;
2. executar `alembic upgrade head`;
3. executar `seed_manufacturers`;
4. executar `seed_materials`;
5. iniciar o backend.

Por padrão, o banco é criado em `data/filament.db`, sempre relativo à raiz do
projeto, independentemente do diretório a partir do qual o processo foi
iniciado.

## 6. Executar no Linux

### 6.1 Backend — primeiro terminal

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
alembic upgrade head
python -m app.scripts.seed_manufacturers
python -m app.scripts.seed_materials
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 6.2 Frontend — segundo terminal

```bash
cd frontend
npm ci
npm run dev
```

Abra `http://localhost:5173`. O Vite escuta em todas as interfaces no modo de
desenvolvimento, mas a URL local continua sendo a opção recomendada. As
requisições relativas para `/api` são encaminhadas a
`http://127.0.0.1:8000`.

## 7. Executar no macOS

Use dois terminais. Os comandos são iguais aos do Linux.

### 7.1 Backend — primeiro terminal

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
alembic upgrade head
python -m app.scripts.seed_manufacturers
python -m app.scripts.seed_materials
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Em Macs com Apple Silicon, use uma instalação ARM64 nativa de Python e Node.
Não é necessário executar o terminal por Rosetta quando todas as dependências
são nativas.

### 7.2 Frontend — segundo terminal

```bash
cd frontend
npm ci
npm run dev
```

Abra `http://localhost:5173`.

## 8. Executar no Windows

Use PowerShell e dois terminais. Os comandos usam os executáveis do ambiente
virtual diretamente e, portanto, não dependem da política de ativação de
scripts do PowerShell.

### 8.1 Backend — primeiro terminal

```powershell
Set-Location backend
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m app.scripts.seed_manufacturers
.\.venv\Scripts\python.exe -m app.scripts.seed_materials
.\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```

### 8.2 Frontend — segundo terminal

```powershell
Set-Location frontend
npm ci
npm run dev
```

Abra `http://localhost:5173`.

Se o PowerShell interceptar `npm.ps1` por política de execução, use os mesmos
comandos com o executável do Windows:

```powershell
npm.cmd ci
npm.cmd run dev
```

O Windows Defender Firewall pode solicitar autorização para Python ou Node.
Para uso somente nesta máquina, mantenha o backend em `127.0.0.1` e não é
necessário liberar uma porta pública.

## 9. URLs e verificação inicial

Com os dois processos ativos:

| Recurso | URL |
| --- | --- |
| Aplicação | `http://localhost:5173` |
| Health check | `http://localhost:8000/api/health` |
| OpenAPI/Swagger | `http://localhost:8000/docs` |
| Especificação OpenAPI | `http://localhost:8000/openapi.json` |
| Diagnóstico P1S | `http://localhost:8000/api/integrations/bambu/status` |

Portas utilizadas:

| Porta | Uso |
| --- | --- |
| `8000/tcp` | FastAPI local. |
| `5173/tcp` | Vite em desenvolvimento. |
| `4173/tcp` | Preview local do build. |
| `8080/tcp` | Entrada Caddy no perfil de produção Linux. |
| `8883/tcp` | Saída do backend para MQTT TLS da P1S, quando habilitado. |
| `990/tcp` | Saída do backend para FTPS implícito da P1S, quando habilitado. |

Linux/macOS:

```bash
curl --fail http://127.0.0.1:8000/api/health
```

Windows PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

A resposta esperada do health check é:

```json
{"status":"ok"}
```

## 10. Configuração por variáveis de ambiente

A aplicação lê a configuração do ambiente do processo. Ela não carrega um
arquivo `.env` automaticamente. Em desenvolvimento, exporte as variáveis antes
de iniciar Uvicorn. Em produção Linux, a unidade systemd lê o arquivo protegido
`~/.config/filament-command-center/env`.

| Variável | Padrão | Finalidade |
| --- | --- | --- |
| `DATABASE_URL` | SQLite em `data/filament.db` | URL SQLAlchemy do banco. |
| `GCODE_UPLOAD_DIRECTORY` | `data/uploads/gcode` | Arquivos G-code gerenciados. |
| `PRINT_JOB_MEDIA_DIRECTORY` | `data/print-jobs` | Miniaturas derivadas de PrintJobs. |
| `GCODE_MAX_UPLOAD_BYTES` | `104857600` | Limite de 100 MiB por upload. |
| `GCODE_UPLOAD_RETENTION_DAYS` | `30` | Retenção antes da limpeza. |
| `GCODE_UPLOAD_MAX_TOTAL_BYTES` | `2147483648` | Cota total de 2 GiB. |
| `GCODE_UPLOAD_TEMP_STALE_SECONDS` | `3600` | Idade de temporários abandonados. |
| `GCODE_UPLOAD_CLEANUP_ENABLED` | `true` | Limpeza antes de novo upload. |
| `GCODE_UPLOAD_RETENTION_ENABLED` | `true` | Expiração baseada em idade. |
| `BAMBU_HOST` | vazio | IP ou hostname local da P1S. |
| `BAMBU_PORT` | `8883` | Porta MQTT da P1S. |
| `BAMBU_FTPS_PORT` | `990` | Porta FTPS implícita para enriquecimento 3MF. |
| `BAMBU_SERIAL` | vazio | Número de série usado no tópico MQTT. |
| `BAMBU_ACCESS_CODE` | vazio | Código LAN da impressora; é um segredo. |
| `BAMBU_MQTT_TLS` | `true` | Ativa TLS no MQTT local. |
| `BAMBU_DEBUG_PAYLOADS` | `false` | Diagnóstico sanitizado; somente desenvolvimento. |

### 10.1 Exemplo no Linux/macOS

Copie o modelo, edite somente os valores necessários e carregue-o no shell:

```bash
cp deploy/env/production.env.example .env
chmod 600 .env
set -a
. ./.env
set +a
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

O arquivo `.env` da raiz é ignorado pelo Git. Nunca registre
`BAMBU_ACCESS_CODE` no repositório ou no histórico do shell.

### 10.2 Exemplo no Windows PowerShell

As variáveis abaixo existem apenas no processo atual e nos processos iniciados
por ele:

```powershell
$env:BAMBU_HOST = "192.168.1.123"
$env:BAMBU_SERIAL = "SERIAL_DA_IMPRESSORA"
$env:BAMBU_ACCESS_CODE = "CODIGO_LAN"
$env:BAMBU_MQTT_TLS = "true"
Set-Location C:\caminho\para\FilMgmt\backend
.\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```

Fechar o terminal remove essas variáveis da sessão. Evite `setx` para segredos,
pois ele persiste valores fora do diretório protegido do projeto.

### 10.3 Banco SQLite alternativo

Linux/macOS:

```bash
export DATABASE_URL="sqlite+pysqlite:////caminho/absoluto/filament.db"
```

Windows PowerShell, usando barras normais na URL:

```powershell
$env:DATABASE_URL = "sqlite+pysqlite:///C:/dados/filament-command-center/filament.db"
```

Use a mesma `DATABASE_URL` para `alembic`, seeds, backend, backup e restore. O
diretório pai do SQLite é criado automaticamente quando possível.

## 11. Integração opcional com Bambu Lab P1S

O coletor só é habilitado quando `BAMBU_HOST`, `BAMBU_SERIAL` e
`BAMBU_ACCESS_CODE` estão preenchidos. Sem essas três variáveis, o restante da
aplicação funciona normalmente.

A integração:

- assina passivamente os relatórios MQTT locais;
- registra PrintJobs observados;
- lê 3MF por FTPS para miniatura e estimativas do fatiador;
- não publica comandos MQTT;
- não inicia, pausa ou cancela impressões;
- não altera estoque sem reconciliação explícita do usuário.

Consulte [Coletor local Bambu Lab P1S](docs/bambu-p1s.md) para configuração,
TLS local, firewall e diagnóstico.

## 12. Build do frontend

O build é igual nas três plataformas:

```bash
cd frontend
npm ci
npm run build
```

Saída: `frontend/dist/`.

O build executa a verificação do PDF do manual, o compilador TypeScript e o
Vite. Falhas nesses passos devem ser corrigidas; não sirva um `dist` parcial.

Para testar localmente o resultado compilado, mantenha o backend na porta 8000
e execute:

```bash
cd frontend
npm run preview -- --host 127.0.0.1 --port 4173
```

Abra `http://localhost:4173`. O `vite preview` é apenas uma validação local do
build, não um servidor recomendado para produção.

## 13. Produção Linux

O deploy suportado usa:

- FastAPI em `127.0.0.1:8000`, com um worker;
- Caddy em `:8080`, servindo `frontend/dist` e encaminhando `/api`;
- unidades systemd do usuário, sem executar a aplicação como root;
- backup SQLite verificado por timer opcional;
- Tailscale Serve como perfil recomendado para HTTPS remoto privado.

O caminho padrão versionado é:

```text
~/.local/share/filament-command-center/app
```

Arquivos de configuração:

```text
~/.config/filament-command-center/env
~/.config/filament-command-center/Caddyfile
~/.config/systemd/user/filament-command-center*.service
```

O procedimento completo de instalação, permissões, Caddy, serviços, logs,
backup, atualização, rollback e recuperação está no
[Production Runbook](docs/operations/production-runbook.md). Não use Uvicorn
com `--reload`, Vite dev ou Vite preview como serviço de produção.

### macOS e Windows em produção

O projeto ainda não fornece um deploy permanente homologado para launchd,
IIS, NSSM ou Windows Service. Para operar 24/7 nessas plataformas seria
necessário adaptar gerenciamento de processo, proxy reverso, permissões,
backups e inicialização automática. Essa adaptação não deve ser considerada
equivalente ao runbook Linux sem validação operacional própria.

## 14. Migrations e manutenção do schema

Consultar e atualizar a revisão atual:

### Linux/macOS, com o ambiente virtual ativo

```bash
cd backend
alembic current
alembic heads
alembic upgrade head
```

### Windows PowerShell

```powershell
Set-Location backend
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe heads
.\.venv\Scripts\alembic.exe upgrade head
```

Para desenvolvimento de schema:

```bash
alembic revision --autogenerate -m "descricao"
```

Revise a migration gerada antes de aplicá-la. Não substitua migrations por
`Base.metadata.create_all()` e não execute downgrade destrutivo em produção
sem um backup validado e um plano explícito.

## 15. Testes

### 15.1 Backend

Linux/macOS:

```bash
cd backend
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest
```

Windows PowerShell:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
```

Os testes usam bancos em memória ou diretórios temporários e não devem alterar
`data/filament.db`.

### 15.2 Frontend

```bash
cd frontend
npm ci
npm test
npm run typecheck
npm run build
```

Não há script de lint configurado atualmente.

### 15.3 Browser/E2E

```bash
cd frontend
npm run browser:doctor
npm run test:e2e
```

Outras suítes disponíveis:

```bash
npm run test:visual
npm run test:e2e:wave2
npm run test:e2e:production
```

Os testes Playwright dependem de um Chromium compatível. Consulte
[testes headless](docs/headless-browser-testing.md) antes de atualizar snapshots
visuais.

## 16. Dados, backup e restore

Dados padrão:

| Caminho | Conteúdo |
| --- | --- |
| `data/filament.db` | Dados canônicos SQLite. |
| `data/uploads/gcode/` | Uploads G-code gerenciados. |
| `data/print-jobs/` | Miniaturas derivadas de PrintJobs. |
| `backups/` | Backups operacionais verificados, quando utilizado. |

Crie um backup consistente com a aplicação em execução:

Linux/macOS:

```bash
cd backend
source .venv/bin/activate
python -m app.scripts.backup_database
```

Windows PowerShell:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m app.scripts.backup_database
```

O backup usa a API de backup do SQLite e gera um `.sqlite` mais um
`.manifest.json` com checksum e revisão. Não copie o arquivo SQLite ativo com
um `cp`/Explorer comum como estratégia de backup.

Antes de restaurar, pare completamente o backend. O fluxo protegido de restore
e a validação de integridade estão documentados no
[Production Runbook](docs/operations/production-runbook.md).

Exportações CSV servem para portabilidade e análise externa, mas não substituem
o backup SQLite completo. Consulte [CSV e portabilidade](docs/csv-export.md).

## 17. Atualização de uma instalação local

Antes de atualizar, faça backup do banco e confirme que o diretório de trabalho
não contém mudanças que seriam sobrescritas.

```bash
git status
git pull --ff-only
```

Depois atualize cada camada:

Linux/macOS:

```bash
cd backend
source .venv/bin/activate
python -m pip install -r requirements.txt
alembic upgrade head
cd ../frontend
npm ci
npm run build
```

Windows PowerShell:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\alembic.exe upgrade head
Set-Location ..\frontend
npm ci
npm run build
```

Reinicie os processos depois da atualização. Em produção Linux, use o helper e
o procedimento de rollback do runbook em vez desta sequência simplificada.

## 18. Funcionalidades e rotas da interface

| Rota | Função |
| --- | --- |
| `/inventory` | Inventário físico de spools. |
| `/dashboard` | Resumo operacional e itens que precisam de atenção. |
| `/printer-status` | Estado observado da P1S e AMS. |
| `/reconciliation` | Confirmação, correção e reversão de consumo. |
| `/prints` | Histórico e detalhes dos PrintJobs. |
| `/analytics` | KPIs, séries, rankings e exportação CSV. |
| `/gcode` | Upload e análise de G-code. |
| `/scan` | Leitura de QR de spool. |
| `/settings` | Idioma, documentação e configurações disponíveis. |
| `/settings/catalogs` | Catálogos de materiais e fabricantes. |

A raiz `/` redireciona para `/inventory`.

APIs principais:

- `/api/spools`, `/api/materials` e `/api/manufacturers`;
- `/api/prints`;
- `/api/reconciliation`;
- `/api/spools/{code}/calibrations` e `/api/tare-profiles`;
- `/api/analytics` e `/api/analytics/export`;
- `/api/gcode/uploads`;
- `/api/integrations/bambu/status`.

Use `/docs` para o contrato HTTP completo gerado pelo FastAPI.

## 19. Regras de segurança

- A aplicação não implementa autenticação ou autorização.
- Não exponha as portas 8000, 5173, 4173 ou 8080 diretamente à Internet.
- Não crie port forwarding público e não use Tailscale Funnel.
- Para acesso remoto, use uma Tailnet privada com ACLs e Tailscale Serve.
- Mantenha `BAMBU_ACCESS_CODE` fora do Git, logs e screenshots.
- O coletor P1S é somente leitura, mas o código LAN continua sendo um segredo.
- Em produção Linux, mantenha o arquivo de ambiente com permissão `0600` e os
  diretórios de dados/backups com acesso restrito ao usuário do serviço.

## 20. Solução de problemas

### O frontend abre, mas a API falha

Confirme que Uvicorn está ativo em `127.0.0.1:8000` e que o health check
responde. O proxy Vite de desenvolvimento aponta para essa porta.

### `npm ci` ou Vitest falha com Node incompatível

Confirme `node --version`. O projeto requer a linha Node 24, no mínimo 24.15.0
e abaixo da versão 25. Remova apenas `frontend/node_modules` e reinstale com
`npm ci` depois de corrigir a versão do Node; não edite o lockfile manualmente.

### `alembic` não é encontrado

Ative o ambiente virtual correto ou use o executável completo:

```text
Linux/macOS: backend/.venv/bin/alembic
Windows:     backend\.venv\Scripts\alembic.exe
```

### A porta já está em uso

Linux/macOS:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
lsof -nP -iTCP:5173 -sTCP:LISTEN
```

Windows PowerShell:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
Get-NetTCPConnection -LocalPort 5173 -State Listen
```

Encerre o processo antigo de forma normal antes de iniciar outra instância.

### O coletor P1S aparece desabilitado

Isso é normal sem as três variáveis obrigatórias. Com elas configuradas,
consulte `/api/integrations/bambu/status`, confirme IP/serial/código LAN e
verifique o firewall local para as portas 8883 e 990.

### Scanner QR não acessa a câmera

APIs de câmera normalmente exigem contexto seguro. `localhost` costuma ser
aceito para desenvolvimento; em outro dispositivo da LAN use o perfil HTTPS
privado descrito no runbook.

### Banco ou migration incorretos

Confirme que backend e Alembic receberam a mesma `DATABASE_URL`. Execute
`alembic current` e `alembic heads`; não apague o banco para contornar uma
falha sem antes criar e validar um backup.

## 21. Estrutura do repositório

```text
.
├── backend/
│   ├── alembic/          # migrations
│   ├── app/
│   │   ├── api/          # rotas FastAPI
│   │   ├── integrations/ # coletor Bambu P1S
│   │   ├── models/       # modelos SQLAlchemy
│   │   ├── schemas/      # contratos Pydantic
│   │   ├── services/     # regras de domínio
│   │   └── scripts/      # seeds, health, backup e restore
│   └── tests/
├── frontend/
│   ├── public/
│   └── src/
├── data/                 # dados locais de runtime
├── deploy/               # Caddy, environment e systemd
├── docs/                 # documentação técnica e manual do usuário
└── hardware/esp32/       # espaço reservado para firmware futuro
```

## 22. Documentação complementar

- [Manual do usuário](docs/user-guide/README.md)
- [Production Runbook](docs/operations/production-runbook.md)
- [Coletor local Bambu Lab P1S](docs/bambu-p1s.md)
- [Analytics API](docs/analytics-api.md)
- [CSV e portabilidade](docs/csv-export.md)
- [Análise e armazenamento de G-code](docs/gcode.md)
- [Formato dos QR codes](docs/qr-format.md)
- [Testes headless](docs/headless-browser-testing.md)

## 23. Idiomas

O frontend oferece Português (Brasil) e English. O idioma inicial é `pt-BR` e
a preferência fica em `localStorage`, na chave `fcc-language`.
