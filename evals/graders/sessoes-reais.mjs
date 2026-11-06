#!/usr/bin/env node
// Plan 003: telemetria observacional das sessões reais já gravadas em ~/.claude/projects/.
// Reusa token-usage.mjs (não alterado) por sessão: copia cada <uuid>.jsonl (+ subagents/) para um
// diretório temporário no scratch do sistema, roda o grader nele, lê o tokens.json e apaga o tmp.
// Somente leitura dos logs originais — nunca move, renomeia ou apaga nada em ~/.claude/projects/.
//
// Uso:
//   node sessoes-reais.mjs --logs <dir-de-sessoes> --out <dir-de-saida>
//
// Saída: <out>/sessoes-reais.csv, <out>/sessoes-reais.md

import { execFileSync } from 'node:child_process';
import {
  readFileSync,
  readdirSync,
  writeFileSync,
  mkdirSync,
  rmSync,
  copyFileSync,
  statSync,
  existsSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const TOKEN_USAGE_MJS = join(__dirname, 'token-usage.mjs');

// ---- args ----
const args = process.argv.slice(2);
const getArg = (name, def) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : def;
};
const logsDir = getArg('--logs', null);
const outDir = getArg('--out', null);

if (!logsDir || !existsSync(logsDir)) {
  console.error(`ERRO: --logs <dir> obrigatorio e deve existir (recebido: ${logsDir})`);
  process.exit(2);
}
if (!outDir) {
  console.error('ERRO: --out <dir> obrigatorio');
  process.exit(2);
}

// ---- 1. lista sessões principais (só o nível de cima) ----
const topEntries = readdirSync(logsDir, { withFileTypes: true });
const sessionFiles = topEntries
  .filter((e) => e.isFile() && e.name.endsWith('.jsonl'))
  .map((e) => e.name);

if (sessionFiles.length === 0) {
  console.error(`ERRO: nenhum .jsonl de sessão encontrado em ${logsDir}`);
  process.exit(2);
}

const rows = [];
const secretsFound = [];

// heurística simples de credencial: chaves de API conhecidas (sk-, AKIA, ghp_, etc.)
const SECRET_PATTERNS = [
  /sk-ant-[a-zA-Z0-9_-]{20,}/,
  /sk-[a-zA-Z0-9]{20,}/,
  /AKIA[0-9A-Z]{16}/,
  /ghp_[a-zA-Z0-9]{30,}/,
  /AIza[0-9A-Za-z_-]{30,}/,
];

function scanForSecrets(text, filePath) {
  for (const re of SECRET_PATTERNS) {
    if (re.test(text)) {
      secretsFound.push({ path: filePath, type: re.source.slice(0, 20) });
    }
  }
}

for (const sessionFile of sessionFiles) {
  const uuid = basename(sessionFile, '.jsonl');
  const mainPath = join(logsDir, sessionFile);
  const subagentsDir = join(logsDir, uuid, 'subagents');
  const hasSubagents = existsSync(subagentsDir);

  // ---- 2. copia para tmp, roda token-usage.mjs, lê tokens.json, apaga tmp ----
  const tmpRoot = join(tmpdir(), `sessoes-reais-${uuid}-${Date.now()}`);
  mkdirSync(tmpRoot, { recursive: true });
  let tokensJson = null;
  try {
    copyFileSync(mainPath, join(tmpRoot, sessionFile));
    if (hasSubagents) {
      const tmpSubDir = join(tmpRoot, uuid, 'subagents');
      mkdirSync(tmpSubDir, { recursive: true });
      for (const f of readdirSync(subagentsDir)) {
        if (f.endsWith('.jsonl')) copyFileSync(join(subagentsDir, f), join(tmpSubDir, f));
      }
    }
    const outTokens = join(tmpRoot, 'tokens.json');
    execFileSync(
      process.execPath,
      [TOKEN_USAGE_MJS, '--logs', tmpRoot, '--out', outTokens],
      { stdio: ['ignore', 'ignore', 'ignore'] },
    );
    tokensJson = JSON.parse(readFileSync(outTokens, 'utf8'));
  } finally {
    rmSync(tmpRoot, { recursive: true, force: true });
  }

  // ---- 3. varredura do .jsonl principal ----
  const raw = readFileSync(mainPath, 'utf8');
  scanForSecrets(raw, mainPath);
  const lines = raw.split('\n');

  const modelosSeq = [];
  let inicio = null;
  let fim = null;
  let compactacoes = 0;

  for (const line of lines) {
    if (!line.trim()) continue;
    let ev;
    try {
      ev = JSON.parse(line);
    } catch {
      continue;
    }
    const ts = ev?.timestamp;
    if (ts) {
      if (inicio === null || ts < inicio) inicio = ts;
      if (fim === null || ts > fim) fim = ts;
    }
    if (ev?.isCompactSummary === true || ev?.type === 'summary') compactacoes += 1;

    const role = ev?.message?.role;
    const model = ev?.message?.model;
    if (role === 'assistant' && model) {
      const last = modelosSeq[modelosSeq.length - 1];
      if (last !== model) modelosSeq.push(model);
    }
  }

  const trocasDeModelo = modelosSeq.length > 0 ? modelosSeq.length - 1 : 0;
  const subagentesCount = hasSubagents
    ? readdirSync(subagentsDir).filter((f) => f.endsWith('.jsonl')).length
    : 0;

  // ---- custo por rubrica (vem pronto do token-usage.mjs, que custeia por model id e por TTL) ----
  const rubrica = tokensJson.totals?.cost_usd_by_rubric ?? {};
  const outputUsd = rubrica.output ?? 0;
  const cacheWriteUsd = rubrica.cache_write ?? 0;
  const cacheReadUsd = rubrica.cache_read ?? 0;

  rows.push({
    sessao: uuid,
    inicio: inicio || '',
    fim: fim || '',
    modelos: modelosSeq.join('|'),
    trocas_de_modelo: trocasDeModelo,
    subagentes: subagentesCount,
    compactacoes,
    cost_usd: Number((tokensJson.totals?.cost_usd ?? 0).toFixed(4)),
    output_usd: Number(outputUsd.toFixed(4)),
    cache_write_usd: Number(cacheWriteUsd.toFixed(4)),
    cache_read_usd: Number(cacheReadUsd.toFixed(4)),
    tool_calls: tokensJson.tool_calls?.total ?? 0,
    edit_write_ratio_main: tokensJson.tool_calls?.by_owner?.pai?.edit_write_ratio ?? '',
  });
}

