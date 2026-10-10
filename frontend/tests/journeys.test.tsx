/** Labelled test adapter responses. These are interaction tests, not model evidence. */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, test, vi } from 'vitest';
import { ExamplePanel } from '../src/components/ExamplePanel';
import { UploadPanel } from '../src/components/UploadPanel';
import * as client from '../src/api/client';
import type { Job, Result } from '../src/types';

vi.mock('../src/api/client', () => ({ fetchExamples: vi.fn(), startExampleJob: vi.fn(),
  startUploadJob: vi.fn(), pollJob: vi.fn(), fetchResults: vi.fn(), deleteJob: vi.fn() }));

const job: Job = { job_id: 'test-job', state: 'queued', progress: null, source_kind: 'example',
  created_at_utc: '2026-10-10T00:00:00Z', model_version: 'test-adapter', result_url: null, error: null };
const result: Result = { job_id: job.job_id, duration_seconds: 6, frame_width: 640, frame_height: 480,
  model_version: 'test-adapter', analysis_mode: 'on_demand', media_url: '/api/v1/jobs/test-job/media',
  predictions: [{ timestamp_seconds: 2, fall_probability: .1 }, { timestamp_seconds: 5, fall_probability: .9 }],
  poses: [], incidents: [{ incident_id: 'test-event', job_id: job.job_id, detected_at_seconds: 5,
    confidence: .9, status: 'detected', created_at_utc: job.created_at_utc }], metrics: {},
  reports: { json: '/api/v1/jobs/test-job/reports/json', csv: '/api/v1/jobs/test-job/reports/csv' } };

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(client.fetchExamples).mockResolvedValue([{ example_id: 'test-fall', title: 'Labelled test fixture',
    expected_outcome: 'fall', video_url: '/test.mp4', duration_seconds: 6,
    analysis_mode: 'on_demand', model_version: null, provenance: 'test-only' }]);
  vi.mocked(client.startExampleJob).mockResolvedValue(job);
  vi.mocked(client.startUploadJob).mockResolvedValue({ ...job, source_kind: 'upload' });
  vi.mocked(client.pollJob).mockResolvedValue({ ...job, state: 'completed' });
  vi.mocked(client.fetchResults).mockResolvedValue(result);
  vi.mocked(client.deleteJob).mockResolvedValue(undefined);
});

describe('example journey', () => {
  test('real fields drive reports, incidents and playback seek synchronization', async () => {
    const user = userEvent.setup();
    const { container } = render(<ExamplePanel />);
    await user.click(await screen.findByRole('button', { name: /Run Analysis/ }));
    await screen.findByText('Detected at');
    expect(container.querySelector('a[href="/api/v1/jobs/test-job/reports/json"]')).not.toBeNull();
    const video = container.querySelector('video')!;
    video.currentTime = 3;
    fireEvent.seeked(video);
    const playhead = container.querySelector('.confidence-chart line[stroke="rgba(34,211,238,0.7)"]')!;
    expect(Number(playhead.getAttribute('x1'))).toBe(310);
    video.currentTime = 0;
    fireEvent.seeked(video);
    expect(Number(playhead.getAttribute('x1'))).toBe(32);
  });

  test('failed results retrieval retries the same job without creating duplicate work', async () => {
    vi.mocked(client.fetchResults).mockRejectedValueOnce(new Error('Network offline'));
    const user = userEvent.setup();
    render(<ExamplePanel />);
    await user.click(await screen.findByRole('button', { name: /Run Analysis/ }));
    await user.click(await screen.findByRole('button', { name: 'Retry Status Check' }));
    await screen.findByText('Detected at');
    expect(client.startExampleJob).toHaveBeenCalledTimes(1);
    expect(client.fetchResults).toHaveBeenCalledTimes(2);
  });

  test('permanent ownership failure is visible and does not poll forever', async () => {
    vi.mocked(client.pollJob).mockRejectedValue(Object.assign(new Error('No such job'), { status: 404 }));
    const user = userEvent.setup();
    render(<ExamplePanel />);
    await user.click(await screen.findByRole('button', { name: /Run Analysis/ }));
    expect((await screen.findByRole('alert')).textContent).toContain('No such job');
    expect(screen.queryByRole('button', { name: 'Retry Status Check' })).toBeNull();
    expect(client.pollJob).toHaveBeenCalledTimes(1);
  });

  test('transient polling stops after three attempts and offers retry', async () => {
    vi.useFakeTimers();
    vi.mocked(client.pollJob).mockRejectedValue(new Error('Offline'));
    render(<ExamplePanel />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    fireEvent.click(screen.getByRole('button', { name: /Run Analysis/ }));
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    await act(async () => { await vi.advanceTimersByTimeAsync(7000); });
    expect(client.pollJob).toHaveBeenCalledTimes(3);
    expect(screen.getByRole('button', { name: 'Retry Status Check' })).not.toBeNull();
  });

  test('unmounting while results load cannot display a stale result in a new panel', async () => {
    let resolve: (value: Result) => void = () => {};
    vi.mocked(client.fetchResults).mockReturnValueOnce(new Promise(value => { resolve = value; }));
    const user = userEvent.setup();
    const view = render(<ExamplePanel />);
    await user.click(await screen.findByRole('button', { name: /Run Analysis/ }));
    await waitFor(() => expect(client.fetchResults).toHaveBeenCalledTimes(1));
    view.unmount();
    render(<UploadPanel />);
    await act(async () => resolve(result));
    expect(screen.queryByText('Detected at')).toBeNull();
    expect(screen.getByRole('button', { name: 'Choose File' })).not.toBeNull();
  });
});

describe('upload journey', () => {
  test('permitted MP4 reaches results and can reset for another upload', async () => {
    const user = userEvent.setup();
    const { container } = render(<UploadPanel />);
    await user.upload(container.querySelector('input[type=file]')!, new File(['fixture'], 'test.mp4', { type: 'video/mp4' }));
    await screen.findByText('Detected at');
    await user.click(screen.getByRole('button', { name: /Upload Another/ }));
    expect(screen.getByRole('button', { name: 'Choose File' })).not.toBeNull();
    expect(container.querySelector('video')).toBeNull();
  });

  test('oversized input never submits a job', async () => {
    const user = userEvent.setup();
    const { container } = render(<UploadPanel />);
    const file = new File(['fixture'], 'huge.mp4', { type: 'video/mp4' });
    Object.defineProperty(file, 'size', { value: 51 * 1024 * 1024 });
    await user.upload(container.querySelector('input[type=file]')!, file);
    expect((await screen.findByRole('alert')).textContent).toContain('Maximum is 50 MB');
    expect(client.startUploadJob).not.toHaveBeenCalled();
  });

  test('queued/running work remains visible and can be cancelled', async () => {
    vi.mocked(client.pollJob).mockResolvedValue({ ...job, state: 'running', progress: .5 });
    const user = userEvent.setup();
    const { container } = render(<UploadPanel />);
    await user.upload(container.querySelector('input[type=file]')!, new File(['fixture'], 'test.mp4', { type: 'video/mp4' }));
    const cancel = await screen.findByRole('button', { name: 'Cancel Analysis' });
    vi.mocked(client.pollJob).mockResolvedValue({ ...job, state: 'cancelled' });
    await user.click(cancel);
    expect(client.deleteJob).toHaveBeenCalledWith('test-job');
    expect((await screen.findByRole('alert')).textContent).toContain('cancelled');
  });
});
