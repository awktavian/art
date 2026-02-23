import { GEM_TYPES } from './config.js';
let ctx=null, muted=false;
function ac(){if(!ctx)ctx=new(window.AudioContext||window.webkitAudioContext)();if(ctx.state==='suspended')ctx.resume();return ctx;}
function t(){return ac().currentTime;}
function osc(freq,type,gain,start,dur){const c=ac(),o=c.createOscillator(),g=c.createGain();o.type=type;o.frequency.value=freq;g.gain.setValueAtTime(gain,start);g.gain.exponentialRampToValueAtTime(0.001,start+dur);o.connect(g).connect(c.destination);o.start(start);o.stop(start+dur+0.05);}
function oscSweep(f1,f2,type,gain,start,dur){const c=ac(),o=c.createOscillator(),g=c.createGain();o.type=type;o.frequency.setValueAtTime(f1,start);o.frequency.exponentialRampToValueAtTime(f2,start+dur);g.gain.setValueAtTime(gain,start);g.gain.exponentialRampToValueAtTime(0.001,start+dur);o.connect(g).connect(c.destination);o.start(start);o.stop(start+dur+0.05);}
function noise(dur,gain,start){const c=ac(),buf=c.createBuffer(1,c.sampleRate*dur,c.sampleRate),d=buf.getChannelData(0);for(let i=0;i<d.length;i++)d[i]=(Math.random()*2-1)*Math.exp(-i/(d.length*0.1));const s=c.createBufferSource(),g=c.createGain();s.buffer=buf;g.gain.setValueAtTime(gain,start);g.gain.exponentialRampToValueAtTime(0.001,start+dur);s.connect(g).connect(c.destination);s.start(start);}
export function setMuted(m){muted=m;}
export function isMuted(){return muted;}
export function resume(){if(ctx)ctx.resume();}
export function playForge(typeId){if(muted)return;const s=t(),f=GEM_TYPES[typeId].freq;osc(f,'sine',0.12,s,0.3);osc(f*2,'sine',0.04,s,0.2);osc(f*3,'triangle',0.02,s+0.05,0.15);}
export function playCombine(grade){if(muted)return;const s=t(),b=440+grade*60;osc(b,'sine',0.1,s,0.4);osc(b*1.5,'sine',0.06,s+0.05,0.35);noise(0.08,0.04,s);}
export function playFire(typeId,grade){if(muted)return;const s=t(),f=GEM_TYPES[typeId].freq*(0.5+grade*0.1);oscSweep(f,f*0.3,'sine',0.06,s,0.08);}
export function playHit(force=0.5){if(muted)return;noise(0.03+force*0.03,0.04+force*0.08,t());}
export function playKill(typeId){if(muted)return;const s=t(),f=GEM_TYPES[typeId].freq;noise(0.06,0.08,s);osc(f*1.5,'sine',0.08,s+0.02,0.2);osc(f*2,'sine',0.04,s+0.06,0.15);}
export function playWaveStart(){if(muted)return;const s=t();osc(220,'sawtooth',0.06,s,0.3);osc(330,'sawtooth',0.04,s+0.1,0.25);osc(440,'triangle',0.05,s+0.2,0.3);}
export function playWaveClear(){if(muted)return;const s=t();[523,659,784,1047].forEach((f,i)=>osc(f,'sine',0.07,s+i*0.08,0.25));}
export function playVictory(){if(muted)return;const s=t();[523,659,784,1047,1318].forEach((f,i)=>{osc(f,'sine',0.08,s+i*0.12,0.4);osc(f*0.5,'triangle',0.03,s+i*0.12,0.3);});}
export function playDefeat(){if(muted)return;const s=t();[440,349,293,220].forEach((f,i)=>osc(f,'sawtooth',0.06,s+i*0.2,0.5));}
export function playLeak(){if(muted)return;const s=t();osc(200,'square',0.08,s,0.15);osc(150,'square',0.06,s+0.1,0.15);}
export function playPlace(){if(muted)return;const s=t();osc(880,'sine',0.05,s,0.1);noise(0.03,0.03,s);}
export function playMana(){if(muted)return;osc(1200,'sine',0.03,t(),0.08);}
