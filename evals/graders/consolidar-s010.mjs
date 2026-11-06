#!/usr/bin/env node
// Plano 005: extrai de runs/ TODOS os números que o relatório consolidado do S010 cita, cada um com a
// origem. Somente leitura sobre runs/, scenarios/ e graders/; escreve só em --out. Não estima nada:
// campo sem arquivo de origem sai null, e toda divergência entre fontes entra em `anomalias`.
//
// Uso:
//   node consolidar-s010.mjs --out <dir>                    # grava <dir>/dados.json e <dir>/tabelas.md
//   node consolidar-s010.mjs --out <dir> --runs <dir-runs>  # padrão: <evals>/runs
//   node consolidar-s010.mjs --out <dir> --evals <raiz>     # padrão: .. relativo a este arquivo
//
// Plano 007 (2026-09-29): (1) runs listados em scenarios/S010-replay-pr-real/runs-fora-do-relatorio.tsv
// não entram em nada do que este script grava — o relatório cobre só a medição com o modelo sonnet
// vigente (MODELO_SONNET_MEDIDO); (2) cada run ganha `aceite` (estrito, funcional, cobertura) calculado
// por graders/aceite-funcional.mjs (plano 006), e "aprovado" passa a ser o aceite funcional.

import { readFileSync, readdirSync, writeFileSync, mkdirSync, existsSync, statSync } from 'node:fs';
import { homedir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { carregarContexto, avaliarAceite } from './aceite-funcional.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ---- args ----
const args = process.argv.slice(2);
const getArg = (name, def) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : def;
};
const EVALS = getArg('--evals', join(__dirname, '..'));
const SCEN = join(EVALS, 'scenarios', 'S010-replay-pr-real');
const RUNS = getArg('--runs', join(EVALS, 'runs'));
const PROJECTS = getArg('--projects', join(homedir(), '.claude', 'projects'));
const OUT = getArg('--out', null);
if (!OUT) {
  console.error('ERRO: --out <dir> obrigatório');
  process.exit(2);
}

const readJson = (p) => {
  try {
    return JSON.parse(readFileSync(p, 'utf8'));
  } catch {
    return null;
  }
};
// session-*.json|.log = saída `--output-format json` do CLI; a última linha é o objeto `result`.
const readSession = (p) => {
  try {
    const linhas = readFileSync(p, 'utf8').trim().split('\n');
    return JSON.parse(linhas[linhas.length - 1]);
  } catch {
    return null;
  }
};
const r4 = (x) => (x == null || Number.isNaN(x) ? null : Math.round(x * 10000) / 10000);
const r1 = (x) => (x == null || Number.isNaN(x) ? null : Math.round(x * 10) / 10);
const slug = (s) => s.replace(/[^A-Za-z0-9]/g, '-');

// Tarifa vigente do grader de custo: tokens.json com prices_version diferente foi custeado com outra tabela.
const PRICES_VERSION =
  (readFileSync(join(EVALS, 'graders', 'token-usage.mjs'), 'utf8').match(/const PRICES_VERSION = '([^']+)'/) || [])[1] ?? null;

// ---- tasks.tsv: id -> tarefa vigente ----
const tasks = {};
for (const linha of readFileSync(join(SCEN, 'tasks.tsv'), 'utf8').trim().split(/\r?\n/).slice(1)) {
  const [id, sha, regime, libs, budget, ref] = linha.split('\t');
  tasks[id] = { id, sha, regime, libs: libs.split(','), budget_usd: Number(budget), hidden_total_ref: Number(ref) };
}

// ---- plano 007: medição vigente e runs fora do relatório ----
// Modelo sonnet da medição que o relatório cobre. Run que sobrar com outro id vira anomalia
// `modelo_fora_da_medicao` (esqueceram de listá-lo em runs-fora-do-relatorio.tsv).
const MODELO_SONNET_MEDIDO = 'claude-sonnet-5-5';
const FORA = new Set();
const foraTsv = join(SCEN, 'runs-fora-do-relatorio.tsv');
if (existsSync(foraTsv))
  for (const linha of readFileSync(foraTsv, 'utf8').trim().split(/\r?\n/).slice(1)) if (linha.trim()) FORA.add(linha.split('\t')[0].trim());
const ACEITE_CTX = carregarContexto(EVALS);

