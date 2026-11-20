// Sorteio de times: 2 goleiros e 10 jogadores de linha, 5 por time.
// Testa as 126 divisões possíveis dos jogadores de linha, fica com as mais
// equilibradas (soma de nível e posições) e sorteia uma delas.

const POSICOES = ["zaga", "meio", "ataque"];
const POSICAO_PADRAO = "meio";
const NIVEL_PADRAO = 2;
// Um ponto de nível de diferença pesa mais que um jogador fora de posição.
const PESO_NIVEL = 2;

function custo(timeA, timeB) {
    const soma = t => t.reduce((s, j) => s + j.nivel, 0);
    let c = PESO_NIVEL * Math.abs(soma(timeA) - soma(timeB));
    for (const pos of POSICOES) {
        const conta = t => t.filter(j => j.posicao === pos).length;
        c += Math.abs(conta(timeA) - conta(timeB));
    }
    return c;
}

function divisoes(n, k) {
    // Combinações de k índices em n que contêm o índice 0, para não
    // contar a mesma divisão duas vezes (A x B e B x A).
    const resultado = [];
    const atual = [0];
    (function rec(inicio) {
        if (atual.length === k) { resultado.push(atual.slice()); return; }
        for (let i = inicio; i < n; i++) {
            atual.push(i);
            rec(i + 1);
            atual.pop();
        }
    })(1);
    return resultado;
}

function sortearTimes(goleiros, linha, aleatorio = Math.random) {
    let melhores = [];
    let menorCusto = Infinity;
    for (const idx of divisoes(linha.length, linha.length / 2)) {
        const noA = new Set(idx);
        const timeA = linha.filter((_, i) => noA.has(i));
        const timeB = linha.filter((_, i) => !noA.has(i));
        const c = custo(timeA, timeB);
        if (c < menorCusto) { menorCusto = c; melhores = []; }
        if (c === menorCusto) melhores.push([timeA, timeB]);
    }
    let [timeA, timeB] = melhores[Math.floor(aleatorio() * melhores.length)];
    if (aleatorio() < 0.5) [timeA, timeB] = [timeB, timeA];
    const [gkAzul, gkVermelho] = aleatorio() < 0.5 ? goleiros : [goleiros[1], goleiros[0]];
    const ordenar = t => t.slice().sort((a, b) =>
        POSICOES.indexOf(a.posicao) - POSICOES.indexOf(b.posicao) || a.nome.localeCompare(b.nome));
    return {
        azul: { goleiro: gkAzul, linha: ordenar(timeA) },
        vermelho: { goleiro: gkVermelho, linha: ordenar(timeB) },
    };
}

if (typeof module !== "undefined") {
    module.exports = { sortearTimes, custo, divisoes };
}

