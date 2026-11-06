#!/usr/bin/env node
// Grader de tokens/custo REAIS (CHARTER P7). Lê os logs .jsonl de sessão do Claude Code, soma tokens
// por família de modelo e estima custo. Tokens explicam ~80% da variância de performance — é métrica
// de primeira classe, não rodapé.
//
// Uso:
//   node token-usage.mjs [--logs <dir>] [--since <ISO>] [--until <ISO>] [--out <arquivo.json>]
//
// Padrões:
//   --logs  -> ~/.claude/projects/-home-usuario-Projetos-meu-app/
//   janela  -> tudo, se --since/--until não forem dados
//
// Preço novo de modelo: acrescente a linha em PRICES (tarifa oficial, skill claude-api) — modelo sem
// linha sai em `unpriced_models` e o grader avisa no stderr em vez de custear zero em silêncio.

import { readFileSync, readdirSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { join, dirname, sep } from 'node:path';

// ---- TABELA DE PREÇOS — USD por 1.000.000 de tokens, POR MODELO e por TTL de cache ----
// Fonte: tarifa oficial de primeira parte (skill claude-api, tabela de modelos + prompt-caching.md:
// cache write = 1,25× input no TTL de 5 min e 2× no de 1 h; cache read = 0,1× input, exceto Opus 5.5).
//
// Corrigido em 2026-09-26 (auditoria do S010 T1). A tabela anterior (2026-08-14-real) tinha dois erros:
//   1. era por FAMÍLIA — Sonnet a $3/$15 (tarifa do Sonnet 4.6; o claude-sonnet-5 é $2/$10) e Opus a
//      $5/$25 (claude-opus-5; o claude-opus-5-5 é $4/$20 com cache read $0,20);
//   2. cobrava todo cache write a 1,25× (TTL 5 min), mas o Claude Code grava com TTL de 1 h (2×) —
//      `usage.cache_creation.ephemeral_1h_input_tokens` no .jsonl.
// Conferência: com esta tabela o custo bate com o `total_cost_usd` do CLI com resíduo 0 nos 5 braços
// do S010 T1 (sessões não retomadas). Os `.jsonl` guardam contagem bruta, então recustear = re-rodar
// este grader com a mesma janela; nenhum trial precisa ser refeito.
const PRICES_VERSION = '2026-09-26-modelo-ttl';
const PRICES = {
  // prefixo do model id (o mais específico primeiro): { input, output, cache_write_5m, cache_write_1h, cache_read }
  'claude-opus-5-5':  { input: 4.0, output: 20.0, cache_write_5m: 5.0,  cache_write_1h: 8.0,  cache_read: 0.2 },
  'claude-opus-5':    { input: 5.0, output: 25.0, cache_write_5m: 6.25, cache_write_1h: 10.0, cache_read: 0.5 },
  'claude-sonnet-5':  { input: 2.0, output: 10.0, cache_write_5m: 2.5,  cache_write_1h: 4.0,  cache_read: 0.2 },
  'claude-haiku-4-5': { input: 1.0, output: 5.0,  cache_write_5m: 1.25, cache_write_1h: 2.0,  cache_read: 0.1 },
};

// `claude-opus-5-5` casa antes de `claude-opus-5` porque as chaves estão ordenadas do mais específico.
function priceFor(model = '') {
  const m = model.toLowerCase();
  const key = Object.keys(PRICES).find((k) => m === k || m.startsWith(`${k}-`) || m.startsWith(`${k}[`));
  return key ? PRICES[key] : null;
}

function family(model = '') {
  const m = model.toLowerCase();
  if (m.includes('opus')) return 'opus';
  if (m.includes('sonnet')) return 'sonnet';
  if (m.includes('haiku')) return 'haiku';
  return 'unknown';
}

// ---- args ----
const args = process.argv.slice(2);
const getArg = (name, def) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : def;
};
const DEFAULT_LOGS = join(homedir(), '.claude', 'projects', '-home-usuario-Projetos-meu-app');
// --logs aceita múltiplos roots separados por vírgula. Cada root é varrido RECURSIVAMENTE — o uso de
// subagente Task fica em `<session-id>/subagents/*.jsonl` (nested), e sessões com cwd distinto (ex.: o
// Haiku frio do braço B rodando no sandbox) caem num projects dir irmão. Sem recursão + multi-root, o
// custo de Haiku desaparecia da fatura.
const logsDirs = getArg('--logs', DEFAULT_LOGS).split(',').map((d) => d.trim()).filter(Boolean);
const since = getArg('--since', null);
const until = getArg('--until', null);
const out = getArg('--out', null);

