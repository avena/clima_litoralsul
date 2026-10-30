import { readFileSync } from "node:fs";
import { renderToString } from "react-dom/server";
import App from "./src/App.jsx";
import Climatograma from "./src/Climatograma.jsx";

const dados = JSON.parse(readFileSync("public/dados.json", "utf8"));

function renderar(hash) {
  globalThis.location = { hash };
  return renderToString(<App dados={dados} />);
}

const registro = renderar("#/registro");

// Uma série só: modo leitura, com o valor impresso em cada mês.
const meses = dados.municipios
  .flatMap((m) => m.estacoes)
  .find((e) => e.slug === "registro").meses;
const soChuva = renderToString(
  <Climatograma meses={meses} foco={null} setFoco={() => {}} rotular="chuva" />,
);
const semRotulo = renderToString(
  <Climatograma meses={meses} foco={null} setFoco={() => {}} />,
);
// Mês fixado pelo clique: a guia fica mais forte e não some no mouseleave.
const fixado = renderToString(
  <Climatograma meses={meses} foco={null} setFoco={() => {}} fixo={6} />,
);
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
      dados.municipios.reduce((n, m) => n + m.estacoes.length, 0),
    "um link por estação",
  ],
  [(registro.match(/aria-disabled="true"/g) || []).length === 4, "os 4 municípios sem estação ficam desativados"],
  [
    registro.includes("(29 anos)") && registro.includes("(14 anos)"),
    "lista de estações mostra quantos anos fechados cada uma tem",
  ],
  [
    dados.regioes.length === 3 &&
      dados.regioes.every((r) => registro.includes(`>${r}<`)),
    "lista separada nas 3 regiões do painel (Litoral Sul, Vale do Ribeira, Alto Vale)",
  ],
  [
    registro.includes('href="fichas/registro.pdf"'),
    "climatograma linka a ficha em PDF da própria estação",
  ],
  [
    unesp.includes('href="fichas/registro-unesp.pdf"') &&
      !unesp.includes('href="fichas/registro.pdf"'),
    "link do PDF segue o slug da estação, não o do município",
  ],
  [registro.includes('href="#/registro-unesp"'), "segunda estação de Registro tem card e URL própria"],
  [unesp.includes("Registro Unesp") && /109/.test(unesp), "URL #/registro-unesp abre a estação 109"],
  [registro.includes("github.com/avena/clima_litoralsul"), "rodapé linka o repositório"],
  [registro.includes("Dados sincronizados em"), "rodapé mostra a data dos dados"],
  [
    soChuva.includes(">248<") && soChuva.includes("<polyline"),
    "destacar chuva imprime os mm sem esconder as linhas",
  ],
  [
    !semRotulo.includes(">248<") && semRotulo.includes("<polyline"),
    "sem destaque o gráfico fica com as quatro séries e sem números",
  ],
  [fixado.includes('stroke-width="1.6"'), "mês clicado fica fixado no gráfico"],
  [registro.includes("mm/mês"), "sazonal mostra máx, mín e média"],
  [registro.includes("média 206 mm/mês"), "média mensal da estação vem do dados.json"],
  [registro.includes("Antes dos solstícios"), "acumulado antes dos solstícios presente"],
  [registro.includes("antes do solstício de inverno (21/06)"), "solstício de inverno datado"],
  [registro.includes("Uso no planejamento"), "card de uso agronômico presente"],
  [registro.includes("Vale para qualquer município da região"), "orientação geral separada da local"],
  [
    !registro.includes("<details") && registro.includes("Média não é previsão"),
    "orientação geral visível sem clique: nada recolhido em <details>",
  ],
  [registro.includes("Calagem em cobertura"), "orientação local cita a janela de calagem"],
  [
    (registro.match(/Uso no planejamento/g) || []).length === 1,
    "card de uso aparece uma vez, não por estação vizinha",
  ],
  [registro.includes("Chuva anual por estação"), "ranking de chuva anual presente"],
  [/NaN|undefined|Infinity/.test(registro) === false, "sem NaN/undefined no HTML"],
];

let falhas = 0;
for (const [ok, nome] of checagens) {
  if (!ok) falhas++;
  console.log(ok ? "ok  " : "FALHA", nome);
}
process.exit(falhas ? 1 : 0);
