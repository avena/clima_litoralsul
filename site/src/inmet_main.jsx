import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import InmetApp from "./InmetApp.jsx";
import "./index.css";

/** Monta o painel de dados históricos do INMET. */
async function iniciar() {
  const raiz = createRoot(document.getElementById("root"));
  try {
    const resposta = await fetch(`${import.meta.env.BASE_URL}inmet_regional.json`);
    if (!resposta.ok) throw new Error(`inmet_regional.json: HTTP ${resposta.status}`);
    const dados = await resposta.json();
    raiz.render(
      <StrictMode>
        <InmetApp dados={dados} />
      </StrictMode>,
    );
  } catch (erro) {
    raiz.render(
      <div className="m-8 max-w-xl rounded-xl border border-borda bg-painel p-6 font-mono">
        <h2 className="text-base font-semibold text-quente">Erro ao carregar dados históricos</h2>
        <p className="mt-2 text-sm text-fraco">
          Não foi possível carregar <code>inmet_regional.json</code> ({String(erro)}).
        </p>
        <p className="mt-3 text-xs text-fraco">
          Arquivo de dados históricos não encontrado na pasta pública.
        </p>
      </div>,
    );
  }
}

iniciar();
