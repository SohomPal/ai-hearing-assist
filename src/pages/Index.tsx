import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Mic, MicOff, Bluetooth, BluetoothOff } from "lucide-react";
import NeuralWaves from "@/components/NeuralWaves";
import BandParamsPanel from "@/components/BandParamsPanel";
import { useWebSocket } from "@/hooks/useWebSocket";

const Index = () => {
  const { isConnected, isBleConnected, bands, logs, sendCommand } =
    useWebSocket();

  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [statusText, setStatusText] = useState("Tap to speak");
  const recognitionRef = useRef<any>(null);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout>>();

  const stopRecording = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    clearTimeout(silenceTimerRef.current);
    setIsRecording(false);
  }, []);

  const startRecording = useCallback(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setStatusText("Speech recognition not supported");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onstart = () => {
      setIsRecording(true);
      setTranscript("");
      setStatusText("Listening...");
    };

    recognition.onresult = (event: any) => {
      clearTimeout(silenceTimerRef.current);
      let finalText = "";
      let interimText = "";
      for (let i = 0; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          finalText += event.results[i][0].transcript;
        } else {
          interimText += event.results[i][0].transcript;
        }
      }
      setTranscript(finalText || interimText);

      // 3s silence timeout
      silenceTimerRef.current = setTimeout(() => {
        stopRecording();
      }, 3000);
    };

    recognition.onend = () => {
      setIsRecording(false);
      setStatusText("Tap to speak");
    };

    recognition.onerror = (event: any) => {
      console.error("Speech error:", event.error);
      setIsRecording(false);
      setStatusText("Tap to speak");
    };

    recognitionRef.current = recognition;
    recognition.start();
  }, [stopRecording]);

  const toggleRecording = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  // Send transcript when recording stops and we have text
  const prevRecording = useRef(isRecording);
  useEffect(() => {
    if (prevRecording.current && !isRecording && transcript.trim()) {
      sendCommand(transcript.trim());
      setStatusText(`Sent: "${transcript.trim()}"`);
      setTimeout(() => setStatusText("Tap to speak"), 3000);
    }
    prevRecording.current = isRecording;
  }, [isRecording, transcript, sendCommand]);

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-between py-8 px-4 overflow-hidden">
      {/* Header */}
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          AI Hearing Aid Control
        </h1>
        <p className="text-sm text-muted-foreground">
          Speak naturally to adjust your hearing
        </p>
      </div>

      {/* BLE Status */}
      <div className="flex items-center gap-2 mt-4">
        {isBleConnected ? (
          <Bluetooth className="w-4 h-4 text-success" />
        ) : (
          <BluetoothOff className="w-4 h-4 text-destructive" />
        )}
        <span
          className={`text-xs font-medium ${
            isBleConnected ? "text-success" : "text-destructive"
          }`}
        >
          {isBleConnected ? "Device Connected" : "Device Disconnected"}
        </span>
        {!isConnected && (
          <span className="text-xs text-muted-foreground ml-2">
            (Backend offline)
          </span>
        )}
      </div>

      {/* Main Mic Area */}
      <div className="relative flex items-center justify-center my-8"
        style={{ width: 320, height: 320 }}
      >
        <NeuralWaves isRecording={isRecording} isConnected={isBleConnected} />

        {/* Mic Button */}
        <motion.button
          onClick={toggleRecording}
          whileTap={{ scale: 0.92 }}
          className={`relative z-10 w-24 h-24 rounded-full flex items-center justify-center transition-all duration-300 border-2 ${
            isRecording
              ? "bg-primary/20 border-primary shadow-[0_0_40px_hsl(var(--primary)/0.4)]"
              : "bg-secondary border-border hover:border-primary/50"
          }`}
        >
          {isRecording ? (
            <MicOff className="w-8 h-8 text-primary" />
          ) : (
            <Mic className="w-8 h-8 text-foreground/70" />
          )}
        </motion.button>
      </div>

      {/* Status & Transcript */}
      <div className="text-center space-y-2 min-h-[60px]">
        <p className="text-sm text-muted-foreground">{statusText}</p>
        <AnimatePresence>
          {transcript && (
            <motion.p
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="text-base font-medium text-foreground max-w-sm"
            >
              "{transcript}"
            </motion.p>
          )}
        </AnimatePresence>
      </div>

      {/* Activity Log */}
      {logs.length > 0 && (
        <div className="w-full max-w-lg mt-4 mb-2">
          <div className="rounded-lg border border-border bg-card/30 p-3 max-h-24 overflow-y-auto">
            {logs.slice(-5).map((log, i) => (
              <p key={i} className="text-xs text-muted-foreground font-mono truncate">
                {log}
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Band Parameters Panel */}
      <BandParamsPanel bands={bands} />
    </div>
  );
};

export default Index;
