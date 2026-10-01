# PRD: bot de Telegram para cadastro de peladas

Status: aprovado para implementação, em 2026-10-01.
Responsável: Eduardo (admin do site e do bot).

## Problema

Hoje só o Eduardo cadastra peladas. Depois de cada domingo, alguém manda as anotações, ele cola o texto numa sessão do Claude Code, responde as dúvidas, revisa o JSON e publica. Os outros organizadores não têm GitHub nem acesso a uma IA, então o site depende de uma pessoa só para ficar atualizado.

## Objetivo

Um organizador autorizado cadastra a pelada sozinho, numa conversa privada com um bot de Telegram, colando as mesmas anotações que já escreve hoje. O site atualiza sem intervenção do admin.

## Fora do escopo

- Foto da súmula. A entrada é só texto.
- Conversa em grupo. O bot só atende em conversa privada.
- Renomear o nome principal de um jogador. Continua sendo tarefa manual do admin.
- Avisar o admin sobre cada cadastro ou jogador novo.
- Editar estatísticas, templates ou qualquer coisa fora dos dados.

## Usuários

O admin é o Eduardo, identificado por um ID fixo do Telegram. Ele aprova organizadores e pode desfazer qualquer publicação.

Organizadores são jogadores que anotam os jogos. Precisam de aprovação do admin para usar o bot. Cadastram peladas novas, corrigem peladas antigas, criam jogadores, adicionam apelidos e desfazem as próprias publicações.

## Como o texto chega hoje

As quatro anotações de setembro (06/09, 13/09, 20/09 e 27/09) mostram um formato estável, mas com falhas frequentes.

O padrão é este:

```
Jogo 1
Azul 2 X 1 Vermelho

Azul
Wesley
Mateus
Erick 1
Giga 1

Vermelho
João
Salvador 1
Júnior
```

Os gols vêm depois do nome, como "Erick 1" ou "Denis - 1". O gol contra vem solto, como "Hulk contra".

As falhas que o bot precisa tratar:

- Numeração repetida ("Jogo 4" duas vezes) e jogo sem número escrito em outro formato ("Time azul: Confiança, Lima, Marcelo...").
- Goleiro às vezes é o primeiro nome da lista e às vezes não aparece.
- Times com 4 ou 5 jogadores, que podem estar certos.
- Erros de digitação ("Fabjnho", "Azu 3l") e confusão entre nomes parecidos ("Guga" e "Giga").
- Jogador novo em três das quatro peladas.
- Data, juiz e quem saiu em cada jogo quase nunca aparecem.
- O texto chega em várias mensagens, normalmente uma por jogo.

## Experiência do organizador

### Primeiro acesso

1. O organizador abre o bot e manda `/start`.
2. O bot não o reconhece e oferece um botão "Pedir acesso".
3. O admin recebe uma mensagem com o nome e o @ do organizador e os botões "Aprovar" e "Recusar".
4. O organizador recebe a resposta. Se aprovado, o bot explica como mandar as anotações.

### Cadastro de pelada

1. O organizador cola as anotações, em uma ou várias mensagens. O bot confirma o recebimento sem interpretar ainda e mostra o botão "Terminei".
2. Ao tocar em "Terminei", o agente lê tudo e monta o rascunho. Assim que a data estiver definida, pelo texto ou pela resposta do organizador, o agente confere se a pelada já existe ou está sendo cadastrada por outra pessoa (ver "Pelada já cadastrada ou em cadastro").
3. O agente manda uma mensagem só com tudo o que falta ou está ambíguo: data, juiz, goleiros, nomes que não estão no cadastro, nomes que batem com mais de um jogador, times com menos de 6, quem saiu num empate e numeração inconsistente. Ele sugere a resposta provável sempre que o histórico permitir, por exemplo "a data é 2026-10-04, domingo seguinte à última pelada?".
4. O organizador responde em texto livre. O agente pode fazer novas rodadas de perguntas se ainda faltar algo.
5. Quando a verificação passa, o bot mostra o resumo, gerado pelo código a partir do JSON e não escrito pelo modelo. O resumo tem a data, o juiz, cada jogo com placar, escalações e gols, os jogadores novos e os apelidos adicionados.
6. O organizador toca em "Publicar" ou responde com correções.
7. O bot publica e, quando o GitHub Pages termina o deploy, responde com o link `https://eduardott.github.io/scouts-da-pelada/?v=<data>`, pronto para o WhatsApp.