// ---- sequencia-S010-<data>_<hora>.log: "<braço>\t<tarefa>\tt<n>\texit=<c>\t<min>min" ----
const seq = [];
for (const f of readdirSync(RUNS).filter((f) => /^sequencia-S010-.*\.log$/.test(f))) {
  const dia = f.match(/sequencia-S010-(\d{4}-\d{2}-\d{2})/)[1];
  for (const l of readFileSync(join(RUNS, f), 'utf8').replace(/^﻿/, '').split(/\r?\n/)) {
    const m = l.match(/^([SPGCV])\t(T\d+)\tt(\d+)\texit=(-?\d+)\t([\d.]+)min/);
    if (m) seq.push({ dia, arm: m[1], task: m[2], trial: Number(m[3]), exit: Number(m[4]), min: Number(m[5]), arquivo: f });
  }
}

// Fases por braço (run-trial.sh). G2 e V3 são `--resume`: o total_cost_usd delas é CUMULATIVO com a
// sessão retomada (G1, V1), então o custo próprio da fase = reportado − reportado da retomada.
const FASES = { S: ['S'], P: ['P1', 'P2'], G: ['G1', 'G2'], C: ['C'], V: ['V1', 'V2', 'V3'] };
const RETOMA = { G2: 'G1', V3: 'V1' };
const MODELO_DA_FASE = { S: 'sonnet', C: 'sonnet', P1: 'sonnet', P2: 'haiku', G1: 'sonnet', G2: 'haiku', V1: 'opus', V2: 'sonnet', V3: 'opus' };

const anomalias = [];
const anota = (run, tipo, detalhe) => anomalias.push({ run, tipo, detalhe });

const runs = [];
const dirs = readdirSync(RUNS)
  .filter((d) => /^\d{4}-\d{2}-\d{2}-S010-[SPGCV]-T\d+-t\d+$/.test(d) && statSync(join(RUNS, d)).isDirectory() && !FORA.has(d))
  .sort();

