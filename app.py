from __future__ import annotations

from pathlib import Path
from threading import Lock

import cv2
import gradio as gr
from fastrtc import WebRTC

from icare_app.inference import FallDetectionSession, UnconfiguredBackend
from icare_app.reports import event_rows, write_report


backend = UnconfiguredBackend()
webcam_session = FallDetectionSession(backend)
upload_lock = Lock()


def format_summary(snapshot: dict) -> str:
    probability = snapshot["latest_fall_probability"]
    probability_text = "Unavailable" if probability is None else f"{probability:.1%}"
    return f"""
### {snapshot['state']}

- **Backend:** {snapshot['backend']}
- **Source:** {snapshot['source']}
- **Frames received:** {snapshot['frames_seen']}
- **Current activity:** {snapshot['latest_activity']}
- **Current fall probability:** {probability_text}
- **Maximum fall probability:** {snapshot['max_fall_probability']:.1%}
- **Confirmation:** {snapshot['confirmation_progress']}
- **Incident count:** {len(snapshot['events'])}
"""


def snapshot_outputs(session: FallDetectionSession, stem_prefix: str):
    snapshot = session.snapshot()
    json_path, csv_path = write_report(snapshot, stem_prefix)
    return format_summary(snapshot), event_rows(snapshot), snapshot, json_path, csv_path


def process_webcam_frame(frame):
    if frame is None:
        return frame
    return webcam_session.process(frame)


def reset_webcam():
    webcam_session.reset("webcam")
    return snapshot_outputs(webcam_session, "webcam")


def inject_demo_webcam_event():
    webcam_session.inject_demo_event()
    return snapshot_outputs(webcam_session, "webcam_demo")


def refresh_webcam_report():
    return snapshot_outputs(webcam_session, "webcam")


def analyze_uploaded_video(video_path: str | None):
    if not video_path:
        raise gr.Error("Upload a video before selecting Analyze.")

    with upload_lock:
        session = FallDetectionSession(backend)
        session.reset(f"upload:{Path(video_path).name}")
        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            raise gr.Error("The uploaded video could not be opened.")

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

        outputs = snapshot_outputs(session, f"upload_{Path(video_path).stem}")
        if not backend.available:
            gr.Warning("Video was read successfully, but model inference is disabled until trained weights are connected.")
        return outputs


CSS = """
.app-shell {max-width: 1180px; margin: 0 auto;}
.model-warning {border-left: 5px solid #f59e0b; padding: 12px 16px; background: #fffbeb;}
"""


with gr.Blocks(title="ICare Fall Detection", css=CSS) as demo:
    gr.Markdown(
        """
        # ICare Fall Detection
        Real-time webcam monitoring and recorded-video incident analysis.

        <div class="model-warning"><strong>Development build:</strong> the interface is operational, but RTMPose and PoseC3D are not connected yet. It will never fabricate a prediction. Use the labelled demo-event button only to test reporting.</div>
        """
    )

    with gr.Tabs():
        with gr.Tab("Live webcam"):
            gr.Markdown("Grant browser camera permission, then start the stream. Do not physically perform a fall for testing.")
            with gr.Row():
                with gr.Column(scale=3):
                    webcam = WebRTC(label="Live camera")
                    with gr.Row():
                        reset_button = gr.Button("Reset monitoring")
                        demo_event_button = gr.Button("Inject demo fall event", variant="secondary")
                with gr.Column(scale=2):
                    live_summary = gr.Markdown(format_summary(webcam_session.snapshot()))
                    live_events = gr.Dataframe(
                        headers=["Event", "Time (s)", "Confidence", "Activity", "Source"],
                        datatype=["number", "number", "number", "str", "str"],
                        interactive=False,
                        label="Incident timeline",
                    )
                    live_json = gr.JSON(label="Current report")
                    with gr.Row():
                        live_json_file = gr.File(label="Download JSON")
                        live_csv_file = gr.File(label="Download CSV")

            webcam.stream(fn=process_webcam_frame, inputs=[webcam], outputs=[webcam], time_limit=180)
            timer = gr.Timer(1.0)
            timer.tick(
                fn=refresh_webcam_report,
                outputs=[live_summary, live_events, live_json, live_json_file, live_csv_file],
                show_progress="hidden",
            )
            reset_button.click(
                fn=reset_webcam,
                outputs=[live_summary, live_events, live_json, live_json_file, live_csv_file],
            )
            demo_event_button.click(
                fn=inject_demo_webcam_event,
                outputs=[live_summary, live_events, live_json, live_json_file, live_csv_file],
            )

        with gr.Tab("Upload video"):
            gr.Markdown("Upload an MP4 or other OpenCV-readable video. The final model will produce timestamped incidents here.")
            with gr.Row():
                upload_video = gr.Video(label="Video to analyze", sources=["upload"])
                with gr.Column():
                    analyze_button = gr.Button("Analyze video", variant="primary")
                    upload_summary = gr.Markdown("No video analyzed yet.")
            upload_events = gr.Dataframe(
                headers=["Event", "Time (s)", "Confidence", "Activity", "Source"],
                datatype=["number", "number", "number", "str", "str"],
                interactive=False,
                label="Incident timeline",
            )
            upload_json = gr.JSON(label="Analysis report")
            with gr.Row():
                upload_json_file = gr.File(label="Download JSON")
                upload_csv_file = gr.File(label="Download CSV")
            analyze_button.click(
                fn=analyze_uploaded_video,
                inputs=[upload_video],
                outputs=[upload_summary, upload_events, upload_json, upload_json_file, upload_csv_file],
            )

    gr.Markdown(
        """
        **Research prototype only.** This application is not a medical device or emergency service. A production elder-care system requires broader validation, privacy controls, monitoring, and a reliable alert-delivery path.
        """
    )


if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860)
