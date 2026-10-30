"""VanishCam - verdwijn uit je webcambeeld.

Toetsen in het previewvenster:
  B  achtergrond vastleggen (stap eerst uit beeld; 3 s aftellen, dan 30 frames gemiddeld)
  V  vanish aan/uit (poef-geluid, strepen + gloeiende omtrek, dissolve naar de achtergrond en terug)
  Q / Esc  stoppen
Gebaar: houd een V-teken (wijs- en middelvinger omhoog) een halve seconde vast = zelfde als V.
"""
import argparse
import sys
import time
import urllib.request
import threading
from pathlib import Path

import cv2
import numpy as np

MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
MODEL_PATH = Path(__file__).with_name("hand_landmarker.task")
SOUND_PATH = Path(__file__).with_name("poof.wav")


def blend(live, background, alpha):
    """alpha 0.0 = volledig live, 1.0 = volledig achtergrond."""
    return cv2.addWeighted(live, 1.0 - alpha, background, alpha, 0.0)


def step_alpha(alpha, vanished, dt, duration):
    """Beweeg alpha richting 1 (vanished) of 0 (zichtbaar), begrensd op [0, 1]."""
    target = 1.0 if vanished else 0.0
    step = dt / duration
    if alpha < target:
        return min(target, alpha + step)
    return max(target, alpha - step)


def is_v_sign(lm):
    """lm: 21 (x, y) handpunten (MediaPipe-volgorde, y omlaag).
    Wijs- en middelvinger gestrekt (tip boven PIP-gewricht), ring- en pink gebogen."""
    # shortcut: gaat uit van een rechtop gehouden hand, upgrade naar hoekberekening als zijwaartse V-tekens moeten werken
    def extended(tip, pip):
        return lm[tip][1] < lm[pip][1]
    return extended(8, 6) and extended(12, 10) and not extended(16, 14) and not extended(20, 18)


class HoldTrigger:
    """Vuurt een keer als `seen` `hold` seconden aaneengesloten waar is, daarna `cooldown` seconden stil."""

    def __init__(self, hold=0.5, cooldown=2.0):
        self.hold, self.cooldown = hold, cooldown
        self.since = None
        self.fired_at = -1e9

    def update(self, seen, now):
        if not seen:
            self.since = None
            return False
        if self.since is None:
            self.since = now
        if now - self.since >= self.hold and now - self.fired_at >= self.cooldown:
            self.fired_at = now
            self.since = None
            return True
        return False


def capture_background(cap, frames=30):
    # shortcut: gemiddelde van N frames tegen sensorruis, geen persoon-detectie; upgrade naar segmentatie als iemand in beeld moet kunnen blijven
    acc = None
    for _ in range(frames):
        ok, frame = cap.read()
        if not ok:
            continue
        acc = frame.astype(np.float32) if acc is None else acc + frame
    if acc is None:
        return None
    return (acc / frames).astype(np.uint8)


def person_outline(frame, background, threshold=20):
    """Lijnstukken (open polylines) rond de vlekken die verschillen van de achtergrond, zonder de stukken langs de beeldrand; of None."""
    # shortcut: achtergrondverschil, faalt als je kleding op de muur lijkt; upgrade naar MediaPipe-segmentatie als de omtrek rafelt
    diff = cv2.cvtColor(cv2.absdiff(frame, background), cv2.COLOR_BGR2GRAY)
    mask = cv2.threshold(cv2.GaussianBlur(diff, (21, 21), 0), threshold, 255, cv2.THRESH_BINARY)[1]
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    contours = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]
    h, w = mask.shape
    segments = []
    for c in contours:
        if cv2.contourArea(c) < 0.01 * mask.size:
            continue
        pts = c[:, 0]
        inside = (pts[:, 0] > 2) & (pts[:, 0] < w - 3) & (pts[:, 1] > 2) & (pts[:, 1] < h - 3)
        if inside.all():
            segments.append(np.vstack([pts, pts[:1]]))
            continue
        shift = -int(np.argmin(inside))  # begin op een randpunt, dan is elk binnenstuk aaneengesloten
        pts, inside = np.roll(pts, shift, 0), np.roll(inside, shift)
        cuts = np.flatnonzero(np.diff(inside.astype(np.int8))) + 1
        segments += [run for run, ok in zip(np.split(pts, cuts), np.split(inside, cuts)) if ok[0] and len(run) > 1]
    return [seg.astype(np.int32) for seg in segments] or None


class VanishFx:
    """Flikkerende verticale strepen, daarna een gloeiende witte omtrek die langzaam vervaagt."""

    def __init__(self, outline, started, duration=2.0):
        self.outline, self.started, self.duration = outline, started, duration
        self.rng = np.random.default_rng()

    def draw(self, frame, now):
        """Geeft (beeld, nog_bezig). `frame` blijft ongewijzigd."""
        t = (now - self.started) / self.duration
        if t >= 1.0:
            return frame, False
        h, w = frame.shape[:2]
        out = frame.copy()
        lines = int(40 * max(0.0, 1.0 - 1.5 * t))  # strepen vooral in het begin, elke frame op een nieuwe plek
        for x, length, shade in zip(self.rng.integers(0, w, lines), self.rng.uniform(0.3, 1.0, lines), self.rng.integers(0, 4, lines)):
            color = (60, 60, 60) if shade == 0 else (235, 240, 245)
            y0 = 0 if self.rng.random() < 0.7 else h - 1
            cv2.line(out, (int(x), y0), (int(x), int(y0 + (h * length if y0 == 0 else -h * length))), color, 1)
        if self.outline is not None and t > 0.15:
            glow = np.zeros_like(frame)
            cv2.polylines(glow, self.outline, False, (255, 255, 255), 4)
            glow = cv2.GaussianBlur(glow, (11, 11), 0)
            cv2.polylines(glow, self.outline, False, (255, 255, 255), 1)
            strength = min(1.0, (t - 0.15) / 0.15) * min(1.0, (1.0 - t) / 0.4)  # infaden, vasthouden, uitfaden
            out = cv2.add(out, (glow * strength).astype(np.uint8))
        return out, True


