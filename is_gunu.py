"""Resmi iş günü yardımcıları: hafta sonu ve resmi tatiller (2024-2027; arife yarım gün sayılıp iş günü kabul edilir)."""
import datetime
D=datetime.date
def rng(a,b): return {a+datetime.timedelta(days=i) for i in range((b-a).days+1)}
RESMI_TATIL = ({D(y,1,1) for y in (2024,2025,2026,2027)} | {D(y,4,23) for y in (2024,2025,2026,2027)} | {D(y,5,1) for y in (2024,2025,2026,2027)}
  | {D(y,5,19) for y in (2024,2025,2026,2027)} | {D(y,7,15) for y in (2024,2025,2026)} | {D(y,8,30) for y in (2024,2025,2026)} | {D(y,10,29) for y in (2024,2025,2026)}
  | rng(D(2024,4,10),D(2024,4,12)) | rng(D(2024,6,16),D(2024,6,19))      # 2024 Ramazan, Kurban
  | rng(D(2025,3,30),D(2025,4,1)) | rng(D(2025,6,6),D(2025,6,9))          # 2025
  | rng(D(2026,3,20),D(2026,3,22)) | rng(D(2026,5,27),D(2026,5,30))      # 2026
  | rng(D(2027,3,9),D(2027,3,11)) | rng(D(2027,5,16),D(2027,5,19)))      # 2027
def is_is_gunu(d): return d.weekday()<5 and d not in RESMI_TATIL
def onceki_is_gunu(d):
    while not is_is_gunu(d): d-=datetime.timedelta(days=1)
    return d
