"""저작권 걱정 없는 배경음을 직접 합성한다 (코드 패드 + 베이스 + 가벼운 비트 + 아르페지오).

사용법: python generator/make_music.py  -> generator/music/*.mp3
music 폴더에 직접 받은 무료 음원(mp3)을 넣어도 make_reel.py 가 함께 사용한다.
"""
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 44100
OUT = Path(__file__).parent / "music"
NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}

# 이름: (bpm, 코드 진행, 분위기 메모)
TRACKS = {
    "bright": (96, ["C maj7", "G 7", "A m7", "F maj7"]),
    "calm": (78, ["A m7", "F maj7", "C maj7", "G 6"]),
    "upbeat": (112, ["F maj7", "G 6", "E m7", "A m7"]),
    "warm": (86, ["D maj7", "B m7", "G maj7", "A 6"]),
}
SHAPES = {"maj7": [0, 4, 7, 11], "m7": [0, 3, 7, 10], "7": [0, 4, 7, 10], "6": [0, 4, 7, 9]}


def freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def chord_notes(name, octave=4):
    root, shape = name.split()
    base = 12 * (octave + 1) + NOTE[root]
    return base, [base + i for i in SHAPES[shape]]


def env(n, attack, release):
    e = np.ones(n)
    a, r = int(attack * SR), int(release * SR)
    e[:a] = np.linspace(0, 1, a)
    e[-r:] *= np.linspace(1, 0, r)
    return e


def tone(f, dur, kind="pad"):
    t = np.arange(int(dur * SR)) / SR
    if kind == "pad":  # 살짝 어긋난 사인파 두 개 + 배음 = 부드러운 패드
        w = np.sin(2 * np.pi * f * t) + np.sin(2 * np.pi * f * 1.004 * t) + 0.25 * np.sin(4 * np.pi * f * t)
        return w * env(len(t), 0.4, 0.6) * 0.12
    if kind == "bass":
        return np.sin(2 * np.pi * f * t) * env(len(t), 0.02, 0.3) * 0.35
    if kind == "pluck":  # 지수 감쇠 = 건반/플럭 느낌
        return (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(6 * np.pi * f * t)) * np.exp(-t * 6) * 0.13
    raise ValueError(kind)


def kick(dur=0.35):
    t = np.arange(int(dur * SR)) / SR
    return np.sin(2 * np.pi * (50 + 90 * np.exp(-t * 30)) * t) * np.exp(-t * 9) * 0.55


def hat(rng, dur=0.06):
    n = rng.standard_normal(int(dur * SR))
    n = np.diff(n, prepend=0)  # 고역만 남기기
    return n * np.exp(-np.arange(len(n)) / SR * 60) * 0.05


def add(buf, sig, start):
    s = int(start * SR)
    if s >= len(buf):
        return
    e = min(len(buf), s + len(sig))
    buf[s:e] += sig[: e - s]


def render(bpm, prog, seconds=40, seed=0):
    rng = np.random.default_rng(seed)
    beat = 60 / bpm
    bar = beat * 4
    buf = np.zeros(int(seconds * SR) + SR)
    t, i = 0.0, 0
    while t < seconds:
        root, notes = chord_notes(prog[i % len(prog)])
        for m in notes:
            add(buf, tone(freq(m), bar + 0.5, "pad"), t)
        add(buf, tone(freq(root - 24), beat * 1.8, "bass"), t)
        add(buf, tone(freq(root - 24), beat * 1.8, "bass"), t + beat * 2)
        for b in range(4):
            if i >= 1:  # 첫 마디는 비트 없이 시작
                if b in (0, 2):
                    add(buf, kick(), t + b * beat)
                add(buf, hat(rng), t + b * beat + beat / 2)
        arp = notes + [notes[0] + 12]
        for k in range(8):
            if rng.random() < 0.75:
                add(buf, tone(freq(arp[rng.integers(len(arp))] + 12), beat, "pluck"), t + k * beat / 2)
        t += bar
        i += 1
    buf = buf[: int(seconds * SR)]
    # 간단한 리버브 느낌 (지연 신호 섞기)
    for d, g in ((0.11, 0.25), (0.23, 0.15), (0.37, 0.08)):
        n = int(d * SR)
        buf[n:] += buf[:-n] * g
    buf = np.tanh(buf * 1.2)
    buf /= np.abs(buf).max() / 0.8
    left = buf
    right = np.roll(buf, int(0.012 * SR))  # 살짝 넓은 스테레오
    return np.stack([left, right], axis=1)


def main():
    OUT.mkdir(exist_ok=True)
    ff = __import__("make_reel").ffmpeg()
    for i, (name, (bpm, prog)) in enumerate(TRACKS.items()):
        data = (render(bpm, prog, seed=i) * 32767).astype(np.int16)
        wav = OUT / f"{name}.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(data.tobytes())
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "160k", str(OUT / f"{name}.mp3")],
                       check=True)
        wav.unlink()
        print("made", name)


if __name__ == "__main__":
    main()