def make_poof(rate=22050, seconds=0.5):
    """Synthetisch 'poef': gedempte ruis met snel wegstervende envelope, float32 mono."""
    n = int(rate * seconds)
    noise = np.convolve(np.random.default_rng(0).standard_normal(n), np.ones(40) / 40, "same")
    return (noise / np.abs(noise).max() * np.exp(-np.linspace(0, 7, n)) * 0.8).astype(np.float32), rate


def load_sound(path=SOUND_PATH):
    """(pcm float32 mono, samplerate) uit een wav/flac/mp3; zonder bestand de synthetische poef."""
    if not path.exists():
        return make_poof()
    import soundfile as sf
    pcm, rate = sf.read(str(path), dtype="float32", always_2d=True)
    return pcm.mean(axis=1), rate


def play(pcm, rate, device=None):
    """Speel pcm af op `device` (naam-deel, None = standaard) zonder de hoofdlus te blokkeren."""
    import sounddevice as sd

    def run():
        with sd.OutputStream(samplerate=rate, channels=1, device=device) as out:
            out.write(pcm)

    threading.Thread(target=run, daemon=True).start()


def make_hand_detector():
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    if not MODEL_PATH.exists():
        print(f"Handmodel downloaden (~8 MB) naar {MODEL_PATH} ...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    opts = vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
    )
    detector = vision.HandLandmarker.create_from_options(opts)

    def detect(frame_bgr, ts_ms):
        img = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        hands = detector.detect_for_video(img, ts_ms).hand_landmarks
        return bool(hands) and is_v_sign([(p.x, p.y) for p in hands[0]])

    return detect


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--camera", type=int, default=0)
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--duration", type=float, default=1.0, help="dissolve-duur in seconden")
    p.add_argument("--virtual", action="store_true", help="ook naar virtuele camera sturen (OBS Virtual Camera / Unity Capture)")
    p.add_argument("--no-gesture", action="store_true", help="V-teken-detectie uit (scheelt CPU)")
    p.add_argument("--sound-device", help="extra uitvoerapparaat voor het poef-geluid: nummer of deel van de naam uit --list-sound-devices")
    p.add_argument("--list-sound-devices", action="store_true")
    args = p.parse_args()
    if args.list_sound_devices:
        import sounddevice as sd
        sys.exit(str(sd.query_devices()))
    if args.sound_device:
        import sounddevice as sd
        if args.sound_device.isdigit():
            args.sound_device = int(args.sound_device)
        try:
            sd.query_devices(args.sound_device, "output")
        except ValueError as e:
            sys.exit(f"{e}. Zie --list-sound-devices.")

    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW if sys.platform == "win32" else 0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, args.fps)
    ok, frame = cap.read()
    if not ok:
        sys.exit(f"Camera {args.camera} geeft geen beeld.")
    h, w = frame.shape[:2]

    vcam = None
    if args.virtual:
        import pyvirtualcam
        vcam = pyvirtualcam.Camera(width=w, height=h, fps=args.fps, fmt=pyvirtualcam.PixelFormat.BGR)
        print(f"Virtuele camera: {vcam.device}")

    detect = None if args.no_gesture else make_hand_detector()
    trigger = HoldTrigger()

    background = None
    vanished = False
    alpha = 0.0
    poof, rate = load_sound()
    fx = None
    start = last = time.monotonic()
    print(__doc__)

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        now = time.monotonic()
        dt, last = now - last, now

        toggle = False
        if detect and background is not None:
            toggle = trigger.update(detect(frame, int((now - start) * 1000)), now)

        if background is not None:
            alpha = step_alpha(alpha, vanished, dt, args.duration)
            out = blend(frame, background, alpha) if alpha > 0 else frame
        else:
            out = frame
        if fx:
            out, alive = fx.draw(out, now)
            fx = fx if alive else None

        preview = out.copy()
        status = "B = achtergrond vastleggen" if background is None else ("VANISHED" if vanished else "V of V-teken = vanish")
        cv2.putText(preview, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow("VanishCam", preview)
        if vcam:
            vcam.send(out)
            vcam.sleep_until_next_frame()

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord("b"):
            for i in (3, 2, 1):
                print(f"Stap uit beeld... {i}")
                time.sleep(1)
            background = capture_background(cap)
            vanished, alpha = False, 0.0
            print("Achtergrond vastgelegd.")
        if (key == ord("v") or toggle) and background is not None:
            vanished = not vanished
            fx = VanishFx(person_outline(frame, background), now, 2 * args.duration) if vanished else None
            play(poof, rate)
            if args.sound_device:
                play(poof, rate, args.sound_device)

    cap.release()
    cv2.destroyAllWindows()
    if vcam:
        vcam.close()


if __name__ == "__main__":
    main()
