const L = 52;
const R = 52;
const T = 16;
const B = 34;
const W = 760;
const H = 330;
const dl = L;
const dr = W - R;
const dt = T;
const db = H - B;
const passo = (dr - dl) / 12;

const CORES = {
  chuva: "#4cd7f6",
  tmax: "#ffb690",
  tmed: "#b4c5ff",
  tmin: "#4cd7f6",
};

/** Maior valor da coluna, ignorando meses sem medição. */
function maior(meses, campo) {
  const reais = meses.map((m) => m[campo]).filter((v) => v !== null);
  return reais.length ? Math.max(...reais) : null;
}

/** Menor valor da coluna, ignorando meses sem medição. */
function menor(meses, campo) {
  const reais = meses.map((m) => m[campo]).filter((v) => v !== null);
  return reais.length ? Math.min(...reais) : null;
}

/** Número de uma casa decimal no formato brasileiro, para rótulo do gráfico. */
const num = (v, casas = 1) => v.toFixed(casas).replace(".", ",");

/**
 * Desenha o climatograma de eixo duplo: chuva em barras (mm, esquerda) e
 * t mín/méd/máx em linhas (°C, direita), com o envelope térmico sombreado.
 * Sem biblioteca de gráfico: SVG puro, escala arredondada e `—` para ausente.
 *
 * As quatro séries são sempre desenhadas: o gráfico não muda de forma quando
 * alguém escolhe uma na legenda. O que muda é `rotular` — a série escolhida
 * ganha o valor de cada mês impresso ao lado da barra ou do ponto.
 */
export default function Climatograma({ meses, foco, setFoco, rotular = null }) {

  const maxChuva = maior(meses, "chuva") ?? 0;
  const topoChuva = Math.max(100, Math.ceil(maxChuva / 50) * 50);

  const minT = Math.min(menor(meses, "tmin") ?? 10, menor(meses, "tmed") ?? 10);
  const maxT = Math.max(maior(meses, "tmax") ?? 30, maior(meses, "tmed") ?? 30);
  const baseT = Math.floor((minT - 1) / 5) * 5;
  const topoT = Math.max(baseT + 10, Math.ceil((maxT + 1) / 5) * 5);

  const yChuva = (v) => db - (v / topoChuva) * (db - dt);
  const yTemp = (v) => db - ((v - baseT) / (topoT - baseT)) * (db - dt);
  const x = (i) => dl + (i + 0.5) * passo;

  const envelope = [];
  let trecho = [];
  {
    [...meses, { tmin: null, tmax: null }].forEach((m, i) => {
      if (m.tmin !== null && m.tmax !== null) {
        trecho.push(i);
        return;
      }
      if (trecho.length > 1) {
        const cima = trecho.map((j) => `${x(j).toFixed(1)},${yTemp(meses[j].tmax).toFixed(1)}`);
        const baixo = [...trecho]
          .reverse()
          .map((j) => `${x(j).toFixed(1)},${yTemp(meses[j].tmin).toFixed(1)}`);
        envelope.push(cima.concat(baixo).join(" "));
      }
      trecho = [];
    });
  }

  const linhas = ["tmax", "tmed", "tmin"]
    .map((campo) => ({
      campo,
      cor: CORES[campo],
      pontos: meses
        .map((m, i) => (m[campo] === null ? null : { i, px: x(i), py: yTemp(m[campo]) }))
        .filter(Boolean),
    }));

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      className="w-full"
      aria-label="Climatograma: chuva mensal e temperaturas"
    >
      <defs>
        <linearGradient id="chuva" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#4cd7f6" stopOpacity="0.95" />
          <stop offset="100%" stopColor="#03b5d3" stopOpacity="0.22" />
        </linearGradient>
      </defs>

      {[0, 1, 2, 3, 4].map((i) => {
        const frac = i / 4;
        const y = db - frac * (db - dt);
        return (
          <g key={i}>
            <line x1={dl} x2={dr} y1={y} y2={y} stroke="#1d2740" strokeDasharray="3 5" />
            <text x={dl - 8} y={y + 4} textAnchor="end" fontSize="12" fill="#4cd7f6">
              {Math.round(topoChuva * frac)}
            </text>
            <text x={dr + 8} y={y + 4} textAnchor="start" fontSize="12" fill="#ffb690">
              {Math.round(baseT + (topoT - baseT) * frac)}°
            </text>
          </g>
        );
      })}

      {envelope.map((pontos, i) => (
        <polygon key={i} points={pontos} fill="#ffb690" fillOpacity="0.08" />
      ))}

      {meses.map((m, i) => (
        <g key={m.mes}>
          {m.chuva !== null && (
            <rect
              x={x(i) - (passo * 0.46) / 2}
              y={yChuva(m.chuva)}
              width={passo * 0.46}
              height={Math.max(1, yChuva(0) - yChuva(m.chuva))}
              rx="3"
              fill="url(#chuva)"
            />
          )}
          {rotular === "chuva" && m.chuva !== null && (
            <text
              x={x(i)}
              y={yChuva(m.chuva) - 5}
              textAnchor="middle"
              fontSize="11"
              fill="#4cd7f6"
            >
              {Math.round(m.chuva)}
            </text>
          )}
          <text x={x(i)} y={db + 20} textAnchor="middle" fontSize="12" fill="#8d90a0">
            {m.mes}
          </text>
          <rect
            x={x(i) - passo / 2}
            y={dt}
            width={passo}
            height={db - dt}
            fill="transparent"
            className="cursor-crosshair"
            onMouseEnter={() => setFoco(i)}
            onMouseLeave={() => setFoco(null)}
            onClick={() => setFoco(foco === i ? null : i)}
          />
          {foco === i && (
            <line x1={x(i)} x2={x(i)} y1={dt} y2={db} stroke="#93a0bd" strokeOpacity="0.35" />
          )}
        </g>
      ))}

      {linhas.map(({ campo, cor, pontos }) => (
        <g key={campo}>
          {pontos.length > 1 && (
            <polyline
              points={pontos.map((p) => `${p.px.toFixed(1)},${p.py.toFixed(1)}`).join(" ")}
              fill="none"
              stroke={cor}
              strokeWidth="2.2"
              strokeLinejoin="round"
              strokeDasharray={campo === "tmin" ? "5 4" : undefined}
            />
          )}
          {pontos.map((p) => (
            <circle key={p.i} cx={p.px} cy={p.py} r="2.6" fill={cor} />
          ))}
          {rotular === campo &&
            pontos.map((p) => (
              <text
                key={`v${p.i}`}
                x={p.px}
                y={campo === "tmax" ? p.py - 8 : p.py + 16}
                textAnchor="middle"
                fontSize="11"
                fill={cor}
              >
                {num(meses[p.i][campo])}
              </text>
            ))}
        </g>
      ))}
    </svg>
  );
}
