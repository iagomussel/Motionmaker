"""TTS local com Piper (piper-tts). Gera um WAV por cena e o tempo de cada palavra.

Tempo das palavras:
  1. Se o modelo de voz tiver alinhamento de fonemas, usa o alinhamento real.
  2. Senão, estima: o Piper gera um bloco de áudio por frase; dentro de cada frase,
     a parte com voz é dividida entre as palavras pelo número de fonemas de cada uma.
     O erro costuma ficar em décimos de segundo, o que basta para sincronizar animação.
"""
import hashlib
import json
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

_VOICES = {}
SENTENCE_PAUSE = 0.22  # silêncio entre frases (s)


def audio_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def resolve_model(voice, voices_dir):
    """Aceita um caminho .onnx ou um nome como 'pt_BR-faber-medium' (baixa se faltar)."""
    p = Path(voice)
    if p.suffix == ".onnx" and p.exists():
        return p
    voices_dir = Path(voices_dir)
    model = voices_dir / f"{voice}.onnx"
    if not model.exists():
        voices_dir.mkdir(parents=True, exist_ok=True)
        print(f"· Baixando a voz Piper '{voice}'…", flush=True)
        subprocess.run([sys.executable, "-m", "piper.download_voices", voice, "--download-dir", str(voices_dir)],
                       check=True)
    if not model.exists():
        raise FileNotFoundError(f"Modelo de voz não encontrado: {model}")
    return model


def load_voice(model_path):
    from piper import PiperVoice
    key = str(model_path)
    if key not in _VOICES:
        _VOICES[key] = PiperVoice.load(model_path)
    return _VOICES[key]


def _voiced_span(audio, sr, thr=0.02):
    idx = np.flatnonzero(np.abs(audio) > thr)
    if idx.size == 0:
        return 0.0, len(audio) / sr
    return idx[0] / sr, (idx[-1] + 1) / sr


def _groups(phonemes):
    """Divide a lista de fonemas da frase em palavras (o espeak separa palavras com espaço)."""
    groups, cur = [], []
    for ph in phonemes:
        if ph == " ":
            if cur:
                groups.append(cur)
            cur = []
        else:
            cur.append(ph)
    if cur:
        groups.append(cur)
    return [g for g in groups if any(re.match(r"\w", x) for x in g)]


def _segments_from_alignment(chunk, offset):
    """Tempo real de cada palavra a partir do alinhamento (só em modelos que suportam)."""
    sr, t, segs, start = chunk.sample_rate, offset, [], None
    for al in chunk.phoneme_alignments:
        dur = al.num_samples / sr
        if al.phoneme == " ":
            if start is not None:
                segs.append((start, t))
                start = None
        elif re.match(r"\w", al.phoneme) and start is None:
            start = t
        t += dur
    if start is not None:
        segs.append((start, t))
    return segs


def _segments_estimated(chunk, offset):
    a, b = _voiced_span(chunk.audio_float_array, chunk.sample_rate)
    groups = _groups(chunk.phonemes)
    if not groups:
        return []
    weights = np.array([len(g) for g in groups], dtype=float)
    edges = np.concatenate([[0], np.cumsum(weights)]) / weights.sum()
    span = b - a
    return [(offset + a + edges[i] * span, offset + a + edges[i + 1] * span) for i in range(len(groups))]


def _label(words, segs, spans):
    """Põe as palavras do texto nos tempos. Se a contagem não bater (números, siglas), distribui por letras."""
    if len(words) == len(segs):
        return [{"w": w, "t": round(float(s), 3), "d": round(float(e - s), 3)} for w, (s, e) in zip(words, segs)]
    total = sum(e - s for s, e in spans) or 1.0
    weights = [max(1, len(re.sub(r"\W", "", w))) for w in words]
    wsum = sum(weights)
    out, acc = [], 0.0
    for w, k in zip(words, weights):
        a_pos, b_pos = acc / wsum * total, (acc + k) / wsum * total
        out.append({"w": w, "t": round(_map(a_pos, spans), 3), "d": round(_map(b_pos, spans) - _map(a_pos, spans), 3)})
        acc += k
    return out


def word_times(text, sent_segs, spans):
    """Casa as palavras do texto com os tempos, frase por frase quando possível."""
    sentences = [x for x in re.split(r"(?<=[.!?…])\s+", text.strip()) if x]
    if len(sentences) == len(sent_segs) == len(spans):
        out = []
        for sent, segs, span in zip(sentences, sent_segs, spans):
            out += _label(re.findall(r"\S+", sent), segs, [span])
        return out
    flat = [x for segs in sent_segs for x in segs]
    return _label(re.findall(r"\S+", text), flat, spans)


def _map(pos, spans):
    """Converte posição no 'tempo falado' (sem pausas) para o tempo real do áudio."""
    for s, e in spans:
        if pos <= e - s:
            return s + pos
        pos -= e - s
    return spans[-1][1] if spans else pos


def synth_scene(text, voice, length_scale, voices_dir, out_dir, scene_id):
    """Gera <id>.wav e <id>.json (palavras com tempo). Reaproveita se nada mudou."""
    from piper import SynthesisConfig

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    wav_path, meta_path = out_dir / f"{scene_id}.wav", out_dir / f"{scene_id}.json"
    key = hashlib.sha1(f"{voice}|{length_scale}|{text}".encode()).hexdigest()
    if wav_path.exists() and meta_path.exists():
        data = json.loads(meta_path.read_text())
        if data.get("key") == key:
            return wav_path, data

    pv = load_voice(resolve_model(voice, voices_dir))
    cfg = SynthesisConfig(length_scale=length_scale)
    pieces, sent_segs, spans, t, sr = [], [], [], 0.0, None
    for chunk in pv.synthesize(text, syn_config=cfg, include_alignments=True):
        sr = chunk.sample_rate
        audio = chunk.audio_float_array
        if chunk.phoneme_alignments:
            sent_segs.append(_segments_from_alignment(chunk, t))
        else:
            sent_segs.append(_segments_estimated(chunk, t))
        a, b = _voiced_span(audio, sr)
        spans.append((t + a, t + b))
        pieces.append(audio)
        t += len(audio) / sr
        pause = np.zeros(int(SENTENCE_PAUSE * sr), dtype=np.float32)
        pieces.append(pause)
        t += len(pause) / sr

    if not pieces:
        raise RuntimeError(f"Piper não gerou áudio para: {text!r}")
    audio = np.concatenate(pieces[:-1])  # sem pausa no final
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())

    data = {"key": key, "text": text, "duration": len(audio) / sr, "words": word_times(text, sent_segs, spans)}
    meta_path.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    return wav_path, data
