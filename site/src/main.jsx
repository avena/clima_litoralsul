import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./index.css";

/** Monta o dashboard; se `dados.json` faltar, mostra o erro em vez de tela vazia. */
async function iniciar() {
  const raiz = createRoot(document.getElementById("root"));
  try {
    const resposta = await fetch(`${import.meta.env.BASE_URL}dados.json`);
    if (!resposta.ok) throw new Error(`dados.json: HTTP ${resposta.status}`);
    const dados = await resposta.json();
    raiz.render(
      <StrictMode>
        <App dados={dados} />
      </StrictMode>,
    );
  } catch (erro) {
    raiz.render(
      <p className="m-8 font-mono text-sm text-quente">
        Não foi possível carregar dados.json — rode <code>python3 relatorio.py</code>. ({String(erro)})
      </p>,
    );
  }
}

iniciar();
