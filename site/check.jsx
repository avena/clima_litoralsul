import { readFileSync } from "node:fs";
import { renderToString } from "react-dom/server";
import App from "./src/App.jsx";

const dados = JSON.parse(readFileSync("public/dados.json", "utf8"));

function renderar(hash) {
  globalThis.location = { hash };
  return renderToString(<App dados={dados} />);
}

const registro = renderar("#/registro");
const itanhaem = renderar("#/itanhaem");
const pariquera = renderar("#/pariquera-acu");
const unesp = renderar("#/registro-unesp");
const p2 = renderar("#/pariquera-acu-2");

const checagens = [
  [registro.includes("Climatograma"), "climatograma renderiza"],
  [registro.includes("1.510"), "chuva anual formatada em pt-BR"],
  [registro.includes("polygon"), "envelope térmico presente"],
  [registro.includes("Matriz mensal"), "tabela presente"],
  [registro.includes("Janeiro (248,4 mm)"), "mês do pico traduzido"],
  [itanhaem.includes("Nenhuma estação do CIIAGRO"), "município sem estação avisa"],
  [p2.includes("Pariquera-Açu 2") && p2.includes("299"), "URL #/pariquera-acu-2 abre a estação 299"],
  [
    (registro.match(/href="#\//g) || []).length ===
      dados.municipios.reduce((n, m) => n + Math.max(1, m.estacoes.length), 0),
    "um card por estação, mais um por município sem estação",
  ],
  [registro.includes('href="#/registro-unesp"'), "segunda estação de Registro tem card e URL própria"],
  [unesp.includes("Registro Unesp") && /109/.test(unesp), "URL #/registro-unesp abre a estação 109"],
  [registro.includes("github.com/avena/clima_litoralsul"), "rodapé linka o repositório"],
  [registro.includes("Dados sincronizados em"), "rodapé mostra a data dos dados"],
  [/NaN|undefined|Infinity/.test(registro) === false, "sem NaN/undefined no HTML"],
];

let falhas = 0;
for (const [ok, nome] of checagens) {
  if (!ok) falhas++;
  console.log(ok ? "ok  " : "FALHA", nome);
}
process.exit(falhas ? 1 : 0);
