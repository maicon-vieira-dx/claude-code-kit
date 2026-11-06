#!/usr/bin/env node
// Plano 005: portão do relatório consolidado. Confere, sem julgamento humano:
//   1. as 16 seções `## N. Título` na ordem da especificação;
//   2. a seção 2 (braços) sem resultado (nenhum "US$" nem "hidden");
//   3. menções obrigatórias derivadas de dados.json (sha de cada grupo, "k=1", tipos de anomalia,
//      ids de modelo que divergem no grupo, prices_version, fonte do custo);
//   4. expressões proibidas (ranking artificial; estatística inferencial com k<3);
//   5. todo decimal, percentual e fração do texto existe numa fonte do harness (arredondado na
//      precisão escrita) ou está declarado na subseção "Números derivados" do apêndice.
//
// Uso:
//   node verificar-relatorio.mjs --relatorio <relatorio.md> --dados <dir> [--evals <raiz>]
//   node verificar-relatorio.mjs --relatorio <relatorio.html> --dados <dir> --so-numeros --fonte-extra <relatorio.md>
//     (--so-numeros: só o item 5; HTML perde tags, <script> e <style> antes da conferência)
// <dir> contém dados.json e tabelas.md. Saída: um problema por linha; exit 0 se nenhum, 1 se houver.

import { readFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const getArg = (name, def) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : def;
};
const REL = getArg('--relatorio', null);
const DADOS = getArg('--dados', null);
const EVALS = getArg('--evals', join(__dirname, '..'));
const EXTRA = getArg('--fonte-extra', null);
const SO_NUMEROS = args.includes('--so-numeros');
if (!REL || !DADOS) {
  console.error('uso: node verificar-relatorio.mjs --relatorio <md|html> --dados <dir> [--evals <raiz>] [--so-numeros --fonte-extra <md>]');
  process.exit(2);
}

let rel = readFileSync(REL, 'utf8');
if (/\.html?$/i.test(REL))
  rel = rel
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ');
const dados = JSON.parse(readFileSync(join(DADOS, 'dados.json'), 'utf8'));
const problemas = [];
const erro = (m) => problemas.push(m);
const maxK = Math.max(...Object.values(dados.grupos).flatMap((g) => Object.values(g.trials_por_braco)));

