"""PANNs CNN14 (pre-addestrato su AudioSet, mAP 0,431 contro ~0,31 di YAMNet) -> ONNX, per farlo girare sull'A21s
Sul PC serve solo per la conversione (una volta), poi il .pth si cancella.
   python panns_onnx.py      -> C:\\sonno_tex\\panns\\cnn14.onnx + controllo: stessi numeri di torch
Ingresso: waveform float32 a 32 kHz, forma [n, campioni] (finestre da 2 s = 64000). Uscita: [n, 527] probabilita'.
"""
import os
import numpy as np
import torch
from panns_inference.models import Cnn14

PTH = os.path.expanduser("~/panns_data/Cnn14.pth")
OUT = r"C:\sonno_tex\panns\cnn14.onnx"


class Solo(torch.nn.Module):
    def __init__(self, m):
        super().__init__()
        self.m = m

    def forward(self, w):
        return self.m(w)["clipwise_output"]


if __name__ == "__main__":
    m = Cnn14(sample_rate=32000, window_size=1024, hop_size=320, mel_bins=64, fmin=50, fmax=14000, classes_num=527)
    m.load_state_dict(torch.load(PTH, map_location="cpu", weights_only=True)["model"])
    m.eval()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    x = torch.randn(2, 64000) * 0.1
    s_m = Solo(m).eval()
    torch.onnx.export(s_m, x, OUT, input_names=["waveform"], output_names=["prob"], opset_version=13,
                      dynamic_axes={"waveform": {0: "n", 1: "campioni"}, "prob": {0: "n"}}, dynamo=False)
    import onnxruntime as ort
    s = ort.InferenceSession(OUT, providers=["CPUExecutionProvider"])
    a = s_m.eval()(x).detach().numpy()  # export rimette il modo di prima: senza eval() confronta col dropout acceso
    b = s.run(None, {"waveform": x.numpy()})[0]
    assert np.abs(a - b).max() < 1e-3, np.abs(a - b).max()
    print("ok", OUT, f"{os.path.getsize(OUT) / 2**20:.0f} MB, differenza max {np.abs(a - b).max():.1e}")
