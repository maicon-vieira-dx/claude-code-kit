> Referência da skill `plan-generation`. **Abrir quando** o pedido citar `.specs/`, um `tasks.md` ou o
> `tlc-spec-driven`. Contém: quem é dono de quê no fluxo de specs do repositório e a regra de fonte única.

## Precedência com o fluxo de specs (`tlc-spec-driven`)

Em repositório que adotou o `tlc-spec-driven` (decisão registrada em `.specs/STATE.md`),
toda feature nova nasce em `.specs/features/<nome>/` com `spec.md`, `design.md` e
`tasks.md`, e o próprio `tasks.md` abre com um "Execution Protocol" que manda executar pelo
`tlc-spec-driven`.

| Pedido | Dono |
| --- | --- |
| Especificar feature nova (spec, design, tasks) | `tlc-spec-driven` |
| **Executar tarefas de um `tasks.md` de `.specs/`** | `tlc-spec-driven` (fluxo Execute dele) — **não** esta skill |
| Implementação não trivial **fora** de `.specs/` | esta skill |
| Plano pedido sobre uma feature de `.specs/` | esta skill, referenciando o `tasks.md` |

**Regra de fonte única:** quando a origem é uma feature de `.specs/`, o `tasks.md` dela é a **única**
lista de tarefas. O plano em `.claude/plans/<slug>.md` **referencia** o caminho e registra só o que é
dele — decisões D0–D6, contexto, gates e estado —, **nunca** copia as tarefas.

**Modo de falha:** copiar a lista "para ficar tudo num lugar só". As duas listas divergem no primeiro
`- [x]` marcado de um lado só, e a partir daí ninguém sabe qual vale.