### Pelada já cadastrada ou em cadastro

Dois organizadores podem mandar as anotações da mesma pelada. O bot descobre isso assim que a data é definida, antes de o segundo organizador responder perguntas ou revisar o resumo.

Se a pelada já foi publicada, o bot avisa: "A pelada de 04/10 já foi cadastrada pelo Fulano em 04/10 às 21h. Quer corrigir alguma coisa nela?". Se o organizador quiser corrigir, o fluxo vira o de correção, partindo do arquivo publicado. Se não, o rascunho é descartado.

Se outro organizador está com essa pelada em rascunho naquele momento, o bot avisa: "O Fulano está cadastrando a pelada de 04/10 agora". O segundo organizador pode esperar e corrigir depois que o Fulano publicar, ou descartar o rascunho. O bot não bloqueia o segundo, porque o primeiro pode ter abandonado a conversa. Se os dois chegarem a publicar, a verificação de data repetida barra o segundo na publicação, e ele recebe a opção de transformar o rascunho em correção.

Quando o primeiro organizador publica, o bot avisa o segundo, se a sessão dele ainda estiver aberta.

### Correção de pelada antiga

O organizador escreve algo como "na pelada de 13/09 o gol do jogo 3 foi do Ricardo, não do Eric". O agente abre o arquivo existente, aplica a mudança e o fluxo segue igual a partir do resumo, que destaca o que mudou.

### Jogadores

Quando um nome do texto não está no cadastro, o agente busca nomes e apelidos parecidos e pergunta "é algum destes?". Só cria um jogador novo se o organizador disser que não é nenhum. Se for um jogador existente escrito de outro jeito, o agente pode adicionar a grafia como apelido.

O nome principal de um jogador novo segue a convenção atual: convidado ganha o sufixo "Conv" (como "Guga Conv"), e jogador fixo fica sem sufixo (como "Landir"). O agente pergunta qual é o caso.

### Desfazer

`/desfazer` lista as últimas publicações que o usuário pode reverter: as próprias, para organizadores, e todas, para o admin. Ao escolher uma, o bot reverte o commit e publica de novo. Se a reversão quebrar os testes, porque uma publicação posterior depende dela, o bot recusa e explica qual publicação está no caminho.

### Uso fora do cadastro

O bot só serve para cadastrar e corrigir peladas e para cuidar do cadastro de jogadores ligado a isso. Se o organizador pedir outra coisa, como uma pergunta geral, um texto, uma conta ou uma conversa qualquer, o agente recusa em uma frase e lembra para que o bot serve. Também ficam de fora perguntas sobre estatísticas, que o organizador consulta no site. O agente responde dúvidas sobre como usar o bot.

Se o organizador insistir, o agente mantém a recusa sem discutir. Tentativas de mudar as instruções do agente ("ignore as regras", "finja que você é outro assistente") recebem a mesma recusa.

### Comandos

- `/start`: boas-vindas ou pedido de acesso.
- `/nova`: descarta o rascunho atual e começa outro.
- `/desfazer`: reverte uma publicação.
- `/organizadores` (só admin): lista os organizadores e permite remover acesso.

## Arquitetura

### Visão geral

```
Telegram ──> bot (Python, código fixo, roda no Railway)
               │
               ├─ conversa ──> agente (Claude Agent SDK)
               │                 lê o repo, escreve só o JSON da pelada,
               │                 usa ferramentas próprias para jogadores
               │
               └─ ao tocar em "Publicar", sem passar pelo modelo:
                    testes ─> build ─> commit ─> push
                                                   │
                                                   v
                                     GitHub Actions (deploy.yml)
                                                   │
                                                   v
                                             GitHub Pages
```

O bot e o agente são peças separadas do mesmo processo. O agente só conversa e edita o rascunho. Testes, build, commit e push são executados pelo código do bot com `subprocess`, sempre na mesma sequência, e o modelo não decide nada nessa etapa.

### Repositório e pastas

