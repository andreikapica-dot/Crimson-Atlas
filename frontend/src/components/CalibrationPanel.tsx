interface CalibrationPanelProps {
  visible: boolean;
  gameX: number;
  gameZ: number;
  points: Array<{ gameX: number; gameZ: number; mapX: number; mapY: number; label?: string }>;
  meanError: number;
  maxError: number;
  onAddPoint: (mapX: number, mapY: number) => void;
  onRemovePoint: (index: number) => void;
  onReset: () => void;
  onExport: () => void;
  onImport: () => void;
}

export default function CalibrationPanel({
  visible, gameX, gameZ, points, meanError, maxError,
  onAddPoint, onRemovePoint, onReset, onExport, onImport
}: CalibrationPanelProps) {
  if (!visible) return null;
  return (
    <div className="calibration-panel">
      <div className="calibration-section">
        <div className="calibration-title">Current Position</div>
        <div>X: {gameX.toFixed(2)}</div>
        <div>Z: {gameZ.toFixed(2)}</div>
      </div>
      <div className="calibration-section">
        <div className="calibration-title">Points: {points.length}</div>
        {points.map((p, i) => (
          <div key={i} className="calibration-point">
            <span>{p.label || `Point ${i + 1}`}</span>
            <span>G({p.gameX.toFixed(1)}, {p.gameZ.toFixed(1)})</span>
            <span>M({p.mapX.toFixed(1)}, {p.mapY.toFixed(1)})</span>
            <button onClick={() => onRemovePoint(i)}>X</button>
          </div>
        ))}
      </div>
      <div className="calibration-section">
        <div>Mean error: {meanError.toFixed(2)}</div>
        <div>Max error: {maxError.toFixed(2)}</div>
      </div>
      <div className="calibration-actions">
        <button onClick={() => onAddPoint(0, 0)}>Add Point (click map)</button>
        <button onClick={onReset}>Reset</button>
        <button onClick={onExport}>Export</button>
        <button onClick={onImport}>Import</button>
      </div>
    </div>
  );
}
