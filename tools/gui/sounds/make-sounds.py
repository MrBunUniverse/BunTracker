#!/usr/bin/env python3
# Original sounds synthesised for Bun Tracker; © MrBunUniverse, MIT
"""Synthesise the complete original Bun Tracker UI sound set from scratch.

Generates 14 stereo 44.1 kHz WAV assets using pure NumPy additive/subtractive
synthesis (no external samples or third-party recordings) and encodes them to
OGG Vorbis in gui/app/public/sounds/.

Usage:
    python3 tools/gui/sounds/make-sounds.py
    python3 tools/gui/sounds/make-sounds.py --wav-dir /tmp/sound-review/wav
"""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

SR = 44100
CHANNELS = 2
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT_DIR = REPO_ROOT / "gui" / "app" / "public" / "sounds"

# Note frequencies (Hz)
C4 = 261.6256
F4 = 349.2282
G4 = 391.9954
A4 = 440.0000
BB4 = 466.1638
C5 = 523.2511
F5 = 698.4565
BB5 = 932.3275
C6 = 1046.5023
D6 = 1174.6591
F6 = 1396.9129


def raised_cosine_fade(n: int, fade_in_s: float, fade_out_s: float) -> np.ndarray:
    """Create a click-free envelope with raised-cosine edge fades."""
    env = np.ones(n, dtype=np.float64)
    fi = min(n // 2, max(1, int(round(fade_in_s * SR))))
    fo = min(n - fi, max(1, int(round(fade_out_s * SR))))
    if fi > 1:
        env[:fi] = 0.5 * (1.0 - np.cos(np.pi * np.arange(fi) / fi))
    if fo > 1:
        env[-fo:] = 0.5 * (1.0 + np.cos(np.pi * np.arange(fo) / fo))
    env[0] = 0.0
    env[-1] = 0.0
    return env


def pan_stereo(mono: np.ndarray, pan: float = 0.0) -> np.ndarray:
    """Equal-power stereo panning (-1.0 left to +1.0 right)."""
    angle = (np.clip(pan, -1.0, 1.0) + 1.0) * (math.pi / 4.0)
    return np.column_stack((mono * math.cos(angle), mono * math.sin(angle)))


def fft_band_filter(
    sig: np.ndarray,
    low_hz: float | None = None,
    high_hz: float | None = None,
    order: float = 4.0,
) -> np.ndarray:
    """Smooth zero-phase Butterworth-magnitude filter in the frequency domain."""
    n = sig.shape[0]
    freqs = np.fft.rfftfreq(n, 1.0 / SR)
    resp = np.ones_like(freqs)
    if low_hz is not None and low_hz > 0.0:
        with np.errstate(divide="ignore"):
            ratio = np.where(freqs > 0.0, low_hz / freqs, np.inf)
        resp /= np.sqrt(1.0 + np.power(ratio, 2.0 * order))
        resp[0] = 0.0
    if high_hz is not None and high_hz > 0.0:
        resp /= np.sqrt(1.0 + np.power(freqs / high_hz, 2.0 * order))

    if sig.ndim == 1:
        return np.fft.irfft(np.fft.rfft(sig) * resp, n=n)
    out = np.empty_like(sig)
    for ch in range(sig.shape[1]):
        out[:, ch] = np.fft.irfft(np.fft.rfft(sig[:, ch]) * resp, n=n)
    return out


def make_room_ir(
    rt60_s: float = 1.15,
    high_hz: float = 3800.0,
    seed: int = 101,
    ir_dur_s: float = 1.6,
) -> np.ndarray:
    """Synthesise a plush, smooth stereo room impulse response."""
    rng = np.random.default_rng(seed)
    n = int(round(ir_dur_s * SR))
    t = np.arange(n, dtype=np.float64) / SR

    # Soft early reflections + decorrelated exponentially decaying noise tail
    decay = np.exp(-6.9078 * t / max(0.08, rt60_s))
    onset = 1.0 - np.exp(-t / 0.018)
    tail_l = rng.standard_normal(n) * decay * onset
    tail_r = rng.standard_normal(n) * decay * onset

    ir = np.column_stack((tail_l, tail_r))
    # Progressive warmth: low-pass the diffuse tail
    ir = fft_band_filter(ir, low_hz=120.0, high_hz=high_hz, order=2.0)

    # Add a few gentle, non-metallic early reflection taps
    early_taps = [
        (0.011, 0.24, -0.30),
        (0.019, 0.18, 0.35),
        (0.029, 0.13, -0.22),
        (0.043, 0.09, 0.25),
    ]
    for delay_s, gain, tap_pan in early_taps:
        idx = int(round(delay_s * SR))
        if idx < n:
            angle = (tap_pan + 1.0) * (math.pi / 4.0)
            ir[idx, 0] += gain * math.cos(angle)
            ir[idx, 1] += gain * math.sin(angle)

    ir *= raised_cosine_fade(n, 0.002, 0.12)[:, None]
    energy = np.sqrt(np.mean(ir**2))
    if energy > 0:
        ir /= energy * 18.0
    return ir


def apply_reverb(dry: np.ndarray, ir: np.ndarray, wet: float = 0.35) -> np.ndarray:
    """Convolve a stereo signal with a stereo IR using FFT and blend wet/dry."""
    n = dry.shape[0]
    m = ir.shape[0]
    n_fft = 1 << int(math.ceil(math.log2(n + m - 1)))
    wet_sig = np.empty_like(dry)
    for ch in range(CHANNELS):
        spec = np.fft.rfft(dry[:, ch], n=n_fft) * np.fft.rfft(ir[:, ch], n=n_fft)
        wet_sig[:, ch] = np.fft.irfft(spec, n=n_fft)[:n]
    return dry + wet * wet_sig


def add_marimba_note(
    buf: np.ndarray,
    t0: float,
    freq: float,
    amp: float = 1.0,
    decay_s: float = 0.26,
    pan: float = 0.0,
    wood_click: float = 0.16,
    detune_pct: float = 0.0005,
) -> None:
    """Add a warm, soft marimba/kalimba note with felt-mallet attack."""
    n_total = buf.shape[0]
    start = int(round(t0 * SR))
    if start >= n_total:
        return
    n = n_total - start
    t = np.arange(n, dtype=np.float64) / SR

    # Smooth 3 ms felt attack
    att = 1.0 - np.exp(-t / 0.0028)
    partials = [
        (1.000, 1.00, decay_s),
        (2.000, 0.16, decay_s * 0.42),
        (3.985, 0.09, decay_s * 0.16),  # classic resonant bar overtone
    ]
    left = np.zeros(n, dtype=np.float64)
    right = np.zeros(n, dtype=np.float64)
    for mult, p_amp, p_dec in partials:
        env = att * np.exp(-t / max(0.01, p_dec))
        left += p_amp * env * np.sin(2.0 * math.pi * freq * mult * (1.0 - detune_pct) * t)
        right += p_amp * env * np.sin(2.0 * math.pi * freq * mult * (1.0 + detune_pct) * t)

    # Gentle felt-mallet knock (quick downward pitch drop over 6 ms)
    if wood_click > 0.0:
        f_knock = freq * (1.0 + 0.75 * np.exp(-t / 0.0045))
        phase_knock = 2.0 * math.pi * np.cumsum(f_knock) / SR
        knock = wood_click * np.exp(-t / 0.0085) * (1.0 - np.exp(-t / 0.0012)) * np.sin(phase_knock)
        left += knock
        right += knock

    angle = (np.clip(pan, -1.0, 1.0) + 1.0) * (math.pi / 4.0)
    buf[start:, 0] += amp * left * math.cos(angle)
    buf[start:, 1] += amp * right * math.sin(angle)


def add_bell_pluck_note(
    buf: np.ndarray,
    t0: float,
    freq: float,
    amp: float = 1.0,
    decay_s: float = 0.30,
    pan: float = 0.0,
    sparkle: float = 0.14,
    detune_pct: float = 0.0005,
) -> None:
    """Add a brighter celesta/kalimba-bell pluck (distinct Mounting Reset voice)."""
    n_total = buf.shape[0]
    start = int(round(t0 * SR))
    if start >= n_total:
        return
    n = n_total - start
    t = np.arange(n, dtype=np.float64) / SR

    att = 1.0 - np.exp(-t / 0.0016)
    partials = [
        (1.000, 1.00, decay_s),
        (2.000, 0.30, decay_s * 0.58),
        (3.000, 0.13, decay_s * 0.32),
        (4.025, 0.055, decay_s * 0.18),
        (5.410, 0.025 * sparkle / 0.14, decay_s * 0.09),
    ]
    left = np.zeros(n, dtype=np.float64)
    right = np.zeros(n, dtype=np.float64)
    for idx, (mult, p_amp, p_dec) in enumerate(partials):
        d = detune_pct * (1 if idx % 2 == 0 else -1)
        env = att * np.exp(-t / max(0.008, p_dec))
        left += p_amp * env * np.sin(2.0 * math.pi * freq * mult * (1.0 - d) * t)
        right += p_amp * env * np.sin(2.0 * math.pi * freq * mult * (1.0 + d) * t)

    # Crisp soft tine/pluck transient
    pluck_f = freq * (1.0 + 0.35 * np.exp(-t / 0.003))
    pluck_ph = 2.0 * math.pi * np.cumsum(pluck_f) / SR
    pluck = sparkle * np.exp(-t / 0.010) * (1.0 - np.exp(-t / 0.0009)) * np.sin(pluck_ph)
    left += pluck
    right += pluck

    angle = (np.clip(pan, -1.0, 1.0) + 1.0) * (math.pi / 4.0)
    buf[start:, 0] += amp * left * math.cos(angle)
    buf[start:, 1] += amp * right * math.sin(angle)


def tv_bandpass_noise(
    noise: np.ndarray,
    fc_hz: np.ndarray,
    q: float = 2.6,
    block: int = 32,
) -> np.ndarray:
    """Time-varying resonant biquad bandpass filter for smooth air sweeps."""
    n = len(noise)
    out = np.zeros(n, dtype=np.float64)
    z1 = 0.0
    z2 = 0.0
    for i in range(0, n, block):
        end = min(n, i + block)
        fc = float(np.clip(fc_hz[(i + end) // 2], 60.0, SR * 0.42))
        w0 = 2.0 * math.pi * fc / SR
        alpha = math.sin(w0) / (2.0 * q)
        cos_w0 = math.cos(w0)
        a0 = 1.0 + alpha
        b0 = (alpha) / a0
        b1 = 0.0
        b2 = (-alpha) / a0
        a1 = (-2.0 * cos_w0) / a0
        a2 = (1.0 - alpha) / a0
        for j in range(i, end):
            x = noise[j]
            y = b0 * x + z1
            z1 = b1 * x - a1 * y + z2
            z2 = b2 * x - a2 * y
            out[j] = y
    return out


def biquad_resonator_tv(
    sig: np.ndarray,
    fc_hz: np.ndarray,
    q: float = 3.5,
    block: int = 32,
) -> np.ndarray:
    """Time-varying constant-peak-gain formant resonator."""
    n = len(sig)
    out = np.zeros(n, dtype=np.float64)
    z1 = 0.0
    z2 = 0.0
    for i in range(0, n, block):
        end = min(n, i + block)
        fc = float(np.clip(fc_hz[(i + end) // 2], 80.0, SR * 0.42))
        w0 = 2.0 * math.pi * fc / SR
        alpha = math.sin(w0) / (2.0 * q)
        cos_w0 = math.cos(w0)
        a0 = 1.0 + alpha
        # Peak gain = Q normalized to ~1 at center
        b0 = (q * alpha) / a0
        b2 = (-q * alpha) / a0
        a1 = (-2.0 * cos_w0) / a0
        a2 = (1.0 - alpha) / a0
        for j in range(i, end):
            x = sig[j]
            y = b0 * x + z1
            z1 = -a1 * y + z2
            z2 = b2 * x - a2 * y
            out[j] = y
    return out


def finalize(
    buf: np.ndarray,
    target_rms_db: float,
    max_peak_db: float = -3.2,
    fade_in_s: float = 0.003,
    fade_out_s: float = 0.060,
) -> np.ndarray:
    """Remove DC offset, apply smooth edge fades, match RMS, and soft-limit."""
    # Remove any DC offset & subsonic rumble
    out = buf - np.mean(buf, axis=0, keepdims=True)
    out = fft_band_filter(out, low_hz=28.0, high_hz=17500.0, order=2.0)

    # Edge fades (guarantee exact 0.0 endpoints)
    env = raised_cosine_fade(out.shape[0], fade_in_s, fade_out_s)
    out *= env[:, None]

    # Scale to target RMS
    cur_rms = float(np.sqrt(np.mean(out**2)))
    if cur_rms > 1e-12:
        target_rms = 10.0 ** (target_rms_db / 20.0)
        out *= target_rms / cur_rms

    # Transparent soft-clip limiter below max_peak_db (always <= -3 dBFS)
    ceiling = 10.0 ** (min(max_peak_db, -3.1) / 20.0)
    peak = float(np.max(np.abs(out)))
    if peak > ceiling:
        # Smooth knee compression via tanh scaled to ceiling
        knee = ceiling * 0.85
        over = np.abs(out) > knee
        sign = np.sign(out)
        mag = np.abs(out)
        headroom = ceiling - knee
        compressed = knee + headroom * np.tanh((mag - knee) / max(1e-9, headroom))
        out = np.where(over, sign * compressed, out)

    # Re-zero exact endpoints and final DC trim
    out -= np.mean(out, axis=0, keepdims=True)
    out *= raised_cosine_fade(out.shape[0], min(fade_in_s, 0.002), min(fade_out_s, 0.015))[:, None]
    # Hard safety guard so peak never exceeds ceiling even by 0.01 dB
    final_peak = float(np.max(np.abs(out)))
    if final_peak > ceiling:
        out *= ceiling / final_peak
    return out


# ---------------------------------------------------------------------------
# Individual Sound Synthesizers (14 sounds)
# ---------------------------------------------------------------------------

def synth_init_full_reset() -> np.ndarray:
    """Warm 3-note rising marimba cue (F4 -> A4 -> C5) with plush room tail."""
    n = int(round(2.546 * SR))
    buf = np.zeros((n, CHANNELS), dtype=np.float64)
    add_marimba_note(buf, 0.010, F4, amp=0.84, decay_s=0.22, pan=-0.20, wood_click=0.18)
    add_marimba_note(buf, 0.115, A4, amp=0.92, decay_s=0.24, pan=0.00, wood_click=0.16)
    add_marimba_note(buf, 0.220, C5, amp=1.00, decay_s=0.38, pan=0.20, wood_click=0.15)
    ir = make_room_ir(rt60_s=1.05, high_hz=3200.0, seed=11, ir_dur_s=1.75)
    buf = apply_reverb(buf, ir, wet=0.30)
    return finalize(buf, target_rms_db=-34.7, max_peak_db=-7.5, fade_in_s=0.004, fade_out_s=0.35)


def synth_end_full_reset() -> np.ndarray:
    """Happy resolved warm marimba chord bloop (F4-A4-C5-F5) with soft tail."""
    n = int(round(2.526 * SR))
    buf = np.zeros((n, CHANNELS), dtype=np.float64)
    # Soft pillow root undertone + gently rolled major chord
    add_marimba_note(buf, 0.006, C4, amp=0.28, decay_s=0.52, pan=0.00, wood_click=0.04)
    add_marimba_note(buf, 0.006, F4, amp=0.82, decay_s=0.50, pan=-0.24, wood_click=0.13)
    add_marimba_note(buf, 0.052, A4, amp=0.86, decay_s=0.52, pan=-0.06, wood_click=0.12)
    add_marimba_note(buf, 0.100, C5, amp=0.94, decay_s=0.58, pan=0.10, wood_click=0.11)
    add_marimba_note(buf, 0.152, F5, amp=0.92, decay_s=0.66, pan=0.24, wood_click=0.09)
    ir = make_room_ir(rt60_s=1.25, high_hz=3400.0, seed=12, ir_dur_s=1.90)
    buf = apply_reverb(buf, ir, wet=0.34)
    return finalize(buf, target_rms_db=-34.8, max_peak_db=-11.5, fade_in_s=0.004, fade_out_s=0.40)


def synth_full_click(freq: float, dur_s: float, target_rms_db: float, pan: float) -> np.ndarray:
    """Short soft wooden marimba 'boop' countdown tap."""
    n = int(round(dur_s * SR))
    buf = np.zeros((n, CHANNELS), dtype=np.float64)
    add_marimba_note(
        buf, 0.003, freq, amp=1.0, decay_s=0.026, pan=pan, wood_click=0.26, detune_pct=0.0
    )
    ir = make_room_ir(rt60_s=0.09, high_hz=2800.0, seed=13, ir_dur_s=0.12)
    buf = apply_reverb(buf, ir, wet=0.12)
    return finalize(buf, target_rms_db=target_rms_db, max_peak_db=-5.0, fade_in_s=0.002, fade_out_s=0.036)


def synth_init_mounting_reset() -> np.ndarray:
    """Brighter 3-note rising celesta/bell-pluck cue (F5 -> Bb5 -> D6) with tail."""
    n = int(round(2.546 * SR))
    buf = np.zeros((n, CHANNELS), dtype=np.float64)
    add_bell_pluck_note(buf, 0.010, F5, amp=0.82, decay_s=0.24, pan=0.22, sparkle=0.15)
    add_bell_pluck_note(buf, 0.115, BB5, amp=0.92, decay_s=0.26, pan=0.00, sparkle=0.16)
    add_bell_pluck_note(buf, 0.220, D6, amp=1.00, decay_s=0.40, pan=-0.22, sparkle=0.17)
    ir = make_room_ir(rt60_s=1.12, high_hz=5600.0, seed=21, ir_dur_s=1.80)
    buf = apply_reverb(buf, ir, wet=0.32)
    return finalize(buf, target_rms_db=-35.4, max_peak_db=-8.5, fade_in_s=0.003, fade_out_s=0.35)


def synth_end_mounting_reset() -> np.ndarray:
    """Happy resolved brighter celesta/bell arpeggio (Bb4-F5-Bb5-D6-F6) with tail."""
    n = int(round(2.526 * SR))
    buf = np.zeros((n, CHANNELS), dtype=np.float64)
    add_marimba_note(buf, 0.006, BB4, amp=0.46, decay_s=0.48, pan=0.00, wood_click=0.05)
    add_bell_pluck_note(buf, 0.048, F5, amp=0.80, decay_s=0.48, pan=0.22, sparkle=0.14)
    add_bell_pluck_note(buf, 0.095, BB5, amp=0.90, decay_s=0.54, pan=0.04, sparkle=0.15)
    add_bell_pluck_note(buf, 0.145, D6, amp=0.94, decay_s=0.60, pan=-0.14, sparkle=0.16)
    add_bell_pluck_note(buf, 0.195, F6, amp=0.56, decay_s=0.62, pan=-0.26, sparkle=0.13)
    ir = make_room_ir(rt60_s=1.30, high_hz=6000.0, seed=22, ir_dur_s=1.90)
    buf = apply_reverb(buf, ir, wet=0.35)
    return finalize(buf, target_rms_db=-35.2, max_peak_db=-12.5, fade_in_s=0.003, fade_out_s=0.40)


def synth_mount_click(freq: float, dur_s: float, target_rms_db: float, pan: float) -> np.ndarray:
    """Short bright delicate celesta/bell-pluck countdown tap."""
    n = int(round(dur_s * SR))
    buf = np.zeros((n, CHANNELS), dtype=np.float64)
    add_bell_pluck_note(
        buf, 0.003, freq, amp=1.0, decay_s=0.025, pan=pan, sparkle=0.20, detune_pct=0.0
    )
    ir = make_room_ir(rt60_s=0.09, high_hz=5200.0, seed=23, ir_dur_s=0.12)
    buf = apply_reverb(buf, ir, wet=0.14)
    return finalize(buf, target_rms_db=target_rms_db, max_peak_db=-5.0, fade_in_s=0.002, fade_out_s=0.036)


def synth_yaw_reset() -> np.ndarray:
    """Quick soft 'swish-boop': airy filtered noise sweep + warm pitched boop."""
    n = int(round(1.243 * SR))
    rng = np.random.default_rng(31)

    # 1) Soft airy stereo swish (0.005s - 0.295s)
    swish_dur = 0.29
    n_sw = int(round(swish_dur * SR))
    ts = np.arange(n_sw, dtype=np.float64) / SR
    # Bell-shaped frequency sweep: 520 Hz -> 2350 Hz -> 880 Hz
    u = ts / swish_dur
    fc = 520.0 + 1830.0 * np.sin(math.pi * np.power(u, 0.80)) ** 1.6 + 360.0 * u
    raw_l = rng.standard_normal(n_sw)
    raw_r = rng.standard_normal(n_sw)
    sw_l = tv_bandpass_noise(raw_l, fc, q=2.8)
    sw_r = tv_bandpass_noise(raw_r, fc * 1.04, q=2.8)
    sw_env = np.sin(math.pi * u) ** 1.7
    # Gentle L->R pan movement across the swish
    pan_curve = -0.40 + 0.80 * u
    ang = (pan_curve + 1.0) * (math.pi / 4.0)

    buf = np.zeros((n, CHANNELS), dtype=np.float64)
    start_sw = int(round(0.005 * SR))
    buf[start_sw : start_sw + n_sw, 0] += 0.52 * sw_l * sw_env * np.cos(ang)
    buf[start_sw : start_sw + n_sw, 1] += 0.52 * sw_r * sw_env * np.sin(ang)

    # 2) Playful soft upward-inflected "boop" landing at F5 (0.140s)
    t_boop0 = 0.140
    b_start = int(round(t_boop0 * SR))
    nb = n - b_start
    tb = np.arange(nb, dtype=np.float64) / SR
    # Quick cute upward pitch glide C5 -> F5 over ~38 ms
    f_boop = F5 - (F5 - C5) * np.exp(-tb / 0.022)
    ph = 2.0 * math.pi * np.cumsum(f_boop) / SR
    att = 1.0 - np.exp(-tb / 0.004)
    boop = att * (
        0.95 * np.exp(-tb / 0.16) * np.sin(ph)
        + 0.18 * np.exp(-tb / 0.08) * np.sin(2.0 * ph)
        + 0.06 * np.exp(-tb / 0.04) * np.sin(3.0 * ph)
    )
    buf[b_start:, 0] += 0.85 * boop
    buf[b_start:, 1] += 0.85 * boop

    ir = make_room_ir(rt60_s=0.60, high_hz=4200.0, seed=32, ir_dur_s=0.90)
    buf = apply_reverb(buf, ir, wet=0.28)
    return finalize(buf, target_rms_db=-31.8, max_peak_db=-8.0, fade_in_s=0.005, fade_out_s=0.22)


def synth_tracking_pause() -> np.ndarray:
    """Soft descending two-note cue (C5 -> G4) indicating pause."""
    n = int(round(0.829 * SR))
    buf = np.zeros((n, CHANNELS), dtype=np.float64)
    add_marimba_note(buf, 0.015, C5, amp=0.92, decay_s=0.17, pan=0.12, wood_click=0.13)
    add_marimba_note(buf, 0.165, G4, amp=0.98, decay_s=0.22, pan=-0.12, wood_click=0.11)
    ir = make_room_ir(rt60_s=0.42, high_hz=2800.0, seed=41, ir_dur_s=0.62)
    buf = apply_reverb(buf, ir, wet=0.24)
    return finalize(buf, target_rms_db=-30.9, max_peak_db=-8.5, fade_in_s=0.004, fade_out_s=0.16)


def synth_tracking_play() -> np.ndarray:
    """Soft ascending two-note cue (G4 -> C5 + gentle C6 shimmer) indicating resume."""
    n = int(round(1.605 * SR))
    buf = np.zeros((n, CHANNELS), dtype=np.float64)
    add_marimba_note(buf, 0.015, G4, amp=0.86, decay_s=0.20, pan=-0.14, wood_click=0.13)
    add_marimba_note(buf, 0.175, C5, amp=1.00, decay_s=0.38, pan=0.14, wood_click=0.11)
    add_bell_pluck_note(buf, 0.180, C6, amp=0.28, decay_s=0.44, pan=0.18, sparkle=0.09)
    ir = make_room_ir(rt60_s=0.88, high_hz=4400.0, seed=42, ir_dur_s=1.25)
    buf = apply_reverb(buf, ir, wet=0.32)
    return finalize(buf, target_rms_db=-32.0, max_peak_db=-9.5, fade_in_s=0.004, fade_out_s=0.28)


def synth_mew() -> np.ndarray:
    """Original cute synthetic bunny squeak: short pitch-bend chirp + soft formants.

    Played alongside end-full-reset and end-mounting-reset on ResetStatus.FINISHED,
    so kept gentle, cozy, and harmonized around F5/C6 with soft formant shaping.
    """
    n = int(round(1.138 * SR))
    rng = np.random.default_rng(51)

    # Active short bunny chirp (~0.26s) starting at 0.16s so it peeks sweetly
    # right after the end-reset chord attack, then fades into a gentle tail.
    chirp_start = int(round(0.160 * SR))
    chirp_dur = 0.260
    nc = int(round(chirp_dur * SR))
    tc = np.arange(nc, dtype=np.float64) / SR
    u = tc / chirp_dur

    # Smooth cute upward-then-curled pitch bend: 698 Hz (F5) -> 1085 Hz -> 895 Hz
    f0 = 698.0 + 390.0 * np.sin(math.pi * np.power(u, 0.72)) ** 1.35 + 165.0 * u
    # Tiny organic vibrato flutter (~18 Hz, +-1.2%)
    f0 *= 1.0 + 0.012 * np.sin(2.0 * math.pi * 18.0 * tc) * np.sin(math.pi * u)

    phase = 2.0 * math.pi * np.cumsum(f0) / SR
    # Soft warm harmonic source (glottal-like gentle rolloff, no harsh buzz)
    source = (
        1.00 * np.sin(phase)
        + 0.44 * np.sin(2.0 * phase + 0.2)
        + 0.18 * np.sin(3.0 * phase + 0.5)
        + 0.06 * np.sin(4.0 * phase)
    )
    # Add a delicate breathy whisper component
    breath = fft_band_filter(rng.standard_normal(nc), low_hz=1200.0, high_hz=3600.0, order=2.0)
    source += 0.045 * breath

    # Amplitude contour: soft attack, cute expressive arch, gentle release
    amp_env = (np.sin(math.pi * np.power(u, 0.85)) ** 1.45) * raised_cosine_fade(nc, 0.015, 0.050)
    source *= amp_env

    # Soft vocal-tract formant shaping (two warm resonators, low-passed <= 4.3 kHz)
    f1_hz = 960.0 + 340.0 * np.sin(math.pi * u)
    f2_hz = 2150.0 + 540.0 * np.sin(math.pi * np.power(u, 0.8))
    formant1 = biquad_resonator_tv(source, f1_hz, q=2.6)
    formant2 = biquad_resonator_tv(source, f2_hz, q=3.5)
    shaped = 0.66 * formant1 + 0.34 * formant2 + 0.18 * source
    shaped = fft_band_filter(shaped, low_hz=260.0, high_hz=4300.0, order=2.5)
    shaped *= raised_cosine_fade(nc, 0.014, 0.048)

    buf = np.zeros((n, CHANNELS), dtype=np.float64)
    buf[chirp_start : chirp_start + nc] = pan_stereo(shaped, pan=0.06)

    ir = make_room_ir(rt60_s=0.50, high_hz=3400.0, seed=52, ir_dur_s=0.70)
    buf = apply_reverb(buf, ir, wet=0.25)
    # Keep mew.ogg subtle (matching original peak ~ -17.8 dB, RMS ~ -32.4 dB)
    return finalize(buf, target_rms_db=-33.0, max_peak_db=-16.5, fade_in_s=0.010, fade_out_s=0.22)


SOUNDS = [
    ("full-reset/init-full-reset-with-tail.ogg", synth_init_full_reset),
    ("full-reset/end-full-reset-with-tail.ogg", synth_end_full_reset),
    ("full-reset/full-click-1.ogg", lambda: synth_full_click(F4, 0.171, -25.5, -0.10)),
    ("full-reset/full-click-2.ogg", lambda: synth_full_click(G4, 0.178, -26.0, 0.00)),
    ("full-reset/full-click-3.ogg", lambda: synth_full_click(A4, 0.171, -25.8, 0.10)),
    ("mounting-reset/init-mounting-reset-with-tail.ogg", synth_init_mounting_reset),
    ("mounting-reset/end-mounting-reset-with-tail.ogg", synth_end_mounting_reset),
    ("mounting-reset/mount-click-1.ogg", lambda: synth_mount_click(BB5, 0.171, -26.1, 0.10)),
    ("mounting-reset/mount-click-2.ogg", lambda: synth_mount_click(C6, 0.178, -26.7, 0.00)),
    ("mounting-reset/mount-click-3.ogg", lambda: synth_mount_click(D6, 0.171, -25.9, -0.10)),
    ("yaw-reset/yaw-reset.ogg", synth_yaw_reset),
    ("tracking/pause.ogg", synth_tracking_pause),
    ("tracking/play.ogg", synth_tracking_play),
    ("mew.ogg", synth_mew),
]


def write_wav(path: Path, audio: np.ndarray) -> None:
    """Write float64 stereo audio in [-1, 1] to 16-bit PCM WAV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(np.round(audio * 32767.0), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())


def detect_vorbis_encoder() -> str:
    """Pick the best available OGG Vorbis encoder without installing packages."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        enc_list = subprocess.check_output(
            [ffmpeg, "-hide_banner", "-encoders"], text=True, stderr=subprocess.DEVNULL
        )
        if " libvorbis " in enc_list:
            return "ffmpeg-libvorbis"
    if shutil.which("oggenc"):
        return "oggenc"
    if ffmpeg:
        enc_list = subprocess.check_output(
            [ffmpeg, "-hide_banner", "-encoders"], text=True, stderr=subprocess.DEVNULL
        )
        if " vorbis " in enc_list:
            return "ffmpeg-vorbis"
    raise RuntimeError(
        "No OGG Vorbis encoder found (tried ffmpeg libvorbis, oggenc, ffmpeg native vorbis)."
    )


def encode_ogg(wav_path: Path, ogg_path: Path, encoder: str) -> None:
    """Encode a 44.1 kHz stereo WAV to OGG Vorbis."""
    ogg_path.parent.mkdir(parents=True, exist_ok=True)
    if encoder == "ffmpeg-libvorbis":
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(wav_path),
            "-ar", str(SR), "-ac", str(CHANNELS),
            "-c:a", "libvorbis", "-q:a", "5",
            str(ogg_path),
        ]
    elif encoder == "oggenc":
        cmd = ["oggenc", "-Q", "-q", "5", "-o", str(ogg_path), str(wav_path)]
    elif encoder == "ffmpeg-vorbis":
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(wav_path),
            "-ar", str(SR), "-ac", str(CHANNELS),
            "-c:a", "vorbis", "-strict", "-2", "-q:a", "7",
            str(ogg_path),
        ]
    else:
        raise ValueError(f"Unknown encoder: {encoder}")
    subprocess.check_call(cmd)


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthesise Bun Tracker sound effects.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Destination directory for encoded .ogg files.",
    )
    parser.add_argument(
        "--wav-dir",
        type=Path,
        default=None,
        help="Optional directory to keep uncompressed 16-bit .wav copies.",
    )
    args = parser.parse_args()

    encoder = detect_vorbis_encoder()
    print(f"Using Vorbis encoder: {encoder}")

    with tempfile.TemporaryDirectory(prefix="bun-sounds-") as tmp:
        tmp_root = Path(tmp)
        for rel_ogg, synth_fn in SOUNDS:
            audio = synth_fn()
            rel_wav = Path(rel_ogg).with_suffix(".wav")
            wav_path = (args.wav_dir / rel_wav) if args.wav_dir else (tmp_root / rel_wav)
            write_wav(wav_path, audio)
            ogg_path = args.out_dir / rel_ogg
            encode_ogg(wav_path, ogg_path, encoder)
            peak_db = 20.0 * math.log10(max(float(np.max(np.abs(audio))), 1e-12))
            rms_db = 20.0 * math.log10(max(float(np.sqrt(np.mean(audio**2))), 1e-12))
            print(
                f"  {rel_ogg:48s} | {len(audio)/SR:.3f}s | "
                f"wav peak={peak_db:6.2f}dB rms={rms_db:6.2f}dB | {ogg_path.stat().st_size:6d}B"
            )


if __name__ == "__main__":
    main()