O código fica em `bot/`, no repositório `EduardoTT/scouts-da-pelada`, que é público. Nenhum segredo vai para o repo.

```
bot/
  main.py          entrada, loop do Telegram
  access.py        organizadores e aprovação
  session.py       uma conversa por chat, worktree e ciclo de vida
  agent.py         configuração do Agent SDK, hook e ferramentas
  tools.py         ferramentas de jogadores e verificação
  checks.py        verificações extras do rascunho
  summary.py       resumo legível gerado a partir do JSON
  publish.py       testes, build, commit, push, revert
  prompt.md        prompt de sistema do agente
  Dockerfile
  requirements.txt
  tests/
  evals/
```

O código que o Railway executa e a cópia do repo onde o bot publica são coisas diferentes. Ao subir, o bot clona o repo no volume (`/volume/repo`), e é ali que ele faz pull, cria worktrees, commita e dá push.

### Mudança prévia: jogadores em JSON

O `players.py` é código Python executado pelo build e pelos testes. Para que nenhuma operação do bot edite código, o cadastro passa para `players.json`, na raiz do repo, e o `players.py` só carrega esse arquivo, mantendo a mesma variável `players` para não mexer em quem importa.

O arquivo não pode ficar em `data/`, porque `models.py` e `tests/test_data.py` tratam todo `data/*.json` como uma pelada.

O agente não edita o `players.json` diretamente. Criar jogador e adicionar apelido passam pelas ferramentas `adicionar_jogador` e `adicionar_apelido`, que validam a entrada e gravam o arquivo de forma determinística.

O CLAUDE.md passa a citar o `players.json` no lugar do `players.py`.

### Sessões e worktrees

Cada conversa ativa tem um `ClaudeSDKClient` e um git worktree próprio em `/volume/worktrees/<chat_id>`, criado a partir do `origin/main` atualizado. O agente roda com `cwd` nesse worktree. Assim, dois organizadores podem cadastrar ao mesmo tempo sem um ver o rascunho do outro.

A sessão termina quando a pelada é publicada, quando o organizador manda `/nova` ou depois de 6 horas sem mensagens. Ao terminar, o worktree é removido.

O estado da conversa fica em memória. Se o Railway reiniciar no meio de um cadastro, a conversa se perde e o organizador recomeça. A decisão foi aceitar essa perda, porque os cadastros são curtos e o organizador ainda tem o texto original. Ao subir de novo, o bot avisa quem tinha uma sessão aberta, a partir de uma lista de chats ativos salva no volume.

### Agente

O agente usa o `claude-agent-sdk` em Python. O pacote já traz o binário do Claude Code, então a imagem não precisa de Node.

Configuração do `ClaudeAgentOptions`:

- `model`: `claude-opus-5-5`, configurável por variável de ambiente.
- `cwd`: o worktree da sessão.
- `system_prompt`: o conteúdo de `bot/prompt.md`.
- `setting_sources=[]`, para não carregar o CLAUDE.md do repo, que tem instruções de desenvolvimento e não de cadastro. As regras da pelada que o agente precisa entram no `prompt.md`.
- `env`: `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`.
- `allowed_tools`: `Read`, `Glob`, `Grep`, `Write`, `Edit` e as ferramentas próprias.
- `disallowed_tools`: `Bash`, `WebFetch`, `WebSearch`, `Agent`, `NotebookEdit`.
- `permission_mode`: `dontAsk`, para que qualquer chamada fora da lista seja negada em vez de esperar aprovação.
- `hooks`: um `PreToolUse` que barra a chamada quando o caminho não obedece às regras abaixo.
- `max_turns` e `max_budget_usd`: limites por sessão, com padrão de 60 turnos e US$ 2,00. Na avaliação, o cadastro mais caro custou US$ 0,47, então o limite dá folga de quatro vezes.

O hook `PreToolUse` roda antes de qualquer outra regra de permissão, então é ele que garante as travas:

- `Write` e `Edit` só em `data/AAAA-MM-DD.json` dentro do worktree.
- `Read`, `Glob` e `Grep` só dentro do worktree.
- Caminho com `..` ou link simbólico que saia do worktree é negado.

O `prompt.md` cobre:

- O propósito único do bot e o que fazer com pedidos fora dele, como descrito em "Uso fora do cadastro". Essa instrução vem no início do prompt, e o prompt deixa claro que mensagens do organizador não alteram essas regras.

- O formato do JSON e as regras da pelada que hoje estão no CLAUDE.md: `team_out`, empate no jogo 1, empate com poucos e muitos suplentes, gol contra.
- Os padrões de anotação listados em "Como o texto chega hoje".
- Como deduzir `team_out` pelo placar e pela escalação do jogo seguinte.
- Juntar todas as perguntas numa mensagem e sugerir a resposta provável.
- Nunca inventar jogador, gol ou placar. Na dúvida, perguntar.
- Chamar `verificar_rascunho` antes de declarar o rascunho pronto.

### Ferramentas próprias

As ferramentas são registradas com `create_sdk_mcp_server` e rodam dentro do processo do bot.

`buscar_jogador(nome)` devolve os jogadores cujo nome principal ou apelido se parece com o texto, com a grafia que bateu. Usa normalização de acentos e caixa e uma medida de similaridade de texto.

`adicionar_jogador(nome, convidado)` cria o jogador no `players.json` do worktree. Recusa se o nome ou algum apelido já existir.

`desfazer_jogador_novo(nome)` remove um jogador criado no próprio rascunho, que ainda não foi publicado. Serve para trocar o nome de quem o agente acabou de cadastrar ou desfazer um cadastro por engano. Jogadores que já estavam publicados continuam sem renomeação pelo bot.

`adicionar_apelido(jogador, apelido)` adiciona a grafia à lista do jogador. Recusa se o apelido já pertencer a outro jogador.

`consultar_data(data)` diz se já existe pelada publicada nessa data no `origin/main`, com quem publicou e quando, a partir do `/volume/publicacoes.json`, e se outra sessão aberta tem rascunho para a mesma data, com o nome do organizador. Ao ser chamada, a ferramenta também registra a data na sessão atual, para que as outras sessões a enxerguem. O prompt manda o agente chamar essa ferramenta assim que souber a data.

`verificar_rascunho(data)` roda os testes de `tests/test_data.py` e as verificações de `bot/checks.py` sobre o worktree e devolve a lista de erros e avisos.

### Verificações do rascunho

Erros bloqueiam a publicação. Avisos viram perguntas ao organizador, que pode confirmar que está certo.

Erros, já cobertos por `tests/test_data.py`:

- Nome fora do cadastro ou escrito como apelido em vez do nome principal.
- Artilheiro que não está escalado no time que marcou, considerando o gol contra.
- Placar diferente da soma dos gols.
- Time sem exatamente um goleiro.

Erros novos, em `bot/checks.py`:

- Jogos fora de sequência a partir de 1, ou número repetido.
- `team_out` ausente ou com valor fora de `blue`, `red` e `both`.
- `team_out` apontando para o vencedor num jogo com vencedor.
- `team_out` igual a `both` no jogo 1.
- Data inválida ou já usada por outra pelada, quando o cadastro é novo.

Avisos:

- Time com tamanho diferente de 6. Já houve times com 5 e com 7 nas peladas publicadas, então isso nunca é erro.
- Jogador escalado nos dois times do mesmo jogo.
- `team_out` que não bate com a escalação do jogo seguinte, quando o time que deveria ter saído reaparece inteiro.

### Publicação

Ao tocar em "Publicar", o bot executa em sequência, sob um lock global para que só uma publicação aconteça por vez:

1. `git fetch` e rebase do worktree sobre `origin/main`.
2. `python -m pytest tests/`.
3. `python build.py`, que valida que o site gera sem erro. A saída não é commitada.
4. `git commit` com a mensagem no padrão do histórico: "Cadastra a pelada de AAAA-MM-DD" ou "Corrige a pelada de AAAA-MM-DD". Quando houver jogador novo, ele vai num commit anterior, "Cadastra o <Nome> no players.json". O corpo do commit registra o nome de exibição do organizador no Telegram.
5. `git push origin HEAD:main`. Se o push for recusado porque o `main` andou, o bot volta ao passo 1, no máximo três vezes.
6. Registro da publicação em `/volume/publicacoes.json`: commits, data da pelada, ID do Telegram do organizador e horário.
7. Espera o deploy do GitHub Pages e responde com o link. Se o deploy demorar mais que 10 minutos, o bot manda o link mesmo assim e avisa que pode levar mais um pouco.

