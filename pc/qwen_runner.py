"""Esperimento completo: tutti i modelli, test e video vengono eseguiti su Kaggle GPU."""
import csv
import gc
import glob
import hashlib
import json
import math
import os
import pathlib
import shutil
import subprocess
import sys
import traceback

os.environ['TOKENIZERS_PARALLELISM']='false'
os.environ['HF_HUB_DISABLE_XET']='1'
if not os.environ.get('NO_PIP'):subprocess.run([sys.executable,'-m','pip','install','-q','transformers==4.51.3','accelerate','bitsandbytes','panns-inference','torchlibrosa'],check=True)
import numpy as np
import torch
assert torch.cuda.is_available(), 'STOP: GPU richiesta; nessun fallback CPU'
torch.set_num_threads(2)
HERE=pathlib.Path('/kaggle/working')
TMP=pathlib.Path('/tmp/wav');TMP.mkdir(exist_ok=True)
INPUT=pathlib.Path(glob.glob('/kaggle/input/**/manifest.json',recursive=True)[0]).parent
for name in ['core.py','video.py']:
    shutil.copy(glob.glob('/kaggle/input/**/sonno-contesto-code/'+name,recursive=True)[0],HERE/name)
# Font: DejaVu e' dentro matplotlib su Kaggle (nessun font di sistema).
_v=(HERE/'video.py').read_text(encoding='utf-8').replace("'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'","__import__('matplotlib').get_data_path()+'/fonts/ttf/DejaVuSans.ttf'")
(HERE/'video.py').write_text(_v,encoding='utf-8')
sys.path.insert(0,str(HERE))
from core import CLASSES, target, bounds, evaluate, selftest


def dump(name,obj):
    (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def pcm(p,sr=32000,start=0,duration=None):
    cmd=['ffmpeg','-v','error','-ss',str(start),'-i',str(p)]
    if duration is not None:cmd+=['-t',str(duration)]
    cmd+=['-ac','1','-ar',str(sr),'-f','f32le','-']
    r=subprocess.run(cmd,capture_output=True,check=True,timeout=45)
    return np.frombuffer(r.stdout,np.float32).copy()


def duration(p):
    r=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(p)],capture_output=True,check=True,timeout=15)
    return float(json.loads(r.stdout)['format']['duration'])


def save_wav(p,a,sr=32000):
    import soundfile as sf
    sf.write(str(p),a,sr,subtype='PCM_16')


def build_records(manifest):
    raws=[]
    for r in manifest['raw_files']:
        r['duration']=duration(INPUT/r['file']);raws.append(r)
    dump('audio_durations.json',raws)
    records=[];coverage=[]
    for w in manifest['windows']:
        n=int(w['end']-w['start']);a=np.zeros(n*32000,np.float32);valid=np.zeros(n*32000,bool)
        for r in raws:
            lo,hi=max(w['start'],r['start']),min(w['end'],r['start']+r['duration'])
            if hi<=lo:continue
            x=pcm(INPUT/r['file'],start=lo-r['start'],duration=hi-lo)
            at=round((lo-w['start'])*32000);x=x[:len(a)-at]
            a[at:at+len(x)]=x;valid[at:at+len(x)]=True
        # Gaps riportati: frame con <95% audio non possono addestrare/valutare.
        ok=valid.reshape(n,32000).mean(1)>=.95
        bags=[]
        for ann in manifest['annotations']:
            if ann['device']!=w['device'] or ann['start']<w['start'] or ann['end']>w['end']:continue
            lo,hi=bounds(ann['start']-w['start'],ann['end']-w['start'],n)
            if hi<=lo or not ok[lo:hi].all():continue
            cats=set(ann['cats'])
            for q in manifest['annotations']:
                if q['device']==ann['device'] and q['start']<ann['end'] and q['end']>ann['start']:
                    cats.update(q['cats'])
            bags.append(dict(id=ann['id'],a=lo,b=hi,target=target(cats).tolist(),raw=ann['raw'],weight=ann['weight']))
        path=TMP/(w['id']+'.wav');save_wav(path,a)
        records.append(dict(id=w['id'],night=w['night'],source='miniapp',role=w['role'],start=w['start'],audio=str(path),bags=bags,valid=ok.tolist(),n=n))
        coverage.append(dict(id=w['id'],coverage=float(valid.mean()),bags=len(bags),gaps_seconds=int((~ok).sum())))
    for c in manifest['bot_clips']:
        a=pcm(INPUT/c['file']);n=math.ceil(len(a)/32000)
        path=TMP/(c['id']+'.wav');save_wav(path,np.pad(a,(0,n*32000-len(a))))
        records.append(dict(id=c['id'],night=c['night'],source='bot',role='clip_debole',audio=str(path),start=c['start'],n=n,valid=[True]*n,bags=[dict(id=c['id'],a=0,b=n,target=target(c['cats']).tolist(),raw=c['raw'],weight=c['weight'])]))
    return records,raws,coverage


