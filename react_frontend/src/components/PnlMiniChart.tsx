import type {PnlPoint} from '../pnlModel';

export function PnlMiniChart({points,positive,label}:{points:PnlPoint[];positive:boolean;label:string}){
 const clean=points.filter(point=>Number.isFinite(point.pnl));
 if(clean.length<2)return <span className="pnl-mini-empty" aria-label={label}/>;
 const min=Math.min(...clean.map(point=>point.pnl)),max=Math.max(...clean.map(point=>point.pnl)),span=max-min||1;
 const coords=clean.map((point,index)=>`${(index/(clean.length-1))*100},${27-((point.pnl-min)/span)*22}`).join(' ');
 return <svg className={'pnl-mini '+(positive?'positive':'negative')} viewBox="0 0 100 32" role="img" aria-label={label} preserveAspectRatio="none"><polyline points={coords} fill="none" vectorEffect="non-scaling-stroke"/><circle cx="100" cy={27-((clean.at(-1)!.pnl-min)/span)*22} r="2.2"/></svg>;
}
