#!/usr/bin/env node
// Aceite do S010 em dois níveis + cobertura do conserto (plano 006, revisão 5 do S010).
//
//   estrito   — pré-registro de 2026-09-25: todos os its do PR (hidden_total_ref) e tsc_errors 0.
//               É o mesmo `pass` do grade.json; aqui só é recontado.
//   funcional — critério de decisão a partir da revisão 5: tsc_errors 0 e todos os its do PR, EXCETO
//               os listados em scenarios/S010-replay-pr-real/aceite-excluidos.tsv para o sha (its
//               "a adivinhar", CHARTER P4). Denominador fixo: hidden_total_ref − nº de excluídos do sha.
//               Não há margem percentual: a margem é a lista, it por it, cada um com motivo.
//   cobertura — descritiva, SEM limiar: dos its que o PR faz passar (passam no controle positivo e
//               não passam no negativo) e não estão excluídos, quantos o braço fez passar.
//               `regressoes` = its que passam no controle negativo (commit pai) e falharam no braço.
//               null quando os controles por it da tarefa ainda não existem.
//
// Só lê. Nunca escreve em runs/.
//
// Uso (a partir de ~/.claude/evals):
//   node graders/aceite-funcional.mjs            → uma linha por run do S010 (diagnóstico)
//   import { carregarContexto, avaliarAceite } from './aceite-funcional.mjs'

import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const readJson = (p) => {
  try {
    return JSON.parse(readFileSync(p, 'utf8'));
  } catch {
    return null;
  }
};

/** Chave estável de um it: caminho do spec a partir de `libs/` + fullName sem espaços nas pontas. */
export const chaveIt = (specPath, fullName) =>
  `${specPath.split('\\').join('/').replace(/^.*?\/(libs\/)/, '$1')} :: ${String(fullName).trim()}`;

/** Lê os vitest-*.json de um diretório → Map(chave → 'passed' | outro status). */
export function lerIts(dir) {
  const its = new Map();
  if (!existsSync(dir)) return null;
  const arquivos = readdirSync(dir).filter((f) => /^vitest-.+\.json$/.test(f));
  if (!arquivos.length) return null;
  for (const f of arquivos) {
    const j = readJson(join(dir, f));
    for (const tr of j?.testResults ?? [])
      for (const a of tr.assertionResults ?? []) its.set(chaveIt(tr.name, a.fullName), a.status);
  }
  return its;
}

/** Lista de excluídos: Map(sha → Set(chave)). */
export function lerExcluidos(scenDir) {
  const mapa = new Map();
  const p = join(scenDir, 'aceite-excluidos.tsv');
  if (!existsSync(p)) return mapa;
  for (const linha of readFileSync(p, 'utf8').trim().split(/\r?\n/).slice(1)) {
    if (!linha.trim()) continue;
    const [sha, spec, teste] = linha.split('\t');
    if (!mapa.has(sha)) mapa.set(sha, new Set());
    mapa.get(sha).add(chaveIt(spec, teste));
  }
  return mapa;
}

/** Controles por it: scenarios/S010-replay-pr-real/controles/<task>-<sha>-{positivo,negativo}/. */
export function lerControles(scenDir, task, sha) {
  const base = join(scenDir, 'controles');
  const positivo = lerIts(join(base, `${task}-${sha}-positivo`));
  const negativo = lerIts(join(base, `${task}-${sha}-negativo`));
  return positivo && negativo ? { positivo, negativo } : null;
}

export function carregarContexto(evalsRoot = join(__dirname, '..')) {
  const scenDir = join(evalsRoot, 'scenarios', 'S010-replay-pr-real');
  return { scenDir, excluidos: lerExcluidos(scenDir), controles: new Map() };
}

/**
 * @param runDir  diretório do run (runs/<run>)
 * @param grade   conteúdo do grade.json do run
 * @param task    'T1' | 'T2'
 * @param sha     sha da tarefa do run
 * @param ctx     retorno de carregarContexto()
 */
export function avaliarAceite(runDir, grade, task, sha, ctx) {
  if (!grade) return null;
  const its = lerIts(runDir) ?? new Map();
  const excl = ctx.excluidos.get(sha) ?? new Set();
  const passou = (k) => its.get(k) === 'passed';

  const ref = grade.hidden_total_ref;
  const tscOk = grade.tsc_errors === 0;
  const estrito = { passou: grade.hidden_passed, total: ref, pass: grade.hidden_passed === ref && tscOk };

  const exclPassou = [...excl].filter(passou).length;
  const fTotal = ref - excl.size;
  const fPassou = grade.hidden_passed - exclPassou;
  const falhasFora = [...its.entries()].filter(([k, s]) => s !== 'passed' && !excl.has(k)).map(([k]) => k);
  const funcional = { passou: fPassou, total: fTotal, excluidos: excl.size, pass: fPassou === fTotal && tscOk, falhas_fora_da_lista: falhasFora };

  const chaveCtl = `${task}@${sha}`;
  if (!ctx.controles.has(chaveCtl)) ctx.controles.set(chaveCtl, lerControles(ctx.scenDir, task, sha));
  const ctl = ctx.controles.get(chaveCtl);
  let cobertura = null;
  if (ctl) {
    const alvo = [...ctl.positivo.entries()]
      .filter(([k, s]) => s === 'passed' && ctl.negativo.get(k) !== 'passed' && !excl.has(k))
      .map(([k]) => k);
    const base = [...ctl.negativo.entries()].filter(([, s]) => s === 'passed').map(([k]) => k);
    const entregues = alvo.filter(passou).length;
    cobertura = {
      passou: entregues,
      total: alvo.length,
      taxa: alvo.length ? Number((entregues / alvo.length).toFixed(4)) : null,
      regressoes: base.filter((k) => !passou(k)).length,
    };
  }
  return { estrito, funcional, cobertura, tsc_errors: grade.tsc_errors };
}

// ---- CLI: diagnóstico, uma linha por run ----
if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) {
  const evals = join(__dirname, '..');
  const ctx = carregarContexto(evals);
  const runsDir = join(evals, 'runs');
  const dirs = readdirSync(runsDir)
    .filter((d) => /^\d{4}-\d{2}-\d{2}-S010-[A-Z]+-T\d+-t\d+$/.test(d) && statSync(join(runsDir, d)).isDirectory())
    .sort();
  for (const run of dirs) {
    const dir = join(runsDir, run);
    const grade = readJson(join(dir, 'grade.json'));
    const win = readJson(join(dir, 'window.json'));
    const task = run.match(/-(T\d+)-t\d+$/)[1];
    const sha = win?.sha ?? grade?.sha ?? '?';
    const a = avaliarAceite(dir, grade, task, sha, ctx);
    if (!a) {
      console.log(`${run}\tsem grade.json`);
      continue;
    }
    const cob = a.cobertura ? `${a.cobertura.passou}/${a.cobertura.total} regressoes=${a.cobertura.regressoes}` : 'sem controles';
    console.log(
      `${run}\t${sha}\testrito ${a.estrito.passou}/${a.estrito.total} ${a.estrito.pass}\tfuncional ${a.funcional.passou}/${a.funcional.total} ${a.funcional.pass}\ttsc ${a.tsc_errors}\tcobertura ${cob}`,
    );
  }
}
