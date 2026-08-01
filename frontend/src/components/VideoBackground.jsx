import { useEffect, useRef } from "react";
import Hls from "hls.js";

const HLS_URL =
  "https://stream.mux.com/tLkHO1qZoaaQOUeVWo8hEBeGQfySP02EPS02BmnNFyXys.m3u8";

export default function VideoBackground() {
  const videoRef = useRef(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    if (Hls.isSupported()) {
      const hls = new Hls({ enableWorker: false });
      hls.loadSource(HLS_URL);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        video.play().catch(() => {
          // Autoplay may be blocked; mute helps
          video.muted = true;
          video.play();
        });
      });
      return () => {
        hls.destroy();
      };
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      // Native HLS support (Safari)
      video.src = HLS_URL;
      video.addEventListener("loadedmetadata", () => {
        video.play().catch(() => {
          video.muted = true;
          video.play();
        });
      });
    }
  }, []);

  return (
    <div className="absolute inset-0 overflow-hidden">
      <div className="video-opacity-wrapper absolute inset-0">
        <video
          ref={videoRef}
          className="absolute inset-0 w-full h-full object-cover"
          muted
          loop
          playsInline
        />
      </div>
      {/* Left-to-right dark gradient */}
      <div className="absolute inset-0 bg-gradient-to-r from-dark-bg via-dark-bg/60 to-transparent pointer-events-none" />
      {/* Bottom-to-top gradient for readability */}
      <div className="absolute inset-0 bg-gradient-to-t from-dark-bg via-dark-bg/40 to-transparent pointer-events-none" />
    </div>
  );
}