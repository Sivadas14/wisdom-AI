print("[TRACE] parallel_video.py import start")
import asyncio
import tempfile
import os
import random
import subprocess
import io
import json
import textwrap
from typing import Tuple
from PIL import Image
import pickle
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from supabase import Client
from tuneapi import tu

from src.settings import get_settings

from src.db import (
    ContentGeneration,
    Conversation,
    RamanaImage,
)
from src.content.image import _generate_image, CONTEMPLATION_PROMPTS
from src.content.audio import (
    collect_source_content_optimized,
    generate_meditation_transcript_optimized,
    generate_audio_from_transcript_optimized,
)
from src.utils.profiler import profile_operation, print_profiler_summary
from src.settings import get_supabase_client, get_supabase_admin_client, get_llm
from src.db import get_db_session, get_background_session
import hashlib

# Cache for image generation with persistent storage
_image_cache = {}
_cache_file = Path("image_cache.pkl")

def _load_image_cache():
    """Load image cache from disk"""
    global _image_cache
    try:
        if _cache_file.exists():
            with open(_cache_file, 'rb') as f:
                _image_cache = pickle.load(f)
                tu.logger.info(f"Loaded {len(_image_cache)} cached images from disk")
    except Exception as e:
        tu.logger.error(f"Failed to load image cache: {e}")
        _image_cache = {}

def _save_image_cache():
    """Save image cache to disk"""
    try:
        with open(_cache_file, 'wb') as f:
            pickle.dump(_image_cache, f)
    except Exception as e:
        tu.logger.error(f"Failed to save image cache: {e}")

# Load cache on module import
_load_image_cache()

# Pre-generate these common meditation images for faster video generation
COMMON_MEDITATION_PROMPTS = [
    "Peaceful zen garden with flowing water and soft sunlight"
    # "Serene mountain lake at sunset with gentle ripples",
    # "Tranquil forest clearing with dappled morning light",
    # "Misty mountains with flowing clouds at dawn",
    # "Peaceful bamboo grove with soft filtered light",
    # "Quiet temple garden with stone lanterns and cherry blossoms",
    # "Serene pond with lotus flowers and reflections",
    # "Calm desert dunes under a twilight sky",
    # "Peaceful meadow with wildflowers and gentle breeze",
    # "Soft morning light filtering through bamboo leaves"
]

def _get_image_cache_key(prompt: str) -> str:
    """Generate cache key for image prompt"""
    return hashlib.sha256(prompt.encode()).hexdigest()[:16] # Use string for better pickle compatibility

async def pre_generate_common_images():
    """Pre-generate common meditation images for faster video generation"""
    tu.logger.info("Pre-generating common meditation images...")
    generated_count = 0

    for prompt in COMMON_MEDITATION_PROMPTS:
        cache_key = _get_image_cache_key(prompt)
        if cache_key not in _image_cache:
            try:
                tu.logger.info(f"Pre-generating image for: {prompt[:50]}...")
                image = await _generate_image(prompt)
                _image_cache[cache_key] = image
                generated_count += 1
                tu.logger.info(f"Cached image for prompt: {prompt[:50]}")

                # Save cache after each image to prevent loss
                _save_image_cache()

            except Exception as e:
                tu.logger.error(f"Failed to pre-generate image for {prompt[:50]}: {e}")

    tu.logger.info(f"Pre-generation complete. Generated {generated_count} new images. Total cached: {len(_image_cache)}")

async def generate_and_cache_image(prompt: str):
    """Generate image and cache it for future use"""
    cache_key = _get_image_cache_key(prompt)

    if cache_key in _image_cache:
        tu.logger.info(f"Using cached image for: {prompt[:50]}")
        return _image_cache[cache_key]

    tu.logger.info(f"Generating new image for: {prompt[:50]}")
    image = await _generate_image(prompt)
    _image_cache[cache_key] = image

    # Save cache after generating new image
    _save_image_cache()

    return image

