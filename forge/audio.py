import subprocess


def mix_and_mux(video, voices, total, out, music=None, music_volume=0.5):
    """voices: lista de (caminho_mp3, inicio_em_segundos). A música abaixa sozinha quando a voz fala."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video)]
    for path, _ in voices:
        cmd += ["-i", str(path)]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]

    f, labels = [], []
    for k, (_, start) in enumerate(voices, start=1):
        ms = int(round(start * 1000))
        f.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{k}]")
        labels.append(f"[v{k}]")
    f.append(f"{''.join(labels)}amix=inputs={len(voices)}:normalize=0:dropout_transition=0,"
             f"apad,atrim=0:{total:.3f}[voice]")
    fade = f"afade=t=out:st={max(0.0, total - 1.2):.3f}:d=1.2"
    if music:
        m = len(voices) + 1
        f.append("[voice]asplit=2[vo][sc]")
        f.append(f"[{m}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total:.3f},"
                 f"volume={music_volume}[mu]")
        f.append("[mu][sc]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350[duck]")
        f.append(f"[vo][duck]amix=inputs=2:normalize=0,{fade}[a]")
    else:
        f.append(f"[voice]{fade}[a]")

    cmd += ["-filter_complex", ";".join(f), "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True)