// ---- 5. previsto x real ----
const plansGlob = process.env.PLANS_DIR ?? '';
const previstoRealRows = [];
if (existsSync(plansGlob)) {
  for (const f of readdirSync(plansGlob)) {
    if (!f.endsWith('.md')) continue;
    const p = join(plansGlob, f);
    const content = readFileSync(p, 'utf8');
    const m = content.match(/D0:\s*previsto\s*(\d+)\s*\/\s*real\s*(\d+)/i);
    if (m) {
      const previsto = Number(m[1]);
      const real = Number(m[2]);
      previstoRealRows.push({
        arquivo: f,
        previsto,
        real,
        razao: previsto > 0 ? Number((real / previsto).toFixed(2)) : '',
      });
    }
  }
}

// ---- 4. escreve CSV ----
mkdirSync(outDir, { recursive: true });
const csvHeader = [
  'sessao',
  'inicio',
  'fim',
  'modelos',
  'trocas_de_modelo',
  'subagentes',
  'compactacoes',
  'cost_usd',
  'output_usd',
  'cache_write_usd',
  'cache_read_usd',
  'tool_calls',
  'edit_write_ratio_main',
].join(',');
const csvRows = rows.map((r) =>
  [
    r.sessao,
    r.inicio,
    r.fim,
    `"${r.modelos}"`,
    r.trocas_de_modelo,
    r.subagentes,
    r.compactacoes,
    r.cost_usd,
    r.output_usd,
    r.cache_write_usd,
    r.cache_read_usd,
    r.tool_calls,
    r.edit_write_ratio_main,
  ].join(','),
);
const csvPath = join(outDir, 'sessoes-reais.csv');
writeFileSync(csvPath, [csvHeader, ...csvRows].join('\n') + '\n');

// ---- 6. resumo em MD ----
function mediana(nums) {
  if (nums.length === 0) return null;
  const s = [...nums].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 === 0 ? (s[mid - 1] + s[mid]) / 2 : s[mid];
}
function p90(nums) {
  if (nums.length === 0) return null;
  const s = [...nums].sort((a, b) => a - b);
  const idx = Math.min(s.length - 1, Math.ceil(0.9 * s.length) - 1);
  return s[idx];
}
function fmt(n) {
  return n === null || n === undefined || Number.isNaN(n) ? 'n/d' : n.toFixed(4);
}

const custos = rows.map((r) => r.cost_usd);
const medianaCusto = mediana(custos);
const p90Custo = p90(custos);
const total = rows.length;
const comSubagente = rows.filter((r) => r.subagentes > 0);
const comTroca = rows.filter((r) => r.trocas_de_modelo > 0);
const comCompactacao = rows.filter((r) => r.compactacoes > 0);
const soloSemTroca = rows.filter((r) => r.subagentes === 0 && r.trocas_de_modelo === 0);

const pct = (n) => (total > 0 ? ((n / total) * 100).toFixed(1) : '0.0');

