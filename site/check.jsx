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

const checagens = [
  [registro.includes("Climatograma"), "climatograma renderiza"],
  [registro.includes("1.510"), "chuva anual formatada em pt-BR"],
  [registro.includes("polygon"), "envelope térmico presente"],
  [registro.includes("Matriz mensal"), "tabela presente"],
  [registro.includes("Janeiro (248,4 mm)"), "mês do pico traduzido"],
  [itanhaem.includes("Nenhuma estação do CIIAGRO"), "município sem estação avisa"],
  [pariquera.includes("Pariquera-Açu") && pariquera.includes("55"), "segunda estação de Pariquera listada"],
  [(registro.match(/href="#\//g) || []).length === dados.municipios.length, "um card com link por município"],
  [registro.includes('href="#/registro"'), "card do município aponta para o hash"],
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
