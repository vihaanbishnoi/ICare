from __future__ import annotations

import os
from pathlib import Path
from threading import Lock

import cv2
import gradio as gr
from fastrtc import VideoStreamHandler, WebRTC

from icare_app.inference import FallDetectionSession, UnconfiguredBackend
from icare_app.onnx_backend import PoseC3DONNXBackend
from icare_app.pose import PosePreviewBackend
from icare_app.reports import event_rows, write_report


onnx_model_path = Path(
    os.getenv("ICARE_POSEC3D_MODEL", "models/posec3d_fall.onnx")
)
if onnx_model_path.exists():
    backend = PoseC3DONNXBackend(
        model_path=onnx_model_path,
        device=os.getenv("ICARE_POSE_DEVICE", "cpu"),
        inference_width=int(os.getenv("ICARE_INFERENCE_WIDTH", "416")),
    )
elif os.getenv("ICARE_ENABLE_RTMPOSE", "0") == "1":
    backend = PosePreviewBackend(
        device=os.getenv("ICARE_POSE_DEVICE", "cpu"),
        inference_width=int(os.getenv("ICARE_INFERENCE_WIDTH", "416")),
    )
else:
    backend = UnconfiguredBackend()
webcam_session = FallDetectionSession(backend)
upload_lock = Lock()


def result_card(snapshot: dict) -> str:
    probability = snapshot["current_fall_probability"]
    probability_text = "—" if probability is None else f"{probability:.1%}"
    state = snapshot["state"]
    colors = {
        "Fall detected": "#ef4444",
        "Checking possible fall": "#f59e0b",
        "No fall detected": "#16a34a",
        "Preparing": "#2563eb",
        "Model not connected": "#64748b",
    }
    color = colors.get(state, "#64748b")
    return (
        f'<div style="background:{color};color:white;padding:14px 18px;'
        f'border-radius:10px;font-size:24px;font-weight:800">{state.upper()}</div>'
        f'<div style="font-size:17px;margin-top:12px">'
        f'<b>Fall confidence:</b> {probability_text} &nbsp;&nbsp; '
        f'<b>Incidents:</b> {len(snapshot["events"])}</div>'
    )


def session_outputs(session: FallDetectionSession, report_name: str):
    snapshot = session.snapshot()
    json_path, csv_path = write_report(snapshot, report_name)
    return result_card(snapshot), event_rows(snapshot), json_path, csv_path


def process_webcam_frame(frame):
    return frame if frame is None else webcam_session.process(frame)


def reset_webcam():
    webcam_session.reset("webcam")
    return session_outputs(webcam_session, "webcam_report")


def preview_report():
    webcam_session.inject_demo_event()
    return session_outputs(webcam_session, "webcam_preview_report")


def refresh_webcam():
    return session_outputs(webcam_session, "webcam_report")


def analyze_video(video_path: str | None):
    if not video_path:
        raise gr.Error("Choose a video first.")

    with upload_lock:
        session = FallDetectionSession(backend)
        session.reset(Path(video_path).name)
        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            raise gr.Error("This video could not be opened.")

        fps = capture.get(cv2.CAP_PROP_FPS)
        fps = fps if fps and fps > 0 else 30.0
        frame_number = 0
        while True:
            ok, frame_bgr = capture.read()
            if not ok:
                break
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            session.process(frame_rgb, timestamp_seconds=frame_number / fps)
            frame_number += 1
        capture.release()

        if not backend.available:
            gr.Warning("Model weights have not been connected yet.")
        return session_outputs(session, f"video_{Path(video_path).stem}")


EVENT_HEADERS = ["Event", "Start", "End", "Duration", "Confidence"]
EVENT_TYPES = ["number", "str", "str", "str", "str"]


with gr.Blocks(title="ICare") as demo:
    gr.Markdown(
        """
        # ICare
        Fall detection for live camera and recorded video.
        """
    )

    with gr.Tabs():
        with gr.Tab("Live camera"):
            with gr.Row():
                with gr.Column(scale=3):
                    webcam = WebRTC(
                        label="Camera",
                        width=640,
                        height=360,
                        track_constraints={
                            "facingMode": "user",
                            "width": {"ideal": 640},
                            "height": {"ideal": 360},
                            "frameRate": {"ideal": 12, "max": 12},
                        },
                    )
                    reset_button = gr.Button("Reset")
                with gr.Column(scale=2):
                    live_result = gr.Markdown(result_card(webcam_session.snapshot()))
                    live_events = gr.Dataframe(
                        headers=EVENT_HEADERS,
                        datatype=EVENT_TYPES,
                        interactive=False,
                        label="Detected falls",
                    )
                    with gr.Row():
                        live_json = gr.File(label="JSON report")
                        live_csv = gr.File(label="CSV report")
                    with gr.Accordion("Developer preview", open=False):
                        gr.Markdown(
                            "Adds a clearly marked simulated incident while model integration is pending."
                        )
                        preview_button = gr.Button("Preview report")

            webcam.stream(
                fn=VideoStreamHandler(
                    callable=process_webcam_frame,
                    fps=12,
                    skip_frames=True,
                ),
                inputs=[webcam],
                outputs=[webcam],
                time_limit=180,
            )
            timer = gr.Timer(1.0)
            timer.tick(
                fn=refresh_webcam,
                outputs=[live_result, live_events, live_json, live_csv],
                show_progress="hidden",
            )
            reset_button.click(
                fn=reset_webcam,
                outputs=[live_result, live_events, live_json, live_csv],
            )
            preview_button.click(
                fn=preview_report,
                outputs=[live_result, live_events, live_json, live_csv],
            )

        with gr.Tab("Upload video"):
            with gr.Row():
                upload = gr.Video(label="Video", sources=["upload"])
                with gr.Column():
                    analyze_button = gr.Button("Analyze", variant="primary")
                    upload_result = gr.Markdown("## Ready\n\nChoose a video to begin.")
                    upload_events = gr.Dataframe(
                        headers=EVENT_HEADERS,
                        datatype=EVENT_TYPES,
                        interactive=False,
                        label="Detected falls",
                    )
                    with gr.Row():
                        upload_json = gr.File(label="JSON report")
                        upload_csv = gr.File(label="CSV report")

            analyze_button.click(
                fn=analyze_video,
                inputs=[upload],
                outputs=[upload_result, upload_events, upload_json, upload_csv],
            )

    gr.Markdown(
        "<small>Research prototype — not a medical device or emergency service.</small>"
    )


if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)
