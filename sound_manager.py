"""
Sound Manager for the Gesture Snake Game.
Uses NumPy and Pygame to create simple retro arcade sound effects
directly in code without needing external audio files.
"""
import numpy as np
import pygame


class SoundManager:
    def __init__(self):
        self.enabled = True
        self.initialized = False
        self.sounds = {}
        self._init_audio()

    def _init_audio(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self.initialized = True
            self._generate_sounds()
        except Exception:
            self.initialized = False
            self.enabled = False

    def _make_tone(self, freqs, durations, volume=0.28, wave_type="sine"):
        """Generate a stereo pygame Sound from a list of (frequency, duration_sec) pairs."""
        sample_rate = 44100
        segments = []
        for freq, dur in zip(freqs, durations):
            n_samples = int(sample_rate * dur)
            if n_samples <= 0:
                continue
            t = np.linspace(0, dur, n_samples, endpoint=False)
            if freq <= 0:
                wave = np.zeros(n_samples, dtype=np.float32)
            elif wave_type == "square":
                wave = np.sign(np.sin(2 * np.pi * freq * t)).astype(np.float32)
            elif wave_type == "triangle":
                wave = (2 * np.abs(2 * (t * freq - np.floor(t * freq + 0.5))) - 1).astype(np.float32)
            else:
                wave = np.sin(2 * np.pi * freq * t).astype(np.float32)

            # Smooth envelope to avoid clicks
            fade_len = min(int(sample_rate * 0.012), n_samples // 4)
            if fade_len > 0:
                envelope = np.ones(n_samples, dtype=np.float32)
                envelope[:fade_len] = np.linspace(0.0, 1.0, fade_len)
                envelope[-fade_len:] = np.linspace(1.0, 0.0, fade_len)
                wave *= envelope

            segments.append(wave)

        if not segments:
            return None

        mono = np.concatenate(segments)
        pcm = np.int16(np.clip(mono * volume, -1.0, 1.0) * 32767)
        stereo = np.column_stack((pcm, pcm))
        return pygame.sndarray.make_sound(stereo)

    def _generate_sounds(self):
        if not self.initialized:
            return
        try:
            # Eat normal food: upbeat two-note chime
            self.sounds["eat"] = self._make_tone(
                [523.25, 659.25, 783.99], [0.055, 0.055, 0.08], volume=0.25, wave_type="triangle"
            )
            # Eat bonus golden food: sparkly arpeggio
            self.sounds["bonus"] = self._make_tone(
                [587.33, 783.99, 987.77, 1174.66], [0.05, 0.05, 0.05, 0.11], volume=0.28, wave_type="triangle"
            )
            # Pause / Resume toggle
            self.sounds["pause"] = self._make_tone(
                [440.0, 330.0], [0.06, 0.08], volume=0.22, wave_type="sine"
            )
            self.sounds["resume"] = self._make_tone(
                [330.0, 440.0], [0.06, 0.08], volume=0.22, wave_type="sine"
            )
            # Game Over: classic descending tones
            self.sounds["game_over"] = self._make_tone(
                [392.0, 349.23, 329.63, 261.63], [0.11, 0.11, 0.11, 0.25], volume=0.28, wave_type="square"
            )
            # UI click / calibration lock
            self.sounds["select"] = self._make_tone(
                [660.0, 880.0], [0.04, 0.06], volume=0.20, wave_type="sine"
            )
        except Exception:
            self.initialized = False

    def play(self, name: str):
        if not self.enabled or not self.initialized:
            return
        snd = self.sounds.get(name)
        if snd is not None:
            try:
                snd.play()
            except Exception:
                pass

    def toggle_mute(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled

