from __future__ import annotations
from pathlib import Path
import os
import configparser

class AudioManager:
    """Sound manager using pygame-ce / SDL2 with selectable driver and output device."""

    SOUND_NAMES = {
        "move": "move.wav",
        "capture": "capture.wav",
        "check": "check.wav",
        "checkmate": "checkmate.wav",
        "draw": "draw.wav",
        "start": "start.wav",
        "stop": "stop.wav",
    }

    def __init__(self, settings_path="data/settings.ini", sound_dir="assets/sounds"):
        self.settings_path = Path(settings_path)
        self.sound_dir = Path(sound_dir)
        self.enabled = True
        self.volume = 0.75
        self.driver = "auto"
        self.device = "auto"
        self._mixer_ready = False
        self._sounds = {}
        self.load_settings()

    def _config(self):
        cfg = configparser.ConfigParser()
        if self.settings_path.exists():
            try:
                cfg.read(self.settings_path, encoding="utf-8")
            except configparser.Error:
                # Never let a damaged settings file prevent Chess Pionier from starting.
                pass
        if "Sound" not in cfg:
            cfg["Sound"] = {}
        return cfg

    def load_settings(self):
        cfg = self._config()
        sec = cfg["Sound"]
        self.enabled = sec.getboolean("enabled", fallback=True)
        self.volume = max(0.0, min(1.0, sec.getfloat("volume", fallback=0.75)))
        self.driver = sec.get("driver", fallback="auto")
        self.device = sec.get("device", fallback="auto")

    def save_settings(self):
        cfg = self._config()
        cfg["Sound"]["enabled"] = str(self.enabled)
        cfg["Sound"]["volume"] = str(self.volume)
        cfg["Sound"]["driver"] = self.driver
        cfg["Sound"]["device"] = self.device
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.settings_path.with_suffix(".ini.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            cfg.write(f)
        tmp.replace(self.settings_path)

    @staticmethod
    def available_drivers():
        choices = ["auto"]
        try:
            import pygame
            # pygame._sdl2 is available in pygame-ce builds with SDL2.
            drivers = []
            try:
                drivers = list(pygame._sdl2.get_audio_device_names(False))
            except Exception:
                pass
            # Keep portable choices; actual initialization decides support.
        except Exception:
            pass
        if os.name == "nt":
            choices += ["wasapi", "directsound", "winmm"]
        elif os.name == "posix":
            choices += ["pipewire", "pulse", "alsa"]
        return list(dict.fromkeys(choices))

    def available_devices(self, driver=None):
        """Return actual SDL2 playback device names for the selected backend."""
        driver = driver if driver is not None else self.driver
        old_driver = os.environ.get("SDL_AUDIODRIVER")
        try:
            if driver and driver != "auto":
                os.environ["SDL_AUDIODRIVER"] = driver
            elif old_driver is not None:
                os.environ.pop("SDL_AUDIODRIVER", None)

            import pygame
            # mixer must be initialized before SDL's playback-device enumeration.
            was_ready = bool(pygame.mixer.get_init())
            if not was_ready:
                try:
                    pygame.mixer.init()
                except Exception:
                    return []
            try:
                from pygame._sdl2 import get_audio_device_names
                return list(get_audio_device_names(False))
            finally:
                if not was_ready:
                    pygame.mixer.quit()
        except Exception:
            return []
        finally:
            if old_driver is None:
                os.environ.pop("SDL_AUDIODRIVER", None)
            else:
                os.environ["SDL_AUDIODRIVER"] = old_driver

    def _init_mixer(self):
        if self._mixer_ready:
            return
        try:
            import pygame
            if self.driver and self.driver != "auto":
                os.environ["SDL_AUDIODRIVER"] = self.driver
            else:
                os.environ.pop("SDL_AUDIODRIVER", None)

            kwargs = {}
            if self.device and self.device != "auto":
                kwargs["devicename"] = self.device
            pygame.mixer.init(**kwargs)
            pygame.mixer.set_num_channels(8)
            self._mixer_ready = True
            self._load_sounds()
        except Exception:
            self._mixer_ready = False

    def _load_sounds(self):
        import pygame
        self._sounds.clear()
        for key, filename in self.SOUND_NAMES.items():
            p = self.sound_dir / filename
            if p.exists():
                try:
                    sound = pygame.mixer.Sound(str(p))
                    sound.set_volume(self.volume)
                    self._sounds[key] = sound
                except Exception:
                    pass

    def play(self, event):
        if not self.enabled:
            return
        self._init_mixer()
        sound = self._sounds.get(event)
        if sound:
            try:
                sound.play()
            except Exception:
                pass

    def set_volume(self, value):
        self.volume = max(0.0, min(1.0, float(value)))
        for sound in self._sounds.values():
            sound.set_volume(self.volume)
        self.save_settings()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self.save_settings()

    def test(self):
        self.play("move")

    def shutdown(self):
        if self._mixer_ready:
            try:
                import pygame
                pygame.mixer.quit()
            except Exception:
                pass
        self._mixer_ready = False
