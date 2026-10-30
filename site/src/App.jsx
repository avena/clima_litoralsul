import { useEffect, useState } from "react";
import Climatograma from "./Climatograma.jsx";

const NOMES = {
  jan: "Janeiro", fev: "Fevereiro", mar: "Março", abr: "Abril",
  mai: "Maio", jun: "Junho", jul: "Julho", ago: "Agosto",
  set: "Setembro", out: "Outubro", nov: "Novembro", dez: "Dezembro",
};

/** Número no formato brasileiro; ausente é travessão, nunca zero. */
const fmt = (v, casas = 1) =>
  v === null || v === undefined
    ? "—"
    : v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

const mesLongo = (m) => NOMES[m] ?? m;

/**
 * Quantos anos fechados a estação tem, em texto corrido.
 *
 * Args:
 *   n: `anos_completos` da estação no `dados.json`.
 *
 * Returns:
 *   `(29 anos)`, `(1 ano)` ou `(sem ano fechado)`. O parêntese já vem junto
 *   porque acompanha o nome da estação na lista, sem virar frase.
 */
const anosFechados = (n) =>
  n ? `(${n} ${n === 1 ? "ano" : "anos"})` : "(sem ano fechado)";

// Séries do climatograma; a legenda é o filtro. `alto` só muda o formato do
// quadradinho (barra) contra o traço das linhas.
const SERIES = [
  { campo: "chuva", rotulo: "chuva", cor: "bg-chuva", alto: true },
  { campo: "tmax", rotulo: "t máx", cor: "bg-quente" },
  { campo: "tmed", rotulo: "t méd", cor: "bg-med" },
  { campo: "tmin", rotulo: "t mín", cor: "border-t-2 border-dashed border-chuva" },
];

// Injetados em build pelo vite.config.js; `typeof` protege o render fora do Vite.
const COMMIT = typeof __COMMIT__ === "string" ? __COMMIT__ : "local";
const COMMIT_INICIAL = typeof __COMMIT_INICIAL__ === "string" ? __COMMIT_INICIAL__ : "local";
const BUILD = typeof __BUILD__ === "string" ? __BUILD__ : "—";

/** Card de KPI: rótulo, valor grande e até três linhas de detalhe. */
function Card({ titulo, valor, unidade, cor = "text-texto", detalhes = [], barra }) {
  return (
    <div className="rounded-xl border border-borda bg-painel p-4">
      <p className="text-xs uppercase tracking-wider text-fraco sm:text-[0.68rem]">{titulo}</p>
      <p className={`tabular mt-1 text-3xl font-bold leading-tight ${cor}`}>
        {valor}
        <span className="ml-1 text-xs font-normal text-fraco">{unidade}</span>
      </p>
      <dl className="mt-3 space-y-1 border-t border-borda pt-2 text-xs text-fraco">
        {detalhes.map(([rotulo, texto]) => (
          <div key={rotulo} className="flex justify-between gap-2">
            <dt>{rotulo}</dt>
            <dd className="tabular text-right text-texto/80">{texto}</dd>
          </div>
        ))}
      </dl>
      {barra !== undefined && (
        <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-painel-alto">
          <div className="h-full rounded-full bg-chuva" style={{ width: `${Math.min(100, barra)}%` }} />
        </div>
      )}
    </div>
  );
}

/** Meses civis de cada estação do ano no hemisfério sul. */
/**
 * Distribuição sazonal da chuva em barras horizontais, em mm e em %.
 *
 * Total, média/mês e os meses maior e menor vêm prontos do `dados.json`: quem
 * calcula é o `relatorio.py`, para o site e a ficha em LaTeX não divergirem.
 * Embaixo vão os acumulados que antecedem os solstícios — a água que a estação
 * já recebeu quando o dia vira.
 */
