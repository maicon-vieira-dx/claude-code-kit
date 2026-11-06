---
name: playwright-validation
description: Valida comportamento visual. Modo diagnóstico analisa HTML/CSS estaticamente ANTES de screenshots. Modo validação captura screenshots para confirmar que uma correção funcionou. Nunca alterar código apenas com base em screenshot. Para achar a causa de um bug que já está acontecendo, ver `bug-diagnosis`.
allowed-tools: Read, Grep, Glob, Bash, Task
metadata:
  version: 2.1.0
---

# Dois Modos de Uso

**Diagnóstico** — causa raiz ANTES de alterar código. **Validação** — screenshots APÓS correção.

**Modo de falha:** o erro plausível é inverter a ordem — olhar o screenshot primeiro e já formular a causa a partir dele, tratando a imagem como diagnóstico em vez de confirmação. Screenshot mostra sintoma (algo deslocado), não causa (qual classe/regra fez deslocar); só o código lido na Etapa 1 explica o porquê.

Regras: screenshot é evidência, não diagnóstico. Nunca alterar CSS/HTML sem evidência visual. Nunca reportar PASS sem screenshot.

**Prints do usuário têm prioridade** — antes de qualquer automação, verificar `/tmp/*.png /tmp/*.jpg` com `ls -lt`. Se existirem: analisar com Read tool. Print do usuário = evidência válida.

---

# Modo Diagnóstico — Fluxo Obrigatório

## Etapa 1: Análise Estática (SEMPRE PRIMEIRO)

Antes de qualquer screenshot, ler os arquivos dos componentes envolvidos:

1. **Ler os HTMLs dos componentes** reportados com problema
2. **Ler os SCSSs** correspondentes
3. **Ler componentes shared** utilizados (wrappers, cards, containers)
4. **Buscar padrões problemáticos** com grep nos caminhos relevantes: `h-full`, `height: 100%`, `min-h-screen`, `flex-1`, `grow`, `min-h`, `min-height`
5. **Identificar a causa raiz** no código antes de prosseguir

**Padrões comuns de problema:**

| Padrão | Efeito | Componentes a verificar |
|--------|--------|------------------------|
| `h-full` em container | Expande para altura do pai | O componente e seus wrappers |
| `height: 100%` em SCSS `:host` | Mesmo efeito | Componentes shared (map, card) |
| `min-height` fixo | Não encolhe em telas pequenas | Componentes de mapa, modais |
| `flex-1` sem `min-h-0` | Overflow em flex container | Grid/flex containers |

## Etapa 2: Screenshot de Confirmação (se necessário)

Capturar screenshot APENAS se:
- A análise estática identificou problema mas precisa confirmar visualmente
- O usuário não enviou prints
- Precisa verificar breakpoints específicos

Se a análise estática já identificou a causa com clareza → ir direto para correção, sem screenshot.

## Etapa 3: Relatório do Diagnóstico

Reportar antes de qualquer alteração:
- Causa raiz identificada (arquivo, linha, classe)
- Por que causa o problema (explicação técnica)
- Solução proposta

---

# Modo Validação — Captura de Screenshots

Usar APENAS após correção aplicada.

## Gate 0 — Rota

**OBRIGATÓRIO antes de qualquer outro gate:** confirmar a rota exata da página a validar.

Se a rota não foi fornecida pelo usuário nem está óbvia pelo contexto:

1. Verificar o arquivo de rotas do componente alterado:
```bash
find . -name "lib.routes.ts" -o -name "app.routes.ts" | grep -v node_modules | grep -v dist
```

2. Ler o arquivo de rotas do feature afetado e rastrear o path completo (shell → feature → rota filha).

3. Se ainda incerto, **perguntar ao usuário**: _"Qual a rota no browser para acessar essa página?"_

Só avançar para Gate 1 com a rota confirmada.

## Gate 1 — Servidor

Sem `lsof` — não existe neste ambiente. Testar resposta HTTP, que é o que importa:

