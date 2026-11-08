import statistics as st,bisect
med=st.median
def clean(o):
    out=[(o[0][0],float(o[0][1]))]
    for i in range(1,len(o)):
        dt=o[i][0]-o[i-1][0]
        if dt<=0: continue
        rr=(o[i][1]-o[i-1][1])/dt
        loc=med([(o[j][1]-o[j-1][1])/(o[j][0]-o[j-1][0]) for j in range(max(1,i-10),min(len(o),i+11)) if o[j][0]>o[j-1][0]])
        if rr>6*max(loc,0.5) and rr*dt>5000: rr=loc
        out.append((o[i][0],out[-1][1]+max(rr,0)*dt))
    return out
def at(c,day):
    xs=[x[0] for x in c]
    if day<=xs[0]: return c[0][1]
    if day>=xs[-1]: return c[-1][1]
    i=bisect.bisect_left(xs,day)
    if xs[i]==day: return c[i][1]
    (x0,y0),(x1,y1)=c[i-1],c[i]
    return y0+(y1-y0)*(day-x0)/(x1-x0)
def slope(o,upto,win=365):
    while True:
        w=[x for x in o if upto-win<x[0]<=upto]
        if len(w)>=10 or win>=8000: break
        win*=2
    r=[(w[i][1]-w[i-1][1])/(w[i][0]-w[i-1][0]) for i in range(1,len(w)) if w[i][0]>w[i-1][0]]
    return max(med(r),0.01) if r else 0.01
def seasonal(c,T,h):
    # gecen yilin ayni takvim araligindaki ilerleme; h>365 ise tam yillar tekrarlanir
    Y=at(c,T)-at(c,T-365); k=int(h//365); rem=h-365*k
    return k*Y+at(c,T-365+rem)-at(c,T-365)
# Eğilim düzeltmesi (Kasım 2026; assets/tahmin-motoru.js egilimKatsayisi/advAt ile aynı formül ve işlem sırası, ham tahmin bit-bit aynı):
# r = son 56 gündeki gözlem aralığı hızlarının medyanı / geçen yılın aynı 56 günündeki medyan; katsayı = 1 + 0.75*(r-1), [0.6, 1.4] ile sınırlı.
# Önümüzdeki 56 günlük temel ilerleme bu katsayıyla düzeltilir, sonrasında yıllık hıza dönülür (düzeltme miktarı sabit kalır).
# Katsayı 1: geçen yılın penceresi ilk gözlemden önceyse, pencerelerden birinde 3'ten az aralık varsa ya da geçen yılın medyanı > 0 değilse.
EGILIM_PENCERE,EGILIM_AGIRLIK,EGILIM_UFUK,EGILIM_MIN,EGILIM_MAKS,EGILIM_EN_AZ_ARALIK=56,0.75,56,0.6,1.4,3
def _egilim_hizlari(o,a,b):
    return [(o[i][1]-o[i-1][1])/(o[i][0]-o[i-1][0]) for i in range(1,len(o)) if a<o[i][0]<=b and o[i][0]>o[i-1][0]]
def egilim_orani(o,T):
    """(r, katsayı): r = son 56 günün medyan hızı / geçen yılın aynı 56 gününün medyan hızı (hesaplanamıyorsa None); katsayı ileri tahmine uygulanan çarpan."""
    o=[x for x in o if x[0]<=T]
    if T-365-EGILIM_PENCERE<o[0][0]: return None,1
    simdi,gecen=_egilim_hizlari(o,T-EGILIM_PENCERE,T),_egilim_hizlari(o,T-365-EGILIM_PENCERE,T-365)
    if len(simdi)<EGILIM_EN_AZ_ARALIK or len(gecen)<EGILIM_EN_AZ_ARALIK: return None,1
    g=med(gecen)
    if not g>0: return None,1
    r=max(0,med(simdi))/g
    return r,min(EGILIM_MAKS,max(EGILIM_MIN,1+EGILIM_AGIRLIK*(r-1)))
def advance(o,c,T,h,sl=None):
    sl=sl or slope(o,T)
    temel=lambda x:0.5*sl*x+0.5*seasonal(c,T,x)
    a=temel(h)
    return a+(egilim_orani(o,T)[1]-1)*(a if h<=EGILIM_UFUK else temel(EGILIM_UFUK))
def bterr(o,h=60,span=280):
    c=clean(o); last=o[-1][0]; errs=[]
    for k in range(0,span//7):
        T=last-h-7*k
        oo=[x for x in o if x[0]<=T]; cc=[x for x in c if x[0]<=T]
        if len(cc)<10 or cc[0][0]>T-365-30: continue
        act=at(c,T+h)-at(c,T)
        if act<=0: continue
        errs.append(abs(advance(oo,cc,T,h)-act)/act*h)
    return round(med(errs),1) if len(errs)>=8 else None