def main():
    manifest=json.loads((INPUT/'manifest.json').read_text())
    dump('tests.json',selftest())
    dump('runtime.json',dict(gpu=torch.cuda.get_device_name(0),torch=torch.__version__,manifest_sha256=hashlib.sha256((INPUT/'manifest.json').read_bytes()).hexdigest()))
    records,raws,coverage=build_records(manifest)
    dump('coverage.json',coverage)
    print('AUDIO',len(records),'sequences',sum(r['n'] for r in records),'seconds',flush=True)
    extract(records)
    serial=[{k:v for k,v in r.items() if k!='features'} for r in records]
    dump('records.json',serial)
    np.savez_compressed(HERE/'features.npz',**{r['id']:r['features'] for r in records})
    report,outputs=evaluate(records)
    dump('evaluation.json',report)
    np.savez_compressed(HERE/'predictions.npz',**{r+'__'+m:a for r,models in outputs.items() for m,a in models.items()})
    from video import render_all
    render_all(records,outputs,HERE,mode='sequenza')
    try:
        qwen(records,outputs)
        render_all(records,outputs,HERE,mode='qwen')
    except Exception:
        dump('qwen_error.json',dict(error=traceback.format_exc()))
        print('QWEN_ERROR',traceback.format_exc(),flush=True)
    dump('completion.json',dict(sequence=True,qwen=(HERE/'qwen.json').exists(),videos=[p.name for p in HERE.glob('*.mp4')]))


def extract(records):
    from panns_inference import AudioTagging
    from transformers import ClapModel,ClapProcessor
    labels_path='/tmp/class_labels_indices.csv'
    subprocess.run(['curl','--fail','-L','-s','--retry','3','-o',labels_path,'http://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/class_labels_indices.csv'],check=True,timeout=120)
    labels=[r[2] for r in list(csv.reader(open(labels_path)))[1:]]
    os.makedirs(os.path.expanduser('~/panns_data'),exist_ok=True)
    shutil.copy(labels_path,os.path.expanduser('~/panns_data/class_labels_indices.csv'))
    checkpoint='/tmp/cnn14.pth'
    subprocess.run(['curl','--fail','-L','-s','--retry','2','-o',checkpoint,'https://zenodo.org/record/3987831/files/Cnn14_mAP%3D0.431.pth?download=1'],check=True,timeout=300)
    # Checkpoint ufficiale fidato, compatibilita torch>=2.6.
    original=torch.load
    torch.load=lambda *a,**kw:original(*a,**{**kw,'weights_only':False})
    at=AudioTagging(checkpoint_path=checkpoint,device='cuda')
    torch.load=original
    names=['Breathing','Gasp','Pant','Snort','Sniff','Sigh','Snoring','Rustle','Silence','Speech','Music','Cough','Throat clearing','Tick','Clicking']
    names=[n for n in names if n in labels];ix=[labels.index(n) for n in names]
    for r in records:
        a=pcm(r['audio']);rows=[]
        for i in range(0,r['n'],32):
            x=np.stack([np.pad(a[j*32000:(j+1)*32000],(0,max(0,32000-len(a[j*32000:(j+1)*32000])))) for j in range(i,min(i+32,r['n']))])
            rows.append(at.inference(x)[0][:,ix])
        r['features']=np.concatenate(rows)
    del at;gc.collect();torch.cuda.empty_cache()
    model=ClapModel.from_pretrained('laion/larger_clap_general').cuda().eval()
    processor=ClapProcessor.from_pretrained('laion/larger_clap_general')
    prompts=['a person breathing while sleeping','a person breathing','quiet breathing','a person snoring','snoring','a person moving in bed','rustling bedsheets','silence','room noise','a person talking','a cough','music playing']
    norm=lambda x:torch.nn.functional.normalize(x if torch.is_tensor(x) else x.pooler_output,dim=-1)
    with torch.no_grad():
        te=norm(model.get_text_features(**processor(text=prompts,return_tensors='pt',padding=True).to('cuda')))
        for r in records:
            a=pcm(r['audio'],48000);a=np.pad(a,(48000,48000));rows=[]
            for i in range(0,r['n'],16):
                aud=[a[j*48000:j*48000+96000] for j in range(i,min(i+16,r['n']))]
                ae=norm(model.get_audio_features(**processor(audios=aud,sampling_rate=48000,return_tensors='pt').to('cuda')))
                rows.append(torch.softmax(100*email@example.com,1).cpu().numpy())
            clap=np.concatenate(rows)
            r['features']=np.concatenate([r['features'],clap],1).astype(np.float32)
            r['l1_raw']=np.stack([clap[:,:3].sum(1),clap[:,3:5].sum(1),clap[:,5:7].sum(1),clap[:,7:9].sum(1),clap[:,9:].sum(1)],1).tolist()
            print('FEATURES',r['id'],r['n'],flush=True)
    dump('feature_config.json',dict(panns=names,clap_prompts=prompts,panns_window_seconds=1,clap_window_seconds=2,hop_seconds=1,checkpoint_clap='laion/larger_clap_general',level1='PANNs+CLAP -> testa MIL senza tempo; ablation confrontabile con GRU'))
    del model,processor;gc.collect();torch.cuda.empty_cache()