const sinceMs = since ? Date.parse(since) : -Infinity;
const untilMs = until ? Date.parse(until) : Infinity;

const missing = logsDirs.filter((d) => !existsSync(d));
if (missing.length === logsDirs.length) {
  console.error(`ERRO: nenhum dir de logs encontrado: ${logsDirs.join(', ')}`);
  console.error('passe --logs <dir[,dir2,...]> apontando para pasta(s) de sessões .jsonl do Claude Code.');
  process.exit(2);
}

// Coleta recursiva de todos os .jsonl sob os roots dados (existentes).
const collectJsonl = (root, acc) => {
  for (const ent of readdirSync(root, { withFileTypes: true })) {
    const p = join(root, ent.name);
    if (ent.isDirectory()) collectJsonl(p, acc);
    else if (ent.isFile() && ent.name.endsWith('.jsonl')) acc.push(p);
  }
  return acc;
};

// ---- acumuladores ----
// DEDUPE POR message.id (bug corrigido em 2026-07-22): o .jsonl regrava a MESMA mensagem assistant a
// cada snapshot de streaming, e cada linha carrega o `usage` PARCIAL daquele instante — ex.:
//   msg_011CdHrx… -> [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2930]   (1 mensagem, 12 linhas)
// Somar linha a linha inflava o custo por um fator ∝ DURAÇÃO da mensagem (medido: até 18×), o que
// distorce comparações entre braços de topologia de forma correlacionada com o braço. O correto é
// uma entrada por `message.id`, com o maior snapshot (o último, cumulativo).
const zero = () => ({
  input: 0, output: 0, cache_write: 0, cache_write_5m: 0, cache_write_1h: 0, cache_read: 0, messages: 0,
});
const zeroUsd = () => ({ input: 0, output: 0, cache_write: 0, cache_read: 0 });
const byModel = {};
let scanned = 0, rawEntries = 0;

// id -> { model, usage } (maior snapshot visto)
const byMessageId = new Map();

const collectUsage = (id, model, u, tsMs) => {
  if (tsMs < sinceMs || tsMs > untilMs) return;
  rawEntries += 1;
  const prev = byMessageId.get(id);
  if (prev && (prev.usage.output_tokens || 0) >= (u.output_tokens || 0)) return;
  byMessageId.set(id, { model, usage: u });
};

// ---- CHAMADAS DE FERRAMENTA (instrumentado em 2026-09-03, achado do S001) ----
// Custo em dólar não distingue trabalho de RETRABALHO: o braço M do S001 e o braço S custaram na
// mesma ordem de grandeza, mas o pai do M gastou 24 Edit para 3 Write (reintegrando o que 3
// subagentes escreveram) enquanto o solo gastou 5 Edit para 22 Write. A razão Edit÷Write separa os
// dois regimes sem ambiguidade e sai de graça: os blocos `tool_use` já estão nas mesmas linhas que
// o `usage`, então é a mesma varredura.
//
// Dedupe por `tool_use.id` pelo mesmo motivo do `message.id`: o snapshot de streaming regrava a
// mensagem inteira, e sem dedupe uma chamada longa conta várias vezes.
//
// Dono: subagente Task grava em `<session-id>/subagents/*.jsonl`. Sem essa separação o retrabalho do
// pai se mistura com a produção dos filhos e a razão perde justamente o que ela mede.
const zeroCalls = () => ({ total: 0, by_tool: {} });
const callsByOwner = { pai: zeroCalls(), subagente: zeroCalls() };
const seenToolIds = new Set();