class ParallelVideoGenerator:
    def __init__(self):
        self.spb_client = get_supabase_client(get_settings())

    async def generate_video_parallel(
        self,
        session: AsyncSession,
        conversation_id: str,
        message_id: str,
        content_id: str,
        length: str = None  # Add length parameter
    ) -> Tuple[str, str]:
        """Generate video content with TRUE parallelization using streaming audio"""

        request_id = f"video_{content_id}_{int(tu.SimplerTimes.get_now_fp64())}"

        # Step 1: Load conversation first (sequential to avoid session conflicts)
        async with profile_operation("conversation_load", request_id) as op:
            conversation = await self._load_conversation(session, conversation_id)
            op.finish()

        # Step 2: Generate source content (sequential)
        async with profile_operation("source_content_generation") as op:
            source_content = await self._generate_source_content(session, conversation_id)
            op.finish(source_length=len(source_content))

        # Step 3: Fetch library images + generate transcript in parallel
        async with profile_operation("parallel_transcript_and_images") as op:
            transcript_task = self.generate_transcript(source_content, length)
            library_images_task = self._get_multiple_library_images(session)

            transcript, library_images = await asyncio.gather(transcript_task, library_images_task)
            op.finish(transcript_length=len(transcript), library_image_count=len(library_images))

        # Step 4: Create video
        async with profile_operation("video_creation") as op:
            if len(library_images) >= 1:
                # LIGHT pipeline: single library image, no zoompan, no xfade.
                # Designed to encode in <60s on 0.5 CPU Render Starter.
                audio_bytes = await self._generate_audio_optimized(transcript)
                quote = self._extract_quote_from_transcript(transcript)
                video_path = await self._create_light_single_image_video(
                    library_images[0], audio_bytes, quote
                )
            else:
                # Fallback: original single DALL-E image pipeline
                image_prompt = await self._generate_image_prompt_cached()
                pil_image = await self._generate_image_cached(image_prompt)
                video_path = await self._create_video_streaming_parallel(pil_image, transcript)
            op.finish(video_path=video_path)

        # Step 5: Upload video
        async with profile_operation("video_upload") as op:
            content_path = await self._upload_video_optimized(video_path, content_id)
            op.finish(upload_path=content_path)

        print_profiler_summary()
        return content_path, transcript

    async def _get_multiple_library_images(
        self, session: AsyncSession, target_count: int = 1
    ) -> list:
        """Fetch multiple random active images from the Ramana library.

        Returns a list of PIL Images.  If fewer than target_count active images
        exist, the available ones are looped so the slideshow always has
        at least target_count clips (minimum 1).  Returns [] if library empty.
        """
        try:
            spb = get_supabase_admin_client(get_settings())

            query = (
                select(RamanaImage)
                .where(RamanaImage.active == True)
                .order_by(func.random())
                .limit(target_count)
            )
            result = await session.execute(query)
            records = result.scalars().all()

            if not records:
                tu.logger.info("Ramana image library is empty — will use DALL-E fallback")
                return []

            images = []
            for rec in records:
                try:
                    image_bytes = spb.storage.from_("generations").download(rec.storage_path)
                    pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                    images.append(pil_image)
                    tu.logger.info(f"Loaded library image: {rec.filename}")
                except Exception as e:
                    tu.logger.warning(f"Could not load library image {rec.filename}: {e}")

            if not images:
                return []

            # Loop images if fewer than target_count so we always have enough clips
            while len(images) < target_count:
                images.extend(images[: target_count - len(images)])

            tu.logger.info(f"Using {len(images)} library images for Ken Burns slideshow")
            return images

        except Exception as e:
            tu.logger.error(f"_get_multiple_library_images failed: {e}")
            return []

    def _resize_cover(self, img: Image.Image, width: int, height: int) -> Image.Image:
        """Resize img to exactly width×height using cover strategy (crop, no black bars)."""
        img_ratio = img.width / img.height
        target_ratio = width / height
        if img_ratio > target_ratio:
            # Wider than target → scale by height, crop width
            new_h = height
            new_w = int(img.width * height / img.height)
        else:
            # Taller than target → scale by width, crop height
            new_w = width
            new_h = int(img.height * width / img.width)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - width) // 2
        top = (new_h - height) // 2
        return img.crop((left, top, left + width, top + height))

    def _find_drawtext_font(self) -> str:
        """Return path to a suitable TrueType font for FFmpeg drawtext, or empty string."""
        # Prefer the DM Serif Text font bundled alongside image.py
        content_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__))
        )
        candidates = [
            os.path.join(content_dir, "DM_Serif_Text", "DMSerifText-Regular.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return ""

    def _extract_quote_from_transcript(self, transcript: str, max_chars: int = 180) -> str:
        """Extract a short opening line from the meditation transcript for the quote overlay."""
        lines = [l.strip() for l in transcript.strip().split("\n") if l.strip()]
        if not lines:
            return "Rest in the stillness\nof pure awareness."

        text = " ".join(lines[:3])
        # Try to find end of first sentence
        for punct in [". ", "! ", "? "]:
            idx = text.find(punct)
            if 20 < idx < max_chars:
                sentence = text[: idx + 1].strip()
                # Wrap at ~40 chars per line for comfortable reading at 42px font
                return textwrap.fill(sentence, width=40)

        # No sentence boundary — just take a clean truncation
        if len(text) <= max_chars:
            return textwrap.fill(text, width=40)
        return textwrap.fill(text[:max_chars].rstrip() + "…", width=40)

    async def _create_ken_burns_video_with_quote(
        self,
        images: list,
        audio_bytes: bytes,
        quote: str,
    ) -> str:
        """Ken Burns slideshow: crossfade transitions + Ramana quote text overlay.

        Produces 1280×720 HD at 24 fps.
        Each image has a slow zoom / pan (Ken Burns effect) via the zoompan filter.
        Images are crossfaded using FFmpeg's xfade filter.
        The quote is rendered as a drawtext overlay that fades in (0–1 s) and
        fades out (1 s before QUOTE_SHOW_DUR).
        """
        FADE_DUR = 1.0       # xfade crossfade duration (seconds)
        FPS = 24
        WIDTH, HEIGHT = 1280, 720
        QUOTE_SHOW_DUR = 15  # seconds the quote is visible

        n = len(images)
        temp_files = []

        try:
            # ── 1. Save audio ──────────────────────────────────────────────────
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as af:
                af.write(audio_bytes)
                audio_path = af.name
            temp_files.append(audio_path)

            # ── 2. Get audio duration via ffprobe ──────────────────────────────
            probe_cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                audio_path,
            ]
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
            probe_data = json.loads(probe_result.stdout)
            audio_duration = float(probe_data["format"]["duration"])
            tu.logger.info(f"Ken Burns: audio_duration={audio_duration:.1f}s, n={n} images")

            # ── 3. Calculate per-clip timing ────────────────────────────────────
            # Total raw clip time must cover audio when accounting for overlapping fades
            # clip_duration * n - FADE_DUR * (n-1) = audio_duration
            clip_duration = (audio_duration + (n - 1) * FADE_DUR) / n
            clip_frames = int(clip_duration * FPS) + 2  # +2 for rounding safety

            # ── 4. Save resized images as temp JPEGs ────────────────────────────
            image_paths = []
            for i, img in enumerate(images):
                img_resized = self._resize_cover(img, WIDTH, HEIGHT)
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as imf:
                    img_resized.save(imf.name, "JPEG", quality=90)
                    image_paths.append(imf.name)
                    temp_files.append(imf.name)

            # ── 5. Save quote to text file (avoids FFmpeg escaping) ─────────────
            with tempfile.NamedTemporaryFile(
                suffix=".txt", delete=False, mode="w", encoding="utf-8"
            ) as tf:
                tf.write(quote)
                quote_textfile = tf.name
            temp_files.append(quote_textfile)

            # ── 6. Find drawtext font ───────────────────────────────────────────
            font_path = self._find_drawtext_font()

            # ── 7. Build FFmpeg command ─────────────────────────────────────────
            cmd = ["ffmpeg", "-y"]
            # N image inputs (each looped for clip_duration)
            for img_path in image_paths:
                cmd += ["-loop", "1", "-t", f"{clip_duration:.3f}", "-i", img_path]
            # Audio input
            cmd += ["-i", audio_path]

            # ── 8. Build filtergraph ────────────────────────────────────────────
            # Ken Burns zoom/pan variations — cycle through for visual variety
            # zoompan: z=zoom expr, x/y=pan, d=frames, s=size, fps=fps
            ZOOM_VARIANTS = [
                # slow zoom in, centred
                f"zoompan=z='min(zoom+0.0008,1.25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={clip_frames}:s={WIDTH}x{HEIGHT}:fps={FPS}",
                # slow zoom out, centred
                f"zoompan=z='if(lte(zoom,1),1.2,zoom-0.0008)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={clip_frames}:s={WIDTH}x{HEIGHT}:fps={FPS}",
                # zoom in, pan right (start left)
                f"zoompan=z='min(zoom+0.0008,1.2)':x='0':y='ih/2-(ih/zoom/2)':d={clip_frames}:s={WIDTH}x{HEIGHT}:fps={FPS}",
                # zoom in, pan left (start right)
                f"zoompan=z='min(zoom+0.0008,1.2)':x='iw-iw/zoom':y='ih/2-(ih/zoom/2)':d={clip_frames}:s={WIDTH}x{HEIGHT}:fps={FPS}",
                # zoom in, pan down (start top)
                f"zoompan=z='min(zoom+0.0008,1.2)':x='iw/2-(iw/zoom/2)':y='0':d={clip_frames}:s={WIDTH}x{HEIGHT}:fps={FPS}",
                # zoom in, pan up (start bottom)
                f"zoompan=z='min(zoom+0.0008,1.2)':x='iw/2-(iw/zoom/2)':y='ih-ih/zoom':d={clip_frames}:s={WIDTH}x{HEIGHT}:fps={FPS}",
            ]

            filter_parts = []

            # Apply zoompan to each image clip
            for i in range(n):
                variant = ZOOM_VARIANTS[i % len(ZOOM_VARIANTS)]
                filter_parts.append(f"[{i}:v] {variant},format=yuv420p [v{i}]")

            # Chain xfade transitions
            if n == 1:
                last_video = "v0"
            else:
                for i in range(n - 1):
                    offset = (i + 1) * (clip_duration - FADE_DUR)
                    if i == 0:
                        in1, in2 = "v0", "v1"
                    else:
                        in1, in2 = f"xf{i - 1}", f"v{i + 1}"
                    out = f"xf{i}"
                    filter_parts.append(
                        f"[{in1}][{in2}] xfade=transition=fade:duration={FADE_DUR}:offset={offset:.3f} [{out}]"
                    )
                last_video = f"xf{n - 2}"

            # Quote drawtext overlay
            quote_end = min(float(QUOTE_SHOW_DUR), audio_duration - 2.0)
            fade_in_end = 1.0
            fade_out_start = max(quote_end - 1.0, fade_in_end + 1.0)

            alpha_expr = (
                f"if(lt(t,{fade_in_end}),t,"
                f"if(lt(t,{fade_out_start:.1f}),1,"
                f"if(lt(t,{quote_end:.1f}),{quote_end:.1f}-t,0)))"
            )

            dt_parts = [f"drawtext=textfile={quote_textfile}"]
            if font_path:
                dt_parts.append(f"fontfile={font_path}")
            dt_parts += [
                "fontsize=44",
                "fontcolor=white",
                "shadowcolor=black@0.85",
                "shadowx=2",
                "shadowy=2",
                "line_spacing=12",
                "x=(w-text_w)/2",
                "y=h*0.78",
                f"alpha={alpha_expr}",
                "fix_bounds=1",
            ]
            drawtext_filter = ":".join(dt_parts)

            filter_parts.append(f"[{last_video}] {drawtext_filter} [vout]")

            filtergraph = "; ".join(filter_parts)
            audio_index = n  # images are 0..n-1, audio is n

            output_path = tempfile.mktemp(suffix=".mp4")

            cmd += [
                "-filter_complex", filtergraph,
                "-map", "[vout]",
                "-map", f"{audio_index}:a",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22",
                "-c:a", "aac",
                "-b:a", "128k",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-shortest",
                "-r", str(FPS),
                output_path,
            ]

            tu.logger.info(
                f"Ken Burns FFmpeg: {n} clips × {clip_duration:.2f}s, "
                f"audio={audio_duration:.1f}s, output={output_path}"
            )

            # ── 9. Run FFmpeg ───────────────────────────────────────────────────
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600
            )

            if result.returncode != 0:
                error_tail = result.stderr[-3000:] if result.stderr else "(no stderr)"
                raise Exception(f"FFmpeg Ken Burns failed (rc={result.returncode}): {error_tail}")

            tu.logger.info(f"Ken Burns video created: {output_path}")
            return output_path

        finally:
            for f in temp_files:
                try:
                    if os.path.exists(f):
                        os.unlink(f)
                except Exception:
                    pass

    async def _create_light_single_image_video(
        self,
        image: Image.Image,
        audio_bytes: bytes,
        quote: str,
    ) -> str:
        """Lightweight video pipeline tuned for 0.5-CPU servers.

        Single static library image + audio + animated quote drawtext overlay.
        NO zoompan, NO xfade chain — these are the most expensive FFmpeg
        filters and routinely hang or take >10 min on Render Starter.

        Output: 854x480, 15 fps, x264 ultrafast, ~30-60 s encode for a 3-min audio.
        """
        WIDTH, HEIGHT = 854, 480
        FPS = 10  # static image — even 1 fps would play fine, 10 is safe for all players
        QUOTE_SHOW_DUR = 15  # seconds the quote stays on screen

        import time as _time
        _t_start = _time.time()
        temp_files: list[str] = []
        try:
            # 1. Save audio to temp mp3
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as af:
                af.write(audio_bytes)
                audio_path = af.name
            temp_files.append(audio_path)

            # 2. Probe audio duration so we can size the quote fade window
            try:
                probe_cmd = [
                    "ffprobe", "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    audio_path,
                ]
                probe_result = subprocess.run(
                    probe_cmd, capture_output=True, text=True, timeout=20
                )
                probe_data = json.loads(probe_result.stdout)
                audio_duration = float(probe_data["format"]["duration"])
            except Exception as e:
                tu.logger.warning(f"ffprobe failed, defaulting audio_duration=180: {e}")
                audio_duration = 180.0

            tu.logger.info(
                f"Light video: audio={audio_duration:.1f}s, target {WIDTH}x{HEIGHT}@{FPS}fps"
            )

            # 3. Resize image once via PIL (much cheaper than ffmpeg scale filter)
            img_resized = self._resize_cover(image, WIDTH, HEIGHT)
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as imf:
                img_resized.save(imf.name, "JPEG", quality=85, optimize=True)
                image_path = imf.name
            temp_files.append(image_path)

            # 4. Save quote text to a file (avoids FFmpeg escape hell)
            with tempfile.NamedTemporaryFile(
                suffix=".txt", delete=False, mode="w", encoding="utf-8"
            ) as tf:
                tf.write(quote or "")
                quote_textfile = tf.name
            temp_files.append(quote_textfile)

            font_path = self._find_drawtext_font()

            # 5. Build a tiny filtergraph: format yuv420p + drawtext overlay
            quote_end = min(float(QUOTE_SHOW_DUR), max(audio_duration - 2.0, 5.0))
            fade_in_end = 1.0
            fade_out_start = max(quote_end - 1.0, fade_in_end + 1.0)
            alpha_expr = (
                f"if(lt(t,{fade_in_end}),t,"
                f"if(lt(t,{fade_out_start:.1f}),1,"
                f"if(lt(t,{quote_end:.1f}),{quote_end:.1f}-t,0)))"
            )

            dt_parts = [f"drawtext=textfile={quote_textfile}"]
            if font_path:
                dt_parts.append(f"fontfile={font_path}")
            dt_parts += [
                "fontsize=32",
                "fontcolor=white",
                "shadowcolor=black@0.85",
                "shadowx=2",
                "shadowy=2",
                "line_spacing=10",
                "x=(w-text_w)/2",
                "y=h*0.78",
                f"alpha={alpha_expr}",
                "fix_bounds=1",
            ]
            drawtext_filter = ":".join(dt_parts)
            vf = f"format=yuv420p,{drawtext_filter}"

            output_path = tempfile.mktemp(suffix=".mp4")

            cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-framerate", str(FPS),
                "-i", image_path,
                "-i", audio_path,
                "-vf", vf,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "stillimage",
                "-crf", "28",
                "-c:a", "aac",
                "-b:a", "96k",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-shortest",
                "-r", str(FPS),
                "-threads", "0",
                output_path,
            ]

            tu.logger.info(f"Light FFmpeg cmd: {' '.join(cmd)}")
            _t_ffmpeg = _time.time()
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300
            )
            ffmpeg_secs = _time.time() - _t_ffmpeg
            if result.returncode != 0:
                error_tail = result.stderr[-3000:] if result.stderr else "(no stderr)"
                raise Exception(f"FFmpeg light pipeline failed (rc={result.returncode}): {error_tail}")

            total_secs = _time.time() - _t_start
            tu.logger.info(
                f"Light video created in {total_secs:.1f}s "
                f"(ffmpeg={ffmpeg_secs:.1f}s) -> {output_path}"
            )
            return output_path

        finally:
            for f in temp_files:
                try:
                    if os.path.exists(f):
                        os.unlink(f)
                except Exception:
                    pass

    async def _load_conversation(self, session: AsyncSession, conversation_id: str):
        """Load conversation efficiently"""
        query = select(Conversation).where(Conversation.id == conversation_id)
        result = await session.execute(query)
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise ValueError("Conversation not found")
        return conversation

    async def _generate_source_content(
        self, session: AsyncSession, conversation_id: str
    ) -> str:
        """Generate source content for transcript"""
        return await collect_source_content_optimized(session, conversation_id)

    async def _generate_image_prompt_cached(self) -> str:
        """Generate image prompt with preference for cached common prompts"""
        import random

        # 70% chance to use a common cached prompt for speed
        if random.random() < 0.7 and COMMON_MEDITATION_PROMPTS:
            return random.choice(COMMON_MEDITATION_PROMPTS)

        # 30% chance to use original variety from CONTEMPLATION_PROMPTS
        return random.choice(CONTEMPLATION_PROMPTS)

    async def _generate_transcript_optimized(self, source_content: str) -> str:
        """Generate meditation transcript with optimization"""
        return await generate_meditation_transcript_optimized(source_content)

    async def _generate_image_cached(self, prompt: str) -> Image.Image:
        """Generate image with persistent caching"""
        return await generate_and_cache_image(prompt)

    async def _generate_audio_optimized(self, transcript: str) -> bytes:
        """Generate audio with optimization"""
        return await generate_audio_from_transcript_optimized(transcript)

    async def _create_video_streaming_parallel(
        self, pil_image: Image.Image, transcript: str
    ) -> str:
        """Create video using streaming audio input - starts immediately and processes audio in parallel"""

        # Create temporary image file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as img_file:
            pil_image.save(img_file.name, "JPEG", quality=85, optimize=True)
            image_path = img_file.name

        # Create output video path
        video_path = tempfile.mktemp(suffix=".mp4")

        try:
            # Generate audio first (this is the bottleneck we're optimizing)
            audio_bytes = await self._generate_audio_optimized(transcript)

            # Start FFmpeg process that reads audio from stdin
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output
                "-loop", "1",  # Loop image
                "-i", image_path,  # Input image
                "-f", "wav",  # Force WAV format for stdin (TTS returns WAV-like format)
                "-i", "pipe:0",  # Read audio from stdin
                "-c:v", "libx264",  # Video codec
                "-preset", "superfast",  # Fast encoding
                "-crf", "30",  # Lower quality for speed
                "-c:a", "aac",  # Audio codec
                "-b:a", "64k",  # Lower audio bitrate
                "-vf", "scale=720:480",  # Lower resolution
                "-r", "15",  # Lower frame rate
                "-shortest",  # End when audio ends
                "-pix_fmt", "yuv420p",  # Pixel format
                "-movflags", "+faststart",  # Web optimization
                "-threads", "0",  # Use all threads
                video_path,
            ]

            # Add hardware acceleration if available
            try:
                test_cmd = ["ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "testsrc2", "-t", "1", "-f", "null", "-"]
                subprocess.run(test_cmd, capture_output=True, timeout=5)
                cmd.insert(1, "-hwaccel")
                cmd.insert(2, "auto")
            except:
                pass

            # Start FFmpeg process and pipe audio using communicate()
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0  # Unbuffered
            )

            # Use communicate() to send audio data and wait for completion
            stdout, stderr = process.communicate(input=audio_bytes, timeout=3600)

            if process.returncode != 0:
                raise Exception(f"FFmpeg failed: {stderr.decode()}")

            return video_path

        finally:
            # Cleanup temporary files
            try:
                if os.path.exists(image_path):
                    os.unlink(image_path)
            except:
                pass

    async def _create_video_ultra_optimized(
        self, pil_image: Image.Image, audio_bytes: bytes
    ) -> str:
        """Create video with ultra-optimized FFmpeg settings"""

        # Create temporary files with optimized settings
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as img_file:
            # Use JPEG instead of PNG for faster processing
            pil_image.save(img_file.name, "JPEG", quality=85, optimize=True)
            image_path = img_file.name

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as audio_file:
            audio_file.write(audio_bytes)
            audio_path = audio_file.name

        # Create output video path
        video_path = tempfile.mktemp(suffix=".mp4")

        try:
            # Ultra-optimized FFmpeg command for maximum speed
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output
                "-loop", "1",  # Loop image
                "-i", image_path,  # Input image
                "-i", audio_path,  # Input audio
                "-c:v", "libx264",  # Video codec
                "-preset", "superfast",  # Even faster than ultrafast
                "-crf", "30",  # Lower quality for faster encoding (was 28)
                "-c:a", "aac",  # Audio codec
                "-b:a", "64k",  # Lower audio bitrate for speed (was 96k)
                "-vf", "scale=720:480",  # Lower resolution for speed
                "-r", "15",  # Lower frame rate for speed
                "-shortest",  # End when shortest input ends
                "-pix_fmt", "yuv420p",  # Pixel format
                "-movflags", "+faststart",  # Web optimization
                "-threads", "0",  # Use all available threads
                video_path,
            ]

            # Add hardware acceleration if available
            try:
                # Check for hardware acceleration
                test_cmd = ["ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "testsrc2", "-t", "1", "-f", "null", "-"]
                subprocess.run(test_cmd, capture_output=True, timeout=5)
                # If successful, use hardware acceleration
                cmd.insert(1, "-hwaccel")
                cmd.insert(2, "auto")
            except:
                pass  # Use software encoding

            # Run FFmpeg with timeout
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

            if result.returncode != 0:
                raise Exception(f"FFmpeg failed: {result.stderr}")

            return video_path

        finally:
            # Cleanup temporary files
            for temp_path in [image_path, audio_path]:
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except:
                    pass

    async def _upload_video_optimized(self, video_path: str, content_id: str) -> str:
        """Upload video with optimized settings"""
        try:
            with open(video_path, "rb") as f:
                video_data = f.read()

            # Use optimized upload path
            content_path = f"meditation-videos/{content_id}.mp4"

            # Upload with correct signature
            self.spb_client.storage.from_("generations").upload(
                content_path,
                video_data,
                {"content-type": "video/mp4"}
            )

            return content_path

        finally:
            # Cleanup video file
            try:
                os.unlink(video_path)
            except:
                pass

    # Legacy methods for backward compatibility
    async def _generate_image_prompt(self) -> str:
        """Generate image prompt"""
        return random.choice(CONTEMPLATION_PROMPTS)

    async def generate_transcript(self, source_content, length: str = None):
        """Generate transcript in parallel"""
        async with profile_operation("video_transcript_generation") as op:
            transcript = await generate_meditation_transcript_optimized(source_content, length)
            op.finish(transcript_length=len(transcript))
            return transcript

    async def _generate_image(self, prompt: str) -> Image.Image:
        """Generate image"""
        return await _generate_image(prompt)

    async def _generate_audio(self, transcript: str) -> bytes:
        """Generate audio from transcript"""
        return await generate_audio_from_transcript_optimized(transcript)

    async def _create_video_optimized(
        self, pil_image: Image.Image, audio_bytes: bytes
    ) -> str:
        """Create video with optimized FFmpeg settings"""
        return await self._create_video_ultra_optimized(pil_image, audio_bytes)

    async def _upload_video(self, video_path: str) -> str:
        """Upload video to Supabase"""
        return await self._upload_video_optimized(video_path, "temp")

# Global instance
parallel_generator = ParallelVideoGenerator()