def qwen(records,outputs):
    from transformers import AutoProcessor,Qwen2AudioForConditionalGeneration,BitsAndBytesConfig
    # 18 finestre da 30 secondi con cambi nelle etichette, non nei punteggi.
    candidates=[]
    for r in records:
        if r['source']!='miniapp':continue
        bags=sorted(r['bags'],key=lambda b:b['a'])
        for x,y in zip(bags,bags[1:]):
            if x['target']==y['target'] or y['a']-x['b']>30:continue
            a=max(0,min(r['n']-30,(x['b']+y['a'])//2-15))
            if not all(r['valid'][a:a+30]):continue
            cats={CLASSES[j] for b in bags if b['a']<a+30 and b['b']>a for j,v in enumerate(b['target']) if v}
            candidates.append(dict(id=r['id'],a=a,b=a+30,truth=sorted(cats),diversity=len(cats)))
    selected=[]
    for c in sorted(candidates,key=lambda c:(-c['diversity'],c['id'],c['a'])):
        if any(c['id']==q['id'] and abs(c['a']-q['a'])<20 for q in selected):continue
        selected.append(c)
        if len(selected)==18:break
    dump('qwen_selection.json',selected)
    model_id='Qwen/Qwen2-Audio-7B-Instruct'
    processor=AutoProcessor.from_pretrained(model_id)
    model=Qwen2AudioForConditionalGeneration.from_pretrained(model_id,device_map='auto',torch_dtype=torch.float16,quantization_config=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_compute_dtype=torch.float16,bnb_4bit_quant_type='nf4'),attn_implementation='eager').eval()
    sr=processor.feature_extractor.sampling_rate
    questions=dict(
        description='You are listening to a nighttime recording of a person in bed near the microphone. Possible sounds: very quiet breathing, breathing while moving, labored or strained breathing, snoring beginning, snoring, bed or blanket rustling, movement in bed, phone or TikTok video playing, silence. Describe chronologically what you hear: sound type, timing in seconds (start-end), and your confidence level (high/medium/low) for each sound event. Do not diagnose; describe only audible evidence.',
        respiro='Can you hear a person breathing in this audio? Answer only yes or no.',
        russa='Can you hear snoring in this audio? Answer only yes or no.',
        movimento='Can you hear body movement or bedsheet rustling in this audio? Answer only yes or no.',
        silenzio='Is there a stretch of near-silence with no breathing and no movement in this audio? Answer only yes or no.',
        faticoso='Does the breathing sound strained, labored or abnormal? Answer only yes, no or unclear.')
    def ask(audio,text):
        conv=[dict(role='user',content=[dict(type='audio',audio_url='local.wav'),dict(type='text',text=text)])]
        t=processor.apply_chat_template(conv,add_generation_prompt=True,tokenize=False)
        inputs=processor(text=t,audios=[audio],sampling_rate=sr,return_tensors='pt',padding=True).to('cuda')
        with torch.no_grad():out=model.generate(**inputs,max_new_tokens=120,do_sample=False)
        return processor.batch_decode(out[:,inputs.input_ids.shape[1]:],skip_special_tokens=True)[0].strip()
    prompt=questions
    results=[]
    for c in selected:
        r=next(r for r in records if r['id']==c['id'])
        audio=pcm(r['audio'],sr,c['a'],c['b']-c['a'])
        ans={k:ask(audio,q) for k,q in questions.items()}
        yes=lambda k:ans[k].lower().startswith('yes')
        predicted=sorted(k for k in ('respiro','russa','movimento','silenzio') if yes(k))
        truth4=sorted(set(c['truth'])-{'altro'})
        parsed=dict(description=ans['description'],noisy_or_strained=ans['faticoso'],answers=ans)
        results.append({**c,'response':ans['description'],'parsed':parsed,'predicted':predicted,'truth4':truth4,'exact_set_agreement':predicted==truth4})
        dump('qwen.json',dict(model=model_id,quantization='nf4',prompt=prompt,items=results,limitation='Confronto di presenza su intervalli deboli (classe altro esclusa); fatica/anomalie senza riferimento valido. Nessuna diagnosi.'))
        print('QWEN',len(results),len(selected),predicted,truth4,ans['faticoso'],flush=True)
    del model,processor;gc.collect();torch.cuda.empty_cache()


if __name__=='__main__':
    try:main()
    except Exception:
        dump('error.json',dict(error=traceback.format_exc()))
        raise