const collectCalls = (ev, tsMs, owner) => {
  if (tsMs < sinceMs || tsMs > untilMs) return;
  const content = ev?.message?.content;
  if (!Array.isArray(content)) return;
  for (const blk of content) {
    if (blk?.type !== 'tool_use' || !blk.id || seenToolIds.has(blk.id)) continue;
    seenToolIds.add(blk.id);
    const bag = callsByOwner[owner];
    bag.total += 1;
    bag.by_tool[blk.name] = (bag.by_tool[blk.name] || 0) + 1;
  }
};

const files = logsDirs.filter((d) => existsSync(d)).reduce((acc, d) => collectJsonl(d, acc), []);
for (const f of files) {
  const owner = f.split(sep).join('/').includes('/subagents/') ? 'subagente' : 'pai';
  const lines = readFileSync(f, 'utf8').split('\n');
  let anon = 0;
  for (const line of lines) {
    if (!line.trim()) continue;
    scanned++;
    let ev;
    try { ev = JSON.parse(line); } catch { continue; }
    const tsMs = ev?.timestamp ? Date.parse(ev.timestamp) : 0;
    collectCalls(ev, tsMs, owner);
    const usage = ev?.message?.usage || ev?.usage;
    if (!usage) continue;
    const model = ev?.message?.model || ev?.model || 'unknown';
    // sem message.id não há como deduplicar: chave única por linha (conta como mensagem própria).
    const id = ev?.message?.id || `${f}#${anon++}`;
    collectUsage(id, model, usage, tsMs);
  }
}

// ---- custo ----
// Custeado POR MENSAGEM, com a tarifa do model id exato: a família agrega modelos de preço diferente
// (claude-opus-5 e claude-opus-5-5 são ambos "opus"). O cache write é separado por TTL a partir de
// `usage.cache_creation`; linha sem esse detalhamento (logs antigos) conta como 5 min, o default da API.
const usdByModel = {};
const unpriced = new Set();
for (const { model, usage: u } of byMessageId.values()) {
  const fam = family(model);
  byModel[fam] ??= zero();
  usdByModel[fam] ??= zeroUsd();
  const b = byModel[fam];
  const usd = usdByModel[fam];

  const cw = u.cache_creation_input_tokens || 0;
  const cw1h = u.cache_creation?.ephemeral_1h_input_tokens || 0;
  const cw5m = cw - cw1h;
  b.input += u.input_tokens || 0;
  b.output += u.output_tokens || 0;
  b.cache_write += cw;
  b.cache_write_5m += cw5m;
  b.cache_write_1h += cw1h;
  b.cache_read += u.cache_read_input_tokens || 0;
  b.messages += 1;

  const p = priceFor(model);
  if (!p) { unpriced.add(model); continue; }
  usd.input += ((u.input_tokens || 0) / 1e6) * p.input;
  usd.output += ((u.output_tokens || 0) / 1e6) * p.output;
  usd.cache_write += (cw5m / 1e6) * p.cache_write_5m + (cw1h / 1e6) * p.cache_write_1h;
  usd.cache_read += ((u.cache_read_input_tokens || 0) / 1e6) * p.cache_read;
}
if (unpriced.size) {
  console.error(`AVISO: modelos sem tarifa em PRICES (custo fica fora do total): ${[...unpriced].join(', ')}`);
}

const arredonda = (usd) => Object.fromEntries(Object.entries(usd).map(([k, v]) => [k, Number(v.toFixed(4))]));
const somaUsd = (usd) => Object.values(usd).reduce((s, v) => s + v, 0);

