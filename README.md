# MotionForge

Briefing → roteiro → narração (Piper, local) → cenas animadas escritas por um LLM local (Ollama) → vídeo MP4.

Serve para qualquer assunto: anúncio, explicação técnica, tutorial de produto, lista de dicas, história.
O assunto entra pelo briefing. O jeito do vídeo entra por dois parâmetros: `--structure` (narrativa) e `--style` (visual).

## Instalação

```bash
pip install -r requirements.txt
playwright install chromium
ollama pull qwen2.5-coder:14b      # ou outro modelo bom em JavaScript
python -m piper.download_voices pt_BR-faber-medium --download-dir voices   # opcional: baixa sozinho no 1º uso
# ffmpeg e ffprobe precisam estar no PATH
```

## Uso

```bash
python main.py "Seu briefing aqui" --brand "Nome" --url site.com --style paper --structure aida
```

Opções principais:

| Opção | O que faz |
|---|---|
| `--style` | `paper`, `flat`, `kinetic`, `blueprint`, `ui`, `editorial` |
| `--structure` | `auto`, `aida`, `pas`, `explainer`, `story`, `list` |
| `--seconds` | duração alvo (define quantas palavras a narração tem) |
| `--format` | `9:16` (padrão) ou `16:9` |
| `--voice` | voz Piper: nome (ex. `pt_BR-faber-medium`) ou caminho `.onnx` |
| `--length-scale` | velocidade da fala Piper (`0.9` = 10% mais rápido) |
| `--music` | trilha de fundo; abaixa sozinha quando a voz fala |
| `--plan` | usa um roteiro JSON seu e pula o LLM do roteiro |
| `--stills` | salva uma prévia PNG de cada cena |
| `--regen` / `--replan` | reescreve as cenas / o roteiro |

Tudo fica em `work/`: `plan.json`, `voice/`, `scenes/*.js`, `film.html`.
Você pode editar o `plan.json` ou uma cena `.js` à mão e rodar de novo: o que já existe é reaproveitado.
Abra `work/film.html` no navegador e rode `renderAt(3.2)` no console para ver qualquer instante.

## Como funciona (a "skill")

O resultado não vem de um prompt mágico. Vem de três camadas que se reforçam:

1. **Roteiro estruturado** (`prompts.PLAN_SYSTEM`). O LLM devolve JSON com cenas, narração, título na tela
   e um storyboard que diz *qual palavra* da narração dispara a ação principal. Regras proíbem números,
   depoimentos e resultados inventados.
2. **A voz define o tempo** (`pipeline.build_timeline`). O TTS devolve o tempo de cada palavra.
   A duração de cada cena vem da fala, e o LLM recebe esses tempos para sincronizar a animação.
3. **Contrato de código + auditoria** (`prompts.SCENE_CORE`, `runtime/`).
   - Cada cena é `render(t)`: uma função pura do tempo. Por isso o vídeo é exato e pode ser exportado quadro a quadro.
   - O prompt traz a API do `kit`, regras de ofício com números concretos e o vocabulário do estilo.
   - O código roda num Chromium de verdade. Erros de sintaxe, erros em tempo de execução, tela vazia e
     texto fora da área segura voltam para o modelo corrigir (`--max-fix`).
   - Se ainda falhar, entra uma cena reserva simples, e o vídeo sempre sai.

## Criar um estilo novo

Em `forge/styles.py`, copie um bloco e mude:
- `look`: uma frase sobre o material, a luz e o movimento;
- `motion` e `drawing`: as regras de movimento e de desenho;
- `snippet`: o "movimento assinatura" em JS;
- `palette` e `fonts`: os padrões.

Nenhum prompt menciona assunto, então o estilo novo vale para qualquer briefing.

## Limites

- A qualidade depende do modelo. Modelos locais pequenos erram mais; a auditoria corrige parte disso.
  Modelos de código de 14B ou mais tendem a ir melhor, mas teste com os seus briefings.
- A voz roda local com Piper, sem internet depois de baixar o modelo.
- Tempo das palavras: se o modelo de voz tiver alinhamento de fonemas, o tempo é exato. Senão, é estimado
  frase a frase pelo número de fonemas de cada palavra (erro de décimos de segundo). Se quiser precisão total,
  troque `word_times` em `forge/tts.py` por um alinhamento com `faster-whisper`.
- Para trocar o TTS, mude só `forge/tts.py`: ele precisa devolver um áudio e a lista de palavras com tempo.
- Verifique a licença da voz e das fontes antes de uso comercial.
- Não há efeitos sonoros; dá para adicioná-los em `forge/audio.py` usando os tempos de `beat`.

## Interface gráfica — MotionForge Studio

```bash
python gui.py
```

Abra **http://127.0.0.1:7860** no navegador. A interface permite escrever o briefing,
selecionar os seis estilos, narrativa, duração, formato, cores, modelo, voz, FPS,
legendas e narração. Acompanhe os registros em tempo real, reproduza e baixe o MP4.
O painel visual é uma referência do estilo; o vídeo final aparece após a geração.

Os projetos ficam em `projects/<id>/` com arquivos intermediários, registro e vídeo.
O histórico é recuperado ao reiniciar. Uma geração roda por vez. Para mudar a porta
ou a pasta: `python gui.py --port 8080 --data-dir ./meus-projetos`.

A interface usa a biblioteca padrão do Python e preserva a CLI existente. O servidor
escuta apenas em `127.0.0.1`, para uso local. Ollama deve estar rodando na porta 11434
(`ollama serve`), com o modelo escolhido instalado. Piper, Chromium e FFmpeg seguem
os requisitos de instalação acima. A primeira narração pode baixar a voz.
Não feche o servidor enquanto o vídeo estiver sendo gerado.

### Testes

```bash
pip install pytest
python -m pytest -q
python -m playwright install chromium
python tests/browser_smoke.py
```

O teste de navegador usa um processo simulado para verificar envio, conclusão,
registro e download sem exigir um modelo Ollama. Ele não avalia a qualidade do LLM
nem a síntese de voz. A geração real requer os serviços locais descritos acima.