for (const run of dirs) {
  const [, data, arm, task, trial] = run.match(/^(\d{4}-\d{2}-\d{2})-S010-([SPGCV])-(T\d+)-t(\d+)$/);
  const dir = join(RUNS, run);
  const grade = readJson(join(dir, 'grade.json'));
  const win = readJson(join(dir, 'window.json'));
  const tok = readJson(join(dir, 'tokens.json'));
  const tarefa = tasks[task];

  // sha: window.json grava desde a revisão 3; antes disso só o relint gravou no grade.json.
  const sha = win?.sha ?? grade?.sha ?? null;
  const sha_fonte = win?.sha ? 'window.json' : grade?.sha ? 'grade.json' : null;
  if (!win?.sha) anota(run, 'sha_fora_do_window', `window.json sem sha; sha=${sha ?? 'desconhecido'} (fonte: ${sha_fonte ?? 'nenhuma'})`);
  const vigente = !!tarefa && sha === tarefa.sha;
  const teto = win?.budget_usd != null ? Number(win.budget_usd) : null;

  if (!grade) anota(run, 'sem_grade', 'grade.json ausente ou ilegível');
  if (!tok) anota(run, 'sem_tokens', 'tokens.json ausente ou ilegível');

  // ---- sessões do CLI ----
  const sessoes = [];
  const reportado = {};
  for (const fase of FASES[arm]) {
    const arq = [`session-${fase}.json`, `session-${fase}.log`].find((f) => existsSync(join(dir, f)));
    const s = arq ? readSession(join(dir, arq)) : null;
    if (!s) {
      anota(run, 'sessao_ausente', `fase ${fase}: arquivo de sessão ausente ou sem JSON`);
      sessoes.push({ fase, arquivo: arq ?? null });
      continue;
    }
    reportado[fase] = s.total_cost_usd;
    const proprio = RETOMA[fase] ? s.total_cost_usd - (reportado[RETOMA[fase]] ?? 0) : s.total_cost_usd;
    const sessao = {
      fase,
      arquivo: arq,
      modelo_pedido: MODELO_DA_FASE[fase],
      modelos: Object.keys(s.modelUsage || {}),
      subtype: s.subtype,
      is_error: !!s.is_error,
      num_turns: s.num_turns,
      duracao_min: r1((s.duration_ms ?? 0) / 60000),
      retomada: !!RETOMA[fase],
      cli_usd_reportado: r4(s.total_cost_usd),
      cli_usd_proprio: r4(proprio),
      pct_teto: teto ? r4(proprio / teto) : null,
    };
    sessoes.push(sessao);
    if (s.is_error || s.subtype !== 'success') anota(run, 'sessao_com_erro', `fase ${fase}: subtype=${s.subtype} is_error=${s.is_error}`);
    if (teto && proprio >= 0.9 * teto) anota(run, 'perto_do_teto', `fase ${fase}: US$ ${r4(proprio)} = ${Math.round((proprio / teto) * 100)}% do --max-budget-usd ${teto}`);
  }

  // ---- custo (fonte única: tokens.json) ----
  let custo = null;
  if (tok) {
    const fases = {};
    for (const f of readdirSync(dir).filter((f) => /^tokens-.+\.json$/.test(f))) {
      const t = readJson(join(dir, f));
      fases[f.replace(/^tokens-|\.json$/g, '')] = t ? { usd: t.totals.cost_usd, modelos: Object.keys(t.by_model) } : null;
    }
    const somaFases = Object.keys(fases).length ? Object.values(fases).reduce((a, x) => a + (x?.usd ?? 0), 0) : null;
    const cliTotal = sessoes.every((s) => s.cli_usd_proprio != null) ? sessoes.reduce((a, s) => a + s.cli_usd_proprio, 0) : null;
    const rub = tok.totals.cost_usd_by_rubric;
    custo = {
      total_usd: tok.totals.cost_usd,
      prices_version: tok.prices_version,
      por_modelo: Object.fromEntries(Object.entries(tok.by_model).map(([k, v]) => [k, v.cost_usd])),
      por_rubrica: rub,
      rubrica_dominante: Object.entries(rub).sort((a, b) => b[1] - a[1])[0][0],
      fases,
      soma_fases: r4(somaFases),
      residuo_fases: somaFases == null ? null : r4(somaFases - tok.totals.cost_usd),
      cli_total_usd: r4(cliTotal),
      residuo_cli: cliTotal == null ? null : r4(cliTotal - tok.totals.cost_usd),
      unpriced_models: tok.unpriced_models ?? [],
    };
    if (tok.prices_version !== PRICES_VERSION) anota(run, 'tarifa_antiga', `tokens.json prices_version=${tok.prices_version}; vigente=${PRICES_VERSION}`);
    if (custo.unpriced_models.length) anota(run, 'modelo_sem_tarifa', custo.unpriced_models.join(','));
    if (custo.residuo_fases != null && Math.abs(custo.residuo_fases) > 0.001)
      anota(run, 'fases_nao_somam_total', `soma das fases US$ ${custo.soma_fases} vs tokens.json US$ ${custo.total_usd} (resíduo ${custo.residuo_fases})`);
    if (custo.residuo_cli != null && Math.abs(custo.residuo_cli) > 0.001)
      anota(run, 'cli_diverge_do_grader', `CLI (custo próprio somado) US$ ${custo.cli_total_usd} vs tokens.json US$ ${custo.total_usd} (resíduo ${custo.residuo_cli})`);
  }

  // ---- ferramentas ----
  let ferramentas = null;
  if (tok?.tool_calls) {
    const tc = tok.tool_calls;
    const pai = tc.by_owner?.pai ?? { total: 0, by_tool: {} };
    const sub = tc.by_owner?.subagente ?? { total: 0, by_tool: {} };
    ferramentas = {
      total: tc.total,
      pai: pai.total,
      subagente: sub.total,
      pai_edit: pai.by_tool?.Edit ?? 0,
      pai_write: pai.by_tool?.Write ?? 0,
      sub_edit: sub.by_tool?.Edit ?? 0,
      sub_write: sub.by_tool?.Write ?? 0,
      ew_pai: pai.edit_write_ratio ?? null,
      ew_sub: sub.edit_write_ratio ?? null,
      por_ferramenta_pai: pai.by_tool ?? {},
      por_ferramenta_sub: sub.by_tool ?? {},
    };
  }

  // ---- tempo ----
  const janela = tok?.window ? (Date.parse(tok.window.until) - Date.parse(tok.window.since)) / 60000 : null;
  const seqMatch = seq.filter((x) => x.dia === data && x.arm === arm && x.task === task && x.trial === Number(trial));
  if (seqMatch.length > 1) anota(run, 'sequencia_duplicada', `${seqMatch.length} linhas de sequência no mesmo dia; usada a última`);
  const somaDuracao = sessoes.reduce((a, s) => a + (s.duracao_min ?? 0), 0);
  const tempo = {
    janela_sessoes_min: r1(janela),
    sequencia_min: seqMatch.length ? seqMatch[seqMatch.length - 1].min : null,
    soma_duracao_cli_min: r1(somaDuracao),
  };
  if (janela && somaDuracao < 0.5 * janela)
    anota(run, 'duracao_cli_incoerente', `soma de duration_ms do CLI = ${r1(somaDuracao)} min, janela das sessões = ${r1(janela)} min`);

  // ---- specs escondidos (um vitest JSON por arquivo de spec) ----
  const specs = [];
  const falhas = [];
  for (const f of readdirSync(dir).filter((f) => /^vitest-.+\.json$/.test(f)).sort()) {
    const j = readJson(join(dir, f));
    if (!j) {
      specs.push({ arquivo_json: f, total: null, passou: null });
      continue;
    }
    for (const tr of j.testResults || []) {
      const nome = tr.name.replace(/\\/g, '/').split('/').pop();
      specs.push({ arquivo_json: f, spec: nome, total: (tr.assertionResults || []).length, passou: (tr.assertionResults || []).filter((a) => a.status === 'passed').length });
      for (const a of tr.assertionResults || [])
        if (a.status !== 'passed')
          falhas.push({ spec: nome, teste: a.fullName.trim(), status: a.status, msg: (a.failureMessages?.[0] ?? '').split('\n')[0].slice(0, 240) });
      // spec que não compilou: arquivo sem nenhum it, com a mensagem de erro do Vitest no nível do arquivo
      if (!(tr.assertionResults || []).length && tr.message) falhas.push({ spec: nome, teste: '(arquivo não executou)', status: tr.status, msg: tr.message.split('\n')[0].slice(0, 240) });
    }
  }

  // ---- lint (regras) ----
  const lintJ = readJson(join(dir, 'lint.json'));
  const regras = {};
  if (Array.isArray(lintJ))
    for (const arq of lintJ)
      for (const m of arq.messages || []) {
        const k = `${m.severity === 2 ? 'E' : 'W'}:${m.ruleId ?? 'parse'}`;
        regras[k] = (regras[k] || 0) + 1;
      }

  // ---- tsc: só erros com caminho dentro da lib do log (mesma regra do grade.sh) ----
  const tscErros = [];
  for (const f of readdirSync(dir).filter((f) => /^tsc-.+\.log$/.test(f))) {
    const libSlug = f.replace(/^tsc-|\.log$/g, '');
    for (const l of readFileSync(join(dir, f), 'utf8').split(/\r?\n/)) {
      const m = l.match(/^(libs\/[^(]+)\(\d+,\d+\): error (TS\d+): (.*)$/);
      if (m && slug(m[1]).startsWith(`${libSlug}-`)) tscErros.push({ arquivo: m[1], codigo: m[2], msg: m[3].slice(0, 160) });
    }
  }
  if (grade && tscErros.length !== grade.tsc_errors) anota(run, 'tsc_recontagem_diverge', `grade.json tsc_errors=${grade.tsc_errors}, recontado=${tscErros.length}`);

  // ---- diff.patch ----
  const arquivos = [];
  if (existsSync(join(dir, 'diff.patch'))) {
    let atual = null;
    for (const l of readFileSync(join(dir, 'diff.patch'), 'utf8').split(/\r?\n/)) {
      const m = l.match(/^diff --git a\/(.+) b\/(.+)$/);
      if (m) {
        atual = { caminho: m[2], tipo: /\.spec\.ts$/.test(m[2]) ? 'spec' : /^libs\//.test(m[2]) ? 'producao' : 'outro', add: 0, del: 0 };
        arquivos.push(atual);
      } else if (atual && l.startsWith('+') && !l.startsWith('+++')) atual.add++;
      else if (atual && l.startsWith('-') && !l.startsWith('---')) atual.del++;
    }
  }
  const prod = arquivos.filter((a) => a.tipo === 'producao').length;
  const diff = {
    arquivos,
    n_producao: prod,
    n_spec: arquivos.filter((a) => a.tipo === 'spec').length,
    linhas_add: arquivos.reduce((a, x) => a + x.add, 0),
    linhas_del: arquivos.reduce((a, x) => a + x.del, 0),
  };

  // ---- versão do Claude Code: campo `version` das linhas do .jsonl dentro da janela do trial ----
  // O dir de transcrição é o do sandbox (mesma regra do logdir() do run-trial.sh) e é REUSADO entre
  // datas com o mesmo run_id (ex.: wt-S010_S_T1_1 em 25/09 e 26/09) — daí o filtro pela janela.
  // Na mesma varredura: skills pessoais acionadas (tool_use "Skill", dedupe por id) — o worktree roda
  // com o ~/.claude do dono, que não é versionado pelo harness.
  let versoes_cli = null;
  const skills = {};
  if (win?.sandbox && tok?.window) {
    const pasta = join(PROJECTS, win.sandbox.replace(/^\/([a-zA-Z])\//, (_, d) => `${d.toUpperCase()}:/`).replace(/[^A-Za-z0-9]/g, '-'));
    const [a, b] = [Date.parse(tok.window.since), Date.parse(tok.window.until)];
    const cont = {};
    const vistos = new Set();
    const varre = (p) => {
      for (const e of readdirSync(p, { withFileTypes: true })) {
        const q = join(p, e.name);
        if (e.isDirectory()) varre(q);
        else if (e.name.endsWith('.jsonl'))
          for (const l of readFileSync(q, 'utf8').split('\n')) {
            if (!l.includes('"version"') && !l.includes('"name":"Skill"')) continue;
            let o;
            try {
              o = JSON.parse(l);
            } catch {
              continue;
            }
            const t = Date.parse(o.timestamp);
            if (!(t >= a && t <= b)) continue;
            if (o.version) cont[o.version] = (cont[o.version] || 0) + 1;
            for (const c of Array.isArray(o.message?.content) ? o.message.content : [])
              if (c.type === 'tool_use' && c.name === 'Skill' && !vistos.has(c.id)) {
                vistos.add(c.id);
                const nome = c.input?.skill ?? '?';
                skills[nome] = (skills[nome] || 0) + 1;
              }
          }
      }
    };
    if (existsSync(pasta)) varre(pasta);
    versoes_cli = Object.keys(cont).length ? Object.keys(cont).sort() : null;
  }
  if (!versoes_cli) anota(run, 'versao_cli_indisponivel', 'transcrição do sandbox ausente ou sem linhas na janela');

  // ---- autoavaliação: o que a última sessão declarou ao terminar ----
  const ultima = FASES[arm][FASES[arm].length - 1];
  const arqUlt = [`session-${ultima}.json`, `session-${ultima}.log`].find((f) => existsSync(join(dir, f)));
  const sUlt = arqUlt ? readSession(join(dir, arqUlt)) : null;

  if (grade && grade.lint_status !== 'ok') anota(run, 'lint_nao_ok', `lint_status=${grade.lint_status}`);
  if (grade && (grade.specs_nao_executados ?? 0) > 0) anota(run, 'spec_nao_executou', `specs_nao_executados=${grade.specs_nao_executados}`);
  if (grade?.lint_regrade) anota(run, 'lint_refeito', grade.lint_regrade);

  runs.push({
    run,
    data,
    arm,
    task,
    trial: Number(trial),
    sha,
    sha_fonte,
    vigente,
    teto_usd_por_sessao: teto,
    effort: win?.effort ?? null,
    grade,
    aceite: avaliarAceite(dir, grade, task, sha, ACEITE_CTX),
    custo,
    tokens: tok ? { input: tok.totals.input, output: tok.totals.output, cache_write: tok.totals.cache_write, cache_read: tok.totals.cache_read } : null,
    sessoes,
    modelos: [...new Set(sessoes.flatMap((s) => s.modelos ?? []))].sort(),
    versoes_cli,
    skills_acionadas: skills,
    ferramentas,
    calls_por_arquivo_producao: ferramentas && prod ? r1(ferramentas.total / prod) : null,
    tempo,
    specs,
    falhas,
    lint: { erros: grade?.lint_errors ?? null, avisos: grade?.lint_warnings ?? null, regras },
    tsc: { erros: tscErros },
    diff,
    plano_linhas: existsSync(join(dir, 'plan.md')) ? readFileSync(join(dir, 'plan.md'), 'utf8').split('\n').length : null,
    autoavaliacao: sUlt?.result ? sUlt.result.slice(0, 900) : null,
  });
}

for (const r of runs)
  for (const m of r.modelos)
    if (/^claude-sonnet/.test(m) && m !== MODELO_SONNET_MEDIDO)
      anota(r.run, 'modelo_fora_da_medicao', `sonnet = ${m}; a medição do relatório é ${MODELO_SONNET_MEDIDO} (liste o run em runs-fora-do-relatorio.tsv ou revise a medição)`);

// ---- grupos de comparação: mesma tarefa E mesmo sha (o id T1 foi reusado na revisão 3) ----
const grupos = {};
for (const r of runs) {
  const k = `${r.task}@${r.sha ?? '?'}`;
  (grupos[k] ??= { chave: k, task: r.task, sha: r.sha, vigente: r.vigente, runs: [] }).runs.push(r.run);
}
for (const g of Object.values(grupos)) {
  const rs = runs.filter((r) => g.runs.includes(r.run));
  g.bracos = [...new Set(rs.map((r) => r.arm))];
  g.trials_por_braco = Object.fromEntries(g.bracos.map((a) => [a, rs.filter((r) => r.arm === a).length]));
  // aprovado = aceite funcional (EXPERIMENT.md, revisão 5); o estrito continua ao lado
  g.aprovados = rs.filter((r) => r.aceite?.funcional.pass === true).map((r) => r.run);
  g.aprovados_estrito = rs.filter((r) => r.grade?.pass === true).map((r) => r.run);
  g.excluidos_do_aceite = rs[0]?.aceite?.funcional.excluidos ?? 0;
  g.datas = [...new Set(rs.map((r) => r.data))];
  // mesmo alias (sonnet/opus/haiku) resolvido para ids diferentes dentro do grupo = confusão de modelo
  const porFamilia = {};
  for (const r of rs) for (const m of r.modelos) (porFamilia[m.replace(/^claude-(\w+).*/, '$1')] ??= new Set()).add(m);
  g.ids_por_familia = Object.fromEntries(Object.entries(porFamilia).map(([k, v]) => [k, [...v].sort()]));
  for (const [fam, ids] of Object.entries(g.ids_por_familia))
    if (ids.length > 1) {
      const quem = ids.map((id) => `${id}: ${rs.filter((r) => r.modelos.includes(id)).map((r) => r.arm).join(',')}`).join(' | ');
      anota(g.chave, 'modelo_diferente_no_grupo', `alias ${fam} resolveu para ${ids.join(' e ')} → ${quem}`);
    }
  g.versoes_cli = Object.fromEntries(rs.map((r) => [r.run, r.versoes_cli]));
  const todasVersoes = [...new Set(rs.flatMap((r) => r.versoes_cli ?? []))].sort();
  if (todasVersoes.length > 1)
    anota(g.chave, 'versao_cli_diferente_no_grupo', rs.map((r) => `${r.arm}: ${(r.versoes_cli ?? ['?']).join('+')}`).join(' | '));
  // agregado por braço (CHARTER P6): pass@k = ≥1 trial aprovado; pass^k = todos aprovados
  const med = (xs) => {
    const s = [...xs].sort((x, y) => x - y);
    return s.length ? (s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : null;
  };
  g.agregado_por_braco = Object.fromEntries(
    g.bracos.map((a) => {
      const ts = rs.filter((r) => r.arm === a);
      const custos = ts.map((r) => r.custo?.total_usd).filter((x) => x != null);
      const taxas = ts.map((r) => r.grade?.hidden_pass_rate).filter((x) => x != null);
      const aprov = ts.filter((r) => r.aceite?.funcional.pass === true).length;
      const aprovEstrito = ts.filter((r) => r.grade?.pass === true).length;
      return [a, { n: ts.length, aprovados: aprov, aprovados_estrito: aprovEstrito, pass_at_k: aprov > 0, pass_hat_k: aprov === ts.length, custo_mediana: r4(med(custos)), custo_min: r4(Math.min(...custos)), custo_max: r4(Math.max(...custos)), taxa_min: Math.min(...taxas), taxa_max: Math.max(...taxas) }];
    }),
  );
  // matriz de falhas: teste -> braços que falharam
  const mapa = {};
  for (const r of rs) for (const f of r.falhas) (mapa[`${f.spec} :: ${f.teste}`] ??= []).push(r.arm);
  g.matriz_falhas = mapa;
}

const dados = {
  gerado_em: new Date().toISOString(),
  gerador: 'graders/consolidar-s010.mjs (plano 005)',
  prices_version_vigente: PRICES_VERSION,
  tarefas_vigentes: tasks,
  sequencias: seq,
  grupos,
  runs,
  anomalias,
};

// ---- tabelas.md ----
const fmt = (x, d = 2) => (x == null ? '—' : typeof x === 'number' ? x.toFixed(d).replace('.', ',') : String(x));
const md = [];
md.push(`# S010 — tabelas consolidadas (geradas, não editar à mão)`, '');
md.push(`Gerado em ${dados.gerado_em} por \`${dados.gerador}\`. Tarifa vigente do grader: \`${PRICES_VERSION}\`.`, '');
md.push('## Tarefas vigentes (tasks.tsv)', '', '| id | sha | regime | libs | teto US$/sessão | hidden_total_ref |', '|---|---|---|---|---:|---:|');
for (const t of Object.values(tasks)) md.push(`| ${t.id} | \`${t.sha}\` | ${t.regime} | ${t.libs.length} | ${t.budget_usd} | ${t.hidden_total_ref} |`);
md.push('', `Medição coberta: sonnet = \`${MODELO_SONNET_MEDIDO}\`. Aprovado = aceite funcional (EXPERIMENT.md, revisão 5); o estrito aparece ao lado.`);
const semRun = Object.values(tasks).filter((t) => !Object.values(grupos).some((g) => g.task === t.id && g.sha === t.sha));
for (const t of semRun) md.push('', `Tarefa vigente sem trial nesta medição: ${t.id} \`${t.sha}\` (0 trials).`);
for (const g of Object.values(grupos)) {
  const rs = runs.filter((r) => g.runs.includes(r.run));
  md.push('', `## Grupo ${g.chave} — ${g.vigente ? 'VIGENTE' : 'SUPERADO (tarefa trocada; não comparar com o vigente)'}`, '');
  md.push(`Datas: ${g.datas.join(', ')} · braços: ${g.bracos.join(', ')} · trials por braço: ${JSON.stringify(g.trials_por_braco)} · aprovados: ${g.aprovados.length}/${rs.length}`, '');
  md.push(`Modelos por família: ${Object.entries(g.ids_por_familia).map(([k, v]) => `${k} → ${v.join(', ')}`).join(' · ')}`, '');
  md.push(`Versões do Claude Code: ${rs.map((r) => `${r.arm} ${(r.versoes_cli ?? ['?']).join('+')}`).join(' · ')}`, '');
  md.push(`Skills pessoais acionadas: ${rs.map((r) => `${r.arm} ${Object.entries(r.skills_acionadas).map(([k, v]) => `${k}×${v}`).join(', ') || 'nenhuma'}`).join(' · ')}`, '');
  md.push(`Aprovados no funcional: ${g.aprovados.length}/${rs.length} · no estrito: ${g.aprovados_estrito.length}/${rs.length} · its fora do aceite funcional (aceite-excluidos.tsv): ${g.excluidos_do_aceite}`, '');
  md.push('### Agregado por braço', '', '| braço | n trials | aprovados (funcional) | aprovados (estrito) | pass@k | pass^k | custo US$ mediana (mín–máx) | taxa mín–máx |', '|---|---:|---:|---:|---|---|---|---|');
  for (const [a, x] of Object.entries(g.agregado_por_braco))
    md.push(`| ${a} | ${x.n} | ${x.aprovados} | ${x.aprovados_estrito} | ${x.pass_at_k} | ${x.pass_hat_k} | ${fmt(x.custo_mediana)} (${fmt(x.custo_min)}–${fmt(x.custo_max)}) | ${fmt(x.taxa_min, 4)}–${fmt(x.taxa_max, 4)} |`);
  md.push('', '### Aceite', '', '| braço | trial | data | hidden (estrito) | taxa | funcional | cobertura | regressões | tsc | lint E/W | arquivos (prod/spec) | +/− linhas | pass estrito | pass funcional |', '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|');
  for (const r of rs) {
    const f = r.aceite?.funcional;
    const c = r.aceite?.cobertura;
    md.push(`| ${r.arm} | t${r.trial} | ${r.data} | ${r.grade?.hidden_passed}/${r.grade?.hidden_total_ref} | ${fmt(r.grade?.hidden_pass_rate, 4)} | ${f ? `${f.passou}/${f.total}` : '—'} | ${c ? `${c.passou}/${c.total}` : '—'} | ${c ? c.regressoes : '—'} | ${r.grade?.tsc_errors} | ${r.lint.erros}/${r.lint.avisos} | ${r.diff.n_producao}/${r.diff.n_spec} | +${r.diff.linhas_add}/−${r.diff.linhas_del} | ${r.grade?.pass} | ${f ? f.pass : '—'} |`);
  }
  md.push('', '### Custo (fonte: tokens.json)', '', '| braço | total US$ | por modelo | por fase | rubrica dominante | resíduo CLI | resíduo fases |', '|---|---:|---|---|---|---:|---:|');
  for (const r of rs) {
    const c = r.custo;
    if (!c) continue;
    const pm = Object.entries(c.por_modelo).map(([k, v]) => `${k} ${fmt(v)}`).join(' + ');
    const pf = Object.entries(c.fases).map(([k, v]) => `${k} ${fmt(v?.usd)}`).join(' · ') || '—';
    md.push(`| ${r.arm} t${r.trial} | ${fmt(c.total_usd)} | ${pm} | ${pf} | ${c.rubrica_dominante} | ${fmt(c.residuo_cli, 4)} | ${fmt(c.residuo_fases, 4)} |`);
  }
  md.push('', '### Processo', '', '| braço | tool calls (pai/sub) | Edit/Write pai | Edit÷Write pai | Edit/Write sub | Edit÷Write sub | turnos (soma) | janela sessões min | sequência min | output tok | cache_read tok | linhas do plano |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|');
  for (const r of rs) {
    const f = r.ferramentas ?? {};
    const turnos = r.sessoes.reduce((a, s) => a + (s.num_turns ?? 0), 0);
    md.push(`| ${r.arm} t${r.trial} | ${f.total} (${f.pai}/${f.subagente}) | ${f.pai_edit}/${f.pai_write} | ${fmt(f.ew_pai)} | ${f.sub_edit}/${f.sub_write} | ${fmt(f.ew_sub)} | ${turnos} | ${fmt(r.tempo.janela_sessoes_min, 1)} | ${fmt(r.tempo.sequencia_min, 1)} | ${r.tokens?.output} | ${r.tokens?.cache_read} | ${r.plano_linhas ?? '—'} |`);
  }
  md.push('', '### Testes escondidos que falharam (✗ = falhou; com k>1, falhas/trials)', '', `| teste | ${g.bracos.join(' | ')} |`, `|---|${g.bracos.map(() => ':-:').join('|')}|`);
  const entradas = Object.entries(g.matriz_falhas).sort((a, b) => b[1].length - a[1].length);
  if (!entradas.length) md.push(`| (nenhuma falha) | ${g.bracos.map(() => '').join(' | ')} |`);
  for (const [teste, quem] of entradas) {
    const cel = (a) => {
      const c = quem.filter((x) => x === a).length;
      return g.trials_por_braco[a] > 1 ? `${c}/${g.trials_por_braco[a]}` : c ? '✗' : '·';
    };
    md.push(`| ${teste.replace(/\|/g, '\\|')} | ${g.bracos.map(cel).join(' | ')} |`);
  }
  md.push('', '### Regras de lint e erros de tsc', '');
  for (const r of rs) {
    const regras = Object.entries(r.lint.regras).map(([k, v]) => `${k} ×${v}`).join(', ') || 'nenhuma';
    const tsc = r.tsc.erros.map((e) => `${e.arquivo} ${e.codigo}`).join('; ') || 'nenhum';
    md.push(`- **${r.arm} t${r.trial}** — lint: ${regras} · tsc: ${tsc}`);
  }
}
md.push('', '## Anomalias detectadas automaticamente', '', '| run/grupo | tipo | detalhe |', '|---|---|---|');
for (const a of anomalias) md.push(`| ${a.run} | ${a.tipo} | ${String(a.detalhe).replace(/\|/g, '\\|')} |`);

mkdirSync(OUT, { recursive: true });
writeFileSync(join(OUT, 'dados.json'), JSON.stringify(dados, null, 2));
writeFileSync(join(OUT, 'tabelas.md'), md.join('\n') + '\n');
console.log(`runs=${runs.length} grupos=${Object.keys(grupos).length} anomalias=${anomalias.length} -> ${OUT}`);
console.log(`fora do relatório: ${FORA.size} run(s) listados em runs-fora-do-relatorio.tsv (não aparecem em dados.json nem em tabelas.md)`);