let totalCost = 0;
const totals = zero();
const totalsUsd = zeroUsd();
const byModelOut = {};
for (const [fam, b] of Object.entries(byModel)) {
  const usd = usdByModel[fam];
  const c = somaUsd(usd);
  totalCost += c;
  for (const k of Object.keys(totals)) totals[k] += b[k];
  for (const k of Object.keys(totalsUsd)) totalsUsd[k] += usd[k];
  byModelOut[fam] = { ...b, cost_usd: Number(c.toFixed(4)), cost_usd_by_rubric: arredonda(usd) };
}

// ---- razão de retrabalho ----
// Edit÷Write por dono. Alto no dono que CONSERTA o que não escreveu; ~0 em quem transcreve um plano
// literal. `null` quando não houve Write (dono que só leu, ex.: a sessão de plano).
const ordenaPorUso = (t) => Object.fromEntries(Object.entries(t).sort((a, b) => b[1] - a[1]));
const somaFerramenta = (nome) =>
  (callsByOwner.pai.by_tool[nome] || 0) + (callsByOwner.subagente.by_tool[nome] || 0);
const razaoRetrabalho = (writes, edits) => (writes > 0 ? Number((edits / writes).toFixed(2)) : null);
const donoOut = (bag) => ({
  total: bag.total,
  by_tool: ordenaPorUso(bag.by_tool),
  edit_write_ratio: razaoRetrabalho(bag.by_tool.Write || 0, bag.by_tool.Edit || 0),
});

const result = {
  generated_at: new Date().toISOString(),
  logs_dirs: logsDirs,
  jsonl_files_scanned: files.length,
  window: { since: since || null, until: until || null },
  lines_scanned: scanned,
  usage_entries_counted: byMessageId.size,
  usage_entries_raw: rawEntries,
  dedupe_note: 'contagem por message.id (maior snapshot). usage_entries_raw = linhas de usage antes do dedupe.',
  by_model: byModelOut,
  tool_calls: {
    total: seenToolIds.size,
    by_owner: { pai: donoOut(callsByOwner.pai), subagente: donoOut(callsByOwner.subagente) },
    by_tool: ordenaPorUso({
      ...callsByOwner.pai.by_tool,
      ...Object.fromEntries(
        Object.entries(callsByOwner.subagente.by_tool).map(([k, v]) => [k, (callsByOwner.pai.by_tool[k] || 0) + v]),
      ),
    }),
    edit_write_ratio: razaoRetrabalho(somaFerramenta('Write'), somaFerramenta('Edit')),
    ratio_note:
      'Edit÷Write = retrabalho. Dedupe por tool_use.id, janela igual à dos tokens; dono separado por ' +
      '`<session-id>/subagents/`. Referência medida no S001 (2026-09-03): solo 0,23 · pai que ' +
      'reintegra 3 subagentes 8,00 · executor frio com plano literal 0,00. Conta só `Edit` e `Write` ' +
      'literais — outra ferramenta de escrita entra em by_tool mas fica fora da razão.',
  },
  totals: { ...totals, cost_usd: Number(totalCost.toFixed(4)), cost_usd_by_rubric: arredonda(totalsUsd) },
  unpriced_models: [...unpriced],
  prices_version: PRICES_VERSION,
  prices_note:
    'Tarifa oficial por model id (claude-opus-5-5 / claude-opus-5 / claude-sonnet-5 / claude-haiku-4-5), ' +
    'cache write separado por TTL (5 min 1,25×, 1 h 2×). Arquivo com prices_version anterior a ' +
    '2026-09-26-modelo-ttl superfatura Sonnet e ignora o TTL de 1 h — recustear re-rodando este grader ' +
    'com a mesma janela (os .jsonl guardam a contagem bruta).',
};

const json = JSON.stringify(result, null, 2);
if (out) {
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, json);
  console.error(`escrito: ${out}`);
} else {
  console.log(json);
}
