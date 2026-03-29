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
- Não há campo `entering_team` — é derivado do resultado do jogo anterior

## Regras da pelada

### Dinâmica dos jogos
- Dois times jogam, os demais jogadores ficam de fora (suplentes)
- O time que perde sai, e entra o próximo time (suplentes)
- O time que vence permanece em campo para o jogo seguinte
- Em caso de empate, fica o time que acabou de entrar (o time que já estava sai)

### "Ficou na mesa"
- A partir do jogo 2, o time que permanece em campo ganha "ficou na mesa"
- Vitória do time que já estava em campo = contabiliza como "vitória"
- Empate quando o time acabou de entrar = contabiliza como "empate ao entrar"
- Baseado no resultado do jogo, não no tracking individual de jogadores
- Um jogador pode permanecer em campo mesmo estando no time perdedor (para completar o time seguinte por falta de suplentes). Nesse caso, ele entra no time novo e NÃO conta como "ficou na mesa"
- Para derivar qual time entrou: verificar o resultado do jogo anterior. O time vencedor permaneceu; o outro time é o que entrou. No jogo 1, nenhum time "ficou na mesa"

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