function Sazonal({ estacao }) {
  return (
    <>
      <div className="mt-3 space-y-3">
        {estacao.sazonal.map((s) => (
          <div key={s.nome}>
            <div className="flex justify-between text-xs">
              <span>{s.nome}</span>
              <span className="tabular text-chuva">
                {fmt(s.mm)} mm · {fmt(s.pct, 0)}%
              </span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-painel-alto">
              <div
                className="h-full rounded-full bg-chuva"
                style={{ width: `${s.pct ?? 0}%` }}
              />
            </div>
            <p className="tabular mt-1 text-[0.7rem] text-fraco">
              {`média ${fmt(s.media, 0)} mm/mês · maior ${fmt(s.max, 0)} (${s.max_mes}) ` +
                `· menor ${fmt(s.min, 0)} (${s.min_mes})`}
            </p>
          </div>
        ))}
      </div>
      <div className="mt-3 border-t border-borda pt-2 text-[0.7rem]">
        <p className="font-medium">Antes dos solstícios</p>
        <ul className="mt-1 space-y-0.5 text-fraco">
          {estacao.solsticios.map((s) => (
            <li key={s.nome}>
              <span className="tabular text-texto">{`${fmt(s.mm)} mm (${fmt(s.pct, 0)}%)`}</span>
              {` — ${s.de} a ${s.ate}, antes do solstício de ${s.nome} ` +
                `(${s.solsticio === "junho" ? "21/06" : "21/12"})`}
            </li>
          ))}
        </ul>
        <p className="mt-1 text-fraco">
          Dezembro fica depois do solstício de verão e entra no total anual, não nestes
          acumulados.
        </p>
      </div>
    </>
  );
}

/**
 * O que os números desta estação permitem decidir no calendário agrícola.
 *
 * O texto chega pronto do `dados.json` — cada item cita o número que o sustenta.
 * O segundo bloco é o que vale para qualquer município: é onde entra o que não
 * depende da série, como "média não é previsão". Ele fica aberto: conselho
 * escondido atrás de um clique ninguém lê, e a ATER imprime a página.
 */
