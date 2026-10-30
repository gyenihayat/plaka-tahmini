"""Test yardımcıları: depo kökü, geçici kopya, il sayfası üretimi ve sayfadaki canlı JS'i Node ile çalıştırma."""
import json, os, re, shutil, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_SIM = os.path.join(ROOT, "tests", "js_sim.js")
NODE = shutil.which("node")
URETIM_DOSYALARI = ("data", "forecast.py", "is_gunu.py", "generate_il_pages.py")

def kopya(ekstra=(), il_dizini=True):
    """Üretim için gerekli dosyaların geçici kopyasını çıkarır (depoya dokunmaz). Dizin yolunu döndürür."""
    t = tempfile.mkdtemp(prefix="plaka_test_")
    for x in URETIM_DOSYALARI + tuple(ekstra):
        h = os.path.join(t, x)
        if os.path.isdir(os.path.join(ROOT, x)): shutil.copytree(os.path.join(ROOT, x), h)
        else: shutil.copy(os.path.join(ROOT, x), h)
    if il_dizini and not os.path.isdir(os.path.join(t, "il")): os.makedirs(os.path.join(t, "il"))
    return t

def uret(dizin, *args):
    """generate_il_pages.py'yi geçici dizinde çalıştırır; CompletedProcess döndürür (hata durumunda atmaz)."""
    return subprocess.run([sys.executable, "generate_il_pages.py", *args], cwd=dizin, capture_output=True, text=True)

def oku(yol):
    with open(yol, encoding="utf-8") as f: return f.read()

def js_sonuc(sayfa, tarihler, hata=False):
    """Sayfadaki satır içi JS'i, tarayıcı tarihi 'tarihler' (ISO) olarak taklit edip çalıştırır."""
    r = subprocess.run([NODE, JS_SIM, sayfa, ",".join(tarihler)] + (["hata"] if hata else []), capture_output=True, text=True, check=True)
    return json.loads(r.stdout)

def sayfa_bilgisi(sayfa):
    """Sayfadan START tarihini ve JS tatil listesini (H) okur."""
    h = oku(sayfa)
    return re.search(r'S="([^"]+)"', h)[1], json.loads(re.search(r"H=(\[[^\]]*\])", h)[1])
