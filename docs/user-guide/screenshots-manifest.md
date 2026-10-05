# Manifesto de screenshots do manual

As imagens são geradas por `npm run docs:screenshots` a partir de um banco SQLite temporário. O cenário acompanha os mesmos Spools e impressões em todas as telas. O tema é claro e o idioma é `pt-BR`.

| Arquivo | Rota | Finalidade e estado | Viewport | Seção | Cenário de dados |
|---|---|---|---|---|---|
| `desktop/01-dashboard.png` | `/dashboard` | Visão geral, indicadores, materiais e alertas | 1440 × 900 | Painel | Oito Spools ativos; um baixo, um vazio e um para secagem |
| `desktop/02-dashboard-attention.png` | `/dashboard` | Lista de Spools que precisam de atenção | 1440 × 900 | Painel | Mesmo inventário do manual |
| `desktop/03-inventory-table.png` | `/inventory` | Inventário em Tabela | 1440 × 900 | Inventário | Spools `FIL-0001` a `FIL-0008` |
| `desktop/04-inventory-grid.png` | `/inventory` | Inventário em Grade | 1440 × 900 | Inventário | Mesmo inventário em outra visualização |
| `desktop/05-inventory-filters.png` | `/inventory` | Painel de filtros aberto | 1440 × 900 | Busca e filtros | Catálogos e intervalos disponíveis |
| `desktop/06-inventory-search.png` | `/inventory?search=Orange` | Resultado de busca por cor/nome | 1440 × 900 | Busca | Polymaker Orange |
| `desktop/07-new-spool-basic.png` | `/inventory/new` | Formulário básico preenchido e nome sugerido | 1440 × 900 | Novo Spool | Bambu Lab PLA Verde Jade |
| `desktop/08-new-spool-purchase.png` | `/inventory/new` | Compra, temperaturas e status inicial | 1440 × 900 | Novo Spool | Mesmo novo Spool |
| `desktop/09-spool-details.png` | `/spools/FIL-0001` | Cabeçalho, peso, configurações e informações | 1440 × 900 | Detalhes do Spool | Bambu Lab Black após impressão concluída |
| `desktop/10-spool-qr.png` | `/spools/FIL-0001` | Cartão de QR e ação de download | 1440 × 900 | QR Code | Bambu Lab Black |
| `desktop/11-spool-archive-dialog.png` | `/spools/FIL-0003` | Confirmação de arquivamento | 1440 × 900 | Arquivar e excluir | eSUN TPU Red |
| `desktop/12-qr-landing.png` | `/qr/spool/FIL-0001` | Consulta rápida aberta pelo QR | 1440 × 900 | QR Code | Bambu Lab Black |
| `desktop/13-qr-scanner.png` | `/scan` | Scanner e alternativa por código | 1440 × 900 | Escanear QR | Câmera ainda não iniciada |
| `desktop/14-print-tracker.png` | `/prints` | Listas Em andamento, Planejadas e Concluídas | 1440 × 900 | Print Tracker | Organizador modular, Dragon Miniature e histórico |
| `desktop/15-new-print-multi-spool.png` | `/prints/new` | Dois Spools, pesos e custo ao vivo | 1440 × 900 | Nova impressão | Dragon Miniature, PLA preto + PETG laranja |
| `desktop/16-planned-print.png` | `/prints/3` | Detalhes no estado Planejada | 1440 × 900 | Ciclo da impressão | Dragon Miniature |
| `desktop/17-start-print-dialog.png` | `/prints/3` | Confirmação de início e reserva dos Spools | 1440 × 900 | Iniciar impressão | Dragon Miniature |
| `desktop/18-printing.png` | `/prints/4` | Detalhes no estado Imprimindo | 1440 × 900 | Ciclo da impressão | Organizador modular |
| `desktop/19-finish-print-dialog.png` | `/prints/4` | Consumo conhecido em um Spool e parcial no outro | 1440 × 900 | Finalizar impressão | Organizador modular |
| `desktop/20-finished-print.png` | `/prints/1` | Estimado versus real e linha do tempo | 1440 × 900 | Histórico da impressão | Suporte articulado, consumo total 190,8 g |
| `desktop/21-gcode-upload.png` | `/gcode` | Estado inicial de upload | 1440 × 900 | G-code | Nenhum arquivo selecionado |
| `desktop/22-gcode-selected.png` | `/gcode` | Arquivo válido selecionado | 1440 × 900 | G-code | `dragon-multicolor.gcode` |
| `desktop/23-gcode-summary.png` | `/gcode` | Resumo da análise e extrusão por ferramenta | 1440 × 900 | Análise de G-code | G-code demonstrativo T0/T1 |
| `desktop/24-gcode-material-detection.png` | `/gcode` | Materiais detectados com confiança e fonte | 1440 × 900 | Detecção de material | PLA em T0 e PETG em T1, metadata do slicer |
| `desktop/25-gcode-time.png` | `/gcode` | Estimativa de tempo do slicer | 1440 × 900 | Tempo estimado | 1 h 13 min |
| `desktop/26-gcode-weight.png` | `/gcode` | Materiais, diâmetros e peso calculado | 1440 × 900 | Peso estimado | T0 PLA e T1 PETG |
| `desktop/27-settings.png` | `/settings` | Idioma e download do manual | 1440 × 900 | Configurações | Português (Brasil) |
| `mobile/01-inventory.png` | `/inventory` | Inventário em tela estreita | 390 × 844 | Uso no celular | Mesmo inventário |
| `mobile/02-new-spool.png` | `/inventory/new` | Cadastro em tela estreita | 390 × 844 | Uso no celular | Bambu Lab PLA Verde Jade |
| `mobile/03-new-print.png` | `/prints/new` | Blocos de Spools e custo em tela estreita | 390 × 844 | Uso no celular | Dragon Miniature |
| `mobile/04-qr-scanner.png` | `/scan` | Scanner e fallback móvel | 390 × 844 | Uso no celular | Câmera ainda não iniciada |
| `mobile/05-gcode.png` | `/gcode` | Seleção de G-code no celular | 390 × 844 | Uso no celular | `dragon-multicolor.gcode` |
| `mobile/06-settings.png` | `/settings` | Idioma e download no celular | 390 × 844 | Uso no celular | Português (Brasil) |

Os IDs das impressões são determinados pela ordem fixa de criação do fixture. Os códigos de Spool são gerados pelo produto, também em ordem fixa no banco temporário.

## Wave 2 — capturas direcionadas

`FCC_WAVE2_SCREENSHOTS=1 npm run test:e2e:wave2 -- --project=wave2` usa Chromium
e um banco temporário vazio; os cadastros são feitos pela interface. Somente
imagens das mudanças de onboarding são geradas, sem recapturar a coleção inteira.

| Arquivo | Rota | Estado | Viewport |
|---|---|---|---|
| `wave2/empty-inventory-desktop.png` | `/inventory` | Primeiro uso, pt-BR, sem Spools | 1280 × 720 |
| `wave2/catalogs-desktop.png` | `/settings/catalogs` | Fabricante e material criados pelo browser | 1280 × 720 |
| `wave2/catalogs-mobile.png` | `/settings/catalogs` | Mesmo catálogo em pt-BR no celular | 390 × 844 |
