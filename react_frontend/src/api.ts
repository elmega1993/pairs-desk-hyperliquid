import type {Data} from './types';
async function getJson(url:string):Promise<any>{const response=await fetch(url,{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status} · ${url}`);return response.json()}
export async function fetchState():Promise<Data>{return getJson('/api/state')}
export async function fetchChart(id:string,interval:string,before?:number):Promise<any>{return getJson('/api/chart/'+encodeURIComponent(id)+'?interval='+encodeURIComponent(interval)+(before?'&before='+encodeURIComponent(String(before)):'')+'&limit=600')}

export async function fetchAdaptiveLevels(id:string){return getJson('/api/adaptive-levels/'+encodeURIComponent(id))}

export async function fetchAnalytics(){return getJson('/api/analytics')}
export async function fetchLevelsV3(id:string){return getJson('/api/levels/'+encodeURIComponent(id))}