```bash
node -e "
const portas=[4200,4201,3000];
(async()=>{
  for(const p of portas){
    try{ const r=await fetch('http://localhost:'+p,{signal:AbortSignal.timeout(3000)}); console.log('UP:'+p+' ('+r.status+')'); return; }catch{}
  }
  console.log('NO_SERVER');
})();
" 2>&1
```

Se `NO_SERVER`: parar e informar `"Execute nx serve e me avise"`. Não tentar iniciar servidor.

## Gate 2 — Playwright funcional

**Nunca usar caminho absoluto de `node_modules`.** Resolver e guardar a variável — todos os scripts adiante usam `$PW`:

```bash
PW=$(node -e "
for(const m of ['playwright-core','playwright']){ try{ console.log(require.resolve(m)); process.exit(0) }catch{} }
console.log('NO_PLAYWRIGHT')
" 2>&1); echo "$PW"
[ "$PW" = "NO_PLAYWRIGHT" ] || node -e "require('$PW').chromium.launch({headless:true}).then(b=>b.close()).then(()=>console.log('OK')).catch(e=>console.log('FAIL:'+e.message.split('\n')[0]))" 2>&1
```

Se `NO_PLAYWRIGHT` ou `FAIL`: ir direto ao Fallback Manual. **Não instalar Playwright por conta própria** — é decisão do usuário (browser de ~150 MB, e esta máquina não tem privilégio de admin).

> **Estado conhecido em 14/ago/2026:** este gate **reprova** nesta máquina — nem `playwright-core` nem `playwright` resolvem, e não há cache `_npx`. O caminho automatizado está indisponível até que alguém instale. Todo o resto desta seção só passa a valer depois disso.

## Gate 3 — Auth (rotas protegidas)

Navegar para a rota e verificar URL final:

```bash
node -e "
const {chromium}=require('$PW');
(async()=>{
  const b=await chromium.launch({headless:true});
  const p=await b.newPage();
  await p.goto('http://localhost:4200/ROTA',{waitUntil:'networkidle',timeout:15000});
  console.log(p.url());
  await b.close();
})().catch(e=>console.log('FAIL:'+e.message));
" 2>&1
```

Se a URL final contém `/auth/login`, a rota é protegida por Firebase. **Nunca pedir `accessToken`, `refreshToken` ou qualquer valor de `stsTokenManager` ao usuário** — token colado no chat vira transcript em disco e trafega para o modelo. Usar sessão salva:

### Sessão salva (uma vez por expiração)

```bash
mkdir -p ~/.claude/.sessoes
node -e "
const {chromium}=require('$PW');
(async()=>{
  const b=await chromium.launch({headless:false});
  const ctx=await b.newContext();
  const p=await ctx.newPage();
  await p.goto('http://localhost:4200');
  console.log('>> Faça login nesta janela. O script salva sozinho e fecha.');
  await p.waitForURL(u=>!String(u).includes('/auth/login'),{timeout:300000});
  await ctx.storageState({path:process.env.HOME+'/.claude/.sessoes/app.json',indexedDB:true});
  console.log('SESSAO_SALVA');
  await b.close();
})().catch(e=>console.log('FAIL:'+e.message));
" 2>&1
```

- **Checkpoint:** este script abre browser visível e espera ação humana. Avisar o usuário e aguardar antes de rodar — nunca disparar no meio de outra tarefa.
- `indexedDB:true` exige Playwright **≥ 1.51**. Sem isso a sessão do Firebase não é capturada, e o Gate 3 continuará caindo em `/auth/login` — nesse caso, atualizar o Playwright, **não** voltar a pedir token.
- O arquivo fica em `~/.claude/.sessoes/`, fora de qualquer repositório. Nunca copiar o conteúdo dele para o chat, para o SKILL.md ou para o relatório.
- Nenhuma constante de projeto (`apiKey`, `appName`, `uid`, e-mail) entra neste arquivo de skill: tudo isso vem de dentro da sessão salva.

## Captura de Screenshots

Script único — preencher `ROTA`. Em rota pública, trocar `auth=true` por `false`; a sessão salva nem é lida.