Se os testes ou o build falharem no passo 2 ou 3, nada é publicado. O bot devolve o erro ao agente, que corrige o rascunho ou pergunta ao organizador.

O push usa uma deploy key com permissão de escrita, que vale só para esse repo. A chave fica em variável de ambiente do Railway e é escrita num arquivo com permissão 600 fora do repo ao subir. O hook impede o agente de ler qualquer coisa fora do worktree.

O `/desfazer` usa o `/volume/publicacoes.json` para listar e autorizar, roda `git revert` dos commits daquela publicação e segue os passos 2 a 7.

### Acesso

A lista de organizadores fica em `/volume/organizadores.json`, com ID, nome, @ e data de aprovação. O admin é definido por `ADMIN_TELEGRAM_ID` e não depende do arquivo. Mensagens de quem não está na lista só recebem a opção de pedir acesso. O bot ignora mensagens de grupos.

### Telegram

O bot usa `python-telegram-bot` em modo long polling, que não exige URL pública nem configuração de webhook no Railway. Mensagens do bot com mais de 4096 caracteres, como o resumo de uma pelada com 10 jogos, são divididas em partes.

### Infraestrutura

O Railway roda a imagem de `bot/Dockerfile`, baseada em `python:3.13-slim`, a mesma versão do Python que o `deploy.yml` usa. Alpine não serve, porque o SDK só tem builds para Linux com glibc. A imagem instala `git`, `tzdata` e `fonts-dejavu-core`, que o `build.py` usa para gerar as imagens de preview, como no `deploy.yml`.

O container roda com `TZ=America/Sao_Paulo`. Sem isso, o relógio fica em UTC, e uma pelada cadastrada num domingo depois das 21h de Brasília já cairia na segunda-feira, o que erra a data sugerida ao organizador e o horário registrado nas publicações. O código também usa esse fuso explicitamente ao calcular datas, em vez de depender só da variável. A cada sessão, o bot informa ao agente a data e o dia da semana de hoje no horário de Brasília, para ele sugerir a data da pelada.

O serviço tem um volume montado em `/volume`, com o clone do repo, os worktrees, a deploy key, os organizadores, as publicações e os chats ativos.

O watch path do Railway é `bot/**`, para que só mudanças no código do bot gerem novo deploy. O `deploy.yml` ganha `paths-ignore: ['bot/**']`, para que mudanças só no bot não reconstruam o site.

Variáveis de ambiente:

- `TELEGRAM_BOT_TOKEN`
- `ANTHROPIC_API_KEY`
- `ADMIN_TELEGRAM_ID`
- `GITHUB_DEPLOY_KEY`
- `REPO_SSH_URL`
- `CLAUDE_MODEL` (opcional, padrão `claude-opus-5-5`)
- `MAX_BUDGET_USD` e `MAX_TURNS` (opcionais)
- `TZ=America/Sao_Paulo`

## Segurança

O risco principal é um texto mandado no Telegram induzir o modelo a fazer algo fora do cadastro. As defesas, em camadas:

- O prompt restringe o agente ao cadastro de peladas e manda recusar qualquer outro uso. Essa é a única camada que depende do modelo obedecer. As demais funcionam mesmo que ele não obedeça.
- O agente não tem Bash nem acesso à web. Ele não consegue executar comandos.
- O hook limita escrita aos JSONs de pelada e leitura ao worktree.
- O cadastro de jogadores só muda pelas ferramentas próprias, que validam a entrada.
- Nada é publicado sem o organizador ver o resumo gerado pelo código e tocar em "Publicar".
- Os testes e o build rodam antes de cada push.
- Só organizadores aprovados pelo admin falam com o agente.
- Toda publicação pode ser desfeita, e o histórico do git guarda tudo.
- `max_turns` e `max_budget_usd` limitam o custo de uma conversa que saia do controle.

## Avaliação do agente

