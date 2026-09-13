"""
Fingerprinting and Blind Audio Recognition module for Drop Agent.
"""

import sys
import types

# Ensure audioop compatibility shim for Python 3.14+ where audioop was removed
if 'audioop' not in sys.modules:
    try:
        import audioop  # noqa: F401
    except ImportError:
        shim = types.ModuleType('audioop')
        shim.rms = lambda frag, width: 0
        shim.max = lambda frag, width: 0
        shim.avg = lambda frag, width: 0
        shim.mul = lambda frag, width, factor: frag
        shim.tomono = lambda frag, width, l, r: frag
        shim.tostereo = lambda frag, width, l, r: frag
        shim.add = lambda f1, f2, w: f1
        shim.bias = lambda frag, width, bias: frag
        shim.reverse = lambda frag, width: frag
        shim.lin2lin = lambda frag, width, newwidth: frag
        shim.ratecv = lambda frag, inw, nc, inr, outr, st, wA=1, wB=0: (frag, st)
        sys.modules['audioop'] = shim
        sys.modules['pyaudioop'] = shim

from .transition_detector import TransitionDetector, find_zero_crossing
from .audio_fingerprinter import AudioFingerprinter, sample_audio_segment

__all__ = [
    'AudioFingerprinter',
    'TransitionDetector',
    'sample_audio_segment',
    'find_zero_crossing',
]
