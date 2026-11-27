/**
 * Testes automatizados do motor determinístico offline (web/offline-core.js).
 *
 * Execução:
 *   node tests/test_offline_core.js
 */
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.resolve(__dirname, "..");
const cardsData = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "cards.json"), "utf8"));
const ngramData = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "ngram.json"), "utf8"));
const cardsById = Object.fromEntries(cardsData.cards.map((c) => [c.id, c]));

const sandbox = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(ROOT, "web", "offline-core.js"), "utf8"), sandbox);
const Offline = sandbox.window.ApontaOffline;

let passed = 0;
function test(name, fn) {
  fn();
  passed++;
  console.log("OK:", name);
}

test("ordenar coloca líder na frente e por_favor no fim", () => {
  assert.deepStrictEqual(Offline.ordenar(["cabeca", "dor"], cardsById), ["dor", "cabeca"]);
  assert.deepStrictEqual(
    Offline.ordenar(["por_favor", "agua", "eu_quero"], cardsById),
    ["eu_quero", "agua", "por_favor"]
  );
});

test("ordenar prioriza eu_quero e nao_quero sobre ajuda", () => {
  assert.deepStrictEqual(Offline.ordenar(["ajuda", "eu_quero"], cardsById), ["eu_quero", "ajuda"]);
  assert.deepStrictEqual(Offline.ordenar(["ajuda", "nao_quero"], cardsById), ["nao_quero", "ajuda"]);
});

test("regras de ajuda", () => {
  assert.strictEqual(Offline.falarOffline(["ajuda", "eu_quero"], [], cardsById).frase, "Eu quero ajuda.");
  assert.strictEqual(Offline.falarOffline(["ajuda", "nao_quero"], [], cardsById).frase, "Não quero ajuda.");
  assert.strictEqual(
    Offline.falarOffline(["ajuda", "banheiro"], [], cardsById).frase,
    "Preciso de ajuda para ir ao banheiro."
  );
  assert.strictEqual(
    Offline.falarOffline(["ajuda", "mochila"], [], cardsById).frase,
    "Preciso de ajuda com a mochila."
  );
  assert.strictEqual(
    Offline.falarOffline(["ajuda", "mamae"], [], cardsById).frase,
    "Mamãe, preciso de ajuda."
  );
});

test("regras de dor e concordância", () => {
  assert.strictEqual(Offline.falarOffline(["cabeca", "dor"], [], cardsById).frase, "Minha cabeça está doendo.");
  assert.strictEqual(Offline.falarOffline(["dor", "barriga"], [], cardsById).frase, "Minha barriga está doendo.");
  assert.strictEqual(
    Offline.falarOffline(["mamae", "dor", "cabeca"], [], cardsById).frase,
    "Mamãe, minha cabeça está doendo."
  );
});

test("recipientes e ações", () => {
  assert.strictEqual(
    Offline.falarOffline(["agua", "copo", "eu_quero"], [], cardsById).frase,
    "Eu quero um copo de água."
  );
  assert.strictEqual(
    Offline.falarOffline(["eu_quero", "garrafa", "agua", "por_favor"], [], cardsById).frase,
    "Eu quero uma garrafa de água, por favor."
  );
  assert.strictEqual(
    Offline.falarOffline(["eu_quero", "banheiro"], [], cardsById).frase,
    "Eu quero ir ao banheiro."
  );
});

test("memória de contexto com mais", () => {
  assert.strictEqual(
    Offline.falarOffline(["mais"], ["eu_quero", "agua"], cardsById).frase,
    "Eu quero mais água."
  );
});

test("listas e vocativos", () => {
  assert.strictEqual(
    Offline.falarOffline(["eu_quero", "bola", "agua"], [], cardsById).frase,
    "Eu quero a bola e água."
  );
  assert.strictEqual(
    Offline.falarOffline(["nao_quero", "bola", "agua"], [], cardsById).frase,
    "Não quero a bola nem água."
  );
  assert.strictEqual(Offline.falarOffline(["oi", "mamae"], [], cardsById).frase, "Oi, mamãe!");
  assert.strictEqual(Offline.falarOffline(["feliz", "mamae"], [], cardsById).frase, "Mamãe, estou feliz.");
});

test("sugerirOffline retorna top-4 a partir da tabela N-grama", () => {
  const sugs = Offline.sugerirOffline("lanche", ["eu_quero"], ngramData, 4);
  assert.ok(Array.isArray(sugs));
  assert.ok(sugs.length > 0 && sugs.length <= 4);
});

console.log(`\nTotal: ${passed} testes do motor offline passaram.`);
