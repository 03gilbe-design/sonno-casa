"""EfficientAT mn10_as (MobileNet su AudioSet, mAP 0,471, ~5M parametri) -> ONNX con lo spettrogramma DENTRO,
Confronto con PANNs CNN14 (mAP 0,431, 80M parametri, 312 MB). Serve il repo clonato in REPO (non va in git).
   python efficientat_onnx.py   -> C:\\sonno_tex\\efficientat\\mn10_as.onnx + controllo torch/onnx + prova ESC-50
Ingresso: waveform float32 [1, campioni] a 32 kHz. Uscita: [1, 527] probabilita' (sigmoid), stesso ordine AudioSet.
"""
import glob, os, subprocess, sys
import numpy as np
import torch

REPO = r"~\.claude\jobs\d3ff7d4b\tmp\EfficientAT"
OUT = r"C:\sonno_tex\efficientat\mn10_as.onnx"
ESC = r"C:\sonno_audio\esc50"
sys.path.insert(0, REPO)
os.chdir(REPO)  # i pesi scaricati finiscono in REPO/resources
from models.mn.model import get_model
from models.preprocess import AugmentMelSTFT


class Tutto(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.mel = AugmentMelSTFT(n_mels=128, sr=32000, win_length=800, hopsize=320)
        self.net = get_model(width_mult=1.0, pretrained_name="mn10_as")

    def forward(self, w):
        return torch.sigmoid(self.net(self.mel(w).unsqueeze(1))[0])


def audio(p):
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-ar", "32000", "-f", "f32le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(pcm, np.float32).copy()


if __name__ == "__main__":
    m = Tutto().eval()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    x = torch.randn(1, 64000) * 0.1
    torch.onnx.export(m, x, OUT, input_names=["waveform"], output_names=["prob"], opset_version=17,
                      dynamic_axes={"waveform": {1: "campioni"}}, dynamo=False)
    import onnxruntime as ort
    s = ort.InferenceSession(OUT, providers=["CPUExecutionProvider"])
    with torch.no_grad():
        a = m.eval()(x).numpy()
    b = s.run(None, {"waveform": x.numpy()})[0]
    print(f"onnx {os.path.getsize(OUT) / 2**20:.0f} MB, differenza max torch/onnx {np.abs(a - b).max():.1e}")
    from helpers.utils import labels
    R = labels.index("Snoring")  # 43: ordine DIVERSO da PANNs (38)! col 38 leggeva un'altra classe (tutto 1,00)
    w = audio(sorted(glob.glob(os.path.join(ESC, "snoring", "*.wav")))[0])[None]
    with torch.no_grad():
        a = m(torch.tensor(w)).numpy()
    print(f"audio vero: differenza torch/onnx {np.abs(a - s.run(None, {'waveform': w})[0]).max():.1e}")
    for cat in ("snoring", "breathing"):
        v = []
        for f in sorted(glob.glob(os.path.join(ESC, cat, "*.wav"))):
            w = audio(f)
            # finestre da 5 s: sotto ~4 s il modello si SATURA (1,00 su tutte le classi, anche su silenzio/rumore;
            v.append(max(s.run(None, {"waveform": w[i:i + 160000][None]})[0][0, R]
                         for i in range(0, max(1, len(w) - 160000 + 1), 32000)))
        print(f"{cat}: sopra 0,2 {sum(x > 0.2 for x in v)}/{len(v)}  (max medio {np.mean(v):.2f})")
