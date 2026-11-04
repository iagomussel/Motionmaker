import argparse
from pathlib import Path

from forge.llm import Ollama
from forge.pipeline import run
from forge.prompts import STRUCTURES
from forge.styles import STYLES


def main():
    p = argparse.ArgumentParser(description="MotionForge: vídeo animado com narração a partir de um briefing.")
    p.add_argument("brief", nargs="?", default="", help="briefing do vídeo (ou use --brief-file / --plan)")
    p.add_argument("--brief-file", help="arquivo .txt com o briefing")
    p.add_argument("--plan", help="usar um roteiro JSON pronto (pula o LLM de roteiro)")
    p.add_argument("--brand", default="", help="nome da marca")
    p.add_argument("--url", default="", help="site para o cartão final")
    p.add_argument("--colors", default="", help="cores da marca, ex: '#F97316, #1C1917'")
    p.add_argument("--language", default="Brazilian Portuguese")
    p.add_argument("--style", default=None, choices=sorted(STYLES), help="estilo visual (padrão: paper)")
    p.add_argument("--structure", default="auto", choices=sorted(STRUCTURES), help="estrutura narrativa")
    p.add_argument("--seconds", type=int, default=30, help="duração alvo")
    p.add_argument("--format", choices=["9:16", "16:9"], default="9:16")
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--model", default="qwen2.5-coder:14b", help="modelo Ollama para o código das cenas")
    p.add_argument("--plan-model", default=None, help="modelo Ollama para o roteiro (padrão: --model)")
    p.add_argument("--ollama", default="http://localhost:11434")
    p.add_argument("--voice", default="pt_BR-faber-medium", help="voz Piper: nome (baixa sozinha) ou caminho .onnx")
    p.add_argument("--voices-dir", default="voices", help="pasta dos modelos de voz Piper")
    p.add_argument("--length-scale", type=float, default=1.0, help="velocidade da fala: <1 mais rápido, >1 mais lento")
    p.add_argument("--no-tts", action="store_true", help="sem narração")
    p.add_argument("--no-captions", action="store_true", help="sem legendas")
    p.add_argument("--music", help="trilha de fundo (mp3/wav); abaixa sozinha sob a voz")
    p.add_argument("--music-volume", type=float, default=0.5)
    p.add_argument("--max-fix", type=int, default=3, help="rodadas de correção por cena")
    p.add_argument("--regen", action="store_true", help="reescrever todas as cenas")
    p.add_argument("--replan", action="store_true", help="refazer o roteiro mesmo se já existir")
    p.add_argument("--stills", action="store_true", help="salvar uma prévia PNG de cada cena")
    p.add_argument("--workdir", default="work")
    p.add_argument("--out", default="video.mp4")
    args = p.parse_args()

    args.style_set = args.style is not None
    args.style = args.style or "paper"
    if args.brief_file:
        args.brief = Path(args.brief_file).read_text(encoding="utf-8")
    if not args.brief and not args.plan and not (Path(args.workdir) / "plan.json").exists():
        p.error("informe um briefing, --brief-file ou --plan")

    run(args, Ollama(args.ollama))


if __name__ == "__main__":
    main()
