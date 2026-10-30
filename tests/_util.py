"""Test yardımcıları: depo kökü, geçici kopya, il sayfası üretimi ve sayfadaki canlı JS'i Node ile çalıştırma."""
import json, os, re, shutil, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_SIM = os.path.join(ROOT, "tests", "js_sim.js")
NODE = shutil.which("node")
URETIM_DOSYALARI = ("data", "forecast.py", "is_gunu.py", "generate_il_pages.py", "index.html")      # üretici ana sayfanın işaretli bölgelerini de yazar

def kopya(ekstra=(), il_dizini=True):
    """Üretim için gerekli dosyaların geçici kopyasını çıkarır (depoya dokunmaz). Dizin yolunu döndürür."""
    t = tempfile.mkdtemp(prefix="plaka_test_")
    for x in dict.fromkeys(URETIM_DOSYALARI + tuple(ekstra)):
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

def sayfa_bilgisi(sayfa):
    """Sayfadan tahmin başlangıç tarihini (üretim günü, data-baslangic) okur."""
    return re.search(r'data-baslangic="([^"]+)"', oku(sayfa))[1]

def canli_sonuc(sayfa, anlar_ms, tz=None):
    """Sayfadaki canlı güncellemeyi (güncellik denetimi + il-arac.js guncelTahmin) verilen UTC anlarında (ms) çalıştırır; TZ ortam değişkeniyle tarayıcı saat dilimi taklit edilir."""
    env = dict(os.environ)
    if tz: env["TZ"] = tz
    r = subprocess.run([NODE, os.path.join(ROOT, "tests", "ui", "il_canli_cikti.js"), sayfa, ",".join(str(a) for a in anlar_ms)], capture_output=True, text=True, check=True, env=env)
    return json.loads(r.stdout)
