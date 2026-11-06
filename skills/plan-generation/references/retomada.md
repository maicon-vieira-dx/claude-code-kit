> Referência da skill `plan-generation`. **Abrir quando** a sessão foi limpa ou compactada
> no meio de uma execução, ou quando um passo falhou duas vezes. Contém: como retomar do
> arquivo do plano e o protocolo de três tentativas.

# Retomada — sobreviver a `/clear` e à compactação

O plano em `.claude/plans/<slug>.md` é o **único** estado que atravessa a perda de contexto. Ele só cumpre
esse papel se a seção `## Estado` estiver atualizada — plano gravado uma vez e nunca mais tocado é
documento morto, não mecanismo de retomada.

**Quando gravar:** ao fechar cada passo, e ao aprender qualquer coisa que contradiga o plano. Não a cada
leitura de arquivo — isso vira ruído e custo.

**Ao retomar (contexto novo, plano já existe), responda pelo arquivo antes de tocar em código:**

1. O que estamos construindo, e qual é o critério de pronto?
2. Qual foi o último passo **fechado** (gate passou)?
3. Qual é o próximo passo, e de que ele depende?
4. O que já foi tentado e falhou neste passo?
5. Que decisão (D0–D4) foi tomada e não pode ser re-decidida agora?

Alguma sem resposta no arquivo → o plano está incompleto: complete-o **antes** de continuar. Retomar
adivinhando é como o mesmo trabalho é refeito duas vezes.

## Retomar por comando (depois de um checkpoint)

`/plan-generation retomar <slug>`, numa sessão limpa:

1. **Não** chame `EnterPlanMode` nem refaça as Fases 0–3: o plano já foi aprovado, e a prova é a linha
   `**Aprovado:**` do `## Estado`. Sem ela, a retomada não vale — volte à Fase 0.
2. Leia `.claude/plans/<slug>.md` com `Read`. É essa leitura que liga o plano à sessão no guard; por
   shell, não liga.
3. Responda as cinco perguntas acima pelo arquivo e siga do **Próximo passo**.
4. Releia só os arquivos do próximo passo. A conversa anterior não volta — é esse o ponto.

## Protocolo de três tentativas

Contabilize em `## Estado → Tentativas`. Falhou o mesmo gate:

| Tentativa | Ação |
| --- | --- |
| 1 | Corrigir e repetir |
| 2 | **Parar de tentar o mesmo.** Registrar em `## Estado` o que falhou e por quê; mudar de abordagem |
| 3 | **Parar de verdade.** Reportar ao usuário: o que foi tentado, o que o gate diz, e as opções |

A terceira tentativa idêntica nunca passa — o que falta é informação, não insistência.

---
