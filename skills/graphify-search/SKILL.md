---
name: graphify-search
description: Pesquisa obrigatória em libs/ usando graphify antes de qualquer leitura de arquivo ou implementação. Cobre qual comando usar, armadilhas conhecidas e sequência de fallback. Para construir, atualizar ou exportar o grafo em si, ver `graphify`.
allowed-tools: Bash
metadata:
  version: 1.1.0
---

# Em uma linha

Antes de editar QUALQUER símbolo em `libs/`: `graphify explain "<Nome>"` para ver quem consome (são os afetados). É o passo que mais importa — não pule. Localizar arquivo de **config/build** (`project.json`, `tsconfig*`) NÃO é busca de código: `ls`/`Read` direto, sem graphify.

---

# Modo de falha

`grep`/`find` são o reflexo treinado para "achar onde está X" — mais rápidos de digitar que `graphify explain`, e sob pressão da tarefa (edição urgente, bug no meio de outra coisa) o impulso vence mesmo com esta skill carregada em contexto. O erro não é "esquecer que graphify existe" — é decidir, no momento, que desta vez grep é mais rápido e a consulta de consumidores pode vir depois. Não vem: o RCA registrado mostra o mesmo padrão em componente Angular — skill de destino ignorada porque o gatilho era semântico, não mecânico. Por isso as regras absolutas abaixo são bloqueio, não sugestão: se a tentação for "só essa vez, é rápido", essa é exatamente a vez que a skill existe para barrar.

---

# Racionalizações barradas

O modo de falha acima nomeia o impulso ("só essa vez"). Estas são as três desculpas que o vestem de argumento técnico:

| Desculpa | Por que está errada | Ação obrigatória |
| --- | --- | --- |
| "o gate libera grep pontual em `libs/`, então estou autorizado" | O hook libera localizar arquivo. Permissão de **localizar** não é permissão de pular a consulta de **consumidores** — são perguntas diferentes | rodar `graphify explain "<Símbolo>"` antes do `Edit`, mesmo tendo achado o arquivo por grep |
| "eu já sei quem consome esse símbolo" | Você sabe os consumidores de que lembra; o grafo lista os que você esqueceu. O risco não está na lista que você tem, está na que falta | rodar `explain` e comparar com a sua lista — se bater, custou 1 call |
| "o grafo está desatualizado, consultar não vale" | Grafo velho ainda nomeia candidatos. Desatualizado é diferente de inútil, e "não vale" é a porta do grep amplo | seguir a seção de staleness (`Read` direto só se o arquivo tem < 5 min) e declarar no relatório que o grafo é anterior à mudança |

---

# Regras absolutas

`find`, `grep`, `ls` são **PROIBIDOS** dentro de `libs/` — exceto nos dois casos abaixo:
- **Fallback de busca**: somente se todos os comandos graphify falharem (explain + query + path)
- **Busca de consumidores**: quando graphify estiver desatualizado (ver seção final)

Para código fora de `libs/` (ex: `apps/`), grep/find são permitidos diretamente.

---

# Verificação obrigatória de consumidores antes de editar

**Nunca editar um componente em `libs/` sem antes mapear onde é usado.**

```bash
graphify explain "NomeDoSimbolo"   # lista quem importa — esses são os afetados
```

**Se graphify estiver desatualizado**, `grep` é permitido exclusivamente para encontrar consumidores:
```bash
grep -r "NomeDoSimbolo\|app-seletor" apps/ libs/ --include="*.ts" --include="*.html" -l
```

Após mapear consumidores → fluxo obrigatório:
1. **É `*.component.ts`/`.html`? PARE — não edite ainda.** Mapear consumidores no graphify **não** dispensa a skill de componente: invoke your project's component-authoring skill, if you have one (it classifies and implements the smart/presentational branch) ANTES de qualquer `Edit`.
2. `Read` → `Edit` no arquivo alvo
3. `Read` → `Edit` em cada consumidor afetado

---

# Verificar existência de domínio ou lib

**Antes de qualquer query graphify**, consultar `architecture.md` — lista todos os domínios existentes.

Para confirmar se uma lib específica já existe estruturalmente:
```bash
graphify query "pedido shared domain" --dfs   # ✅ termos compostos e específicos
graphify query "pedido" --dfs                 # ❌ termo isolado → traz DTOs de outros domínios
```

---

# Qual comando usar

## 1. Nome conhecido → explain
```bash
graphify explain "ButtonComponent"
graphify explain "PedidoStore"
```
Retorna: arquivo + linha + conexões + quem importa. **Sempre tentar primeiro.**