if (typeof document !== "undefined") {
    const form = document.getElementById("sorteio-form");
    const erro = document.getElementById("sorteio-erro");
    const resultado = document.getElementById("sorteio-resultado");
    const NOME_POSICAO = { zaga: "Zaga", meio: "Meio", ataque: "Ataque" };

    function lerFormulario() {
        const goleiros = [...form.querySelectorAll(".gk-nome")].map(i => i.value.trim());
        const linha = [...form.querySelectorAll(".linha-row")].map(row => ({
            nome: row.querySelector(".linha-nome").value.trim(),
            posicao: row.querySelector(".linha-posicao").dataset.valor || POSICAO_PADRAO,
            nivel: Number(row.querySelector(".linha-nivel").dataset.valor) || NIVEL_PADRAO,
        }));
        return { goleiros, linha };
    }

    function validar({ goleiros, linha }) {
        const nomes = [...goleiros, ...linha.map(j => j.nome)];
        if (nomes.some(n => !n)) return "Preencha os 2 goleiros e os 10 jogadores de linha.";
        const vistos = new Set();
        for (const n of nomes) {
            const chave = n.toLocaleLowerCase("pt-BR");
            if (vistos.has(chave)) return `O nome "${n}" aparece mais de uma vez.`;
            vistos.add(chave);
        }
        return null;
    }

    function el(tag, attrs = {}, ...filhos) {
        const e = document.createElement(tag);
        Object.assign(e, attrs);
        e.append(...filhos);
        return e;
    }

    function renderTime(time, cor, titulo) {
        const lista = el("ul", {},
            el("li", {}, time.goleiro + " ", el("span", { className: "gk-badge", textContent: "GOL" })),
            ...time.linha.map(j => el("li", {}, j.nome + " ",
                el("span", { className: "pos-badge pos-" + j.posicao, textContent: NOME_POSICAO[j.posicao] }))));
        return el("div", { className: `team ${cor}-team` }, el("h4", { textContent: titulo }), lista);
    }

    function textoWhatsApp(times) {
        const bloco = (titulo, t) => [titulo, `${t.goleiro} (goleiro)`, ...t.linha.map(j => j.nome)].join("\n");
        return bloco("*Time azul*", times.azul) + "\n\n" + bloco("*Time vermelho*", times.vermelho);
    }

    function mostrar(times) {
        const copiar = el("button", { type: "button", className: "filter-btn", textContent: "Copiar times" });
        copiar.addEventListener("click", async () => {
            try {
                await navigator.clipboard.writeText(textoWhatsApp(times));
                copiar.textContent = "Copiado!";
            } catch {
                copiar.textContent = "Não deu para copiar";
            }
        });
        const denovo = el("button", { type: "button", className: "filter-btn", textContent: "Sortear de novo" });
        denovo.addEventListener("click", () => form.requestSubmit());
        resultado.replaceChildren(
            el("div", { className: "game-card" },
                el("div", { className: "game-teams" },
                    renderTime(times.azul, "blue", "Time azul"),
                    renderTime(times.vermelho, "red", "Time vermelho"))),
            el("div", { className: "sorteio-acoes" }, denovo, copiar));
        resultado.hidden = false;
        resultado.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    // Posição e nível: um toque escolhe, outro toque no mesmo botão desmarca.
    function definir(grupo, valor) {
        grupo.dataset.valor = valor;
        grupo.querySelectorAll("button").forEach(b => {
            const ativo = b.dataset.valor === valor;
            b.classList.toggle("ativo", ativo);
            b.setAttribute("aria-pressed", ativo);
        });
    }

    form.querySelectorAll(".seg").forEach(grupo => {
        definir(grupo, "");
        grupo.addEventListener("click", ev => {
            const botao = ev.target.closest("button");
            if (!botao) return;
            definir(grupo, grupo.dataset.valor === botao.dataset.valor ? "" : botao.dataset.valor);
        });
    });

    // Chips: um toque coloca o nome no primeiro campo vazio; outro toque tira.
    const mesmoNome = (a, b) => a.trim().toLocaleLowerCase("pt-BR") === b.trim().toLocaleLowerCase("pt-BR");
    const campos = () => [...form.querySelectorAll(".gk-nome, .linha-nome")];

    // Cada grupo de chips olha só os próprios campos: o Wesley, por exemplo,
    // aparece nos goleiros frequentes e nos mensalistas.
    const camposDo = chip => [...form.querySelectorAll("." + chip.dataset.alvo)];

    function atualizarChips() {
        form.querySelectorAll(".chip").forEach(chip => {
            chip.classList.toggle("selecionado", camposDo(chip).some(i => mesmoNome(i.value, chip.textContent)));
        });
    }

    function limparCampo(input) {
        input.value = "";
        const row = input.closest(".linha-row");
        if (row) row.querySelectorAll(".seg").forEach(g => definir(g, ""));
    }

    form.querySelectorAll(".chip").forEach(chip => {
        chip.addEventListener("click", () => {
            const nome = chip.textContent;
            const proprio = camposDo(chip).find(i => mesmoNome(i.value, nome));
            if (proprio) {
                limparCampo(proprio);
            } else {
                const vazio = camposDo(chip).find(i => !i.value.trim());
                if (!vazio) {
                    erro.textContent = chip.dataset.alvo === "gk-nome"
                        ? "Os 2 goleiros já estão preenchidos."
                        : "Os 10 jogadores de linha já estão preenchidos.";
                    erro.hidden = false;
                    return;
                }
                // Se o nome estava no outro grupo, ele muda de lugar.
                const outro = campos().find(i => mesmoNome(i.value, nome));
                if (outro) limparCampo(outro);
                vazio.value = nome;
                preencherPosicao(vazio);
            }
            erro.hidden = true;
            atualizarChips();
        });
    });

    // Mensalista com posição de costume já entra com ela, pelo chip ou digitado.
    const posicaoDe = {};
    form.querySelectorAll('.chip[data-alvo="linha-nome"]').forEach(c => {
        if (c.dataset.posicao) posicaoDe[c.textContent.toLocaleLowerCase("pt-BR")] = c.dataset.posicao;
    });

    function preencherPosicao(input) {
        const row = input.closest(".linha-row");
        if (!row) return;  // campo de goleiro não tem posição
        const grupo = row.querySelector(".linha-posicao");
        const posicao = posicaoDe[input.value.trim().toLocaleLowerCase("pt-BR")];
        if (posicao && !grupo.dataset.valor) definir(grupo, posicao);
    }

    form.querySelectorAll(".linha-nome").forEach(i => i.addEventListener("change", () => preencherPosicao(i)));

    form.addEventListener("input", atualizarChips);

    form.addEventListener("submit", ev => {
        ev.preventDefault();
        const dados = lerFormulario();
        const msg = validar(dados);
        erro.textContent = msg || "";
        erro.hidden = !msg;
        if (msg) { resultado.hidden = true; return; }
        mostrar(sortearTimes(dados.goleiros, dados.linha));
    });
}
