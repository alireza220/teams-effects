import numpy as np

from vanishcam import blend, step_alpha


def test_blend_endpoints():
    live = np.full((2, 2, 3), 200, np.uint8)
    bg = np.full((2, 2, 3), 50, np.uint8)
    assert (blend(live, bg, 0.0) == live).all()
    assert (blend(live, bg, 1.0) == bg).all()
    assert (blend(live, bg, 0.5) == 125).all()


def test_step_alpha_moves_toward_target_and_clamps():
    assert step_alpha(0.0, True, 0.5, 1.0) == 0.5
    assert step_alpha(0.9, True, 0.5, 1.0) == 1.0
    assert step_alpha(1.0, False, 0.25, 1.0) == 0.75
    assert step_alpha(0.1, False, 0.5, 1.0) == 0.0


def _hand(index_up=True, middle_up=True, ring_up=False, pinky_up=False):
    # 21 punten; tip boven (y kleiner dan) PIP = gestrekt
    lm = [(0.5, 0.5)] * 21
    for tip, pip, up in ((8, 6, index_up), (12, 10, middle_up), (16, 14, ring_up), (20, 18, pinky_up)):
        lm[tip] = (0.5, 0.3 if up else 0.7)
    return lm


def test_is_v_sign():
    from vanishcam import is_v_sign
    assert is_v_sign(_hand())
    assert not is_v_sign(_hand(ring_up=True, pinky_up=True))   # open hand
    assert not is_v_sign(_hand(middle_up=False))               # alleen wijsvinger
    assert not is_v_sign(_hand(False, False))                  # vuist


def test_hold_trigger_fires_once_after_hold_then_cooldown():
    from vanishcam import HoldTrigger
    t = HoldTrigger(hold=0.5, cooldown=2.0)
    assert not t.update(True, 0.0)
    assert not t.update(True, 0.4)
    assert t.update(True, 0.5)
    assert not t.update(True, 1.0)      # cooldown
    assert not t.update(False, 1.5)     # losgelaten
    assert not t.update(True, 2.0)      # opnieuw vasthouden begint
    assert t.update(True, 2.6)


def test_make_poof_is_half_second_mono_in_range():
    from vanishcam import make_poof
    pcm, rate = make_poof()
    assert pcm.shape == (rate // 2,) and pcm.dtype == np.float32
    assert np.abs(pcm).max() <= 0.8 and np.abs(pcm[-100:]).max() < 0.01  # sterft uit


def test_load_sound_reads_poof_wav_as_mono_float32():
    from vanishcam import load_sound
    pcm, rate = load_sound()
    assert pcm.ndim == 1 and pcm.dtype == np.float32 and rate == 44100 and len(pcm) > rate


def test_person_outline_finds_blob_or_none():
    from vanishcam import person_outline
    import cv2
    bg = np.full((240, 320, 3), 100, np.uint8)
    assert person_outline(bg.copy(), bg) is None
    frame = bg.copy()
    frame[60:240, 120:200] = 220  # "persoon"
    (blob,) = person_outline(frame, bg)
    x, y, w, h = cv2.boundingRect(blob)
    assert abs(x - 120) < 15 and abs(w - 80) < 30 and abs(y - 60) < 15
    bottom = blob[blob[:, 1] >= 230]
    assert not ((bottom[:, 0] > 140) & (bottom[:, 0] < 180)).any()  # geen lijn langs de onderrand, alleen de zijkanten


def test_vanish_fx_draws_then_ends():
    from vanishcam import VanishFx
    frame = np.full((90, 160, 3), 100, np.uint8)
    outline = np.array([[[40, 20]], [[120, 20]], [[120, 80]], [[40, 80]]], np.int32)
    fx = VanishFx([outline], started=0.0, duration=2.0)
    out, alive = fx.draw(frame, 0.8)
    assert alive and (out != frame).any() and (frame == 100).all()
    out, alive = fx.draw(frame, 2.0)
    assert not alive and (out == frame).all()
