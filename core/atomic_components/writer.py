"""Video writing utilities."""

import imageio
import os
from typing import Optional


class VideoWriterByImageIO:
    """Wrapper around :mod:`imageio` video writer used by the pipeline.

    The original implementation exposed a callable interface.  To support
    segmented writing we provide an explicit ``start_segment``/``write_frame``
    API while keeping the default behaviour of producing a single file.
    """

    def __init__(self, video_path: str, fps: int = 25, **kwargs) -> None:
        self.video_path = video_path
        self.fps = fps
        self.kwargs = kwargs
        self.writer: Optional[imageio.core.format.Writer] = None

    # ------------------------------------------------------------------
    def _open_writer(self) -> None:
        """Internal helper to instantiate the ``imageio`` writer."""
        video_format = self.kwargs.get("format", "mp4")
        codec = self.kwargs.get("vcodec", "libx264")
        quality = self.kwargs.get("quality")
        pixelformat = self.kwargs.get("pixelformat", "yuv420p")
        macro_block_size = self.kwargs.get("macro_block_size", 2)
        ffmpeg_params = ["-crf", str(self.kwargs.get("crf", 18))]

        os.makedirs(os.path.dirname(self.video_path), exist_ok=True)
        self.writer = imageio.get_writer(
            self.video_path,
            fps=self.fps,
            format=video_format,
            codec=codec,
            quality=quality,
            ffmpeg_params=ffmpeg_params,
            pixelformat=pixelformat,
            macro_block_size=macro_block_size,
        )

    # ------------------------------------------------------------------
    def start_segment(self) -> None:
        """Start writing a new segment to ``self.video_path``."""
        if self.writer is not None:
            raise RuntimeError("segment already started")
        self._open_writer()

    def write_frame(self, img, fmt: str = "bgr") -> None:
        """Append a frame to the current segment."""
        if self.writer is None:
            raise RuntimeError("call start_segment() before write_frame()")
        frame = img[..., ::-1] if fmt == "bgr" else img
        self.writer.append_data(frame)

    def close_segment(self):
        """Finalize the current segment."""
        if self.writer is None:
            return None
        self.writer.close()
        self.writer = None
        return self.video_path

    # Backwards compatibility -------------------------------------------------
    def __call__(self, img, fmt: str = "bgr"):
        self.write_frame(img, fmt=fmt)

    def close(self):
        return self.close_segment()


class SegmentedVideoWriter:
    """Create sequential ``segment_XXXXX.mp4`` files or in-memory buffers."""

    def __init__(self, base_path: str, fps: int = 25, in_memory: bool = False, **kwargs) -> None:
        self.base_path = base_path
        self.fps = fps
        self.kwargs = kwargs
        self.in_memory = in_memory
        self.counter = 0
        self.writer: Optional[imageio.core.format.Writer] = None
        self.current_output = None  # path or bytes

    def _next_path(self) -> str:
        os.makedirs(self.base_path, exist_ok=True)
        name = f"segment_{self.counter:05d}.mp4"
        self.counter += 1
        return os.path.join(self.base_path, name)

    def start_segment(self) -> None:
        if self.writer is not None:
            raise RuntimeError("segment already started")
        if self.in_memory:
            self.writer = imageio.get_writer(
                imageio.RETURN_BYTES,
                fps=self.fps,
                format=self.kwargs.get("format", "mp4"),
                codec=self.kwargs.get("vcodec", "libx264"),
                pixelformat=self.kwargs.get("pixelformat", "yuv420p"),
                macro_block_size=self.kwargs.get("macro_block_size", 2),
                ffmpeg_params=["-crf", str(self.kwargs.get("crf", 18))],
            )
            self.current_output = None
        else:
            path = self._next_path()
            self.writer = imageio.get_writer(
                path,
                fps=self.fps,
                format=self.kwargs.get("format", "mp4"),
                codec=self.kwargs.get("vcodec", "libx264"),
                pixelformat=self.kwargs.get("pixelformat", "yuv420p"),
                macro_block_size=self.kwargs.get("macro_block_size", 2),
                ffmpeg_params=["-crf", str(self.kwargs.get("crf", 18))],
            )
            self.current_output = path

    def write_frame(self, img, fmt: str = "bgr") -> None:
        if self.writer is None:
            raise RuntimeError("call start_segment() before write_frame()")
        frame = img[..., ::-1] if fmt == "bgr" else img
        self.writer.append_data(frame)

    def close_segment(self):
        if self.writer is None:
            return None
        if self.in_memory:
            data = self.writer.close()
            self.writer = None
            return data
        else:
            self.writer.close()
            path = self.current_output
            self.writer = None
            self.current_output = None
            return path

    def close(self):
        return self.close_segment()

