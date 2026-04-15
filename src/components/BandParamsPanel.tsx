import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { useState } from "react";

interface BandData {
  cr: number | null;
  gain_dB: number | null;
  atk_ms: number | null;
  rel_ms: number | null;
  tk_dB?: number | null;
}

interface BandParamsPanelProps {
  bands: BandData[];
}

const PARAM_LABELS: Record<string, string> = {
  cr: "Comp Ratio",
  gain_dB: "Gain (dB)",
  atk_ms: "Attack (ms)",
  rel_ms: "Release (ms)",
  tk_dB: "Threshold (dB)",
};

const BandParamsPanel = ({ bands }: BandParamsPanelProps) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="w-full max-w-lg mx-auto">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-5 py-3 rounded-lg bg-secondary/50 border border-border hover:bg-secondary/80 transition-colors"
      >
        <span className="text-sm font-medium text-foreground/80">
          Band Parameters
        </span>
        <motion.div
          animate={{ rotate: isOpen ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        </motion.div>
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="mt-2 rounded-lg border border-border bg-card/50 backdrop-blur-sm overflow-hidden">
              {/* Header */}
              <div className="grid grid-cols-6 gap-px bg-border">
                <div className="bg-secondary px-3 py-2 text-xs font-semibold text-muted-foreground">
                  Param
                </div>
                {[0, 1, 2, 3, 4, 5].map((i) => (
                  <div
                    key={i}
                    className="bg-secondary px-3 py-2 text-xs font-semibold text-muted-foreground text-center"
                  >
                    B{i}
                  </div>
                ))}
              </div>

              {/* Rows */}
              {Object.keys(PARAM_LABELS).map((param) => (
                <div key={param} className="grid grid-cols-6 gap-px bg-border">
                  <div className="bg-card px-3 py-2 text-xs text-muted-foreground">
                    {PARAM_LABELS[param]}
                  </div>
                  {bands.map((band, i) => {
                    const val = band[param as keyof BandData];
                    return (
                      <div
                        key={i}
                        className="bg-card px-3 py-2 text-xs text-center font-mono text-foreground/80"
                      >
                        {val !== null && val !== undefined
                          ? typeof val === "number"
                            ? val.toFixed(1)
                            : "–"
                          : "–"}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default BandParamsPanel;