## 2. Nome desconhecido → query --dfs
```bash
graphify query "validators cpf cnpj email" --dfs       # ✅ específico e composto
graphify query "toSelectOptions EnumsMapper" --dfs     # ✅

graphify query "endereco formulario" --dfs             # ❌ Endereco tem degree >150
graphify query "upload foto produto" --dfs             # ❌ termos ambíguos
```
Nunca usar palavras genéricas isoladas — explodem o resultado (80+ nós).

## 3. Ligação entre domínios distintos → path
```bash
graphify path "ClienteDto" "PedidoStore"  # ✅ ≤4 hops
```
Descartar se resultado ≥5 hops — caminho passa por intermediários sem significado.

---

# Fronteira com o grafo do Nx

Duas perguntas diferentes, dois donos. Confundir os dois é o que reintroduz roteamento não confiável.

| Pergunta | Dono |
| --- | --- |
| Onde está o símbolo? Quem consome isso? Que domínios se ligam? Já existe artefato equivalente? | **graphify** (esta skill, obrigatória por hook) |
| Que projetos existem? Que targets tem esse projeto? Qual o nome dele no Nx? Que tag ele carrega? | **config do Nx** — `ls`/`Read` em `project.json` e `nx.json`, que não são busca de código |

O graphify indexa **código dentro de `libs/`**. Ele não sabe o nome de projeto no Nx nem que targets
existem — isso vive em `project.json`, que é config, não código.

Erro de fronteira mais provável: usar graphify para descobrir o nome do projeto antes de rodar um teste.
Ele não responde, você conclui que "não achou", e cai no grep amplo — que o hook nega.

> Ler config **não** substitui esta skill em nada: `project.json` não conhece símbolo nem import.
> Nunca use config para encontrar consumidor antes de editar.

# Armadilhas conhecidas

**Colisão de nome** (ex: `InputComponent` existe em `ui-mobile` E `shared/frontend/ui`):
```bash
graphify explain "InputComponent shared frontend ui"          # adicionar contexto
graphify query "InputComponent formControlName nzStatus" --dfs # se ainda falhar
```

**`explain` retorna `No node found` — quatro causas:**

| Causa | Solução |
|-------|---------|
| Utilitária indexada por método | `graphify query "toSelectOptions EnumsMapper" --dfs` |
| Guard funcional (`guestGuard`, não `GuestGuard`) | `graphify explain "guestGuard"` |
| Nome indexado diferente | `graphify query "termos do contexto" --dfs` |
| **Grafo desatualizado** (arquivo recém-criado) | Ver abaixo |

**Grafo desatualizado (staleness):** arquivo criado há < 5 min + explain retorna "No node found".
- Criado recentemente? → usar `Read` direto, não aguardar reindexação
- Existia antes? → nome pode ter mudado; verificar `tsconfig.base.json`

**Explosão de nós (80+):** `explain` direto no símbolo em vez de `query` na categoria.
Nós confirmados com degree alto: `Endereco` (>150), `RegistrationStatus` (83), `PipesModule` (36).

---

# Sequência de fallback

```
1. explain "NomeExato"
   ✅ 1–10 nós → usar resultado
   ⚠️ 80+ nós → refinar: explain "NomeExato ContextoLib"
   ❌ "No node found" → ir para 2

2. query "NomeExato termo2 termo3" --dfs
   ✅ < 20 nós → usar resultado
   ❌ Nenhum resultado → ir para 3

3. Staleness? Arquivo criado nos últimos 5 min?
   SIM → usar Read direto (grafo ainda não indexou)
   NÃO → ir para 4

4. path "NóA" "NóB" (quando busca de relação)
   ✅ ≤ 4 hops → usar resultado
   ❌ → ir para 5

5. ÚLTIMO RECURSO:
   grep -r "NomeExato" libs/caminho/ --include="*.ts" -l
```

---

# Critério de parada

Antes de qualquer `Edit` em `libs/`, responder: **rodei `graphify explain`/`query` para este símbolo, e listei quem consome?** Se a resposta for "não, fui direto no grep porque parecia mais rápido" ou "não, achei que não precisava desta vez" — reprova. Voltar ao passo 1 da sequência de fallback antes de editar.

---

## Aviso de Cobertura

Se o protocolo não cobre o cenário atual, prosseguir e notificar:
> ℹ️ A skill `graphify-search` não cobre este passo — prosseguindo com [breve descrição].
