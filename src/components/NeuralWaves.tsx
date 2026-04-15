import { useEffect, useRef } from "react";

interface NeuralWavesProps {
  isRecording: boolean;
  isConnected: boolean;
}

const NeuralWaves = ({ isRecording, isConnected }: NeuralWavesProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const timeRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    const size = 320;
    canvas.width = size;
    canvas.height = size;
    const cx = size / 2;
    const cy = size / 2;

    const draw = () => {
      timeRef.current += 0.02;
      const t = timeRef.current;
      ctx.clearRect(0, 0, size, size);

      const waveCount = 4;
      const baseRadius = 90;

      for (let w = 0; w < waveCount; w++) {
        const amp = isRecording ? 18 + w * 6 : 6 + w * 2;
        const speed = 1.2 + w * 0.3;
        const radius = baseRadius + w * 16;
        const alpha = isRecording ? 0.6 - w * 0.1 : 0.2 - w * 0.03;

        ctx.beginPath();
        for (let i = 0; i <= 360; i++) {
          const angle = (i * Math.PI) / 180;
          const noise =
            Math.sin(angle * 6 + t * speed) * amp * 0.5 +
            Math.sin(angle * 3 - t * speed * 0.7) * amp * 0.3 +
            Math.cos(angle * 8 + t * speed * 1.3) * amp * 0.2;
          const r = radius + noise;
          const x = cx + Math.cos(angle) * r;
          const y = cy + Math.sin(angle) * r;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.closePath();

        const hue = isConnected ? 199 : 260;
        const sat = isRecording ? "90%" : "60%";
        const light = isRecording ? "55%" : "40%";
        ctx.strokeStyle = `hsla(${hue + w * 15}, ${sat}, ${light}, ${alpha})`;
        ctx.lineWidth = 2;
        ctx.stroke();

        if (isRecording) {
          ctx.shadowColor = `hsla(${hue}, 90%, 55%, ${alpha * 0.5})`;
          ctx.shadowBlur = 20;
          ctx.stroke();
          ctx.shadowBlur = 0;
        }
      }

      animRef.current = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(animRef.current);
  }, [isRecording, isConnected]);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 m-auto"
      style={{ width: 320, height: 320 }}
    />
  );
};

export default NeuralWaves;
