import type {AvailableAsset,Data,PairAnalysis,PositionRatioChangesResponse,ScannerResponse} from './types';
async function getJson(url:string):Promise<any>{const response=await fetch(url,{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status} · ${url}`);return response.json()}
export async function fetchState():Promise<Data>{return getJson('/api/state')}
export async function fetchChart(id:string,interval:string,before?:number):Promise<any>{return getJson('/api/chart/'+encodeURIComponent(id)+'?interval='+encodeURIComponent(interval)+(before?'&before='+encodeURIComponent(String(before)):'')+'&limit=600')}

export async function fetchAdaptiveLevels(id:string){return getJson('/api/adaptive-levels/'+encodeURIComponent(id))}

export async function fetchAnalytics(){return getJson('/api/analytics')}
export async function fetchPositionRatioChanges():Promise<PositionRatioChangesResponse>{return getJson('/api/position-ratio-changes')}
export async function fetchLevelsV3(id:string){return getJson('/api/levels/'+encodeURIComponent(id))}
export async function fetchScanner(params:{interval:string;search:string;venue:string;limit?:number}):Promise<ScannerResponse>{const query=new URLSearchParams({interval:params.interval,search:params.search,venue:params.venue,limit:String(params.limit??50)});return getJson('/api/scanner?'+query.toString())}
export async function fetchScannerAssets():Promise<{assets:AvailableAsset[];total:number;as_of_ms:number}>{return getJson('/api/scanner/assets')}
export async function analyzeScannerPair(payload:{long_instrument_id:string;short_instrument_id:string;interval:string;lookback_days:number}):Promise<PairAnalysis>{const response=await fetch('/api/scanner/analyze',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});if(!response.ok)throw new Error(`HTTP ${response.status} · /api/scanner/analyze`);return response.json()}
