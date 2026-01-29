export function buildSignalMarkers(signalPoints = []) {
  return signalPoints.map((point) => ({
    time: point.time,
    position: 'aboveBar',
    color: point.color || '#4a7c89',
    shape: 'circle',
    text: point.text || '',
  }))
}
