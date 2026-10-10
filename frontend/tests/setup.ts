import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers(); });
vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} });
vi.stubGlobal('requestAnimationFrame', () => 1);
vi.stubGlobal('cancelAnimationFrame', () => {});
Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
  value: () => ({ clearRect() {}, fillText() {}, setLineDash() {}, strokeRect() {},
    beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, arc() {}, fill() {} }),
});
