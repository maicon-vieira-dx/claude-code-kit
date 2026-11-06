#!/usr/bin/env node
// SubagentStart: injeta o PONTEIRO — não a doutrina — no contexto do filho.
//
// Subagente não herda skill, rule nem contexto de SessionStart. Hoje isso é
// tapado por cópia manual dentro de cada skill (improve copia as Hard Rules
// verbatim; bug-hunt cita o caminho do SKILL.md no prompt do lote), o que só
// funciona quando a skill é invocada E quem monta o prompt lembra. O handoff
// handoff entre duas skills de fluxo de PR falhou exatamente assim.
// A doutrina da casa já decidiu isto: o que precisa valer sempre, sem depender
// de o modelo escolher, é hook — prosa é probabilística.
//
// Classe: INJEÇÃO. FAIL-OPEN em todos os caminhos (JSON ilegível, agent_type
// ausente, erro de stdin, timeout). Um hook de contexto que falha fechado é
// pior que não existir, porque ninguém percebe.
//
// Orçamento: ~12 linhas, ~200 tokens por spawn. Ele garante o PONTEIRO, não o
// conteúdo — quem precisa da regra inteira abre o arquivo apontado.

const ROTEADOR = [
  'Você está num monorepo Nx (Angular 19 · NestJS).',
  '- `AGENTS.md` na raiz é a fonte canônica de engenharia; em conflito, ele vence.',
  '- `any` e `@ts-ignore` são proibidos em produção.',
  '- Nunca rodar `git commit`, `git add`, `git push` — são do usuário.',
  '- Vai tocar `libs/`? Mapeie com graphify antes; grep/find exploratório amplo ali é negado por hook.',
  '- Vai tocar `SKILL.md`, `AGENTS.md`, `CLAUDE.md` ou `.claude/rules/`? Invoque `struct-rules` antes.',
  '- Não reformate arquivo que você não editou.',
].join('\n');

function emitir() {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'SubagentStart',
        additionalContext: ROTEADOR,
      },
    }) + '\n',
  );
}

// Lê stdin com teto de tempo. O payload não muda o que é injetado — ele é lido
// só para não deixar o pipe pendurado. Qualquer desfecho leva ao mesmo emitir().
function main() {
  let encerrado = false;
  const fim = () => {
    if (encerrado) return;
    encerrado = true;
    emitir();
    process.exit(0);
  };

  const relogio = setTimeout(fim, 3000);
  relogio.unref?.();

  try {
    process.stdin.resume();
    process.stdin.on('data', () => {});
    process.stdin.on('end', fim);
    process.stdin.on('error', fim);
  } catch {
    fim();
  }
}

try {
  main();
} catch {
  emitir();
  process.exit(0);
}
