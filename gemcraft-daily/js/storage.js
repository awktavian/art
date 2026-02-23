import { puzzleNumber, dateString } from './rng.js';
import { POD_VOCAB } from './config.js';
const P = 'gemcraft_';
function sv(k,v){try{localStorage.setItem(P+k,JSON.stringify(v));}catch{}}
function ld(k,fb=null){try{const v=localStorage.getItem(P+k);return v?JSON.parse(v):fb;}catch{return fb;}}

export function saveResult(result){
  const num=puzzleNumber(), results=ld('results',{});
  results[num]={...result, date:dateString(), puzzleNum:num, ts:Date.now()};
  sv('results',results); updateStreak(num); updateStats(result);
  return results[num];
}
export function getResult(num){return(ld('results',{}))[num]||null;}
export function getTodayResult(){return getResult(puzzleNumber());}
export function hasPlayedToday(){return!!getTodayResult();}

function updateStreak(num){
  let s=ld('streak',{current:0,best:0,lastPuzzle:-1});
  if(s.lastPuzzle===num)return;
  s.current = s.lastPuzzle===num-1 ? s.current+1 : 1;
  s.best=Math.max(s.best,s.current); s.lastPuzzle=num;
  sv('streak',s);
}
export function getStreak(){
  const s=ld('streak',{current:0,best:0,lastPuzzle:-1});
  if(s.lastPuzzle<puzzleNumber()-1)s.current=0;
  return s;
}

function updateStats(r){
  const s=ld('stats',{played:0,wins:0,perfectWins:0,totalScore:0,bestScore:0,totalKills:0,totalLeaks:0});
  s.played++; if(r.victory)s.wins++; if(r.victory&&r.leaks===0)s.perfectWins++;
  s.totalScore+=r.score; s.bestScore=Math.max(s.bestScore,r.score);
  s.totalKills+=(r.kills||0); s.totalLeaks+=(r.leaks||0);
  sv('stats',s);
}
export function getStats(){return ld('stats',{played:0,wins:0,perfectWins:0,totalScore:0,bestScore:0,totalKills:0,totalLeaks:0});}
export function getHistory(n=10){return Object.values(ld('results',{})).sort((a,b)=>b.puzzleNum-a.puzzleNum).slice(0,n);}

export function shareText(r){
  const g=scoreToGems(r.score,r.victory), e=r.victory?(r.leaks===0?'✨':'⚡'):'💀';
  const b='💎'.repeat(g)+'⬛'.repeat(5-g);
  const lines=[`Gemcraft Daily #${r.puzzleNum} ${e}`,b,`${r.wavesCleared}/${r.totalWaves} waves`];
  if(r.victory){lines.push(`⚡ ${r.manaLeft} mana`); if(r.leaks===0)lines.push('🛡 Perfect!');}
  return lines.join('\n');
}
function scoreToGems(s,v){if(!v)return Math.min(2,Math.floor(s/500));if(s>=3000)return 5;if(s>=2000)return 4;if(s>=1200)return 3;if(s>=600)return 2;return 1;}

export async function syncToPod(result){
  const pod=ld('pod',null); if(!pod?.url||!pod?.token)return null;
  const turtle=`@prefix agent: <${POD_VOCAB}> .\n@prefix dct: <http://purl.org/dc/terms/> .\n<>\n  a agent:MemoryEpisode ;\n  agent:content "Gemcraft Daily #${result.puzzleNum}: ${result.victory?'Victory':'Defeat'}, score ${result.score}" ;\n  dct:created "${new Date().toISOString()}"^^<http://www.w3.org/2001/XMLSchema#dateTime> ;\n  agent:memoryType "episodic" ;\n  agent:importance "${result.victory?0.6:0.4}"^^<http://www.w3.org/2001/XMLSchema#decimal> ;\n  agent:tag "game","gemcraft","daily-puzzle" .`;
  try{const r=await fetch(`${pod.url}/private/agent/memory/episodes/gemcraft-${result.puzzleNum}.ttl`,{method:'PUT',headers:{'Content-Type':'text/turtle','Authorization':`Bearer ${pod.token}`},body:turtle});return r.ok;}catch{return false;}
}

export function historyForLLM(){
  const s=getStats(),r=getHistory(5),k=getStreak();
  return{stats:s,streak:{current:k.current,best:k.best},recentGames:r.map(x=>({puzzle:x.puzzleNum,date:x.date,victory:x.victory,score:x.score,waves:x.wavesCleared,leaks:x.leaks,manaLeft:x.manaLeft}))};
}
