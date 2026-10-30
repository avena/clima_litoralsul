# Deploy na Netlify

O painel é estático: a Netlify builda `site/` com Vite e publica `dist/`. Não há
backend, nem função, nem variável secreta obrigatória.

## Configuração do site

No assistente **Configure project and deploy** (o da captura), os campos são:

| Campo | Valor | Por quê |
|---|---|---|
| Branch to deploy | `main` | histórico linear, deploy a cada push |
| **Base directory** | **`site`** | o `package.json` está em `site/`, não na raiz. **Vazio aqui o build falha** |
| Build command | `npm run build` | roda dentro de `site/` |
| Publish directory | `dist` | relativo a `site/` → publica `site/dist` |
| Functions directory | *(deixe vazio)* | não há funções |

Os mesmos valores estão em `netlify.toml` na raiz (`base = "site"`). Se o painel
já mostrou build `npm run build` e publish `dist` sozinho, **confira o Base
directory**: com ele vazio a Netlify procura `package.json` na raiz e o deploy
morre com `Missing script: build`.

Se preferir não depender do painel, apague os campos opcionais e deixe o
`netlify.toml` mandar — ele já define base, comando, publish e cache.

## Antes do primeiro deploy

`site/public/dados.json` é versionado (40 KiB) justamente porque a Netlify não
tem acesso a `dados/clima.sqlite`, que é gitignorado. Se ele faltar, o build
passa mas o painel abre com "Não foi possível carregar dados.json":

```bash
python3 relatorio.py                       # regenera site/public/dados.json
git add site/public/dados.json && git commit -m "chore(dados): atualiza a série"
git push
```

## Atualizar os dados depois

```bash
python3 coletor.py coletar --desde 2000-01 --ate 2026-10   # ou cron
./deploy.sh                                                # JSON novo + build + push
```

`./deploy.sh` roda `relatorio.py`, os 26 testes, o `npm run check`, o build,
commita só `site/public/dados.json` e faz push — a Netlify rebuilda sozinha.

A data que aparece no rodapé ("Dados sincronizados em") é a do `dados.json`, não
a do build. O hash e a hora do rodapé vêm do build (`vite.config.js` lê
`COMMIT_REF`).

## Deploy hook (opcional)

Só é necessário se você quiser disparar build **sem push** (ex.: cron que
commitou direto no servidor). Netlify → Site configuration → Build & deploy →
Build hooks → Add build hook; salve a URL em *Secrets* → `NETLIFY_DEPLOY_HOOK_URL`
no GitHub. O workflow `.github/workflows/deploy.yml` usa esse secret quando ele
existe; sem ele, o passo é pulado.

## Conferir depois do deploy

- `https://clima-litoralsul.netlify.app/` abre com os 17 cards de município.
- Trocar de cidade muda a URL para `#/registro` sem recarregar.
- `https://clima-litoralsul.netlify.app/dados.json` responde 200 com o JSON.
- `/<hash>.js` e `.css` em `/assets/` vêm com `cache-control: immutable`
  (`netlify.toml`).

## Problemas comuns

| Sintoma | Causa |
|---|---|
| `Missing script: "build"` | Base directory vazio |
| Painel abre com erro de `dados.json` | o JSON não foi commitado |
| 404 ao abrir `#/registro` | a rota é hash de propósito — não precisa de rewrite; 404 aqui é rewrite forçado no painel |
| Dados velhos no ar | commitou só código; rode `relatorio.py` e commite o JSON |