const rubricaMaiorCount = { output_usd: 0, cache_write_usd: 0, cache_read_usd: 0 };
for (const r of rows) {
  const entries = [
    ['output_usd', r.output_usd],
    ['cache_write_usd', r.cache_write_usd],
    ['cache_read_usd', r.cache_read_usd],
  ];
  entries.sort((a, b) => b[1] - a[1]);
  if (entries[0][1] > 0) rubricaMaiorCount[entries[0][0]] += 1;
}

const compactMarkerFound = rows.some((r) => r.compactacoes > 0);

let md = `# Sessões reais — telemetria observacional\n\n`;
md += `> **Observacional, não causal.** Estes números descrevem sessões reais já gravadas, sem grupo\n`;
md += `> de controle e sem contrafactual. Diferenças entre grupos (com/sem subagente, com/sem troca de\n`;
md += `> modelo, com/sem compactação) podem refletir o tipo de tarefa escolhida, não o efeito do fator.\n`;
md += `> Não tirar conclusão causal deste documento — ele mostra onde o dono passa a maior parte do\n`;
md += `> tempo e para onde vai a fatura, não o que causa o quê.\n\n`;
md += `Gerado em: ${new Date().toISOString()}\n\n`;
md += `## Visão geral\n\n`;
md += `- Sessões analisadas: ${total}\n`;
md += `- Custo mediano: US$ ${fmt(medianaCusto)}\n`;
md += `- Custo p90: US$ ${fmt(p90Custo)}\n`;
md += `- % de sessões com subagente: ${pct(comSubagente.length)}% (${comSubagente.length}/${total})\n`;
md += `- % de sessões com troca de modelo: ${pct(comTroca.length)}% (${comTroca.length}/${total})\n`;
md += `- % de sessões com compactação: ${pct(comCompactacao.length)}% (${comCompactacao.length}/${total})\n`;
if (!compactMarkerFound) {
  md += `\n> Nenhum marcador de compactação (\`isCompactSummary\` ou \`type: "summary"\`) foi encontrado em\n`;
  md += `> nenhuma sessão analisada — compactações = 0 em todas as linhas.\n`;
}
md += `\n## Custo mediano por grupo (vs. solo sem troca de modelo)\n\n`;
md += `| Grupo | N | Custo mediano (US$) |\n`;
md += `| --- | --- | --- |\n`;
md += `| Solo, sem troca de modelo | ${soloSemTroca.length} | ${fmt(mediana(soloSemTroca.map((r) => r.cost_usd)))} |\n`;
md += `| Com subagente | ${comSubagente.length} | ${fmt(mediana(comSubagente.map((r) => r.cost_usd)))} |\n`;
md += `| Com troca de modelo | ${comTroca.length} | ${fmt(mediana(comTroca.map((r) => r.cost_usd)))} |\n`;
md += `| Com compactação | ${comCompactacao.length} | ${fmt(mediana(comCompactacao.map((r) => r.cost_usd)))} |\n`;
md += `\n## Rubrica dominante por sessão (contagem de sessões onde a rubrica foi a maior)\n\n`;
md += `| Rubrica | Sessões |\n`;
md += `| --- | --- |\n`;
md += `| output_usd | ${rubricaMaiorCount.output_usd} |\n`;
md += `| cache_write_usd | ${rubricaMaiorCount.cache_write_usd} |\n`;
md += `| cache_read_usd | ${rubricaMaiorCount.cache_read_usd} |\n`;
md += `\n## Previsto × real (D0 da plan-generation)\n\n`;
if (previstoRealRows.length === 0) {
  md += `Nenhum plano com linha \`D0: previsto N / real M\` encontrado em \`.claude/plans/*.md\`.\n`;
} else {
  md += `| Arquivo | Previsto | Real | Razão (real/previsto) |\n`;
  md += `| --- | --- | --- | --- |\n`;
  for (const r of previstoRealRows) {
    md += `| ${r.arquivo} | ${r.previsto} | ${r.real} | ${r.razao} |\n`;
  }
}
md += `\n## Notas\n\n`;
md += `- CSV completo: \`sessoes-reais.csv\` (${total} linhas de dados).\n`;
md += `- Segredos encontrados nos logs: ${secretsFound.length === 0 ? 'nenhum' : secretsFound.length}.\n`;
if (secretsFound.length > 0) {
  md += `  (caminho + tipo apenas, valor nunca reproduzido)\n`;
  for (const s of secretsFound) md += `  - ${s.path} (${s.type})\n`;
}

const mdPath = join(outDir, 'sessoes-reais.md');
writeFileSync(mdPath, md);

console.error(`escrito: ${csvPath}`);
console.error(`escrito: ${mdPath}`);
if (secretsFound.length > 0) {
  console.error(`ATENCAO: ${secretsFound.length} possivel(is) credencial(is) encontrada(s) nos logs — ver ${mdPath}`);
}
