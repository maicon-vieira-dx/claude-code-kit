> Template da skill `plan-generation`. **Abrir quando** a D3 der **subagente** — e só
> nesse caso. Contém: o prompt de delegação e o que ele obriga a carregar.

# Prompt de delegação (só se D3 = subagente)

O subagente **começa com contexto zerado** — não herda a conversa nem os arquivos lidos. O único handoff é
o prompt + o arquivo do plano. **Um prompt por camada** (nunca o plano inteiro num spawn só): a camada é
o lote, e o gate dela é o que você verifica antes de despachar a próxima.

```
Task(subagent_type: "general-purpose", model: "<nível baixo do provedor — nunca omitido>",
  prompt: "Execute APENAS o passo <N> (camada <X>) de .claude/plans/<slug>.md, LITERALMENTE.
   Não re-analise, não explore, não avance para o passo seguinte.
   Arquivos-alvo: <lista exata>. NÃO leia: <lista>.
   Aplique os blocos de código do plano como estão. TDD: spec primeiro, RED, depois produção.
   Gate: <comando com output esperado>. STOP e reporte se o gate falhar.
   Devolva SÓ, em no máximo 15 linhas: (a) lista de arquivos alterados; (b) output literal do gate;
   (c) toda divergência entre
   o plano e o que de fato compilou — assinatura, caminho de import ou nome de campo que você teve de
   mudar, e por quê. NÃO devolva o conteúdo dos arquivos nem narrativa do que fez.")
```

O prompt acima só funciona se a **D5** entregou conteúdo literal: "aplique os blocos de código do plano"
pressupõe que existam blocos de código no plano.

O **contrato de retorno enxuto é controle de custo**, não formalidade — na medição, a sessão sem contrato
emitiu 7–34× mais output.

**Escrever o arquivo e devolver o caminho NÃO é resumo** — e é o modo de falha mais caro da delegação. O
pai não recebeu informação, recebeu um ponteiro: para saber o que aconteceu tem de ler tudo de volta,
pagando exatamente a releitura que a delegação existia para evitar. No piloto de construção, o
orquestrador que recebeu arquivos em vez de resumo acumulou releitura de janela equivalente a **2,5× a
sessão solo inteira** e gastou 24 Edit para 3 Write reintegrando o que não escreveu — a primeira
integração dos três subagentes trouxe ~70 erros de compilação, todos de contrato que o prompt não ditou.
O item **(c)** é o que substitui a releitura: divergência declarada é barata, divergência descoberta é
uma rodada de integração inteira.

E **o retorno do subagente nunca é aceito sem verificação sua** (`ngc`, `lint`, `git diff` sem `any`).

## Modelo e papel do pai (medido no S010, 2026-10-08)

- **Nível baixo do provedor** para passo literal com gate determinístico: é o que o S010 mediu. Nível
  intermediário só quando o passo obriga o subagente a decidir um contrato que o plano não ditou (não
  medido; espere ~1,5× o custo do nível baixo, pelo único par comparável). **Nunca** o nível alto;
  **nunca** omitido.
- **O apelido não é o modelo.** O apelido de um nível já passou a resolver para outro modelo entre duas
  versões do CLI, sem aviso. Registre na Fase 5 o id efetivo (comando na seção `## Verificação` do template).
- **O pai não escreve código enquanto delega.** Com "Não escreva código você mesmo" no próprio prompt, o
  pai fez 0 Edit e 0 Write em 6 de 6 trials. É o que mantém a janela dele magra. Gate do subagente
  vermelho → redespache o passo com a divergência em vez de consertar no pai (inferido, não medido).
- **Verificar não é reler.** O pai confere por comando (`ngc`, vitest, `git diff --stat`) e só abre um
  arquivo escrito pelo subagente quando o gate dele falhou.

---
