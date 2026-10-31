import { useState } from "react";

/** Formata número em pt-BR com casas decimais fixas ou hífen se ausente. */
function fmt(val, casas = 1) {
  if (val === null || val === undefined || isNaN(val)) return "—";
  return Number(val).toLocaleString("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });
}

/** Dashboard dos dados históricos em lote do INMET. */
export default function InmetApp({ dados }) {
  const estacoes = dados?.estacoes || [];
  const [ativaId, setAtivaId] = useState(estacoes[0]?.codigo || "");

  const est = estacoes.find((e) => e.codigo === ativaId) || estacoes[0];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <header className="border-b border-borda pb-6">
        <a
          href="/"
          className="inline-flex items-center gap-1.5 text-xs text-sky-400 underline-offset-2 hover:underline mb-3"
        >
          ← Voltar para o Painel Climatológico Principal
        </a>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold uppercase tracking-wider border border-sky-400/30 bg-sky-400/10 text-sky-400">
              Dados Históricos em Lote · INMET
            </span>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
              Dados Históricos INMET
            </h1>
            <p className="mt-1 text-sm text-fraco">
              Séries horárias consolidadas a partir dos arquivos anuais compactados oficiais.
            </p>
          </div>
          <div>
            <a
              href="https://portal.inmet.gov.br/dadoshistoricos"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-lg border border-borda bg-painel px-3 py-1.5 text-xs font-medium text-med hover:border-borda/80 hover:bg-painel-alto"
            >
              portal.inmet.gov.br/dadoshistoricos ↗
            </a>
          </div>
        </div>
      </header>

      <div className="mt-6 rounded-xl border border-sky-500/20 bg-sky-950/20 p-4 text-xs text-sky-200/90 leading-relaxed sm:text-sm">
        <strong className="text-sky-300">Origem e consolidação dos dados:</strong> Estas medições foram
        extraídas diretamente dos arquivos <code>.zip</code> anuais do INMET cobrindo as estações
        meteorológicas automáticas de superfície do Litoral Sul e Vale do Ribeira (SP).
      </div>

      {/* Abas de seleção de estação */}
      <div className="mt-6 flex flex-wrap gap-2">
        {estacoes.map((item) => {
          const ativo = item.codigo === est?.codigo;
          return (
            <button
              key={item.codigo}
              type="button"
              onClick={() => setAtivaId(item.codigo)}
              className={`rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
                ativo
                  ? "border-sky-400 bg-sky-400/15 text-sky-300 font-semibold"
                  : "border-borda bg-painel text-texto hover:border-borda/80 hover:bg-painel-alto"
              }`}
            >
              {item.nome} ({item.codigo})
            </button>
          );
        })}
      </div>

      {est && (
        <>
          {/* Grid de Metadados */}
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-borda bg-painel p-4">
              <p className="text-xs uppercase tracking-wider text-fraco">Estação / Código</p>
              <p className="mt-1 text-lg font-semibold text-texto truncate">
                {est.nome}{" "}
                <span className="text-xs font-normal text-fraco">({est.codigo})</span>
              </p>
              <p className="text-xs text-fraco">{est.uf} · Início: {est.inicio || "—"}</p>
            </div>

            <div className="rounded-xl border border-borda bg-painel p-4">
              <p className="text-xs uppercase tracking-wider text-fraco">Coordenadas (GPS)</p>
              {est.lat != null && est.lon != null ? (
                <a
                  href={`https://www.google.com/maps?q=${est.lat},${est.lon}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="tabular mt-1 block text-lg font-semibold text-sky-400 underline-offset-2 hover:underline"
                  title="Abrir no Google Maps"
                >
                  {fmt(est.lat, 4)}, {fmt(est.lon, 4)} ↗
                </a>
              ) : (
                <p className="tabular mt-1 text-lg font-semibold text-texto">—</p>
              )}
              <p className="text-[0.7rem] text-fraco">Clique para abrir no Google Maps</p>
            </div>

            <div className="rounded-xl border border-borda bg-painel p-4">
              <p className="text-xs uppercase tracking-wider text-fraco">Altitude</p>
              <p className="tabular mt-1 text-lg font-semibold text-texto">
                {est.altitude != null ? `${fmt(est.altitude, 1)} m` : "—"}
              </p>
              <p className="text-xs text-fraco">Nível médio do mar</p>
            </div>

            <div className="rounded-xl border border-borda bg-painel p-4">
              <p className="text-xs uppercase tracking-wider text-fraco">Meses Processados</p>
              <p className="tabular mt-1 text-lg font-semibold text-texto">
                {est.total_meses}
              </p>
              <p className="text-xs text-fraco">Agregações mensais</p>
            </div>
          </div>

          {/* Tabela de Séries Mensais */}
          <section className="mt-6 rounded-xl border border-borda bg-painel p-4">
            <div className="flex items-center justify-between gap-2 mb-3">
              <h2 className="text-sm font-semibold text-texto">Série Histórica Mensal Consolidada</h2>
              <span className="tabular text-xs text-fraco">{est.meses?.length || 0} meses</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-right text-xs sm:text-sm">
                <thead>
                  <tr className="border-b border-borda text-[0.7rem] font-semibold uppercase tracking-wider text-fraco">
                    <th className="py-2.5 px-3 text-left">Mês</th>
                    <th className="py-2.5 px-3">Chuva (mm)</th>
                    <th className="py-2.5 px-3">T. Média (°C)</th>
                    <th className="py-2.5 px-3">T. Mín (°C)</th>
                    <th className="py-2.5 px-3">T. Máx (°C)</th>
                    <th className="py-2.5 px-3">UR Média (%)</th>
                    <th className="py-2.5 px-3">Dias com dado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-borda/50">
                  {est.meses?.length > 0 ? (
                    est.meses
                      .slice()
                      .reverse()
                      .map((m) => (
                        <tr key={m.mes} className="hover:bg-painel-alto/50">
                          <td className="py-2 px-3 text-left font-mono font-medium text-texto">
                            {m.mes}
                          </td>
                          <td className="tabular py-2 px-3 font-medium text-chuva">
                            {fmt(m.chuva, 1)}
                          </td>
                          <td className="tabular py-2 px-3 text-med">
                            {fmt(m.tmed, 1)}
                          </td>
                          <td className="tabular py-2 px-3 text-sky-300">
                            {fmt(m.tmin, 1)}
                          </td>
                          <td className="tabular py-2 px-3 text-quente">
                            {fmt(m.tmax, 1)}
                          </td>
                          <td className="tabular py-2 px-3 text-texto">
                            {fmt(m.urmed, 0)}%
                          </td>
                          <td className="tabular py-2 px-3 text-fraco">
                            {m.dias_com_dado ?? "—"}
                          </td>
                        </tr>
                      ))
                  ) : (
                    <tr>
                      <td colSpan={7} className="py-6 text-center text-fraco">
                        Nenhum registro histórico encontrado para esta estação.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      <footer className="mt-12 border-t border-borda pt-6 text-center text-xs text-fraco">
        Observatório Agroclimático do Litoral Sul e Vale do Ribeira · Dados:{" "}
        <a
          href="https://portal.inmet.gov.br"
          target="_blank"
          rel="noopener noreferrer"
          className="text-med underline-offset-2 hover:underline"
        >
          INMET
        </a>
      </footer>
    </div>
  );
}
