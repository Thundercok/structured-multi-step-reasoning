# Du lieu tong hop, chi de do toc do va bo nho. Khong phai bang chung ve chat luong.
import json,random,sys,pathlib
out=pathlib.Path(sys.argv[1]); r=random.Random(0)
names=['An','Binh','Chi','Dung','Lan','Minh']; things=['apples','books','pens','tickets','boxes']
def row():
    n=r.choice(names); t=r.choice(things); a,b,c=r.randint(12,90),r.randint(2,9),r.randint(3,11)
    q=(f"{n} buys {a} {t} every week for {b} weeks. Then {n} gives away {c} {t} to each of {b+1} friends and later sells "
       f"half of what is left at the market on a rainy Saturday morning. How many {t} does {n} still have at the end?")
    s=(f"Let me work step by step. First, {n} buys {a} * {b} = {a*b} {t} in total over the {b} weeks.\n"
       f"Next, {n} gives away {c} * {b+1} = {c*(b+1)} {t} to the friends, so {a*b} - {c*(b+1)} = {a*b-c*(b+1)} {t} remain.\n"
       f"Then {n} sells half of those, leaving ({a*b-c*(b+1)}) / 2 = {(a*b-c*(b+1))/2} {t}.\n"
       f"Therefore the final answer is {(a*b-c*(b+1))/2}.\n#### {(a*b-c*(b+1))/2}")
    return {"messages":[{"role":"user","content":q},{"role":"assistant","content":s}]}
for name,k in (('train',200),('valid',8),('test',8)):
    (out/f'{name}.jsonl').write_text('\n'.join(json.dumps(row()) for _ in range(k))+'\n')