As quatro anotações de setembro viram casos de teste em `bot/evals/`. Cada caso tem o texto original, dividido em mensagens como chegou; as respostas que o Eduardo deu às perguntas, nas sessões do Claude Code de cada data; e o JSON esperado, que é o arquivo já publicado em `data/`.

O script de avaliação roda o agente com cada texto, responde as perguntas dele com as respostas registradas e compara o JSON final com o esperado, jogo a jogo. Também registra o custo (`total_cost_usd`) e o número de turnos de cada caso. Esses números definem os valores iniciais de `max_turns` e `max_budget_usd`.

Além dos quatro casos de cadastro, a avaliação tem casos de uso fora do propósito: pergunta geral, pedido de texto, pergunta sobre estatísticas, tentativa de mudar as instruções e um pedido fora do escopo no meio de um cadastro. O resultado esperado é a recusa curta, sem nenhuma ferramenta chamada e, no último caso, com o rascunho intacto.

A avaliação chama a API e custa dinheiro, então roda manualmente, antes de mudar o prompt ou o modelo, e não no CI. O comando é `uv run python evals/run.py`, dentro de `bot/`.

Na primeira rodada, em 2026-10-01, com `claude-opus-5-5`, os quatro casos reais geraram o JSON idêntico ao publicado. O custo por cadastro ficou entre US$ 0,25 e US$ 0,47. Os cinco pedidos fora do propósito receberam recusa curta, sem mudança no repositório, a cerca de US$ 0,01 cada. O caso de 20/09 só passou depois da criação de `desfazer_jogador_novo`: as anotações pediam "Gustavo Conv", a resposta seguinte pedia "Guga Conv", e o agente não tinha como trocar o nome do jogador que ele mesmo tinha acabado de criar.

## Testes automatizados

Em `bot/tests/`, sem chamar a API:

- O hook nega escrita fora de `data/AAAA-MM-DD.json`, leitura fora do worktree e caminhos com `..`.
- As ferramentas de jogadores recusam nomes e apelidos duplicados.
- As verificações de `checks.py` pegam cada erro e aviso listado.
- A publicação funciona contra um repositório git local, incluindo o retry quando o push é recusado.
- O `/desfazer` respeita quem pode reverter o quê e recusa quando os testes quebram.
- O resumo gerado bate com o JSON.
- `consultar_data` encontra a pelada publicada e o rascunho de outra sessão na mesma data, e não acusa a própria sessão.
- A data de hoje e o horário das publicações saem no fuso de Brasília quando o relógio do sistema está em UTC, inclusive num domingo depois das 21h.
- O controle de acesso ignora desconhecidos e grupos.

## Plano de implementação

1. Migrar os jogadores para `players.json`, com `players.py` como carregador, e atualizar o CLAUDE.md. Os testes atuais precisam passar sem mudança.
2. Publicação e acesso: `publish.py`, `access.py` e seus testes, rodando contra um repositório local.
3. Agente local: `agent.py`, `tools.py`, `checks.py`, `summary.py` e `prompt.md`, acionados por um script de linha de comando, e a avaliação com os quatro casos.
4. Telegram: `main.py` e `session.py`, testados com um bot de desenvolvimento.
5. Deploy no Railway: Dockerfile, volume, variáveis, deploy key e `paths-ignore` no `deploy.yml`.
6. Seção no CLAUDE.md sobre o bot: como funciona, onde ficam os dados no volume e como rodar a avaliação.

## Critérios de sucesso

- Os quatro casos de avaliação geram o JSON esperado.
- Um organizador que não é o admin cadastra uma pelada real do início ao fim sem ajuda.
- Nenhuma publicação do bot quebra o deploy do site.

## Riscos e pontos em aberto

- O custo por pelada ainda não foi medido. A avaliação vai dar a primeira estimativa.
- O nome de exibição do organizador fica nos commits de um repo público. Se algum organizador não quiser, o bot pode registrar só o @ ou nada, mantendo a autoria apenas no volume.
- O formato das anotações pode mudar com organizadores novos. Casos novos entram em `bot/evals/` conforme aparecerem.
- O volume do Railway é o único lugar com a lista de organizadores e o registro de publicações. Perder o volume obriga a reaprovar os organizadores, e o `/desfazer` passa a funcionar só para o admin, que pode reverter pelo histórico do git.
