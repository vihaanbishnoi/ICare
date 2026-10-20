/** Wait for a fresh camera frame; a stalled stream never reuses a frozen image. */
export function nextCameraFrame(video: HTMLVideoElement, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    let callback = 0;
    const previous = video.currentTime;
    const cleanup = () => {
      clearTimeout(timeout);
      signal.removeEventListener('abort', aborted);
      if (video.cancelVideoFrameCallback) video.cancelVideoFrameCallback(callback);
      else cancelAnimationFrame(callback);
    };
    const aborted = () => { cleanup(); reject(new DOMException('Stopped', 'AbortError')); };
    const check = () => {
      if (signal.aborted) return aborted();
      if (video.readyState >= 2 && video.videoWidth > 0 && video.currentTime !== previous) {
        cleanup(); resolve();
      } else schedule();
    };
    const schedule = () => {
      callback = video.requestVideoFrameCallback ? video.requestVideoFrameCallback(check) : requestAnimationFrame(check);
    };
    const timeout = setTimeout(() => { cleanup(); reject(new Error('The camera stopped providing frames. Reconnect it and try again.')); }, 5000);
    signal.addEventListener('abort', aborted, { once: true });
    if (signal.aborted) aborted(); else schedule();
  });
}

export async function captureCamera(video: HTMLVideoElement): Promise<Blob> {
  const canvas = document.createElement('canvas');
  const scale = Math.min(1, 640 / video.videoWidth, 480 / video.videoHeight);
  canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
  canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Camera capture is not supported by this browser.');
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) => canvas.toBlob(blob => {
    if (blob) resolve(blob); else reject(new Error('Could not capture a camera frame.'));
  }, 'image/jpeg', 0.9));
}

export function cameraError(error: unknown): string {
  if (error instanceof Error || error instanceof DOMException) {
    if (error.name === 'NotAllowedError') return 'Camera permission was denied. Allow camera access for this local site and try again.';
    if (error.name === 'NotFoundError') return 'No camera was found. Connect a webcam and try again.';
    if (error.name === 'NotReadableError') return 'The camera is disconnected or being used by another application.';
    return error.message;
  }
  return 'Camera inference could not continue.';
}
