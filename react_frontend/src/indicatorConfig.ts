const STACKED_INDICATORS = new Set(['RSI', 'MACD']);

export function indicatorIsStacked(name: string): boolean {
  return STACKED_INDICATORS.has(name);
}

export function indicatorPaneId(name: string): string {
  return indicatorIsStacked(name) ? `indicator_${name.toLowerCase()}` : 'candle_pane';
}

export function indicatorPaneConfig(name: string): {id: string} {
  return {id: indicatorPaneId(name)};
}
