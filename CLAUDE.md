# Pelada de domingo

## Descrição
Este é um gerador de site estático. O objetivo é prover um site com estatísticas dos jogos de futebol do meu condomínio.

Durante os jogos nós vamos anotar os times, placar e quem fez os gols.
Depois da pelada vamos cadastrar os novos dados para poder atualizar o site.

## Stack
- Python + Jinja2 para gerar HTML estático
- Hospedagem: GitHub Pages
- Dados: JSON (um arquivo por pelada)
- Idioma do site: português

## Formato JSON de cada pelada

```json
{
  "date": "2026-03-29",
  "referee": "Nome do Juíz",
  "games": [
    {
      "game_number": 1,
      "score": { "blue": 2, "red": 1 },
      "team_out": "red",
      "blue_team": [
        { "name": "João", "role": "goalkeeper" },
        { "name": "Pedro", "role": "player" },
        { "name": "Lucas", "role": "player" },
        { "name": "Bruno", "role": "player" },
        { "name": "Thiago", "role": "player" },
        { "name": "Rafael", "role": "player" }
      ],
      "red_team": [
        { "name": "Carlos", "role": "goalkeeper" },
        { "name": "André", "role": "player" },
        { "name": "Felipe", "role": "player" },
        { "name": "Marcos", "role": "player" },
        { "name": "Daniel", "role": "player" },
        { "name": "Gustavo", "role": "player" }
      ],
      "goals": [
        { "player": "Pedro", "team": "blue", "count": 2 },
        { "player": "André", "team": "red", "count": 1 }
      ]
    }
  ]
}
```

### Regras do formato
- 6 jogadores por time: 1 goleiro (`role: "goalkeeper"`) e 5 de linha (`role: "player"`)
- Em média 8 jogos por pelada
- Gols agrupados por jogador com campo `count`
- Gol contra: adicionar `"own_goal": true` — aparece no detalhamento mas não conta na artilharia
- Campo `team_out` em cada jogo: `"blue"`, `"red"` ou `"both"` (indica qual time saiu após o jogo)

## Regras da pelada

### Dinâmica dos jogos
- Dois times jogam, os demais jogadores ficam de fora (suplentes)
- O time que perde sai, e entra o próximo time (suplentes)
- O time que vence permanece em campo para o jogo seguinte
- Em caso de empate com poucos suplentes: fica o time que acabou de entrar (o time que já estava sai)
- Em caso de empate com muitos suplentes (>10): ambos os times saem
- Em caso de empate no jogo 1: vai para pênaltis (o perdedor dos pênaltis sai)
- O campo `team_out` registra explicitamente qual time saiu: `"blue"`, `"red"` ou `"both"`

### "Ficou na mesa"
- Vencer o jogo 1 conta como "ficou na mesa" (vitória) — o time ficou para o jogo 2
- Empate no jogo 1 não conta (nenhum time ficou por mérito, vai para pênaltis)
- A partir do jogo 2, o time que permanece em campo ganha "ficou na mesa"
- A lógica usa `team_out` do jogo anterior para determinar qual time ficou e qual entrou
  - Se `team_out` do jogo anterior = `"red"` → azul ficou (incumbent), vermelho é novo (entering) no jogo atual... depende das composições do próximo jogo
  - Se `team_out` do jogo anterior = `"both"` → ambos são novos no próximo jogo, ninguém é incumbent
- Vitória do time que já estava em campo (incumbent) = contabiliza como "vitória"
- Empate quando o time acabou de entrar = contabiliza como "empate ao entrar"
- Se `team_out` anterior foi `"both"`: ninguém ganha crédito de "ficou na mesa" no jogo seguinte (ambos são novos)
- Um jogador pode permanecer em campo mesmo estando no time perdedor (para completar o time seguinte por falta de suplentes). Nesse caso, ele entra no time novo e NÃO conta como "ficou na mesa"
- No jogo 1, nenhum time "ficou na mesa" (ambos são novos)

### Gol contra
- Conta no placar do time adversário
- Aparece no detalhamento dos jogos
- Não entra no ranking da artilharia

## Para cada pelada, será possível consultar:
- Data
- Juíz
- Ranking de vitórias
    - Nome do jogador
    - Quantidade de vitórias
- Ranking "ficou na mesa"
    - Nome do jogador
    - Quantidade de vitórias
    - Quantidade de empates logo ao entrar
- Artilharia
    - Nome do jogador
    - Número de gols (excluindo gols contra)
- Goleiro menos vazado
    - Nome do jogador
    - Número de gols tomados
- Detalhamento dos jogos
    - Jogo N (onde N é o número do jogo)
    - Placar (azul x vermelho)
    - Nome dos jogadores que estavam no time azul
    - Nome dos jogadores que estavam no time vermelho
    - Gols do jogo (quantidade de gols que cada jogador fez, incluindo gols contra)

Haverá uma lista com todas as peladas, para poder acessar os detalhes.

## Estatísticas agregadas (total, mensal, anual)
- Ranking de vitórias (Maior vencedor)
- Ranking "ficou na mesa" (Rei da mesa)
- Ranking da Artilharia (Goleador)
- Ranking de goleiro menos vazado (Pega tudo)
- Ranking de participação em jogos (Fominha)
- Ranking de juíz com mais peladas apitadas (Apitador)

O default é mensal, e pode filtrar também por anual e total.

## Página
- O destaque da página são os números da pelada mais recente.
- Logo em seguida vem a lista de todas as peladas.
- Em outra aba há as estatísticas agregadas, com opções de filtros.

## Design
- Cores inspiradas nas camisas: vermelho/branco quadriculado e azul/branco quadriculado
- Cada jogador é identificado pelo nome (que na prática pode ser um apelido)
