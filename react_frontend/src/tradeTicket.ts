export function remainingTicketSeconds(expiresInS:number, receivedAtMs:number, nowMs:number):number{
  if(!Number.isFinite(expiresInS)||expiresInS<=0)return 0;
  return Math.max(0,Math.ceil(expiresInS-(nowMs-receivedAtMs)/1000));
}

export function isTicketExpired(expiresInS:number, receivedAtMs:number, nowMs:number):boolean{
  return remainingTicketSeconds(expiresInS,receivedAtMs,nowMs)<=0;
}
