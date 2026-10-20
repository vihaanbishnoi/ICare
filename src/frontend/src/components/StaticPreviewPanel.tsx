export function StaticPreviewPanel() {
  return <div className="demo-grid">
    <div className="video-section">
      <div className="mode-notice">Static research preview · No inference runs on this website</div>
      <div className="video-placeholder blank-demo">
        <span className="blank-demo__icon" aria-hidden="true">▷</span>
        <p>No video provided.</p>
        <span>Run ICare locally to analyze your own MP4 or camera frames.</span>
      </div>
    </div>
    <div className="results-placeholder">
      <div className="results-placeholder__content">
        <p>No inference results available.</p>
        <p className="results-placeholder__sub">Confidence charts and incidents appear after local analysis.</p>
      </div>
    </div>
  </div>;
}