```bash
node -e "
const {chromium}=require('$PW');
const url='http://localhost:4200/ROTA';
const auth=true; // false para rota pública
const estado=process.env.HOME+'/.claude/.sessoes/app.json';
const sizes=[{n:'mobile',w:375,h:812},{n:'tablet',w:768,h:1024},{n:'desktop',w:1440,h:900}];
(async()=>{
  const b=await chromium.launch({headless:true});
  for(const s of sizes){
    const ctx=await b.newContext(auth?{storageState:estado,viewport:{width:s.w,height:s.h}}:{viewport:{width:s.w,height:s.h}});
    const p=await ctx.newPage();
    await p.goto(url,{waitUntil:'networkidle',timeout:30000});
    console.log('URL ['+s.n+']:',p.url());
    await p.screenshot({path:'/tmp/screen_'+s.n+'.png',fullPage:true});
    await ctx.close();
    console.log('OK:'+s.n);
  }
  await b.close();
})().catch(e=>console.log('FAIL:'+e.message));
" 2>&1
```

**Critério que reprova a captura:** se alguma `URL [<tamanho>]` impressa contiver `/auth/login`, a sessão salva não carregou — o screenshot é da tela de login, não da página. Refazer a sessão salva; **não** capturar assim e **não** pedir token.

Após captura: ler cada screenshot com Read tool e analisar.

---

# Fallback Manual

Quando automação falha ou dependências ausentes:

> "Automação bloqueada ([motivo]). Tire prints no browser logado em:
> Mobile (375×812), Tablet (768×1024), Desktop (1440×900) via DevTools.
> Cole diretamente no chat."

Aguardar. Não tentar workarounds. Não alterar código sem evidência.

---

# O que esta skill escreve fora da sessão

| Caminho | O que é | Cuidado |
|---|---|---|
| `~/.claude/.sessoes/` (arquivo `app.json`, gerado em runtime) | Sessão autenticada do Firebase | **Contém credencial de sessão.** Fora de qualquer repositório. Nunca abrir com Read, nunca citar conteúdo, nunca colar no chat ou no relatório |
| `/tmp/screen_{mobile,tablet,desktop}.png` | Screenshots da captura | Sobrescritos a cada execução |

Nada mais é criado. Nenhuma dependência é instalada.

# Racionalizações barradas

| Desculpa | Por que está errada | Ação obrigatória |
|---|---|---|
| “É mais rápido pedir o token pro usuário do que montar sessão salva” | Token colado no chat vira transcript em disco e trafega para o modelo. Rápido uma vez, exposto para sempre | Rodar o script de sessão salva. Se o Playwright não suporta `indexedDB:true`, atualizar — nunca voltar ao token |
| “O caminho do `node_modules` funcionou da última vez, deixo fixo” | Foi exatamente assim que a skill quebrou: um path de `/home/` num Windows | Sempre resolver via Gate 2 e usar `$PW` |
| “A apiKey do Firebase é pública mesmo, pode ficar no arquivo” | Pública não é o ponto — ela envelhece, vaza contexto de projeto e some sozinha com a sessão salva | Zero constante de projeto neste arquivo |
| “O Gate 2 reprovou, mas dá pra instalar o Playwright rapidinho” | Baixa browser de ~150 MB, e esta máquina não tem privilégio de admin | Ir ao Fallback Manual e reportar `BLOCKED` |
| “O screenshot saiu, então passou” | Screenshot da tela de login também “sai” | Conferir a `URL [<tamanho>]` impressa antes de analisar qualquer imagem |

---

# Output

**Diagnóstico:**
- Arquivos lidos
- Causa raiz (arquivo:linha + padrão problemático)
- Solução proposta (ainda sem alterar código)

**Validação:**
- Screenshots lidos com Read tool
- Comparação com estado anterior (se disponível)
- `APROVADO` / `REPROVADO` / `BLOCKED`
  - REPROVADO: listar exatamente o que difere, com localização no código
  - BLOCKED: causa + próximos passos para o **usuário** (não tentar mais workarounds)

## Aviso de Cobertura

Se o protocolo não cobre o cenário atual, prosseguir e notificar:
> ℹ️ A skill `playwright-validation` não cobre este passo — prosseguindo com [breve descrição].
