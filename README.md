# Catálogo Galeria Imobiliária - Scraper

Scraper profissional para coleta automatizada de imóveis do site Galeria Imobiliária, com geração de feeds CSV e XML para Meta Ads e Google Ads.

## Estrutura

```
catalogo-imoveis-galeria/
├── scraper.py           # Orquestrador principal
├── parser.py            # Parsing e extração de dados
├── feed_generator.py    # Geração de CSV e XML
├── diff_engine.py       # Comparação entre execuções
├── requirements.txt     # Dependências
├── output/              # Feeds finais (sempre refletem o sitemap atual)
│   ├── output.csv
│   └── output.xml
├── data/                # Snapshots para comparação
│   ├── previous_properties.json
│   └── current_properties.json
├── reports/             # Relatórios de mudanças
│   ├── new_properties.csv
│   ├── removed_properties.csv
│   ├── updated_properties.csv
│   └── summary.txt
└── logs/                # Logs de execução
```

## Instalação

```bash
pip install -r requirements.txt
```

## Uso

```bash
python scraper.py
```

## Como funciona a atualização

O **sitemap é a fonte da verdade**. A cada execução o scraper:

1. Lê o sitemap atual e coleta todos os imóveis
2. Compara com a execução anterior (via `data/previous_properties.json`)
3. Gera relatórios de diferenças em `reports/`
4. Sobrescreve `output.csv` e `output.xml` com **somente os imóveis ativos**
5. Rotaciona os snapshots (`current` vira `previous`)

### Regras do feed final

- Imóveis novos no sitemap entram automaticamente no feed
- Imóveis removidos do sitemap saem automaticamente do feed
- O feed final contém **apenas** imóveis presentes no sitemap atual
- Nunca mantém imóvel antigo que não está mais no sitemap
- O feed é sobrescrito a cada execução (sem acúmulo)

### Comparação entre execuções

O diff engine compara os IDs entre a execução anterior e a atual:

| Situação | Significado |
|---|---|
| ID existe no atual, não existia antes | Imóvel novo |
| ID existia antes, não existe mais | Imóvel removido/vendido/alugado |
| ID existe nos dois | Imóvel mantido |
| ID existe nos dois, com campo diferente | Imóvel atualizado |

Campos monitorados para detecção de atualização: `price`, `title`, `description`, `image_link`.

### Relatórios gerados

| Arquivo | Conteúdo |
|---|---|
| `reports/new_properties.csv` | Imóveis que entraram no catálogo |
| `reports/removed_properties.csv` | Imóveis que saíram do catálogo |
| `reports/updated_properties.csv` | Campos alterados (campo, valor antigo, valor novo) |
| `reports/summary.txt` | Resumo completo da comparação |

### Integração com Meta/Google Ads

Os feeds `output/output.csv` e `output/output.xml` podem ser servidos por URL pública para catálogos de anúncios. Como são regenerados do zero a cada execução, sempre refletem exatamente os imóveis ativos do sitemap.

## Configuração

Edite as constantes no início de `scraper.py`:

| Variável | Padrão | Descrição |
|---|---|---|
| `MAX_WORKERS` | 5 | Threads simultâneas |
| `REQUEST_TIMEOUT` | 30 | Timeout por request (s) |
| `MAX_RETRIES` | 3 | Tentativas por URL |
| `PARTIAL_SAVE_INTERVAL` | 50 | Salvar progresso a cada N imóveis |
