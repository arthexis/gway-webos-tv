"""Repackage installed 0.2.2 with the reviewed simple pause frontend."""
import argparse, hashlib, io, json, os, pathlib, subprocess, tarfile, tempfile, zipfile
from bundle_player import arm_elf, glibc_gate, checked
BASE='44c847b964365ad6e8a6e470eb07c04ef8e80b476a934e879c94c015ed699329'
CORE='5e3d16d4502b251ad3a7de105b3edcd9fc5857807f30339f1c873f4f158de5d4'
PREFIX='usr/palm/applications/com.arthexis.aeon.rpgplayer/'
FILES={'AEON-PROVENANCE.json','appinfo.json','cores/mkxp-z_libretro.so','fixture/Game.ini','fixture/Data/Scripts.rvdata2','icon160.png','launcher','retroarch','lib/libSDL2-2.0.so.0','lib/libatomic.so.1','lib/libstdc++.so.6','licenses/RetroArch-COPYING','licenses/mkxp-z-COPYING','library/AEon-Lantern-Gate.mkxpz','aeon-menu.cfg'}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('base','frontend','frontend-sha','output'):
        p.add_argument('--'+arg,required=True)
    a=p.parse_args()
    checked(a.base,BASE)
    frontend=checked(a.frontend,a.frontend_sha); arm_elf(frontend,(2,3)); glibc_gate(a.frontend)
    out=pathlib.Path(a.output).resolve(); out.mkdir(mode=0o700,exist_ok=True)
    if any(out.iterdir()): raise ValueError('output not empty')
    with tempfile.TemporaryDirectory(prefix='aeon-menu-') as tmp:
        stage=pathlib.Path(tmp)/'app'; stage.mkdir(); seen=set()
        data=subprocess.check_output(['ar','p',a.base,'data.tar.gz'])
        with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as t:
            for m in t.getmembers():
                if not m.name.startswith(PREFIX) or m.isdir(): continue
                rel=m.name[len(PREFIX):]
                if rel not in FILES or rel in seen or not m.isfile(): raise ValueError('unexpected base file')
                seen.add(rel); dest=stage/rel; dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(t.extractfile(m).read()); dest.chmod(0o755 if rel in ('launcher','retroarch') else 0o644)
        if seen!=FILES: raise ValueError('incomplete base')
        checked(stage/'cores/mkxp-z_libretro.so',CORE)
        checked(stage/'launcher','fd5e2d725fdaf0ab2e37501b266ab094e7721116baa96d238031ccfd1a51f84d')
        (stage/'retroarch').write_bytes(frontend)
        (stage/'aeon-menu.cfg').write_bytes(pathlib.Path(__file__).with_name('aeon-menu.cfg').read_bytes())
        meta=json.loads((stage/'appinfo.json').read_text()); meta.update(version='0.2.3',requiredACG=[])
        (stage/'appinfo.json').write_text(json.dumps(meta,indent=2)+'\n')
        prov=json.loads((stage/'AEON-PROVENANCE.json').read_text()); prov.update(base_ipk_sha256=BASE,frontend_sha256=a.frontend_sha,frontend_revision="4c4953bf331348263cd68df0b654cf00583b437a",select_hold_ms=3000,pause_menu="resume-library-advanced")
        (stage/'AEON-PROVENANCE.json').write_text(json.dumps(prov,indent=2)+'\n')
        node=os.environ.get('WEBOS_NODE_BIN',str(pathlib.Path.home()/'.local/opt/webos-node24/node_modules/node/bin/node'))
        cli=pathlib.Path(os.environ.get('WEBOS_CLI_DIR',str(pathlib.Path.home()/'.local/opt/webos-tools/node_modules/@webos-tools/cli/bin')))
        subprocess.run([node,str(cli/'ares-package.js'),str(stage),'-o',str(out)],check=True,env={**os.environ,'NODE_OPTIONS':'--no-addons'})
    ipk=out/'com.arthexis.aeon.rpgplayer_0.2.3_arm.ipk'
    (out/'SHA256SUMS').write_text(hashlib.sha256(ipk.read_bytes()).hexdigest()+'  '+ipk.name+'\n')
if __name__=='__main__': main()