function Uso({ estacao, regiao }) {
  return (
    <section className="mt-4 rounded-xl border border-borda bg-painel p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold">Uso no planejamento</h2>
        <span className="text-xs text-fraco">
          escrito a partir dos números desta estação
        </span>
      </div>
      <ul className="mt-3 space-y-2 text-sm">
        {estacao.uso.map((item) => (
          <li key={item.titulo}>
            <strong className="font-semibold">{item.titulo}:</strong>{" "}
            <span className="text-fraco">{item.texto}</span>
          </li>
        ))}
      </ul>
      <div className="mt-3 border-t border-borda pt-2">
        <h3 className="text-sm font-semibold">Vale para qualquer município da região</h3>
        <ul className="mt-2 space-y-2 text-sm">
          {regiao.map((item) => (
            <li key={item.titulo}>
              <strong className="font-semibold">{item.titulo}:</strong>{" "}
              <span className="text-fraco">{item.texto}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/** Ranking das estações por chuva anual, da maior para a menor, em barras. */
function Ranking({ estacoes, atual }) {
  const ordenado = [...estacoes]
    .filter((e) => e.chuva_ano !== null)
    .sort((a, b) => b.chuva_ano - a.chuva_ano);
  const maior = ordenado[0]?.chuva_ano ?? 1;
  return (
    <div className="mt-3 space-y-2">
      {ordenado.map((e) => (
        <div key={e.id}>
          <div className="flex justify-between gap-2 text-xs">
            <span className={e.slug === atual ? "font-semibold text-chuva" : ""}>
              {e.nome}
              {e.nome !== e.municipio && (
                <span className="text-fraco"> · {e.municipio}</span>
              )}
            </span>
            <span className="tabular text-chuva">{fmt(e.chuva_ano, 0)} mm</span>
          </div>
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-painel-alto">
            <div
              className={`h-full rounded-full ${e.slug === atual ? "bg-chuva" : "bg-chuva/50"}`}
              style={{ width: `${(e.chuva_ano / maior) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

/** Matriz mensal com micro-barra de chuva proporcional ao mês mais chuvoso. */
function Tabela({ estacao }) {
  const pico = Math.max(...estacao.meses.map((m) => m.chuva ?? 0), 1);
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-xs uppercase tracking-wider text-fraco sm:text-[0.68rem]">
            <th className="border-b border-borda px-2 py-2 text-left">mês</th>
            <th className="border-b border-borda px-2 py-2 text-right">chuva (mm)</th>
            <th className="hidden border-b border-borda px-2 py-2 text-left sm:table-cell">perfil</th>
            <th className="border-b border-borda px-2 py-2 text-right">t mín</th>
            <th className="border-b border-borda px-2 py-2 text-right">t méd</th>
            <th className="border-b border-borda px-2 py-2 text-right">t máx</th>
            <th className="border-b border-borda px-2 py-2 text-right">UR %</th>
            <th className="border-b border-borda px-2 py-2 text-right">n</th>
          </tr>
        </thead>
        <tbody className="tabular">
          {estacao.meses.map((m) => (
            <tr key={m.mes} className="border-b border-borda/60">
              <td className="px-2 py-1.5">{m.mes}</td>
              <td className="px-2 py-1.5 text-right text-chuva">{fmt(m.chuva)}</td>
              <td className="hidden px-2 py-1.5 sm:table-cell">
                <div className="h-1.5 w-24 overflow-hidden rounded-full bg-painel-alto">
                  <div
                    className="h-full rounded-full bg-chuva"
                    style={{ width: `${((m.chuva ?? 0) / pico) * 100}%` }}
                  />
                </div>
              </td>
              <td className="px-2 py-1.5 text-right text-chuva">{fmt(m.tmin)}</td>
              <td className="px-2 py-1.5 text-right text-med">{fmt(m.tmed)}</td>
              <td className="px-2 py-1.5 text-right text-quente">{fmt(m.tmax)}</td>
              <td className="px-2 py-1.5 text-right">{fmt(m.urmed, 0)}</td>
              <td className="px-2 py-1.5 text-right text-fraco">{m.n || "—"}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t border-borda font-semibold">
            <td className="px-2 py-2">ano</td>
            <td className="px-2 py-2 text-right text-chuva">{fmt(estacao.chuva_ano, 0)}</td>
            <td className="hidden px-2 py-2 text-xs text-fraco sm:table-cell">
              {estacao.anos_completos} anos fechados
            </td>
            <td className="px-2 py-2 text-right text-fraco">—</td>
            <td className="px-2 py-2 text-right text-med">{fmt(estacao.tmed_media)}</td>
            <td className="px-2 py-2 text-right text-fraco">—</td>
            <td className="px-2 py-2 text-right">{fmt(estacao.ur, 0)}</td>
            <td className="px-2 py-2 text-right text-fraco">{estacao.anos_completos || "—"}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

/** Dashboard: escolhe município e estação sem recarregar a página. */
export default function App({ dados }) {
  const { municipios } = dados;
  const inicios = municipios.flatMap((m) => m.estacoes.map((e) => e.inicio)).filter(Boolean).sort();
  const fins = municipios.flatMap((m) => m.estacoes.map((e) => e.fim)).filter(Boolean).sort();
  const periodo = inicios.length ? `${inicios[0]} → ${fins[fins.length - 1]}` : "—";
  const estacoes = municipios.flatMap((m) => m.estacoes);
  const daHash = () => decodeURIComponent(location.hash.replace(/^#\/?/, ""));
  const [slug, setSlug] = useState(daHash);
  const [foco, setFoco] = useState(null);
  const [fixo, setFixo] = useState(null);
  // Nenhuma série some do gráfico: `rotular` só diz qual delas mostra os valores.
  const [rotular, setRotular] = useState(null);

  useEffect(() => {
    const aoTrocar = () => setSlug(daHash());
    addEventListener("hashchange", aoTrocar);
    return () => removeEventListener("hashchange", aoTrocar);
  }, []);

  // A rota é da estação (`#/registro-unesp`); o slug do município só serve para
  // chegar ao aviso de "sem estação". Sem hash, abre a primeira estação.
  const semEstacao = municipios.find((m) => m.slug === slug && !m.estacoes.length);
  const estacao =
    estacoes.find((e) => e.slug === slug) ?? (semEstacao ? null : estacoes[0]);
  const municipio = estacao ? estacao.municipio : semEstacao?.nome ?? municipios[0].nome;
  const mes = fixo ?? foco;
  const chave = estacao?.slug ?? semEstacao?.slug;
  // Registro tem "Registro" e "Registro Unesp": o nome da estação precisa aparecer.
  const titulo = estacao
    ? estacao.nome === estacao.municipio
      ? estacao.municipio
      : `${estacao.municipio} — ${estacao.nome}`
    : municipio;
  const cardChuva = estacao ? ((estacao.chuva_ano ?? 0) / 2000) * 100 : 0;

  return (
    <div className="mx-auto max-w-6xl px-3 py-6 sm:px-4 sm:py-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-widest text-fraco sm:text-[0.72rem]">
            Litoral Sul Paulista · CIIAGRO
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">
            Climatologia das estações
          </h1>
          <p className="mt-1 text-base text-fraco sm:text-sm">
            Série mensal medida pelo CIIAGRO, sem interpolação e sem estimativa.
          </p>
        </div>
        <p className="tabular text-xs text-fraco">exportado em {dados.gerado}</p>
      </header>

      <section className="mt-6 rounded-xl border border-borda bg-painel p-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2 px-1">
          <h2 className="text-sm font-semibold">Municípios e estações</h2>
          <span className="tabular text-xs text-fraco">
            {municipios.length} municípios · {estacoes.length} estações
          </span>
        </div>
        <ul className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          {municipios.flatMap((m) =>
            (m.estacoes.length
              ? m.estacoes
              : [{ slug: m.slug, nome: m.nome, semEstacao: true }]
            ).map((e) => {
              const ativo = e.slug === chave;
              const caixa = ativo
                ? "border-med bg-painel-alto"
                : "border-borda/60 hover:border-borda hover:bg-painel-alto";
              const texto = (
                <>
                  <span
                    className={`block text-base leading-snug ${
                      ativo ? "font-semibold text-med" : "text-texto"
                    }`}
                  >
                    {e.nome}
                    {!e.semEstacao && (
                      <span className="tabular ml-1.5 text-[0.7rem] font-normal text-fraco">
                        {anosFechados(e.anos_completos)}
                      </span>
                    )}
                  </span>
                  <span className="tabular block text-[0.72rem] leading-tight text-fraco sm:text-xs">
                    {e.semEstacao ? "sem estação no CIIAGRO" : `${e.inicio} → ${e.fim}`}
                  </span>
                </>
              );
              // Município sem estação fica na lista (não sumir é o ponto), mas
              // desativado: não há série para abrir.
              if (e.semEstacao) {
                return (
                  <li key={e.slug}>
                    <div
                      aria-disabled="true"
                      className="block cursor-not-allowed rounded-lg border border-dashed border-borda/50 px-3 py-2 opacity-45"
                    >
                      {texto}
                    </div>
                  </li>
                );
              }
              return (
                <li key={e.slug}>
                  <a
                    href={`#/${e.slug}`}
                    aria-current={ativo ? "page" : undefined}
                    onClick={() => {
                      setFoco(null);
                      setFixo(null);
                    }}
                    className={`block rounded-lg border px-3 py-2 transition-colors ${caixa}`}
                  >
                    {texto}
                  </a>
                </li>
              );
            }),
          )}
        </ul>
      </section>

      {estacao && (
        <p className="tabular mt-3 text-xs text-fraco">
          estação {estacao.id} · {estacao.inicio} → {estacao.fim} ·{" "}
          {estacao.total_meses} meses
        </p>
      )}

      {!estacao && (
        <p className="mt-4 border-l-2 border-quente bg-painel px-4 py-3 text-sm text-quente/90">
          Nenhuma estação do CIIAGRO neste município. Itanhaém, Mongaguá, Ilha
          Comprida e Peruíbe não têm série na rede usada por este painel — os
          outros 13 municípios têm.
        </p>
      )}

      {estacao && (
        <>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Card
              titulo="Chuva anual"
              valor={fmt(estacao.chuva_ano, 0)}
              unidade="mm/ano"
              cor="text-chuva"
              detalhes={[
                ["Pico mensal", `${mesLongo(estacao.mes_chuvoso)} (${fmt(estacao.chuva_max)} mm)`],
                ["Anos fechados", estacao.anos_completos],
              ]}
              barra={cardChuva}
            />
            <Card
              titulo="Temperatura média"
              valor={fmt(estacao.tmed_media)}
              unidade="°C"
              cor="text-med"
              detalhes={[
                ["Faixa mensal", `${fmt(estacao.tmin_global)} — ${fmt(estacao.tmax_global)} °C`],
                ["Rótulo", estacao.rotulo],
              ]}
            />
            <Card
              titulo="Amplitude sazonal"
              valor={fmt(estacao.amplitude)}
              unidade="°C"
              cor="text-quente"
              detalhes={[
                ["Mais quente", `${mesLongo(estacao.quente)} (${fmt(estacao.quente_t)} °C)`],
                ["Mais frio", `${mesLongo(estacao.frio)} (${fmt(estacao.frio_t)} °C)`],
              ]}
            />
            <Card
              titulo="Umidade relativa"
              valor={fmt(estacao.ur, 0)}
              unidade="%"
              detalhes={[
                ["Mês mais seco", `${mesLongo(estacao.mes_seco)} (${fmt(estacao.chuva_min)} mm)`],
                ["Descarte", estacao.aviso_descarte ? "há leitura excluída" : "nenhum"],
              ]}
              barra={estacao.ur ?? 0}
            />
          </div>

          <div className="mt-4 rounded-xl border border-borda bg-painel p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h2 className="text-base font-semibold">
                  Climatograma — {titulo}
                </h2>
                <a
                  href={`fichas/${estacao.slug}.pdf`}
                  target="_blank"
                  rel="noreferrer"
                  title="Abrir a ficha desta estação em PDF, uma página A4 para imprimir"
                  className="rounded-md border border-borda px-2 py-0.5 text-xs font-medium text-med transition-colors hover:border-med hover:bg-painel-alto"
                >
                  PDF
                </a>
              </div>
              <div className="flex flex-wrap gap-1 text-xs">
                {SERIES.map(({ campo, rotulo, cor, alto }) => {
                  const ligada = rotular === campo;
                  return (
                    <button
                      key={campo}
                      type="button"
                      aria-pressed={ligada}
                      title={`Mostrar os valores de ${rotulo} em cada mês`}
                      onClick={() => setRotular(ligada ? null : campo)}
                      className={`flex items-center gap-1.5 rounded-md px-2 py-1 transition-colors ${
                        ligada
                          ? "bg-painel-alto font-semibold text-texto"
                          : "text-fraco hover:bg-painel-alto hover:text-texto"
                      }`}
                    >
                      <i className={`${alto ? "h-2 w-3 rounded-sm" : "w-4"} ${cor}`} />
                      {rotulo}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="tabular mt-2 flex flex-wrap gap-x-5 gap-y-1 rounded-lg bg-painel-alto px-3 py-2 text-xs text-fraco">
              {mes === null ? (
                <span>Clique num mês para fixar os valores; passe o cursor para só espiar.</span>
              ) : (
                <>
                  <span className="text-texto">
                    <strong>{mesLongo(estacao.meses[mes].mes)}</strong>
                    {fixo === null ? "" : " · fixado"}
                  </span>
                  {[
                    ["Chuva", `${fmt(estacao.meses[mes].chuva)} mm`, "text-chuva"],
                    ["mín", `${fmt(estacao.meses[mes].tmin)} °C`, "text-chuva"],
                    ["méd", `${fmt(estacao.meses[mes].tmed)} °C`, "text-med"],
                    ["máx", `${fmt(estacao.meses[mes].tmax)} °C`, "text-quente"],
                    ["UR", `${fmt(estacao.meses[mes].urmed, 0)} %`, "text-texto"],
                    ["n", `${estacao.meses[mes].n} anos`, "text-texto"],
                  ].map(([rotulo, texto, cor]) => (
                    <span key={rotulo}>
                      {rotulo}: <strong className={cor}>{texto}</strong>
                    </span>
                  ))}
                  {fixo !== null && (
                    <button
                      type="button"
                      onClick={() => setFixo(null)}
                      className="text-med underline-offset-2 hover:underline"
                    >
                      soltar
                    </button>
                  )}
                </>
              )}
            </div>

            <div className="mt-2">
              <Climatograma
                meses={estacao.meses}
                foco={foco}
                setFoco={setFoco}
                fixo={fixo}
                setFixo={setFixo}
                rotular={rotular}
              />
            </div>
            <p className="mt-2 text-xs text-fraco">
              Barras: chuva mensal (mm, eixo esquerdo). Linhas e faixa sombreada:
              temperaturas mínima, média e máxima (°C, eixo direito). O gráfico
              mostra sempre as quatro séries; clique na legenda para imprimir os
              valores de uma delas em cada mês.
            </p>
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-[17rem_1fr]">
            <div className="rounded-xl border border-borda bg-painel p-4">
              <h2 className="text-base font-semibold">Chuva por estação do ano</h2>
              <Sazonal estacao={estacao} />
            </div>
            <div className="rounded-xl border border-borda bg-painel p-4">
              <h2 className="text-base font-semibold">Matriz mensal</h2>
              <Tabela estacao={estacao} />
            </div>
          </div>

          {estacao.aviso && (
            <p className="mt-4 border-l-2 border-quente bg-painel px-4 py-3 text-sm text-quente/90">
              {estacao.aviso}
            </p>
          )}

          <section className="mt-4 rounded-xl border border-borda bg-painel p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-base font-semibold">Chuva anual por estação</h2>
              <span className="text-xs text-fraco">da maior para a menor · mm/ano</span>
            </div>
            <Ranking estacoes={estacoes} atual={estacao.slug} />
            <p className="mt-3 text-xs text-fraco">
              Média dos anos com os 12 meses fechados. Comparação direta, sem
              ajuste por período — série curta continua sendo série curta.
            </p>
          </section>

          <Uso estacao={estacao} regiao={dados.regiao.uso} />

          <p className="mt-4 text-xs text-fraco">
            {estacao.aviso_descarte ??
              "Nenhuma leitura excluída: tudo o que está no gráfico entrou na média."}{" "}
            Fonte: CIIAGRO (IAC), chuva é o total do mês.
          </p>
        </>
      )}

      <footer className="mt-8 border-t border-borda pt-4 text-xs text-fraco">
        <dl className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <dt className="text-fraco/70">Fonte</dt>
            <dd>
              <a className="text-med underline-offset-2 hover:underline" href="http://www.ciiagro.org.br">
                CIIAGRO (IAC)
              </a>{" "}
              · chuva em mm, temperatura em °C, UR em %
            </dd>
          </div>
          <div>
            <dt className="text-fraco/70">Série no painel</dt>
            <dd className="tabular">{periodo} · {estacoes.length} estações</dd>
          </div>
          <div>
            <dt className="text-fraco/70">Dados sincronizados em</dt>
            <dd className="tabular">{dados.gerado}</dd>
          </div>
          <div>
            <dt className="text-fraco/70">Build</dt>
            <dd className="tabular">
              <code>{COMMIT}</code> em {BUILD}
            </dd>
          </div>
          <div>
            <dt className="text-fraco/70">Commit inicial</dt>
            <dd className="tabular">
              <code>{COMMIT_INICIAL}</code>
            </dd>
          </div>
          <div>
            <dt className="text-fraco/70">Código</dt>
            <dd>
              <a
                className="text-med underline-offset-2 hover:underline"
                href="https://github.com/avena/clima_litoralsul"
              >
                github.com/avena/clima_litoralsul
              </a>
            </dd>
          </div>
        </dl>
        <p className="mt-3">
          Ambiente: coleta em Python 3.12 (só stdlib) → SQLite → JSON → este painel
          em React + Tailwind buildado com Vite, servido como estático. O banco
          preserva o valor original; a faixa de sanidade só exclui da média.
        </p>
      </footer>
    </div>
  );
}