if (!SO_NUMEROS) {
  // ---- 1. seções na ordem ----
  const SECOES = [
    'Resumo executivo',
    'Entendimento prático dos braços',
    'Metodologia dos Evals',
    'Resultados gerais',
    'Análise por dimensão',
    'Análise detalhada de cada braço',
    'Comparação direta entre os braços',
    'Casos em que os braços se comportaram de forma diferente',
    'Análise dos resultados inesperados',
    'Consistência e variabilidade',
    'Custo, eficiência e trade-offs',
    'Qualidade dos resultados',
    'Limitações do experimento',
    'Principais achados',
    'Conclusões',
    'Dados brutos / apêndice',
  ];
  const titulos = [...rel.matchAll(/^## (\d+)\. (.+)$/gm)].map((m) => ({ n: Number(m[1]), t: m[2].trim(), i: m.index }));
  SECOES.forEach((s, k) => {
    const h = titulos.find((x) => x.n === k + 1);
    if (!h) erro(`seção ausente: "## ${k + 1}. ${s}"`);
    else if (!h.t.toLowerCase().startsWith(s.toLowerCase())) erro(`seção ${k + 1} com título "${h.t}", esperado "${s}"`);
  });
  for (let k = 1; k < titulos.length; k++) if (titulos[k].n !== titulos[k - 1].n + 1) erro(`seções fora de ordem: ${titulos[k - 1].n} → ${titulos[k].n}`);
  const secao = (n) => {
    const a = titulos.find((x) => x.n === n);
    const b = titulos.find((x) => x.n === n + 1);
    return a ? rel.slice(a.i, b ? b.i : rel.length) : '';
  };

  // ---- 2. seção 2 sem resultado ----
  if (/US\$|hidden/i.test(secao(2))) erro('seção 2 cita resultado ("US$" ou "hidden") — os braços vêm antes de qualquer número de resultado');

  // ---- 3. menções obrigatórias ----
  const exige = (txt, motivo) => {
    if (!rel.includes(txt)) erro(`menção obrigatória ausente: "${txt}" (${motivo})`);
  };
  for (const g of Object.values(dados.grupos)) exige(g.sha, `sha do grupo ${g.chave}`);
  if (Object.values(dados.grupos).some((g) => !g.vigente) && !/superad/i.test(rel)) erro('há grupo superado e o relatório não usa a tarja "superado"');
  if (maxK < 3) exige('k=1', 'nenhum braço tem 3 trials; a regra do EXPERIMENT.md proíbe ordem entre braços');
  exige('tokens.json', 'fonte única do custo');
  exige(dados.prices_version_vigente, 'tarifa usada no custo');
  for (const tipo of new Set(dados.anomalias.map((a) => a.tipo))) exige(tipo, 'tipo de anomalia detectado pelo consolidador (seção 9 ou 16)');
  for (const a of dados.anomalias.filter((x) => x.tipo === 'modelo_diferente_no_grupo'))
    for (const id of new Set(a.detalhe.match(/claude-[a-z0-9-]+/g) ?? [])) exige(id, `modelo divergente no grupo ${a.run}`);

  // ---- 3b. plano 007: aceite em dois níveis e nenhuma referência à medição anterior ----
  exige('funcional', 'critério de decisão (EXPERIMENT.md, revisão 5)');
  exige('estrito', 'aceite pré-registrado, reportado ao lado do funcional');
  exige('aceite-excluidos.tsv', 'fonte da lista de its fora do aceite funcional');
  const foraTsv = join(EVALS, 'scenarios', 'S010-replay-pr-real', 'runs-fora-do-relatorio.tsv');
  if (existsSync(foraTsv))
    for (const run of readFileSync(foraTsv, 'utf8').trim().split(/\r?\n/).slice(1).map((l) => l.split('\t')[0].trim()).filter(Boolean))
      if (rel.includes(run)) erro(`run fora da medição citado: ${run} (runs-fora-do-relatorio.tsv)`);
  const antigo = rel.match(/claude-sonnet-5(?!-5)\b/);
  if (antigo) erro(`referência a modelo anterior à medição: "${antigo[0]}"`);
  if (/superad[oa]/i.test(rel)) erro('referência à T1 antiga ou a grupo superado — o relatório cobre só a medição vigente');

  // ---- 4. expressões proibidas ----
  const PROIBIDAS = [/\bvencedor(a|es)?\b/i, /\bo melhor braço\b/i, /claramente superior/i, /muito (melhor|pior)/i];
  if (maxK < 3) PROIBIDAS.push(/p-valor|p-value|intervalo de confiança|\bIC ?95/i, /estatisticamente significativ/i);
  for (const re of PROIBIDAS) {
    const m = rel.match(re);
    if (m) erro(`expressão proibida: "${m[0]}"`);
  }
}

// ---- 5. números com fonte ----
const fontes = [join(DADOS, 'tabelas.md'), join(DADOS, 'dados.json')];
if (EXTRA) fontes.push(EXTRA);
for (const f of ['FATOS.md', 'CHARTER.md', 'plans/README.md', 'scenarios/S010-replay-pr-real/EXPERIMENT.md', 'scenarios/S010-replay-pr-real/controles.md', 'scenarios/S010-replay-pr-real/COMO-RODAR.md', 'scenarios/S010-replay-pr-real/tasks.tsv'])
  if (existsSync(join(EVALS, f))) fontes.push(join(EVALS, f));
const corpusTxt = fontes.map((f) => readFileSync(f, 'utf8')).join('\n');
const corpusNum = new Set();
for (const m of corpusTxt.matchAll(/-?\d+(?:[.,]\d+)?/g)) corpusNum.add(Number(m[0].replace(',', '.')));
const corpus = [...corpusNum];

// "Números derivados": subseção do apêndice; o que está declarado lá é aceito (e revisado por humano).
let corpo = rel;
const idxDer = rel.search(/^#{3,4} .*Números derivados/m);
if (idxDer >= 0) {
  // corta do título "Números derivados" até o próximo título (ou o fim do arquivo)
  const resto = rel.slice(idxDer);
  const nl = resto.indexOf('\n');
  const fim = nl >= 0 ? resto.slice(nl + 1).search(/^#{2,4} /m) : -1;
  corpo = rel.slice(0, idxDer) + (fim >= 0 ? resto.slice(nl + 1 + fim) : '');
} else if (!SO_NUMEROS) erro('apêndice sem a subseção "Números derivados" (use-a mesmo que vazia: "nenhum")');

const casa = (v, casas) => corpus.some((c) => Math.abs(Number(c.toFixed(casas)) - v) < 1e-9);
const casaPct = (p, casas) => corpus.some((c) => c >= 0 && c <= 1 && Math.abs(Number((c * 100).toFixed(casas)) - p) < 1e-9) || casa(p, casas);
const limpo = corpo
  .replace(/```[\s\S]*?```/g, ' ')
  .replace(/\d{4}-\d{2}-\d{2}(T[\d:.+-Z]+)?/g, ' ')
  .replace(/\b\d+\.\d+\.\d+\b/g, ' ')
  .replace(/\b[0-9a-f]{7,40}\b/g, ' ')
  .replace(/claude-[a-z0-9-]+/g, ' ');
const semFonte = new Set();
for (const m of limpo.matchAll(/(?<![\w/.,])(\d+)\/(\d+)(?![\w/])/g)) if (!corpusTxt.includes(`${m[1]}/${m[2]}`)) semFonte.add(`${m[1]}/${m[2]}`);
for (const m of limpo.matchAll(/(?<![\w.,])(\d+(?:[.,]\d+)?)\s?%/g)) {
  const casas = (m[1].split(/[.,]/)[1] ?? '').length;
  if (!casaPct(Number(m[1].replace(',', '.')), casas)) semFonte.add(`${m[1]}%`);
}
for (const m of limpo.matchAll(/(?<![\w.,/])(\d+[.,]\d+)(?![\d%]|[.,]\d|\s?%)/g)) {
  const casas = m[1].split(/[.,]/)[1].length;
  if (!casa(Number(m[1].replace(',', '.')), casas)) semFonte.add(m[1]);
}
for (const n of semFonte) erro(`número sem fonte: ${n} — confira nas fontes ou declare em "Números derivados" (valor | fórmula | entradas)`);

if (problemas.length) {
  console.log(problemas.join('\n'));
  console.log(`\n${problemas.length} problema(s).`);
  process.exit(1);
}
console.log(SO_NUMEROS ? 'OK: números conferidos.' : 'OK: seções, menções, expressões e números conferidos.');
