import math, pathlib, struct, wave, zlib, zipfile, re, hashlib
root=pathlib.Path('game')
(root/'Data').mkdir(parents=True,exist_ok=True)
(root/'Audio/BGM').mkdir(parents=True,exist_ok=True)
(root/'Audio/SE').mkdir(parents=True,exist_ok=True)
src=pathlib.Path('adventure.rb').read_bytes()
rows=re.findall(rb'"([#.<>]+)"',src)
assert len(rows)==22 and all(len(r)==17 for r in rows)
# Ruby Marshal v4.8, array of [script ID, name, zlib payload].
def num(n):
 if n==0: return b'\0'
 if n<=122: return bytes([n+5])
 b=n.to_bytes((n.bit_length()+7)//8,'little')
 return bytes([len(b)])+b
def string(b): return b'"'+num(len(b))+b
payload=b'\x04\x08['+num(1)+b'['+num(3)+b'i'+num(1)+string(b'Lantern Gate')+string(zlib.compress(src,9))
(root/'Data/Scripts.rvdata2').write_bytes(payload)
(root/'Game.ini').write_text('[Game]\nLibrary=System\\RGSS301.dll\nScripts=Data\\Scripts.rvdata2\nTitle=AEon - The Lantern Gate\nRTP=\n')
rate=22050
def wav(path,length,fn):
 with wave.open(str(path),'wb') as w:
  w.setparams((1,2,rate,0,'NONE','not compressed'))
  w.writeframes(b''.join(struct.pack('<h',max(-32768,min(32767,int(fn(i/rate))))) for i in range(int(rate*length))))
notes=[60,64,67,72,69,67,64,62,59,62,65,69,67,65,62,55]
bass=[48,45,43,43]
def hz(n): return 440*2**((n-69)/12)
def music(t):
 beat=int(t*2)%16; local=t%0.5
 env=min(1,local/0.02,(0.5-local)/0.12)
 f=hz(notes[beat]); g=hz(bass[beat//4])
 return 5200*env*(math.sin(2*math.pi*f*t)+0.24*math.sin(4*math.pi*f*t))+2400*math.sin(2*math.pi*g*t)*min(1,(t%2)/0.06,(2-t%2)/0.08)
wav(root/'Audio/BGM/Lantern.wav',8,music)
wav(root/'Audio/SE/Chime.wav',0.35,lambda t: 9000*(1-t/.35)*math.sin(2*math.pi*880*t))
with zipfile.ZipFile('AEon-Lantern-Gate.mkxpz','w',zipfile.ZIP_STORED) as z:
 for f in sorted(root.rglob('*')):
  if f.is_file(): z.write(f,f.relative_to(root))
with zipfile.ZipFile('AEon-Lantern-Gate.mkxpz') as z: assert z.testzip() is None
print('Game archive:',hashlib.sha256(pathlib.Path('AEon-Lantern-Gate.mkxpz').read_bytes()).hexdigest())
